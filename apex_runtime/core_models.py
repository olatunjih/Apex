"""
APEX Core Domain Models
Implements: Epistemic Assessment, Ticker Intelligence Files, Guardrails (G1-G11)
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Optional, Any
import json


class EpistemicState(Enum):
    """Section 16: Epistemic States"""
    CERTAIN = "certain"  # Verified data, mathematical truth
    PROBABLE = "probable"  # High confidence inference
    POSSIBLE = "possible"  # Plausible but unverified
    SPECULATIVE = "speculative"  # Low confidence hypothesis
    UNKNOWN = "unknown"  # No data available


class ConfidenceLevel(Enum):
    """Section 16: Confidence Levels"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class KnowledgeBoundary:
    """Section 16: Knowledge Boundary Evaluation"""
    domain: str
    state: EpistemicState
    confidence: ConfidenceLevel
    evidence_count: int
    last_verified: datetime
    source_quality_score: Decimal  # 0.0 to 1.0
    
    def is_reliable(self) -> bool:
        return (
            self.confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM] and
            self.source_quality_score >= Decimal("0.7")
        )


@dataclass
class ThesisChange:
    """Section 18: Thesis Change Record"""
    timestamp: datetime
    previous_thesis: str
    new_thesis: str
    reason: str
    epistemic_trigger: EpistemicState
    confidence_delta: float
    invalidation_source: Optional[str] = None  # e.g., "component_health_failure"


@dataclass
class TickerIntelligenceFile:
    """
    Section 17: Ticker Intelligence File
    Persistent per-ticker knowledge repository
    """
    ticker: str
    current_thesis: str = "No thesis established"
    thesis_confidence: ConfidenceLevel = ConfidenceLevel.NONE
    created_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    
    # Core Thesis
    thesis_history: List[ThesisChange] = field(default_factory=list)
    
    # Knowledge Boundaries
    knowledge_boundaries: Dict[str, KnowledgeBoundary] = field(default_factory=dict)
    
    # Historical Records
    price_history_summary: Dict[str, Any] = field(default_factory=dict)
    event_log: List[Dict[str, Any]] = field(default_factory=list)
    
    # Component Health (for invalidation tracking)
    component_health_scores: Dict[str, Decimal] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.last_updated is None:
            self.last_updated = self.created_at
    
    def add_thesis_change(self, new_thesis: str, reason: str, trigger: EpistemicState, 
                         old_confidence: ConfidenceLevel, new_confidence: ConfidenceLevel):
        """Record a thesis change with full narration context"""
        delta = self._confidence_to_float(new_confidence) - self._confidence_to_float(old_confidence)
        change = ThesisChange(
            timestamp=datetime.now(),
            previous_thesis=self.current_thesis,
            new_thesis=new_thesis,
            reason=reason,
            epistemic_trigger=trigger,
            confidence_delta=delta
        )
        self.thesis_history.append(change)
        self.current_thesis = new_thesis
        self.thesis_confidence = new_confidence
        self.last_updated = datetime.now()
        
    def _confidence_to_float(self, conf: ConfidenceLevel) -> float:
        mapping = {
            ConfidenceLevel.HIGH: 1.0,
            ConfidenceLevel.MEDIUM: 0.6,
            ConfidenceLevel.LOW: 0.3,
            ConfidenceLevel.NONE: 0.0
        }
        return mapping.get(conf, 0.0)

    def update_component_health(self, component_name: str, score: Decimal):
        """Update health score for a specific thesis component"""
        self.component_health_scores[component_name] = score
        self.last_updated = datetime.now()
        
    def get_average_component_health(self) -> Decimal:
        if not self.component_health_scores:
            return Decimal("1.0")
        total = sum(self.component_health_scores.values())
        return total / len(self.component_health_scores)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "current_thesis": self.current_thesis,
            "thesis_confidence": self.thesis_confidence.value,
            "thesis_changes_count": len(self.thesis_history),
            "last_updated": self.last_updated.isoformat(),
            "avg_component_health": float(self.get_average_component_health())
        }


class GuardrailResult:
    """Result of a guardrail check"""
    def __init__(self, passed: bool, message: str, severity: str = "info"):
        self.passed = passed
        self.message = message
        self.severity = severity  # info, warning, critical, block


