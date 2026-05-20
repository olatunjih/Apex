from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List


@dataclass
class MemoryRecord:
    ticker: str
    thesis: str
    confidence: float
    evidence_quality: float
    created_at: datetime


@dataclass
class FailureRecord:
    ticker: str
    reason: str
    strategy: str
    created_at: datetime


@dataclass
class CognitiveState:
    strategic_memory: Dict[str, MemoryRecord] = field(default_factory=dict)
    failure_memory: List[FailureRecord] = field(default_factory=list)


class CognitiveLayer:
    def __init__(self, memory_ttl_days: int = 30) -> None:
        self.memory_ttl = timedelta(days=memory_ttl_days)
        self.state = CognitiveState()

    def upsert_thesis(self, ticker: str, thesis: str, confidence: float, evidence_quality: float) -> MemoryRecord:
        adjusted_confidence = max(0.0, min(1.0, confidence * evidence_quality))
        record = MemoryRecord(
            ticker=ticker,
            thesis=thesis,
            confidence=adjusted_confidence,
            evidence_quality=evidence_quality,
            created_at=datetime.now(timezone.utc),
        )
        self.state.strategic_memory[ticker] = record
        return record

    def record_failure(self, ticker: str, reason: str, strategy: str) -> FailureRecord:
        rec = FailureRecord(
            ticker=ticker,
            reason=reason,
            strategy=strategy,
            created_at=datetime.now(timezone.utc),
        )
        self.state.failure_memory.append(rec)
        return rec

    def get_bias_adjusted_confidence(self, ticker: str, base_confidence: float) -> float:
        recent_failures = [
            f for f in self.state.failure_memory if f.ticker == ticker and f.created_at >= datetime.now(timezone.utc) - self.memory_ttl
        ]
        penalty = min(0.4, len(recent_failures) * 0.05)
        return max(0.0, base_confidence - penalty)

    def evict_stale_memory(self) -> int:
        cutoff = datetime.now(timezone.utc) - self.memory_ttl
        stale = [k for k, v in self.state.strategic_memory.items() if v.created_at < cutoff]
        for k in stale:
            del self.state.strategic_memory[k]
        return len(stale)
