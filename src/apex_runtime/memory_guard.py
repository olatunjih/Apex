"""
APEX v3 - Memory Management (§1.7)
MemoryGuard: RSS monitoring, leak detection, graceful restart triggers
"""
import os
import time
import tracemalloc
import weakref
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from collections import OrderedDict
from threading import RLock, Thread
import gc

@dataclass
class MemorySnapshot:
    timestamp: float
    rss_mb: float
    heap_mb: float
    top_allocations: List[tuple]

@dataclass
class MemoryAlert:
    alert_type: str
    severity: str
    message: str
    timestamp: float
    details: Dict[str, Any] = field(default_factory=dict)

class BoundedCache:
    def __init__(self, max_size: int = 1000):
        self._cache = OrderedDict()
        self._max_size = max_size
        self._lock = RLock()
        
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                value = self._cache[key]
                if isinstance(value, weakref.ref):
                    return value()
                return value
            return None
    
    def set(self, key: str, value: Any, use_weak_ref: bool = False):
        with self._lock:
            if use_weak_ref and not isinstance(value, weakref.ref):
                value = weakref.ref(value)
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
    
    def size(self) -> int:
        return len(self._cache)

class MemoryGuard:
    def __init__(self, memory_leak_alert_threshold_mb_per_hour: float = 50.0, max_rss_mb: float = 2048.0):
        self.memory_leak_threshold = memory_leak_alert_threshold_mb_per_hour
        self.max_rss_mb = max_rss_mb
        self.snapshot_history: List[MemorySnapshot] = []
        self._alerts: List[MemoryAlert] = []
        self._lock = RLock()
        self._idempotency_cache = BoundedCache(10000)
        self._data_registry_cache = BoundedCache(5000)
        self._baseline_snapshot = None
        tracemalloc.start()
        
    def take_snapshot(self) -> MemorySnapshot:
        """Take a memory snapshot for baseline comparison"""
        snap = self.get_memory_usage()
        if self._baseline_snapshot is None:
            self._baseline_snapshot = snap
        with self._lock:
            self.snapshot_history.append(snap)
            while len(self.snapshot_history) > 60:
                self.snapshot_history.pop(0)
        return snap
        
    def get_memory_usage(self) -> MemorySnapshot:
        import psutil
        process = psutil.Process(os.getpid())
        rss_mb = process.memory_info().rss / (1024 * 1024)
        current, _ = tracemalloc.get_traced_memory()
        heap_mb = current / (1024 * 1024)
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics("lineno")[:10]
        return MemorySnapshot(time.time(), rss_mb, heap_mb, [(str(s.traceback), s.size/1024) for s in top_stats])
    
    def detect_leak(self) -> Optional[MemoryAlert]:
        with self._lock:
            if len(self.snapshot_history) < 2:
                return None
            oldest, newest = self.snapshot_history[0], self.snapshot_history[-1]
            hours = (newest.timestamp - oldest.timestamp) / 3600
            if hours < 0.5:
                return None
            rate = (newest.rss_mb - oldest.rss_mb) / hours
            if rate > self.memory_leak_threshold:
                return MemoryAlert("leak_suspected", "warning", f"Leak: {rate:.1f} MB/hr", time.time(), {"rate": rate})
        return None
    
    def check_ceiling(self) -> Optional[MemoryAlert]:
        snap = self.get_memory_usage()
        if snap.rss_mb > self.max_rss_mb:
            return MemoryAlert("ceiling_exceeded", "critical", f"RSS {snap.rss_mb:.1f} > {self.max_rss_mb}", time.time())
        return None
    
    def record_snapshot(self):
        """Record a memory snapshot (alias for take_snapshot)"""
        return self.take_snapshot()
    
    def get_status(self) -> Dict[str, Any]:
        snap = self.get_memory_usage()
        return {"rss_mb": snap.rss_mb, "heap_mb": snap.heap_mb, "max_rss_mb": self.max_rss_mb, "usage_pct": snap.rss_mb/self.max_rss_mb*100, "caches": {"idempotency": self._idempotency_cache.size(), "data_registry": self._data_registry_cache.size()}}

DEFAULT_MEMORY_GUARD = MemoryGuard()
