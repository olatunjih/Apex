from __future__ import annotations

from dataclasses import dataclass

from .policy import DEFAULT_NUMERICAL_POLICY, NumericalPolicy


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



def validate_runtime_config(config: RuntimeConfig) -> None:
    if config.max_clock_drift_ms <= 0:
        raise ValueError("max_clock_drift_ms must be > 0")
    if config.max_startup_snapshot_age_seconds <= 0:
        raise ValueError("max_startup_snapshot_age_seconds must be > 0")
    if config.max_idempotency_cache_size < 1:
        raise ValueError("max_idempotency_cache_size must be >= 1")
    if config.outbox_retry_limit < 1:
        raise ValueError("outbox_retry_limit must be >= 1")
    if not 0 <= config.min_actionable_confidence <= 1:
        raise ValueError("min_actionable_confidence must be in [0,1]")
    if config.min_risk_budget < 0:
        raise ValueError("min_risk_budget must be >= 0")


RuntimeConfig.numerical_policy = DEFAULT_NUMERICAL_POLICY
