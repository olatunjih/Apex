"""Tests for DataRegistry - FIX-01.

Tests cover:
- TTL expiry behavior
- Namespace isolation
- Concurrent put/get under threading
- Eviction metrics and behavior
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from typing import List

import pytest

from apex_runtime.data_registry import DataRegistry, RegistryEntry


class TestTTLExpiry:
    """Test TTL expiration behavior."""

    def test_entry_expires_after_ttl(self) -> None:
        """Test that entries expire after their TTL."""
        registry = DataRegistry()
        
        # Put with very short TTL (0.1 seconds)
        key = registry.put(
            namespace="test",
            ticker="AAPL",
            data_type="price",
            value=Decimal("150.00"),
            ttl_seconds=0.1,
        )
        
        # Should be retrievable immediately
        assert registry.get(key) == Decimal("150.00")
        
        # Wait for expiry
        time.sleep(0.15)
        
        # Should return None after expiry
        assert registry.get(key) is None

    def test_entry_not_expired_before_ttl(self) -> None:
        """Test that entries remain valid before TTL expires."""
        registry = DataRegistry()
        
        key = registry.put(
            namespace="test",
            ticker="AAPL",
            data_type="price",
            value=Decimal("150.00"),
            ttl_seconds=10.0,  # Long TTL
        )
        
        # Should still be available after short delay
        time.sleep(0.1)
        assert registry.get(key) == Decimal("150.00")

    def test_default_ttl_by_namespace(self) -> None:
        """Test that different namespaces get different default TTLs."""
        registry = DataRegistry()
        
        # Market data has 3600s default TTL
        market_key = registry.put(
            namespace="market_data",
            ticker="AAPL",
            data_type="ohlcv",
            value={"bars": []},
        )
        
        # Signals have 300s default TTL
        signal_key = registry.put(
            namespace="signals",
            ticker="AAPL",
            data_type="rsi_signal",
            value={"signal": "buy"},
        )
        
        # Both should be retrievable
        assert registry.get(market_key) is not None
        assert registry.get(signal_key) is not None
        
        # Check the entry metadata
        market_entry = registry.get_entry(market_key)
        signal_entry = registry.get_entry(signal_key)
        
        assert market_entry.ttl_seconds == 3600.0
        assert signal_entry.ttl_seconds == 300.0

    def test_custom_ttl_overrides_default(self) -> None:
        """Test that custom TTL overrides namespace default."""
        registry = DataRegistry()
        
        key = registry.put(
            namespace="market_data",  # Default 3600s
            ticker="AAPL",
            data_type="ohlcv",
            value={"bars": []},
            ttl_seconds=0.1,  # Override to 0.1s
        )
        
        entry = registry.get_entry(key)
        assert entry.ttl_seconds == 0.1


class TestNamespaceIsolation:
    """Test namespace isolation prevents ticker collision."""

    def test_different_namespaces_isolated(self) -> None:
        """Test that same ticker in different namespaces are isolated."""
        registry = DataRegistry()
        
        # Same ticker, different namespaces
        market_key = registry.put(
            namespace="market_data",
            ticker="AAPL",
            data_type="ohlcv",
            value={"market": "data"},
        )
        
        signal_key = registry.put(
            namespace="signals",
            ticker="AAPL",
            data_type="rsi",
            value={"signal": "buy"},
        )
        
        # Both retrievable independently
        assert registry.get(market_key) == {"market": "data"}
        assert registry.get(signal_key) == {"signal": "buy"}

    def test_invalidate_namespace_only_affects_target(self) -> None:
        """Test that invalidating a namespace doesn't affect others."""
        registry = DataRegistry()
        
        # Create entries in multiple namespaces
        key1 = registry.put("ns1", "TICK", "type", "value1")
        key2 = registry.put("ns1", "TICK", "type", "value2")
        key3 = registry.put("ns2", "TICK", "type", "value3")
        
        # Invalidate ns1
        count = registry.invalidate_namespace("ns1")
        
        assert count == 2
        assert registry.get(key1) is None
        assert registry.get(key2) is None
        assert registry.get(key3) == "value3"  # ns2 unaffected

    def test_count_by_namespace(self) -> None:
        """Test counting entries per namespace."""
        registry = DataRegistry()
        
        registry.put("ns1", "T1", "t", "v")
        registry.put("ns1", "T2", "t", "v")
        registry.put("ns2", "T1", "t", "v")
        
        assert registry.count_by_namespace("ns1") == 2
        assert registry.count_by_namespace("ns2") == 1
        assert registry.count_by_namespace("ns3") == 0


