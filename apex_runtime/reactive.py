from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal

from .cognitive import CognitiveLayer
from .config import RuntimeConfig
from .errors import validation_error

IntentTier = Literal["portfolio", "ticker", "education"]


@dataclass(frozen=True)
class AnalysisRequest:
    ticker: str
    intent: str
    user_risk_budget: float
    base_confidence: float
    target_horizon_days: int


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
    def __init__(self, cognitive: CognitiveLayer, config: RuntimeConfig) -> None:
        self.cognitive = cognitive
        self.config = config
        self.router = IntentRouter()

    def analyze(self, request: AnalysisRequest) -> ReactiveDecision:
        self._validate_request(request)
        tier = self.router.route(request.intent)
        memory = self.cognitive.state.strategic_memory.get(request.ticker)
        calibrated = self.cognitive.get_bias_adjusted_confidence(request.ticker, request.base_confidence)

        horizon_penalty = (
            self.config.long_horizon_penalty
            if request.target_horizon_days > self.config.long_horizon_days_threshold
            else 0.0
        )
        adjusted = max(0.0, calibrated - horizon_penalty)

        blocked = adjusted < self.config.min_actionable_confidence or request.user_risk_budget < self.config.min_risk_budget
        action = self.config.blocked_action if blocked else self.config.actionable_research_action
        reason = "insufficient calibrated confidence" if blocked else "thesis supported by available evidence"

        regime = memory.regime_tag if memory else "unknown"
        why = WhyLayer(
            market_structure=f"regime={regime}",
            strategy_context=(memory.thesis if memory else "No prior thesis; using current request context."),
            evidence_quality=(f"{memory.evidence_quality:.2f}" if memory else "unknown"),
            risk_constraints=(
                f"risk_budget={request.user_risk_budget:.4f}; "
                f"min_risk_budget={self.config.min_risk_budget:.4f}; blocked={blocked}"
            ),
            confidence_calibration=(
                f"base={request.base_confidence:.2f} calibrated={calibrated:.2f} "
                f"horizon_penalty={horizon_penalty:.2f} final={adjusted:.2f} "
                f"threshold={self.config.min_actionable_confidence:.2f}"
            ),
        )
        return ReactiveDecision(tier=tier, action=action, confidence=adjusted, blocked=blocked, reason=reason, why=why)

    def position_confirmation(self, ticker: str, proposed_heat: float, max_heat: float) -> Dict[str, str | bool | float]:
        if not ticker:
            raise validation_error("TICKER_REQUIRED", "ticker is required")
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

    def _validate_request(self, request: AnalysisRequest) -> None:
        if not request.ticker:
            raise validation_error("TICKER_REQUIRED", "ticker is required")
        if request.user_risk_budget < 0:
            raise validation_error("RISK_BUDGET_INVALID", "user_risk_budget must be non-negative")
        if not 0 <= request.base_confidence <= 1:
            raise validation_error("CONFIDENCE_INVALID", "base_confidence must be in [0,1]")
        if request.target_horizon_days < 1:
            raise validation_error("TARGET_HORIZON_INVALID", "target_horizon_days must be >= 1")
