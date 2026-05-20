from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .reactive import ReactiveDecision


@dataclass(frozen=True)
class ReflectionRecord:
    ticker: str
    decision_action: str
    confidence: float
    blocked: bool
    rationale: str
    created_at: datetime


class ReflectionLayer:
    """Captures post-analysis self-critique and analytical debt signals."""

    def __init__(self) -> None:
        self._records: List[ReflectionRecord] = []

    def reflect(self, ticker: str, decision: "ReactiveDecision") -> ReflectionRecord:
        rationale = self._build_rationale(decision)
        rec = ReflectionRecord(
            ticker=ticker,
            decision_action=decision.action,
            confidence=decision.confidence,
            blocked=decision.blocked,
            rationale=rationale,
            created_at=datetime.now(timezone.utc),
        )
        self._records.append(rec)
        return rec

    def analytical_debt_score(self) -> float:
        if not self._records:
            return 0.0
        blocked_ratio = sum(1 for r in self._records if r.blocked) / len(self._records)
        low_confidence_ratio = sum(1 for r in self._records if r.confidence < 0.4) / len(self._records)
        return round((blocked_ratio * 0.6) + (low_confidence_ratio * 0.4), 4)

    def recent(self, limit: int = 10) -> List[ReflectionRecord]:
        return self._records[-limit:]

    def _build_rationale(self, decision: "ReactiveDecision") -> str:
        if decision.blocked:
            return f"Blocked: {decision.reason}; calibration={decision.why.confidence_calibration}"
        return f"Allowed: {decision.reason}; evidence={decision.why.evidence_quality}"
