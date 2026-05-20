from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Deque, Dict, Iterable, List, Optional

from .config import RuntimeConfig
from .errors import APEXError, ErrorCategory, ErrorSeverity, validation_error


@dataclass(frozen=True)
class RuntimeEvent:
    key: str
    payload: dict
    created_at: datetime
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
        self._idempotency_cache: "OrderedDict[str, dict]" = OrderedDict()
        self._outbox: Deque[RuntimeEvent] = deque()
        self._dead_letter_queue: Deque[RuntimeEvent] = deque()
        self._processed_keys: set[str] = set()
        self._lock = RLock()
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

    def _validate_snapshot_age(self, snapshot_timestamp: Optional[datetime]) -> None:
        if snapshot_timestamp is None:
            self.state.degraded_modes.append("pil_cold_start")
            return
        age = datetime.now(timezone.utc) - snapshot_timestamp
        if age > timedelta(seconds=self.config.max_startup_snapshot_age_seconds):
            self.state.degraded_modes.append("pil_cold_start")

    def startup(
        self,
        measured_drift_ms: int = 0,
        vendor_ok: bool = True,
        llm_ok: bool = True,
        snapshot_timestamp: Optional[datetime] = None,
    ) -> RuntimeState:
        with self._lock:
            self.state.phase = "preflight"
            self._check_clock(measured_drift_ms)
            self._audit("PRE_FLIGHT_COMPLETE")

            self.state.phase = "storage"
            self._audit("STORAGE_READY")

            self.state.phase = "intelligence_loading"
            self._audit("INTELLIGENCE_READY")

            self.state.phase = "state_reconstruction"
            self._validate_snapshot_age(snapshot_timestamp)
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
        with self._lock:
            self.state.phase = "shutdown"
            self.state.ready = False
            self._audit("SHUTDOWN_COMPLETE")
            return self.state

    def process_idempotent(self, key: str, payload: dict) -> dict:
        if not key:
            raise validation_error("IDEMPOTENCY_KEY_REQUIRED", "idempotency key must be non-empty")

        with self._lock:
            if key in self._idempotency_cache:
                self._idempotency_cache.move_to_end(key)
                return self._idempotency_cache[key]

            result = {"accepted": True, "payload": payload}
            self._idempotency_cache[key] = result
            self._processed_keys.add(key)
            self._outbox.append(RuntimeEvent(key=key, payload=result, created_at=datetime.now(timezone.utc)))
            self._prune_cache_if_needed()
            return result

    def _prune_cache_if_needed(self) -> None:
        while len(self._idempotency_cache) > self.config.max_idempotency_cache_size:
            self._idempotency_cache.popitem(last=False)

    def drain_outbox(self, fail_keys: Optional[Iterable[str]] = None) -> int:
        failures = set(fail_keys or [])
        delivered = 0

        with self._lock:
            pending = deque(self._outbox)
            self._outbox.clear()

            while pending:
                event = pending.popleft()
                if event.key in failures:
                    self._dead_letter_queue.append(event)
                    continue
                delivered += 1
            if len(self._dead_letter_queue) > self.config.dlq_alert_threshold:
                self._audit("DLQ_GROWING")
            return delivered

    @property
    def outbox_size(self) -> int:
        return len(self._outbox)

    @property
    def dead_letter_size(self) -> int:
        return len(self._dead_letter_queue)
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
