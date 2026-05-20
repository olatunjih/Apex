from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from threading import RLock
from typing import Deque, Dict, Iterable, List, Optional

from .config import RuntimeConfig, validate_runtime_config
from .errors import APEXError, ErrorCategory, ErrorSeverity, validation_error
from .policy import validate_numerical_policy


class RuntimePhase(str, Enum):
    CREATED = "created"
    PREFLIGHT = "preflight"
    STORAGE = "storage"
    INTELLIGENCE_LOADING = "intelligence_loading"
    STATE_RECONSTRUCTION = "state_reconstruction"
    EXTERNAL_CONNECTIONS = "external_connections"
    SERVICES = "services"
    SHUTDOWN = "shutdown"


class AuditEvent(str, Enum):
    PRE_FLIGHT_COMPLETE = "PRE_FLIGHT_COMPLETE"
    STORAGE_READY = "STORAGE_READY"
    INTELLIGENCE_READY = "INTELLIGENCE_READY"
    STATE_RECONSTRUCTION_READY = "STATE_RECONSTRUCTION_READY"
    PIL_STARTING = "PIL_STARTING"
    SESSION_STARTED = "SESSION_STARTED"
    STARTUP_COMPLETE = "STARTUP_COMPLETE"
    SHUTDOWN_IMMINENT = "SHUTDOWN_IMMINENT"
    SHUTDOWN_COMPLETE = "SHUTDOWN_COMPLETE"
    DLQ_GROWING = "DLQ_GROWING"


@dataclass(frozen=True)
class RuntimeEvent:
    key: str
    payload: dict
    created_at: datetime
    retries: int = 0


@dataclass
class RuntimeState:
    phase: RuntimePhase = RuntimePhase.CREATED
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
        self._lock = RLock()

    def _audit(self, event: AuditEvent) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        self.state.audit_trail.append(f"{ts} {event.value}")

    def _check_clock(self, measured_drift_ms: int) -> None:
        if measured_drift_ms > self.config.max_clock_drift_ms:
            raise APEXError(
                code="CLOCK_DRIFT_TOO_HIGH",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.CRITICAL,
                retryable=False,
                message=f"Clock drift {measured_drift_ms}ms exceeds limit {self.config.max_clock_drift_ms}ms",
            )

    def _validate_snapshot_age(self, snapshot_timestamp: Optional[datetime]) -> None:
        if snapshot_timestamp is None:
            self.state.degraded_modes.append("pil_cold_start")
            return
        age = datetime.now(timezone.utc) - snapshot_timestamp
        if age > timedelta(seconds=self.config.max_startup_snapshot_age_seconds):
            self.state.degraded_modes.append("pil_cold_start")

    def startup(self, measured_drift_ms: int = 0, vendor_ok: bool = True, llm_ok: bool = True, snapshot_timestamp: Optional[datetime] = None) -> RuntimeState:
        with self._lock:
            self.state.phase = RuntimePhase.PREFLIGHT
            validate_runtime_config(self.config)
            validate_numerical_policy(self.config.numerical_policy)
            self._check_clock(measured_drift_ms)
            self._audit(AuditEvent.PRE_FLIGHT_COMPLETE)

            self.state.phase = RuntimePhase.STORAGE
            self._audit(AuditEvent.STORAGE_READY)

            self.state.phase = RuntimePhase.INTELLIGENCE_LOADING
            self._audit(AuditEvent.INTELLIGENCE_READY)

            self.state.phase = RuntimePhase.STATE_RECONSTRUCTION
            self._validate_snapshot_age(snapshot_timestamp)
            self._audit(AuditEvent.STATE_RECONSTRUCTION_READY)

            self.state.phase = RuntimePhase.EXTERNAL_CONNECTIONS
            if not vendor_ok and self.config.startup_vendor_optional:
                self.state.degraded_modes.append("analysis_mode_data_warning")
            elif not vendor_ok:
                raise APEXError("DATA_VENDOR_UNAVAILABLE", ErrorCategory.EXTERNAL, ErrorSeverity.HIGH, True, "Data vendor unavailable")

            if not llm_ok and self.config.startup_llm_optional:
                self.state.degraded_modes.append("deterministic_only")
            elif not llm_ok:
                raise APEXError("LLM_UNAVAILABLE", ErrorCategory.EXTERNAL, ErrorSeverity.HIGH, True, "LLM unavailable")

            self.state.phase = RuntimePhase.SERVICES
            self._audit(AuditEvent.PIL_STARTING)
            self.state.ready = True
            self._audit(AuditEvent.SESSION_STARTED)
            self._audit(AuditEvent.STARTUP_COMPLETE)
            return self.state

    def shutdown(self) -> RuntimeState:
        with self._lock:
            self.state.phase = RuntimePhase.SHUTDOWN
            self._audit(AuditEvent.SHUTDOWN_IMMINENT)
            self.state.ready = False
            self._audit(AuditEvent.SHUTDOWN_COMPLETE)
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
                    if event.retries + 1 >= self.config.outbox_retry_limit:
                        self._dead_letter_queue.append(RuntimeEvent(event.key, event.payload, event.created_at, retries=event.retries + 1))
                    else:
                        self._outbox.append(RuntimeEvent(event.key, event.payload, event.created_at, retries=event.retries + 1))
                    continue
                delivered += 1

            if len(self._dead_letter_queue) > self.config.dlq_alert_threshold:
                self._audit(AuditEvent.DLQ_GROWING)
            return delivered

    @property
    def outbox_size(self) -> int:
        return len(self._outbox)

    @property
    def dead_letter_size(self) -> int:
        return len(self._dead_letter_queue)
