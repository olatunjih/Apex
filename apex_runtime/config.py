from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeConfig:
    # Section 1.3 / 1.4 defaults from APEX_v3_INSTRUCTION_SET.md
    max_clock_drift_ms: int = 50
    max_startup_snapshot_age_seconds: int = 900

    # Degraded startup policy
    startup_vendor_optional: bool = True
    startup_llm_optional: bool = True

    # Runtime buffering / reliability
    max_idempotency_cache_size: int = 10_000
    outbox_retry_limit: int = 5
    dlq_alert_threshold: int = 100
    shutdown_drain_timeout_seconds: int = 15

    # Reactive policy knobs (avoid hardcoded decision constants)
    min_actionable_confidence: float = 0.35
    min_risk_budget: float = 0.01
    long_horizon_days_threshold: int = 30
    long_horizon_penalty: float = 0.08
    actionable_research_action: str = "research_long"
    blocked_action: str = "hold"
