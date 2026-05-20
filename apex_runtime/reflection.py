from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .reactive import ReactiveDecision


@dataclass(frozen=True)
class ReflectionRecord:
    ticker: str
    decision_action: str
    confidence: float
    blocked: bool
    rationale: str
    evidence_quality: float
    failure_rate: float
    created_at: datetime


class ReflectionLayer:
    """Captures post-analysis self-critique and analytical debt signals."""

    def __init__(self, max_records: int = 2000) -> None:
        self._records: List[ReflectionRecord] = []
        self._max_records = max_records

    def reflect(self, ticker: str, decision: "ReactiveDecision") -> ReflectionRecord:
        evidence_quality = self._extract_float(decision.why.evidence_quality, "evidence_quality")
        failure_rate = self._extract_float(decision.why.evidence_quality, "failure_rate")
        rationale = self._build_rationale(decision)
        rec = ReflectionRecord(
            ticker=ticker,
            decision_action=decision.action,
            confidence=decision.confidence,
            blocked=decision.blocked,
            rationale=rationale,
            evidence_quality=evidence_quality,
            failure_rate=failure_rate,
            created_at=datetime.now(timezone.utc),
        )
        self._records.append(rec)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        return rec

    def analytical_debt_score(self) -> float:
        if not self._records:
            return 0.0
        blocked_ratio = sum(1 for r in self._records if r.blocked) / len(self._records)
        low_confidence_ratio = sum(1 for r in self._records if r.confidence < 0.4) / len(self._records)
        poor_evidence_ratio = sum(1 for r in self._records if r.evidence_quality < 0.55) / len(self._records)
        mean_failure_rate = mean(r.failure_rate for r in self._records)
        score = (blocked_ratio * 0.4) + (low_confidence_ratio * 0.25) + (poor_evidence_ratio * 0.2) + (mean_failure_rate * 0.15)
        return round(min(1.0, max(0.0, score)), 4)

    def recent(self, limit: int = 10) -> List[ReflectionRecord]:
        return self._records[-limit:]

    def _build_rationale(self, decision: "ReactiveDecision") -> str:
        if decision.blocked:
            return f"Blocked: {decision.reason}; calibration={decision.why.confidence_calibration}"
        return f"Allowed: {decision.reason}; evidence={decision.why.evidence_quality}"

    def _extract_float(self, text: str, key: str) -> float:
        for chunk in text.split(";"):
            chunk = chunk.strip()
            if chunk.startswith(f"{key}="):
                try:
                    return float(chunk.split("=", 1)[1])
                except ValueError:
                    return 0.0
        return 0.0
