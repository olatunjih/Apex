from __future__ import annotations

from dataclasses import dataclass

from .cognitive import CognitiveLayer


@dataclass(frozen=True)
class WhyContext:
    ticker: str
    base_confidence: float
    adjusted_confidence: float
    intent: str
    risk_budget: float
    target_horizon_days: int


@dataclass(frozen=True)
class WhyExplanation:
    market_structure: str
    strategy_context: str
    evidence_quality: str
    risk_constraints: str
    confidence_calibration: str


class WhyEngine:
    """Five-layer explanation engine aligned with APEX v3 reactive layer."""

    def __init__(self, cognitive: CognitiveLayer) -> None:
        self.cognitive = cognitive

    def explain(self, ctx: WhyContext) -> WhyExplanation:
        memory = self.cognitive.state.strategic_memory.get(ctx.ticker)
        regime = memory.regime_tag if memory else "unknown"
        strategy = memory.thesis if memory else "No stored thesis; response derived from request context."
        evidence = memory.evidence_quality if memory else 0.0
        source_count = memory.source_count if memory else 0

        failure_rate = self.cognitive.get_failure_rate(ctx.ticker)
        loss_adjusted = ctx.base_confidence - ctx.adjusted_confidence

        return WhyExplanation(
            market_structure=(
                f"regime={regime}; intent={ctx.intent}; horizon_days={ctx.target_horizon_days}"
            ),
            strategy_context=(
                f"thesis={strategy}; prior_sources={source_count}; "
                f"memory_present={memory is not None}"
            ),
            evidence_quality=(
                f"evidence_quality={evidence:.2f}; failure_rate={failure_rate:.2f}"
            ),
            risk_constraints=f"risk_budget={ctx.risk_budget:.4f}",
            confidence_calibration=(
                f"base={ctx.base_confidence:.2f} adjusted={ctx.adjusted_confidence:.2f} "
                f"loss_adjustment={loss_adjusted:.2f}"
            ),
        )