class TestConcurrency:
    """Test thread-safe concurrent access."""

    def test_concurrent_puts(self) -> None:
        """Test concurrent puts from multiple threads."""
        registry = DataRegistry(max_entries=1000)
        keys: List[str] = []
        lock = threading.Lock()
        
        def put_item(i: int) -> None:
            key = registry.put("test", f"TICK{i}", "data", i)
            with lock:
                keys.append(key)
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(put_item, i) for i in range(100)]
            for f in futures:
                f.result()
        
        assert len(keys) == 100
        # All keys should be retrievable
        for key in keys:
            assert registry.get(key) is not None

    def test_concurrent_gets_and_puts(self) -> None:
        """Test concurrent reads and writes."""
        registry = DataRegistry(max_entries=1000)
        errors: List[Exception] = []
        
        def writer(start: int) -> None:
            try:
                for i in range(start, start + 50):
                    registry.put("test", f"TICK{i}", "data", i)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        def reader() -> None:
            try:
                for _ in range(100):
                    stats = registry.stats()
                    assert isinstance(stats["total_entries"], int)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        threads = []
        for i in range(4):
            threads.append(threading.Thread(target=writer, args=(i * 50,)))
        threads.append(threading.Thread(target=reader))
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0

    def test_no_race_condition_on_expiry(self) -> None:
        """Test that expiry check doesn't cause race conditions."""
        registry = DataRegistry()
        
        # Put many items with short TTL
        keys = []
        for i in range(50):
            key = registry.put("test", f"T{i}", "d", i, ttl_seconds=0.2)
            keys.append(key)
        
        # Wait for expiry
        time.sleep(0.25)
        
        # All gets should return None without errors
        for key in keys:
            result = registry.get(key)
            assert result is None


class TestEviction:
    """Test eviction behavior and metrics."""

    def test_eviction_on_max_entries(self) -> None:
        """Test that oldest entries are evicted when max is reached."""
        registry = DataRegistry(max_entries=10)
        
        # Insert more than max
        keys = []
        for i in range(15):
            key = registry.put("test", f"T{i}", "d", i)
            keys.append(key)
            time.sleep(0.01)  # Ensure different timestamps
        
        # Should have at most max_entries
        stats = registry.stats()
        assert stats["total_entries"] <= 10
        
        # Some early keys should be evicted
        retrieved_count = sum(1 for k in keys if registry.get(k) is not None)
        assert retrieved_count <= 10

    def test_eviction_count_increments(self) -> None:
        """Test that eviction_count increments on eviction."""
        registry = DataRegistry(max_entries=5)
        
        initial_stats = registry.stats()
        assert initial_stats["eviction_count"] == 0
        
        # Trigger eviction by exceeding max
        for i in range(10):
            registry.put("test", f"T{i}", "d", i)
            time.sleep(0.01)
        
        final_stats = registry.stats()
        assert final_stats["eviction_count"] > 0

    def test_eviction_on_expiry(self) -> None:
        """Test that expired entries are evicted and counted."""
        registry = DataRegistry()
        
        # Put items with short TTL
        keys = []
        for i in range(5):
            key = registry.put("test", f"T{i}", "d", i, ttl_seconds=0.1)
            keys.append(key)
        
        initial_stats = registry.stats()
        assert initial_stats["eviction_count"] == 0
        
        # Wait for expiry and trigger eviction via get
        time.sleep(0.15)
        for key in keys:
            registry.get(key)  # Triggers eviction check
        
        final_stats = registry.stats()
        assert final_stats["eviction_count"] == 5

    def test_evict_oldest_removes_earliest(self) -> None:
        """Test that _evict_oldest removes the earliest entry."""
        registry = DataRegistry(max_entries=3)
        
        key1 = registry.put("test", "T1", "d", "v1")
        time.sleep(0.01)
        key2 = registry.put("test", "T2", "d", "v2")
        time.sleep(0.01)
        key3 = registry.put("test", "T3", "d", "v3")
        
        # Adding 4th should evict key1 (oldest)
        key4 = registry.put("test", "T4", "d", "v4")
        
        assert registry.get(key1) is None  # Evicted
        assert registry.get(key2) == "v2"
        assert registry.get(key3) == "v3"
        assert registry.get(key4) == "v4"


