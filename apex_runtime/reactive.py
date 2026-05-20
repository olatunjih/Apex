from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal

from .cognitive import CognitiveLayer
from .errors import validation_error

IntentTier = Literal["portfolio", "ticker", "education"]


@dataclass(frozen=True)
class AnalysisRequest:
    ticker: str
    intent: str
    user_risk_budget: float
    base_confidence: float


@dataclass(frozen=True)
class WhyLayer:
    market_structure: str
    strategy_context: str
    evidence_quality: str
    risk_constraints: str
    confidence_calibration: str


@dataclass(frozen=True)
class ReactiveDecision:
    tier: IntentTier
    action: str
    confidence: float
    blocked: bool
    reason: str
    why: WhyLayer


class IntentRouter:
    def route(self, intent: str) -> IntentTier:
        normalized = intent.strip().lower()
        if "portfolio" in normalized or "position" in normalized:
            return "portfolio"
        if "learn" in normalized or "explain" in normalized:
            return "education"
        return "ticker"


class ReactiveLayer:
    """On-demand analysis layer that uses cognitive memory for calibrated decisions."""

    def __init__(self, cognitive: CognitiveLayer) -> None:
        self.cognitive = cognitive
        self.router = IntentRouter()

    def analyze(self, request: AnalysisRequest) -> ReactiveDecision:
        if not request.ticker:
            raise validation_error("TICKER_REQUIRED", "ticker is required")
        if request.user_risk_budget < 0:
            raise validation_error("RISK_BUDGET_INVALID", "user_risk_budget must be non-negative")

        tier = self.router.route(request.intent)
        memory = self.cognitive.state.strategic_memory.get(request.ticker)
        adjusted = self.cognitive.get_bias_adjusted_confidence(request.ticker, request.base_confidence)

        blocked = adjusted < 0.35 or request.user_risk_budget < 0.01
        action = "hold" if blocked else "research_long"
        reason = "insufficient calibrated confidence" if blocked else "thesis supported by available evidence"

        why = WhyLayer(
            market_structure="Regime context inferred from stored thesis metadata.",
            strategy_context=(memory.thesis if memory else "No prior thesis; using current request context."),
            evidence_quality=(f"{memory.evidence_quality:.2f}" if memory else "unknown"),
            risk_constraints=f"risk_budget={request.user_risk_budget:.4f}; blocked={blocked}",
            confidence_calibration=f"base={request.base_confidence:.2f} adjusted={adjusted:.2f}",
        )
        return ReactiveDecision(tier=tier, action=action, confidence=adjusted, blocked=blocked, reason=reason, why=why)

    def position_confirmation(self, ticker: str, proposed_heat: float, max_heat: float) -> Dict[str, str | bool | float]:
        if proposed_heat < 0 or max_heat <= 0:
            raise validation_error("HEAT_INVALID", "heat values must be positive and max_heat > 0")
        approved = proposed_heat <= max_heat
        return {
            "ticker": ticker,
            "approved": approved,
            "message": "within risk cap" if approved else "exceeds risk cap",
            "proposed_heat": proposed_heat,
            "max_heat": max_heat,
        }
