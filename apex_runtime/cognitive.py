from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from statistics import mean
from threading import RLock
from typing import Dict, List

from .errors import validation_error


@dataclass(frozen=True)
class MemoryRecord:
    ticker: str
    thesis: str
    confidence: float
    evidence_quality: float
    created_at: datetime
    source_count: int
    horizon_days: int
    regime_tag: str


@dataclass(frozen=True)
class FailureRecord:
    ticker: str
    reason: str
    strategy: str
    realized_return_bps: float
    created_at: datetime


@dataclass
class CognitiveState:
    strategic_memory: Dict[str, MemoryRecord] = field(default_factory=dict)
    failure_memory: List[FailureRecord] = field(default_factory=list)


class CognitiveLayer:
    """Cross-session intelligence substrate for confidence calibration and memory."""

    def __init__(self, memory_ttl_days: int = 30) -> None:
        if memory_ttl_days <= 0:
            raise validation_error("MEMORY_TTL_INVALID", "memory_ttl_days must be > 0")
        self.memory_ttl = timedelta(days=memory_ttl_days)
        self.state = CognitiveState()
        self._lock = RLock()

    def upsert_thesis(
        self,
        ticker: str,
        thesis: str,
        confidence: float,
        evidence_quality: float,
        source_count: int,
        horizon_days: int,
        regime_tag: str = "unknown",
    ) -> MemoryRecord:
        self._validate_inputs(ticker, confidence, evidence_quality, source_count, horizon_days)
        source_factor = min(1.0, 0.5 + (source_count * 0.08))
        horizon_factor = 1.0 if horizon_days <= 30 else 0.9
        adjusted_confidence = max(0.0, min(1.0, confidence * evidence_quality * source_factor * horizon_factor))
        record = MemoryRecord(
            ticker=ticker,
            thesis=thesis,
            confidence=adjusted_confidence,
            evidence_quality=evidence_quality,
            created_at=datetime.now(timezone.utc),
            source_count=source_count,
            horizon_days=horizon_days,
            regime_tag=regime_tag,
        )
        with self._lock:
            self.state.strategic_memory[ticker] = record
        return record

    def set_memory_timestamp(self, ticker: str, created_at: datetime) -> None:
        with self._lock:
            rec = self.state.strategic_memory.get(ticker)
            if rec is None:
                raise validation_error("MEMORY_NOT_FOUND", f"no memory for ticker {ticker}")
            self.state.strategic_memory[ticker] = replace(rec, created_at=created_at)

    def record_failure(self, ticker: str, reason: str, strategy: str, realized_return_bps: float) -> FailureRecord:
        if not ticker:
            raise validation_error("TICKER_REQUIRED", "ticker is required")
        rec = FailureRecord(
            ticker=ticker,
            reason=reason,
            strategy=strategy,
            realized_return_bps=realized_return_bps,
            created_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self.state.failure_memory.append(rec)
        return rec

    def get_failure_rate(self, ticker: str) -> float:
        recent = self._recent_failures(ticker)
        if not recent:
            return 0.0
        loss_events = [f for f in recent if f.realized_return_bps < 0]
        return len(loss_events) / len(recent)

    def get_bias_adjusted_confidence(self, ticker: str, base_confidence: float) -> float:
        base = max(0.0, min(1.0, base_confidence))
        recent_failures = self._recent_failures(ticker)
        if not recent_failures:
            return base

        failure_rate = self.get_failure_rate(ticker)
        avg_loss_bps = abs(mean([f.realized_return_bps for f in recent_failures if f.realized_return_bps < 0] or [0.0]))
        severity_penalty = min(0.25, avg_loss_bps / 1000.0)
        frequency_penalty = min(0.35, failure_rate * 0.35)
        confidence = max(0.0, base - severity_penalty - frequency_penalty)
        return min(1.0, confidence)

    def evict_stale_memory(self) -> int:
        cutoff = datetime.now(timezone.utc) - self.memory_ttl
        with self._lock:
            stale = [k for k, v in self.state.strategic_memory.items() if v.created_at < cutoff]
            for k in stale:
                del self.state.strategic_memory[k]
            self.state.failure_memory = [f for f in self.state.failure_memory if f.created_at >= cutoff]
            return len(stale)

    def _recent_failures(self, ticker: str) -> List[FailureRecord]:
        cutoff = datetime.now(timezone.utc) - self.memory_ttl
        with self._lock:
            return [f for f in self.state.failure_memory if f.ticker == ticker and f.created_at >= cutoff]

    def _validate_inputs(self, ticker: str, confidence: float, evidence_quality: float, source_count: int, horizon_days: int) -> None:
        if not ticker:
            raise validation_error("TICKER_REQUIRED", "ticker is required")
        if not 0 <= confidence <= 1:
            raise validation_error("CONFIDENCE_INVALID", "confidence must be in [0,1]")
        if not 0 <= evidence_quality <= 1:
            raise validation_error("EVIDENCE_QUALITY_INVALID", "evidence_quality must be in [0,1]")
        if source_count < 1:
            raise validation_error("SOURCE_COUNT_INVALID", "source_count must be >= 1")
        if horizon_days < 1:
            raise validation_error("HORIZON_INVALID", "horizon_days must be >= 1")