class TestStatsAndMetadata:
    """Test statistics and metadata retrieval."""

    def test_stats_returns_correct_structure(self) -> None:
        """Test that stats returns expected structure."""
        registry = DataRegistry()
        
        registry.put("market_data", "AAPL", "ohlcv", {"bars": []})
        registry.put("signals", "AAPL", "rsi", {"signal": "buy"})
        
        stats = registry.stats()
        
        assert "total_entries" in stats
        assert "eviction_count" in stats
        assert "namespaces" in stats
        assert stats["total_entries"] == 2
        assert set(stats["namespaces"]) == {"market_data", "signals"}

    def test_get_entry_returns_full_metadata(self) -> None:
        """Test that get_entry returns full RegistryEntry."""
        registry = DataRegistry()
        
        before = datetime.now(timezone.utc)
        key = registry.put(
            namespace="test",
            ticker="AAPL",
            data_type="price",
            value=Decimal("150.00"),
            quality_score=0.95,
            ttl_seconds=3600,
        )
        after = datetime.now(timezone.utc)
        
        entry = registry.get_entry(key)
        
        assert entry is not None
        assert entry.value == Decimal("150.00")
        assert entry.namespace == "test"
        assert entry.data_type == "price"
        assert entry.quality_score == 0.95
        assert entry.ttl_seconds == 3600
        assert before <= entry.fetched_at <= after

    def test_get_entry_returns_none_for_missing_key(self) -> None:
        """Test that get_entry returns None for non-existent key."""
        registry = DataRegistry()
        assert registry.get_entry("nonexistent.key") is None


class TestClear:
    """Test clear functionality."""

    def test_clear_removes_all_entries(self) -> None:
        """Test that clear removes all entries."""
        registry = DataRegistry()
        
        registry.put("ns1", "T1", "d", "v1")
        registry.put("ns2", "T2", "d", "v2")
        
        registry.clear()
        
        stats = registry.stats()
        assert stats["total_entries"] == 0
        assert stats["eviction_count"] == 0

    def test_clear_resets_eviction_count(self) -> None:
        """Test that clear resets eviction counter."""
        registry = DataRegistry(max_entries=2)
        
        # Trigger some evictions
        for i in range(5):
            registry.put("test", f"T{i}", "d", i)
        
        stats = registry.stats()
        assert stats["eviction_count"] > 0
        
        registry.clear()
        
        stats = registry.stats()
        assert stats["eviction_count"] == 0


class TestRegistryEntry:
    """Test RegistryEntry dataclass."""

    def test_is_expired_false_when_fresh(self) -> None:
        """Test is_expired returns False for fresh entry."""
        entry = RegistryEntry(
            value="test",
            namespace="test",
            data_type="test",
            fetched_at=datetime.now(timezone.utc),
            ttl_seconds=3600,
            quality_score=1.0,
        )
        assert not entry.is_expired()

    def test_is_expired_true_when_old(self) -> None:
        """Test is_expired returns True for old entry."""
        from datetime import timedelta
        
        entry = RegistryEntry(
            value="test",
            namespace="test",
            data_type="test",
            fetched_at=datetime.now(timezone.utc) - timedelta(seconds=100),
            ttl_seconds=50,
            quality_score=1.0,
        )
        assert entry.is_expired()

    def test_is_expired_boundary(self) -> None:
        """Test is_expired at exact boundary."""
        from datetime import timedelta
        
        # Exactly at TTL boundary should be expired
        entry = RegistryEntry(
            value="test",
            namespace="test",
            data_type="test",
            fetched_at=datetime.now(timezone.utc) - timedelta(seconds=100),
            ttl_seconds=100,
            quality_score=1.0,
        )
        assert entry.is_expired()