class Guardrails:
    """
    Sections 6-15: APEX Guardrails G1-G11
    Enforces ethical, safety, and operational constraints
    """
    
    def __init__(self):
        self.violations_log: List[Dict[str, Any]] = []
        
    def check_all(self, context: Dict[str, Any]) -> List[GuardrailResult]:
        """Run all guardrails against current context"""
        results = []
        results.append(self.g1_no_harm(context))
        results.append(self.g2_privacy(context))
        results.append(self.g3_fairness(context))
        results.append(self.g4_transparency(context))
        results.append(self.g5_accountability(context))
        results.append(self.g6_security(context))
        results.append(self.g7_reliability(context))
        results.append(self.g8_safety(context))
        results.append(self.g9_ethical_alignment(context))
        results.append(self.g10_regulatory_compliance(context))
        results.append(self.g11_decimal_precision(context))
        
        # Log violations
        for r in results:
            if not r.passed:
                self.violations_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "guardrail": r.message.split(":")[0],
                    "severity": r.severity,
                    "details": r.message
                })
                
        return results

    def g1_no_harm(self, ctx: Dict) -> GuardrailResult:
        """G1: Do No Harm - Prevent harmful outputs"""
        # Placeholder for actual harm detection logic
        if ctx.get("intent") == "harmful":
            return GuardrailResult(False, "G1: Detected harmful intent", "block")
        return GuardrailResult(True, "G1: No harm detected")

    def g2_privacy(self, ctx: Dict) -> GuardrailResult:
        """G2: Privacy Protection"""
        sensitive_fields = ["ssn", "password", "credit_card", "private_key"]
        data = str(ctx.get("data", ""))
        if any(field in data.lower() for field in sensitive_fields):
            return GuardrailResult(False, "G2: Sensitive data detected", "critical")
        return GuardrailResult(True, "G2: Privacy check passed")

    def g3_fairness(self, ctx: Dict) -> GuardrailResult:
        """G3: Fairness and Bias Mitigation"""
        # Simplified check
        if ctx.get("bias_detected", False):
            return GuardrailResult(False, "G3: Bias detected in analysis", "warning")
        return GuardrailResult(True, "G3: Fairness check passed")

    def g4_transparency(self, ctx: Dict) -> GuardrailResult:
        """G4: Transparency and Explainability"""
        if not ctx.get("reasoning_provided", True):
            return GuardrailResult(False, "G4: Missing reasoning/explanation", "warning")
        return GuardrailResult(True, "G4: Transparency maintained")

    def g5_accountability(self, ctx: Dict) -> GuardrailResult:
        """G5: Accountability and Audit Trail"""
        if "audit_id" not in ctx:
            return GuardrailResult(False, "G5: Missing audit trail ID", "warning")
        return GuardrailResult(True, "G5: Accountability verified")

    def g6_security(self, ctx: Dict) -> GuardrailResult:
        """G6: Security and Integrity"""
        if ctx.get("security_risk", False):
            return GuardrailResult(False, "G6: Security risk detected", "block")
        return GuardrailResult(True, "G6: Security check passed")

    def g7_reliability(self, ctx: Dict) -> GuardrailResult:
        """G7: Reliability and Consistency"""
        if ctx.get("data_stale", False):
            return GuardrailResult(False, "G7: Data reliability compromised", "warning")
        return GuardrailResult(True, "G7: Reliability verified")

    def g8_safety(self, ctx: Dict) -> GuardrailResult:
        """G8: Operational Safety"""
        if ctx.get("unsafe_operation", False):
            return GuardrailResult(False, "G8: Unsafe operation requested", "block")
        return GuardrailResult(True, "G8: Safety check passed")

    def g9_ethical_alignment(self, ctx: Dict) -> GuardrailResult:
        """G9: Ethical Alignment"""
        if ctx.get("ethical_violation", False):
            return GuardrailResult(False, "G9: Ethical misalignment detected", "critical")
        return GuardrailResult(True, "G9: Ethically aligned")

    def g10_regulatory_compliance(self, ctx: Dict) -> GuardrailResult:
        """G10: Regulatory Compliance"""
        if ctx.get("regulatory_issue", False):
            return GuardrailResult(False, "G10: Potential regulatory violation", "critical")
        return GuardrailResult(True, "G10: Compliance verified")

    def g11_decimal_precision(self, ctx: Dict) -> GuardrailResult:
        """G11: Decimal Precision Enforcement"""
        # Check that financial values are Decimals
        values = ctx.get("financial_values", [])
        for v in values:
            if not isinstance(v, Decimal):
                return GuardrailResult(False, f"G11: Non-Decimal value detected: {type(v)}", "block")
        return GuardrailResult(True, "G11: Decimal precision enforced")


@dataclass
class AbstainModeState:
    """Section 14: Abstain Mode"""
    is_active: bool = False
    reason: str = ""
    triggered_at: Optional[datetime] = None
    guardrail_violations: List[str] = field(default_factory=list)
    
    def activate(self, reason: str, violations: List[str]):
        self.is_active = True
        self.reason = reason
        self.triggered_at = datetime.now()
        self.guardrail_violations = violations
        
    def deactivate(self):
        self.is_active = False
        self.reason = ""
        self.triggered_at = None
        self.guardrail_violations = []
