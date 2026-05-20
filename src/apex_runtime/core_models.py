"""
APEX Core Domain Models
Implements: Epistemic Assessment, Ticker Intelligence Files, Guardrails (G1-G11)
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Optional, Any, Set
import json
import re


# =============================================================================
# Epistemic States & Confidence Levels (Section 16)
# =============================================================================

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


# =============================================================================
# G1: NO HARM - Blocklist and Pattern Matching
# =============================================================================

HARM_PHRASES: Set[str] = {
    # Self-harm
    "kill yourself", "kill myself", "suicide", "self-harm", "cut yourself",
    "end your life", "take your own life", "jump off", "overdose",
    # Violence
    "kill them", "kill him", "kill her", "murder", "assault", "beat them",
    "hurt someone", "violence", "terrorist", "bomb", "shooting",
    # Illegal activities
    "how to launder", "money laundering", "tax evasion", "insider trading",
    "fraud", "scam", "phishing", "hack into", "breach security",
    "illegal drugs", "cocaine", "heroin", "meth", "buy weapons",
    # Financial harm
    "guaranteed profit", "risk-free", "ponzi", "pyramid scheme",
    "pump and dump", "market manipulation", "front-running",
}

HARM_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(kill|murder|assault|attack)\s+(yourself|myself|them|him|her)\b", re.I),
    re.compile(r"\b(suicide|self[- ]?harm|overdose)\b", re.I),
    re.compile(r"\b(money\s+laundering|tax\s+evasion|insider\s+trading)\b", re.I),
    re.compile(r"\b(how\s+to\s+(hack|fraud|scam|steal))\b", re.I),
    re.compile(r"\b(guaranteed\s+profit|no\s+risk|free\s+money)\b", re.I),
]


# =============================================================================
# G6: POSITION LIMITS - Static ceilings from config
# =============================================================================

DEFAULT_POSITION_LIMITS: Dict[str, int] = {
    "*": 10000,  # Default limit for any symbol
    "AAPL": 50000,
    "MSFT": 50000,
    "GOOGL": 30000,
    "AMZN": 30000,
    "TSLA": 20000,
    "SPY": 100000,
    "QQQ": 100000,
}

# G9: Price reasonability bounds
DEFAULT_PRICE_BOUNDS: Dict[str, tuple] = {
    "*": (Decimal("0.01"), Decimal("1000000")),  # Min, Max price
}

# G10: Truthfulness - required confidence threshold
TRUTHFULNESS_MIN_CONFIDENCE: float = 0.9


class GuardrailViolationError(Exception):
    """Raised when a guardrail check fails, aborting the action."""
    def __init__(self, guardrail_name: str, message: str, severity: str = "block"):
        self.guardrail_name = guardrail_name
        self.message = message
        self.severity = severity
        super().__init__(f"[{guardrail_name}] {message}")


class GuardrailResult:
    """Result of a guardrail check"""
    def __init__(self, passed: bool, message: str, severity: str = "info"):
        self.passed = passed
        self.message = message
        self.severity = severity  # info, warning, critical, block


class Guardrails:
    """
    Sections 6-15: APEX Guardrails G1-G11
    Enforces ethical, safety, and operational constraints with deterministic checks.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self.blocked_phrases: Set[str] = config.get("harm_phrases", HARM_PHRASES)
        self.position_limits: Dict[str, int] = config.get("position_limits", DEFAULT_POSITION_LIMITS)
        self.price_bounds: Dict[str, tuple] = config.get("price_bounds", DEFAULT_PRICE_BOUNDS)
        self.truthfulness_min_confidence: float = config.get("truthfulness_min_confidence", TRUTHFULNESS_MIN_CONFIDENCE)
        self.violations_log: List[Dict[str, Any]] = []
        
    def enforce_all(self, text: str, context: Dict[str, Any]) -> bool:
        """
        Run all guardrails against text output and context.
        Raises GuardrailViolationError on first failure.
        Returns True if all pass.
        """
        results = self.check_all({**context, "output_text": text})
        
        for r in results:
            if not r.passed and r.severity in ("block", "critical"):
                raise GuardrailViolationError(
                    guardrail_name=r.message.split(":")[0],
                    message=r.message,
                    severity=r.severity
                )
        return True
    
    def check_all(self, context: Dict[str, Any]) -> List[GuardrailResult]:
        """Run all guardrails against current context"""
        results = []
        results.append(self.g1_no_harm(context))
        results.append(self.g2_no_illegal_advice(context))
        results.append(self.g3_fairness(context))
        results.append(self.g4_transparency(context))
        results.append(self.g5_accountability(context))
        results.append(self.g6_position_limit(context))
        results.append(self.g7_reliability(context))
        results.append(self.g8_operational_safety(context))
        results.append(self.g9_price_reasonability(context))
        results.append(self.g10_truthfulness(context))
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
        """G1: Do No Harm - Prevent harmful outputs using blocklist + regex"""
        text = ctx.get("output_text", "") or ctx.get("text", "") or ""
        lower = text.lower()
        
        # Check blocklist
        if any(phrase in lower for phrase in self.blocked_phrases):
            return GuardrailResult(False, "G1: Harmful content detected (blocklist match)", "block")
        
        # Check regex patterns
        for pattern in HARM_PATTERNS:
            if pattern.search(text):
                return GuardrailResult(False, "G1: Harmful pattern detected", "block")
        
        # Check explicit harmful intent flag
        if ctx.get("intent") == "harmful":
            return GuardrailResult(False, "G1: Detected harmful intent", "block")
            
        return GuardrailResult(True, "G1: No harm detected")

    def g2_no_illegal_advice(self, ctx: Dict) -> GuardrailResult:
        """G2: No Illegal Advice - Block illegal financial/legal advice patterns"""
        text = ctx.get("output_text", "") or ctx.get("text", "") or ""
        lower = text.lower()
        
        banned_patterns = [
            "how to launder", "tax evasion", "insider trading",
            "avoid taxes illegally", "hide income", "offshore tax haven",
            "market manipulation", "pump and dump", "front running",
            "wash trading", "spoofing orders", "layering trades",
        ]
        
        if any(pattern in lower for pattern in banned_patterns):
            return GuardrailResult(False, "G2: Illegal advice pattern detected", "block")
        
        # Also check context flags
        if ctx.get("illegal_advice_detected", False):
            return GuardrailResult(False, "G2: Illegal advice flagged", "block")
            
        return GuardrailResult(True, "G2: No illegal advice detected")

    def g3_fairness(self, ctx: Dict) -> GuardrailResult:
        """G3: Fairness and Bias Mitigation"""
        # Check for bias indicators in context
        if ctx.get("bias_detected", False):
            return GuardrailResult(False, "G3: Bias detected in analysis", "warning")
        
        # Check for discriminatory language
        text = ctx.get("output_text", "") or ""
        biased_terms = ["inferior", "superior race", "discriminate based on"]
        if any(term in text.lower() for term in biased_terms):
            return GuardrailResult(False, "G3: Potentially biased language detected", "warning")
            
        return GuardrailResult(True, "G3: Fairness check passed")

    def g4_transparency(self, ctx: Dict) -> GuardrailResult:
        """G4: Transparency and Explainability"""
        # Require reasoning provided for decisions
        if not ctx.get("reasoning_provided", True):
            return GuardrailResult(False, "G4: Missing reasoning/explanation", "warning")
        
        # Check if decision has explanation
        if "decision" in ctx and "explanation" not in ctx:
            return GuardrailResult(False, "G4: Decision lacks explanation", "warning")
            
        return GuardrailResult(True, "G4: Transparency maintained")

    def g5_accountability(self, ctx: Dict) -> GuardrailResult:
        """G5: Accountability and Audit Trail"""
        if "audit_id" not in ctx and "trace_id" not in ctx:
            return GuardrailResult(False, "G5: Missing audit trail ID", "warning")
        return GuardrailResult(True, "G5: Accountability verified")

    def g6_position_limit(self, ctx: Dict) -> GuardrailResult:
        """G6: Position Limits - Check proposed position against limits"""
        symbol = ctx.get("symbol", "*")
        proposed_qty = ctx.get("proposed_quantity", 0)
        proposed_size = ctx.get("proposed_size", 0)
        
        # Get limit for symbol (or default)
        limit = self.position_limits.get(symbol, self.position_limits.get("*", 10000))
        
        if proposed_qty > limit:
            return GuardrailResult(
                False, 
                f"G6: Position {proposed_qty} exceeds limit {limit} for {symbol}", 
                "block"
            )
        
        # Also check size-based limits if provided
        max_size = ctx.get("max_position_size", limit * 1000)  # Rough estimate
        if proposed_size > max_size:
            return GuardrailResult(
                False,
                f"G6: Position size ${proposed_size} exceeds maximum ${max_size}",
                "block"
            )
            
        return GuardrailResult(True, "G6: Position within limits")

    def g7_reliability(self, ctx: Dict) -> GuardrailResult:
        """G7: Reliability and Consistency"""
        if ctx.get("data_stale", False):
            return GuardrailResult(False, "G7: Data reliability compromised", "warning")
        
        # Check data age
        data_timestamp = ctx.get("data_timestamp")
        if data_timestamp:
            age = datetime.now() - data_timestamp if isinstance(data_timestamp, datetime) else None
            if age and age.total_seconds() > 3600:  # 1 hour stale
                return GuardrailResult(False, "G7: Data is stale (>1 hour old)", "warning")
        
        return GuardrailResult(True, "G7: Reliability verified")

    def g8_operational_safety(self, ctx: Dict) -> GuardrailResult:
        """G8: Operational Safety"""
        if ctx.get("unsafe_operation", False):
            return GuardrailResult(False, "G8: Unsafe operation requested", "block")
        
        # Check for dangerous operation patterns
        action = ctx.get("action", "")
        unsafe_actions = ["delete_all_positions", "liquidate_everything", "disable_safeguards"]
        if action in unsafe_actions:
            return GuardrailResult(False, f"G8: Unsafe action '{action}' blocked", "block")
        
        return GuardrailResult(True, "G8: Safety check passed")

    def g9_price_reasonability(self, ctx: Dict) -> GuardrailResult:
        """G9: Price Reasonability - Validate prices are within reasonable bounds"""
        symbol = ctx.get("symbol", "*")
        price = ctx.get("price", ctx.get("proposed_price"))
        
        if price is None:
            return GuardrailResult(True, "G9: No price to validate")
        
        # Convert to Decimal if needed
        if not isinstance(price, Decimal):
            price = Decimal(str(price))
        
        # Get bounds for symbol
        min_price, max_price = self.price_bounds.get(symbol, self.price_bounds.get("*", (Decimal("0.01"), Decimal("1000000"))))
        
        if price < min_price or price > max_price:
            return GuardrailResult(
                False,
                f"G9: Price {price} outside reasonable range [{min_price}, {max_price}]",
                "warning"
            )
        
        # Check for extreme price changes
        prev_price = ctx.get("previous_price")
        if prev_price:
            if not isinstance(prev_price, Decimal):
                prev_price = Decimal(str(prev_price))
            if prev_price > 0:
                change_pct = abs(price - prev_price) / prev_price
                if change_pct > Decimal("0.5"):  # >50% change
                    return GuardrailResult(
                        False,
                        f"G9: Extreme price change {change_pct*100:.1f}%",
                        "warning"
                    )
        
        return GuardrailResult(True, "G9: Price is reasonable")

    def g10_truthfulness(self, ctx: Dict) -> GuardrailResult:
        """G10: Truthfulness - Require source citation or high confidence for factual claims"""
        text = ctx.get("output_text", "") or ""
        confidence = ctx.get("confidence", 1.0)
        sources = ctx.get("sources", [])
        
        # Detect factual claim patterns
        factual_patterns = [
            r"\b(according to|studies show|research indicates|data suggests)\b",
            r"\b(is|are|was|were)\s+\w+\s+(fact|true|certain|known)\b",
            r"\b(evidence proves|it is clear that)\b",
        ]
        
        has_factual_claim = any(re.search(p, text, re.I) for p in factual_patterns)
        
        if has_factual_claim:
            # Require either high confidence or source citation
            if confidence < self.truthfulness_min_confidence and not sources:
                return GuardrailResult(
                    False,
                    f"G10: Factual claim without source or sufficient confidence ({confidence})",
                    "warning"
                )
        
        # Check confidence threshold
        if confidence < self.truthfulness_min_confidence and ctx.get("requires_verification", False):
            return GuardrailResult(
                False,
                f"G10: Low confidence ({confidence}) requires verification",
                "warning"
            )
        
        return GuardrailResult(True, "G10: Truthfulness check passed")

    def g11_decimal_precision(self, ctx: Dict) -> GuardrailResult:
        """G11: Decimal Precision Enforcement - Financial values must be Decimals"""
        values = ctx.get("financial_values", [])
        
        for v in values:
            if not isinstance(v, Decimal):
                return GuardrailResult(
                    False, 
                    f"G11: Non-Decimal value detected: {type(v).__name__}", 
                    "block"
                )
        
        # Also check specific financial fields
        financial_fields = ["price", "quantity", "size", "amount", "value", "cost"]
        for field_name in financial_fields:
            if field_name in ctx:
                val = ctx[field_name]
                if val is not None and not isinstance(val, Decimal):
                    return GuardrailResult(
                        False,
                        f"G11: Field '{field_name}' must be Decimal, got {type(val).__name__}",
                        "block"
                    )
        
        return GuardrailResult(True, "G11: Decimal precision enforced")
