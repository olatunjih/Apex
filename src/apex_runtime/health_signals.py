"""
APEX v3 — Health Endpoints
Implements Section 1.8 (Health Endpoints). Signal handling lives in signal_handler.py.

Features:
- GET /health/live, /health/ready, /health/startup, /admin/health/deep
"""

from __future__ import annotations
import threading
import time
import json
import os
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, Optional, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import socketserver

from .runtime import RuntimePhase


@dataclass
class HealthStatus:
    """Health check response structure."""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: float
    checks: Dict[str, Dict[str, Any]]
    version: str
    uptime_seconds: float


class HealthCheckSystem:
    """
    Manages health checks and exposes them via HTTP endpoints.
    Thread-safe registration of check functions.
    """

    def __init__(self, version: str = "3.0.0"):
        self.version = version
        self._lock = threading.RLock()
        self._checks: Dict[str, Callable[[], Tuple[bool, str, Optional[float]]]] = {}
        self._start_time = time.time()
        self._server: Optional[HTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None

    def register_check(
        self,
        name: str,
        check_fn: Callable[[], Tuple[bool, str, Optional[float]]],
    ) -> None:
        """
        Register a health check function.
        
        Args:
            name: Unique identifier for the check
            check_fn: Function returning (passed, message, latency_ms)
        """
        with self._lock:
            self._checks[name] = check_fn

    def unregister_check(self, name: str) -> None:
        """Remove a health check."""
        with self._lock:
            self._checks.pop(name, None)

    def run_all_checks(self) -> HealthStatus:
        """Execute all registered checks and return aggregated status."""
        results = {}
        worst_status = "healthy"
        
        with self._lock:
            checks_copy = dict(self._checks)
        
        for name, check_fn in checks_copy.items():
            try:
                start = time.perf_counter()
                passed, message, latency_ms = check_fn()
                elapsed = (time.perf_counter() - start) * 1000 if latency_ms is None else latency_ms
                
                status = "pass" if passed else "fail"
                results[name] = {
                    "status": status,
                    "message": message,
                    "latency_ms": round(elapsed, 2)
                }
                
                if not passed:
                    if worst_status == "healthy":
                        worst_status = "degraded"
                    # If any critical check fails, mark unhealthy
                    if name.startswith("critical_"):
                        worst_status = "unhealthy"
                        
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "message": str(e),
                    "latency_ms": 0
                }
                worst_status = "unhealthy"

        return HealthStatus(
            status=worst_status,
            timestamp=time.time(),
            checks=results,
            version=self.version,
            uptime_seconds=time.time() - self._start_time
        )

    def get_live_status(self) -> Dict[str, Any]:
        """Simple liveness probe - just confirms process is alive."""
        return {"status": "alive", "timestamp": time.time()}

    def get_ready_status(self) -> HealthStatus:
        """Readiness probe - checks if ready to serve traffic."""
        status = self.run_all_checks()
        # Filter to only readiness-critical checks
        ready_checks = {
            k: v for k, v in status.checks.items()
            if k.startswith("ready_") or k.startswith("critical_")
        }
        return HealthStatus(
            status=status.status,
            timestamp=status.timestamp,
            checks=ready_checks,
            version=status.version,
            uptime_seconds=status.uptime_seconds
        )

    def get_startup_status(self, current_phase: RuntimePhase) -> Dict[str, Any]:
        """Startup probe - reports current startup phase."""
        return {
            "phase": current_phase.name,
            "ready": current_phase == RuntimePhase.SERVICES,
            "timestamp": time.time()
        }

    def get_deep_health(self) -> Dict[str, Any]:
        """Deep health check with full system diagnostics."""
        status = self.run_all_checks()
        return {
            "overall": status.status,
            "checks": status.checks,
            "version": status.version,
            "uptime_seconds": status.uptime_seconds,
            "timestamp": status.timestamp,
            "pid": os.getpid(),
            "memory_info": self._get_memory_info(),
        }

    def _get_memory_info(self) -> Dict[str, Any]:
        """Get current process memory info when psutil is available."""
        from importlib.util import find_spec

        if find_spec("psutil") is None:
            return {"error": "psutil not available"}

        import psutil

        process = psutil.Process(os.getpid())
        mem = process.memory_info()
        return {
            "rss_mb": mem.rss / (1024 * 1024),
            "vms_mb": mem.vms / (1024 * 1024),
        }

    def start_server(self, port: int = 8080, host: str = "0.0.0.0") -> None:
        """Start HTTP server for health endpoints."""
        handler = make_health_handler(self)
        
        class ReuseAddrServer(socketserver.TCPServer):
            allow_reuse_address = True
        
        self._server = ReuseAddrServer((host, port), handler)
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()

    def stop_server(self) -> None:
        """Stop HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        if self._server_thread:
            self._server_thread.join(timeout=5.0)


def make_health_handler(health_system: HealthCheckSystem) -> type:
    """Factory to create HTTP request handler with access to health system."""
    
    class HealthHTTPHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Suppress default logging

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            
            if path == "/health/live":
                self._send_json(health_system.get_live_status())
            elif path == "/health/ready":
                status = health_system.get_ready_status()
                code = 200 if status.status != "unhealthy" else 503
                self._send_json(asdict(status), code)
            elif path == "/health/startup":
                # Need phase from runtime - will be set via setter
                phase = getattr(self, '_current_phase', RuntimePhase.PREFLIGHT)
                self._send_json(health_system.get_startup_status(phase))
            elif path == "/admin/health/deep":
                self._send_json(health_system.get_deep_health())
            else:
                self.send_error(404, "Not Found")

        def _send_json(self, data: Dict, status_code: int = 200) -> None:
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))

    return HealthHTTPHandler


# Canonical health checker name. HealthCheckSystem remains as a compatibility alias.
HealthChecker = HealthCheckSystem
HealthResponse = HealthStatus
HealthCheckResult = HealthStatus
DEFAULT_HEALTH_CHECKER = HealthChecker()


def start_health_server(port: int = 8080, host: str = "0.0.0.0") -> threading.Thread:
    """Start the canonical health server and return its background thread."""
    DEFAULT_HEALTH_CHECKER.start_server(port=port, host=host)
    assert DEFAULT_HEALTH_CHECKER._server_thread is not None
    return DEFAULT_HEALTH_CHECKER._server_thread


__all__ = [
    "HealthStatus",
    "HealthCheckSystem",
    "HealthChecker",
    "HealthResponse",
    "HealthCheckResult",
    "make_health_handler",
    "start_health_server",
    "DEFAULT_HEALTH_CHECKER",
]
