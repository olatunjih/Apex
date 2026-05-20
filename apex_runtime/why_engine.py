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
        evidence = f"{memory.evidence_quality:.2f}" if memory else "unknown"

        return WhyExplanation(
            market_structure=f"regime={regime}; intent={ctx.intent}",
            strategy_context=strategy,
            evidence_quality=f"evidence_quality={evidence}",
            risk_constraints=f"risk_budget={ctx.risk_budget:.4f}",
            confidence_calibration=(
                f"base={ctx.base_confidence:.2f} adjusted={ctx.adjusted_confidence:.2f} "
                f"delta={(ctx.adjusted_confidence - ctx.base_confidence):.2f}"
            ),
        )
