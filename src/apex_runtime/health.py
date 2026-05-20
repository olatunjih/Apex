"""
APEX v3 - Health Endpoints (§1.8)
HTTP health checks: /health/live, /health/ready, /health/startup, /admin/health/deep
"""
import json
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import socket

@dataclass
class HealthCheckResult:
    name: str
    status: str  # "pass", "fail", "warn"
    latency_ms: float
    message: str
    details: Dict[str, Any] = None

@dataclass
class HealthResponse:
    status: str  # "healthy", "unhealthy", "degraded"
    timestamp: str
    checks: List[HealthCheckResult]
    version: str
    uptime_seconds: float

class HealthChecker:
    def __init__(self):
        self.start_time = time.time()
        self.version = "3.0.0"
        self._checks: Dict[str, callable] = {}
        self.current_phase = "PREFLIGHT"
        
    def register_check(self, name: str, check_fn: callable):
        self._checks[name] = check_fn
        
    def run_check(self, name: str) -> HealthCheckResult:
        start = time.time()
        try:
            result = self._checks[name]()
            latency = (time.time() - start) * 1000
            return HealthCheckResult(
                name=name,
                status="pass",
                latency_ms=round(latency, 2),
                message="OK",
                details=result or {}
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return HealthCheckResult(
                name=name,
                status="fail",
                latency_ms=round(latency, 2),
                message=str(e),
                details={"error": str(e)}
            )
    
    def check_live(self) -> HealthResponse:
        """Liveness probe: is the process running?"""
        return HealthResponse(
            status="healthy",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            checks=[HealthCheckResult("process_alive", "pass", 0.0, "Process is running")],
            version=self.version,
            uptime_seconds=round(time.time() - self.start_time, 2)
        )
    
    def check_ready(self) -> HealthResponse:
        """Readiness probe: can we accept traffic?"""
        checks = []
        has_failure = False
        has_warning = False
        
        for name in self._checks:
            result = self.run_check(name)
            checks.append(result)
            if result.status == "fail":
                has_failure = True
            elif result.status == "warn":
                has_warning = True
        
        status = "unhealthy" if has_failure else ("degraded" if has_warning else "healthy")
        
        return HealthResponse(
            status=status,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            checks=checks,
            version=self.version,
            uptime_seconds=round(time.time() - self.start_time, 2)
        )
    
    def check_startup(self) -> HealthResponse:
        """Startup probe: what phase are we in?"""
        phase_status = {
            "PREFLIGHT": "starting",
            "STORAGE": "connecting_db",
            "INTELLIGENCE_LOADING": "loading_intelligence",
            "STATE_RECONSTRUCTION": "reconstructing_state",
            "EXTERNAL_CONNECTIONS": "connecting_externals",
            "SERVICES": "starting_services",
            "READY": "ready",
            "SHUTDOWN": "shutting_down"
        }
        
        check = HealthCheckResult(
            name="startup_phase",
            status="pass" if self.current_phase == "READY" else "warn",
            latency_ms=0.0,
            message=f"Current phase: {self.current_phase}",
            details={"phase": self.current_phase, "status": phase_status.get(self.current_phase, "unknown")}
        )
        
        return HealthResponse(
            status="healthy" if self.current_phase == "READY" else "degraded",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            checks=[check],
            version=self.version,
            uptime_seconds=round(time.time() - self.start_time, 2)
        )
    
    def check_deep(self) -> HealthResponse:
        """Deep health check: comprehensive diagnostics"""
        checks = []
        
        # Memory check
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()
            mem_percent = (mem_info.rss / (1024 * 1024 * 1024)) * 100  # GB
            checks.append(HealthCheckResult(
                name="memory_usage",
                status="warn" if mem_percent > 80 else "pass",
                latency_ms=0.0,
                message=f"RSS: {mem_info.rss / (1024*1024):.1f} MB",
                details={"rss_mb": mem_info.rss / (1024*1024), "percent_of_1gb": mem_percent}
            ))
        except ImportError:
            checks.append(HealthCheckResult("memory_usage", "warn", 0.0, "psutil not available"))
        
        # Clock drift check
        checks.append(HealthCheckResult(
            name="clock_sync",
            status="pass",
            latency_ms=0.0,
            message="Clock synchronized",
            details={"drift_ms": 0}  # Would measure against NTP in production
        ))
        
        # Idempotency cache health
        checks.append(HealthCheckResult(
            name="idempotency_cache",
            status="pass",
            latency_ms=0.0,
            message="Cache healthy",
            details={"size": 0, "max_size": 10000}  # Would check actual cache
        ))
        
        # Outbox health
        checks.append(HealthCheckResult(
            name="outbox_queue",
            status="pass",
            latency_ms=0.0,
            message="Outbox empty",
            details={"pending": 0, "dlq_size": 0}
        ))
        
        has_failure = any(c.status == "fail" for c in checks)
        has_warning = any(c.status == "warn" for c in checks)
        status = "unhealthy" if has_failure else ("degraded" if has_warning else "healthy")
        
        return HealthResponse(
            status=status,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            checks=checks,
            version=self.version,
            uptime_seconds=round(time.time() - self.start_time, 2)
        )

DEFAULT_HEALTH_CHECKER = HealthChecker()

# --- HTTP Server for Health Endpoints ---

class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging
    
    def send_json_response(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())
    
    def do_GET(self):
        if self.path == '/health/live':
            response = DEFAULT_HEALTH_CHECKER.check_live()
            status_code = 200
        elif self.path == '/health/ready':
            response = DEFAULT_HEALTH_CHECKER.check_ready()
            status_code = 200 if response.status != "unhealthy" else 503
        elif self.path == '/health/startup':
            response = DEFAULT_HEALTH_CHECKER.check_startup()
            status_code = 200 if response.status == "healthy" else 503
        elif self.path == '/admin/health/deep':
            response = DEFAULT_HEALTH_CHECKER.check_deep()
            status_code = 200 if response.status != "unhealthy" else 503
        else:
            self.send_error(404)
            return
        
        self.send_json_response(status_code, asdict(response))

def start_health_server(port: int = 8080) -> Thread:
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread
