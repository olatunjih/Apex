from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from .config import RuntimeConfig
from .errors import APEXError, ErrorCategory, ErrorSeverity


@dataclass
class RuntimeState:
    phase: str = "created"
    ready: bool = False
    degraded_modes: List[str] = field(default_factory=list)
    audit_trail: List[str] = field(default_factory=list)


class ApexRuntime:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.state = RuntimeState()
        self._idempotency_cache: Dict[str, dict] = {}

    def _audit(self, event: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        self.state.audit_trail.append(f"{ts} {event}")

    def _check_clock(self, measured_drift_ms: int) -> None:
        if measured_drift_ms > self.config.max_clock_drift_ms:
            raise APEXError(
                code="CLOCK_DRIFT_TOO_HIGH",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.CRITICAL,
                retryable=False,
                message=(
                    f"Clock drift {measured_drift_ms}ms exceeds "
                    f"limit {self.config.max_clock_drift_ms}ms"
                ),
            )

    def startup(self, measured_drift_ms: int = 0, vendor_ok: bool = True, llm_ok: bool = True) -> RuntimeState:
        self.state.phase = "preflight"
        self._check_clock(measured_drift_ms)
        self._audit("PRE_FLIGHT_COMPLETE")

        self.state.phase = "storage"
        self._audit("STORAGE_READY")

        self.state.phase = "intelligence_loading"
        self._audit("INTELLIGENCE_READY")

        self.state.phase = "state_reconstruction"
        self._audit("STATE_RECONSTRUCTION_READY")

        self.state.phase = "external_connections"
        if not vendor_ok and self.config.startup_vendor_optional:
            self.state.degraded_modes.append("analysis_mode_data_warning")
        elif not vendor_ok:
            raise APEXError("DATA_VENDOR_UNAVAILABLE", ErrorCategory.EXTERNAL, ErrorSeverity.HIGH, True, "Data vendor unavailable")

        if not llm_ok and self.config.startup_llm_optional:
            self.state.degraded_modes.append("deterministic_only")
        elif not llm_ok:
            raise APEXError("LLM_UNAVAILABLE", ErrorCategory.EXTERNAL, ErrorSeverity.HIGH, True, "LLM unavailable")

        self.state.phase = "services"
        self.state.ready = True
        self._audit("STARTUP_COMPLETE")
        return self.state

    def shutdown(self) -> RuntimeState:
        self.state.phase = "shutdown"
        time.sleep(0.01)
        self.state.ready = False
        self._audit("SHUTDOWN_COMPLETE")
        return self.state

    def process_idempotent(self, key: str, payload: dict) -> dict:
        if key in self._idempotency_cache:
            return self._idempotency_cache[key]
        result = {"accepted": True, "payload": payload}
        self._idempotency_cache[key] = result
        return result
