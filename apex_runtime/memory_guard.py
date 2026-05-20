"""
APEX v3 — Memory Management & Guard System
Implements Section 1.7: Memory Management (MemoryGuard)

Features:
- tracemalloc snapshot comparison for leak detection
- psutil RSS monitoring
- Bounded cache enforcement
- WeakSet for event listeners
- Graceful restart trigger on ceiling breach
"""

from __future__ import annotations
import tracemalloc
import gc
import weakref
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from collections import OrderedDict
import psutil
import os

from .errors import APEXError, ErrorCategory, ErrorSeverity


@dataclass(frozen=True)
class MemorySnapshot:
    """Immutable snapshot of memory state."""
    timestamp: float
    rss_mb: float
    heap_mb: float
    top_allocations: List[tuple]  # (traceback, size_kb)
    object_counts: Dict[str, int]


@dataclass
class MemoryStats:
    """Accumulated memory statistics."""
    peak_rss_mb: float = 0.0
    leak_rate_mb_per_hour: float = 0.0
    last_snapshot: Optional[MemorySnapshot] = None
    alert_count: int = 0


class MemoryGuard:
    """
    Monitors memory usage, detects leaks, and enforces ceilings.
    Thread-safe singleton-like behavior per runtime instance.
    """

    def __init__(
        self,
        max_rss_mb: float = 1024.0,
        leak_threshold_mb_per_hour: float = 50.0,
        snapshot_interval_sec: float = 60.0,
        alert_callback: Optional[Callable[[str, MemoryStats], None]] = None,
        restart_callback: Optional[Callable[[], None]] = None,
    ):
        self.max_rss_mb = max_rss_mb
        self.leak_threshold_mb_per_hour = leak_threshold_mb_per_hour
        self.snapshot_interval_sec = snapshot_interval_sec
        self.alert_callback = alert_callback
        self.restart_callback = restart_callback

        self._lock = threading.RLock()
        self._stats = MemoryStats()
        self._baseline_snapshot: Optional[tracemalloc.Snapshot] = None
        self._last_check_time: float = 0.0
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        
        # WeakSet for listeners to prevent memory leaks from listeners themselves
        self._listeners: weakref.WeakSet = weakref.WeakSet()

    def start(self) -> None:
        """Start memory monitoring background thread."""
        with self._lock:
            if self._running:
                return
            tracemalloc.start(25)  # Store 25 frames
            self._baseline_snapshot = tracemalloc.take_snapshot()
            self._last_check_time = time.time()
            self._running = True
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop monitoring."""
        with self._lock:
            self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        tracemalloc.stop()

    def add_listener(self, listener: Any) -> None:
        """Add a listener using weak reference."""
        self._listeners.add(listener)

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                self.check_memory()
            except Exception as e:
                # Log error but don't crash the monitor
                if self.alert_callback:
                    self.alert_callback(f"MEMORY_MONITOR_ERROR: {e}", self._stats)
            time.sleep(self.snapshot_interval_sec)

    def check_memory(self) -> MemoryStats:
        """Perform a full memory check."""
        with self._lock:
            now = time.time()
            process = psutil.Process(os.getpid())
            current_rss_mb = process.memory_info().rss / (1024 * 1024)
            
            # Update peak
            if current_rss_mb > self._stats.peak_rss_mb:
                self._stats.peak_rss_mb = current_rss_mb

            # Check ceiling
            if current_rss_mb > self.max_rss_mb:
                self._handle_ceiling_exceeded(current_rss_mb)

            # Analyze leak rate
            if self._baseline_snapshot and self._stats.last_snapshot:
                elapsed_hours = (now - self._last_check_time) / 3600.0
                if elapsed_hours > 0:
                    # Simple linear estimation based on RSS growth
                    rss_growth = current_rss_mb - self._stats.last_snapshot.rss_mb
                    rate = rss_growth / elapsed_hours
                    self._stats.leak_rate_mb_per_hour = rate
                    
                    if rate > self.leak_threshold_mb_per_hour:
                        self._handle_leak_detected(rate)

            # Take new snapshot
            current_snapshot = tracemalloc.take_snapshot()
            top_stats = current_snapshot.compare_to(
                self._baseline_snapshot or current_snapshot, 'lineno'
            )[:10]
            top_allocations = [(str(s.traceback), s.size / 1024) for s in top_stats]

            # Basic object count estimation (expensive, so limited)
            object_counts = {}
            # In production, limit this to specific tracked types
            
            snapshot = MemorySnapshot(
                timestamp=now,
                rss_mb=current_rss_mb,
                heap_mb=sum(s.size for s in current_snapshot.statistics('lineno')) / (1024*1024),
                top_allocations=top_allocations,
                object_counts=object_counts
            )
            
            self._stats.last_snapshot = snapshot
            self._last_check_time = now
            
            # Force GC if growth is detected
            if current_rss_mb > (self._stats.peak_rss_mb * 0.9):
                gc.collect()

            return self._stats

    def _handle_ceiling_exceeded(self, current_rss_mb: float) -> None:
        """Handle memory ceiling breach."""
        self._stats.alert_count += 1
        msg = f"MEMORY_CEILING_EXCEEDED: {current_rss_mb:.2f}MB > {self.max_rss_mb:.2f}MB"
        
        if self.alert_callback:
            self.alert_callback(msg, self._stats)
            
        if self.restart_callback:
            # Trigger graceful restart
            self.restart_callback()

    def _handle_leak_detected(self, rate: float) -> None:
        """Handle suspected leak."""
        self._stats.alert_count += 1
        msg = f"MEMORY_LEAK_SUSPECTED: Rate {rate:.2f}MB/h exceeds threshold {self.leak_threshold_mb_per_hour:.2f}MB/h"
        
        if self.alert_callback:
            self.alert_callback(msg, self._stats)

    def get_bounded_cache(self, max_size: int) -> OrderedDict:
        """Factory for creating bounded caches with automatic eviction."""
        return BoundedCache(max_size, self)

    @property
    def stats(self) -> MemoryStats:
        return self._stats


class BoundedCache(OrderedDict):
    """LRU Cache that reports evictions to MemoryGuard."""
    
    def __init__(self, max_size: int, guard: MemoryGuard):
        super().__init__()
        self.max_size = max_size
        self.guard = guard
        self.eviction_count = 0

    def __setitem__(self, key, value):
        if len(self) >= self.max_size and key not in self:
            oldest = next(iter(self))
            del self[oldest]
            self.eviction_count += 1
        super().__setitem__(key, value)

    def __getitem__(self, key):
        # Move to end (LRU)
        val = super().__getitem__(key)
        self.move_to_end(key)
        return val
