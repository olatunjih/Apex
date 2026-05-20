"""
APEX v3 — Health Endpoints & Signal Handling
Implements Section 1.8 (Health Endpoints) and Section 1.5 (Signal Handling)

Features:
- GET /health/live, /health/ready, /health/startup, /admin/health/deep
- SIGTERM, SIGINT, SIGHUP, SIGUSR1, SIGUSR2 handlers
- Graceful shutdown with drain timeout
- Debug state dump on SIGUSR1
"""

from __future__ import annotations
import signal
import threading
import time
import json
import os
import sys
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, List, Optional, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import socketserver

from .errors import APEXError
from .runtime import RuntimeState, RuntimePhase


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

    def _get_memory_info(self) -> Dict[str, float]:
        """Get current process memory info."""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            mem = process.memory_info()
            return {
                "rss_mb": mem.rss / (1024 * 1024),
                "vms_mb": mem.vms / (1024 * 1024),
            }
        except Exception:
            return {"error": "unable to retrieve memory info"}

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


class SignalHandler:
    """
    Manages Unix signal handlers for graceful shutdown and debugging.
    Implements Section 1.5 signal handling requirements.
    """

    def __init__(
        self,
        shutdown_callback: Callable[[], None],
        reload_callback: Optional[Callable[[], None]] = None,
        debug_dump_callback: Optional[Callable[[], Dict[str, Any]]] = None,
        toggle_logging_callback: Optional[Callable[[], None]] = None,
    ):
        self.shutdown_callback = shutdown_callback
        self.reload_callback = reload_callback
        self.debug_dump_callback = debug_dump_callback
        self.toggle_logging_callback = toggle_logging_callback
        
        self._shutdown_requested = False
        self._lock = threading.Lock()
        self._original_handlers: Dict[int, Any] = {}

    def install(self) -> None:
        """Install all signal handlers."""
        # Save original handlers
        for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGUSR1, signal.SIGUSR2]:
            self._original_handlers[sig] = signal.getsignal(sig)
        
        # Install new handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGHUP, self._handle_reload)
        signal.signal(signal.SIGUSR1, self._handle_debug_dump)
        signal.signal(signal.SIGUSR2, self._handle_toggle_logging)

    def restore(self) -> None:
        """Restore original signal handlers."""
        for sig, handler in self._original_handlers.items():
            try:
                signal.signal(sig, handler)
            except ValueError:
                pass  # Signal may not be available on all platforms

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def _handle_shutdown(self, signum: int, frame) -> None:
        """Handle SIGTERM/SIGINT for graceful shutdown."""
        with self._lock:
            if self._shutdown_requested:
                # Already shutting down, force exit
                os._exit(1)
            self._shutdown_requested = True
        
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        print(f"\n[{sig_name}] Graceful shutdown initiated...", flush=True)
        
        # Call shutdown callback (should handle draining)
        try:
            self.shutdown_callback()
        except Exception as e:
            print(f"[ERROR] Shutdown callback failed: {e}", flush=True)
            os._exit(1)

    def _handle_reload(self, signum: int, frame) -> None:
        """Handle SIGHUP for configuration reload."""
        print("\n[SIGHUP] Reloading configuration...", flush=True)
        if self.reload_callback:
            try:
                self.reload_callback()
                print("[SIGHUP] Configuration reloaded successfully", flush=True)
            except Exception as e:
                print(f"[SIGHUP ERROR] Reload failed: {e}", flush=True)

    def _handle_debug_dump(self, signum: int, frame) -> None:
        """Handle SIGUSR1 for debug state dump."""
        print("\n[SIGUSR1] Dumping debug state...", flush=True)
        if self.debug_dump_callback:
            try:
                dump = self.debug_dump_callback()
                dump_file = f"/tmp/apex_debug_{os.getpid()}_{int(time.time())}.json"
                with open(dump_file, 'w') as f:
                    json.dump(dump, f, indent=2, default=str)
                print(f"[SIGUSR1] Debug state written to {dump_file}", flush=True)
            except Exception as e:
                print(f"[SIGUSR1 ERROR] Dump failed: {e}", flush=True)

    def _handle_toggle_logging(self, signum: int, frame) -> None:
        """Handle SIGUSR2 for toggling verbose logging."""
        print("\n[SIGUSR2] Toggling verbose logging...", flush=True)
        if self.toggle_logging_callback:
            try:
                self.toggle_logging_callback()
                print("[SIGUSR2] Logging level toggled", flush=True)
            except Exception as e:
                print(f"[SIGUSR2 ERROR] Toggle failed: {e}", flush=True)
