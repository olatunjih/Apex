"""APEX v3 Data Registry - Thread-safe, TTL-enforced, namespace-isolated in-memory data store.

§5 of the APEX v3 specification.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RegistryEntry:
    """Immutable registry entry with TTL metadata."""
    
    value: Any
    namespace: str
    data_type: str
    fetched_at: datetime
    ttl_seconds: float
    quality_score: float

    def is_expired(self) -> bool:
        """Check if entry has expired based on TTL."""
        elapsed = (datetime.now(timezone.utc) - self.fetched_at).total_seconds()
        return elapsed > self.ttl_seconds


class DataRegistry:
    """Thread-safe, TTL-enforced, namespace-isolated in-memory data store.
    
    §5 of the APEX v3 specification.
    
    Features:
    - Per-namespace TTL enforcement with sensible defaults
    - Thread-safe operations via RLock
    - Eviction metrics for observability
    - Namespace isolation to prevent ticker collision
    - Configurable max entries with LRU-style eviction
    """

    DEFAULT_TTL: Dict[str, float] = {
        "market_data": 3600.0,
        "indicators":  1800.0,
        "signals":      300.0,
        "risk":         600.0,
        "plans":        900.0,
        "options":      600.0,
        "depth":         30.0,
        "decisions":    1800.0,
    }

    def __init__(self, max_entries: int = 10_000) -> None:
        """Initialize the data registry.
        
        Args:
            max_entries: Maximum number of entries before eviction triggers.
        """
        self._store: Dict[str, RegistryEntry] = {}
        self._max_entries = max_entries
        self._lock = threading.RLock()
        self._eviction_count = 0

    def put(
        self,
        namespace: str,
        ticker: str,
        data_type: str,
        value: Any,
        quality_score: float = 1.0,
        ttl_seconds: Optional[float] = None,
    ) -> str:
        """Store a value in the registry.
        
        Args:
            namespace: Logical namespace (e.g., 'market_data', 'signals')
            ticker: Ticker symbol or identifier
            data_type: Type of data being stored
            value: The actual data value
            quality_score: Quality score 0.0-1.0
            ttl_seconds: Custom TTL; uses DEFAULT_TTL[namespace] if not provided
            
        Returns:
            Unique key for retrieving the value
        """
        key = f"{namespace}.{ticker}.{data_type}.{uuid.uuid4().hex[:8]}"
        ttl = ttl_seconds if ttl_seconds is not None else self.DEFAULT_TTL.get(namespace, 3600.0)
        
        entry = RegistryEntry(
            value=value,
            namespace=namespace,
            data_type=data_type,
            fetched_at=datetime.now(timezone.utc),
            ttl_seconds=ttl,
            quality_score=quality_score,
        )
        
        with self._lock:
            self._evict_expired()
            if len(self._store) >= self._max_entries:
                self._evict_oldest()
            self._store[key] = entry
        
        return key

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the registry.
        
        Args:
            key: The key returned by put()
            
        Returns:
            The stored value, or None if not found or expired
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._store[key]
                self._eviction_count += 1
                return None
            return entry.value

    def invalidate_namespace(self, namespace: str) -> int:
        """Invalidate all entries in a namespace.
        
        Args:
            namespace: The namespace to invalidate
            
        Returns:
            Number of entries invalidated
        """
        with self._lock:
            keys = [k for k, e in self._store.items() if e.namespace == namespace]
            for k in keys:
                del self._store[k]
            return len(keys)

    def stats(self) -> Dict[str, Any]:
        """Get registry statistics.
        
        Returns:
            Dict with total_entries, eviction_count, and namespaces list
        """
        with self._lock:
            namespaces = list({e.namespace for e in self._store.values()})
            return {
                "total_entries": len(self._store),
                "eviction_count": self._eviction_count,
                "namespaces": namespaces,
            }

    def _evict_expired(self) -> None:
        """Remove all expired entries."""
        expired = [k for k, e in self._store.items() if e.is_expired()]
        for k in expired:
            del self._store[k]
            self._eviction_count += 1

    def _evict_oldest(self) -> None:
        """Evict the oldest entry by fetched_at timestamp."""
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k].fetched_at)
        del self._store[oldest_key]
        self._eviction_count += 1

    def clear(self) -> None:
        """Clear all entries from the registry."""
        with self._lock:
            self._store.clear()
            self._eviction_count = 0

    def get_entry(self, key: str) -> Optional[RegistryEntry]:
        """Get the full RegistryEntry including metadata.
        
        Args:
            key: The key returned by put()
            
        Returns:
            RegistryEntry or None if not found
        """
        with self._lock:
            return self._store.get(key)

    def count_by_namespace(self, namespace: str) -> int:
        """Count entries in a specific namespace.
        
        Args:
            namespace: The namespace to count
            
        Returns:
            Number of entries in the namespace
        """
        with self._lock:
            return sum(1 for e in self._store.values() if e.namespace == namespace)
