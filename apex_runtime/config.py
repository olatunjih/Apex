from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeConfig:
    max_clock_drift_ms: int = 50
    startup_vendor_optional: bool = True
    startup_llm_optional: bool = True
    shutdown_drain_timeout_seconds: int = 15
    max_startup_snapshot_age_seconds: int = 900
    max_idempotency_cache_size: int = 10_000
    outbox_retry_limit: int = 5
    dlq_alert_threshold: int = 100
