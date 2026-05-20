from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeConfig:
    max_clock_drift_ms: int = 50
    startup_vendor_optional: bool = True
    startup_llm_optional: bool = True
    shutdown_drain_timeout_seconds: int = 15
