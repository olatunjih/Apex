"""
APEX Second-Order Analysis & Narrative Consistency
Implements: Section 24 - Second-Order Effects, Section 25 - Narrative Agent
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

try:
    from .core_models import EpistemicState, ConfidenceLevel, TickerIntelligenceFile
except ImportError:
    from core_models import EpistemicState, ConfidenceLevel, TickerIntelligenceFile


class EffectType(Enum):
    """Types of second-order effects"""
    DIRECT = "direct"
    INDIRECT = "indirect"
    SYSTEMIC = "systemic"
    FEEDBACK_LOOP = "feedback_loop"
    UNINTENDED_CONSEQUENCE = "unintended_consequence"


@dataclass
class SecondOrderEffect:
    """Represents a second-order effect from a decision or event"""
    effect_id: str
    source_event: str
    effect_description: str
    effect_type: EffectType
    probability: Decimal
    impact_severity: Decimal  # 0.0 to 1.0
    time_horizon_days: int
    affected_tickers: List[str]
    chain_depth: int  # How many steps removed from original cause
    identified_at: datetime
    mitigation_strategies: List[str] = field(default_factory=list)
    
    def risk_score(self) -> Decimal:
        """Calculate overall risk score"""
        return self.probability * self.impact_severity * Decimal(str(max(1, self.chain_depth)))


@dataclass
class CausalChain:
    """A chain of causal relationships"""
    root_cause: str
    effects: List[SecondOrderEffect]
    total_chain_length: int
    max_impact: Decimal
    identified_tickers: Set[str]


@dataclass
class NarrativeInconsistency:
    """Detected inconsistency in analytical narrative"""
    inconsistency_id: str
    severity: str  # minor, moderate, severe, critical
    description: str
    conflicting_statements: List[str]
    epistemic_violation: Optional[EpistemicState]
    detected_at: datetime
    resolution_required: bool = True
    resolved: bool = False
    resolution_notes: Optional[str] = None


class SecondOrderAnalysis:
    """
    Section 24: Second-Order Effects Analysis
    Identifies and evaluates indirect consequences of decisions/events
    """
    
    def __init__(self):
        self.effects_registry: Dict[str, SecondOrderEffect] = {}
        self.causal_chains: List[CausalChain] = []
        self.effect_counter = 0
        
    def analyze_decision(self, decision: str, context: Dict[str, Any],
                        ticker_intelligence: Dict[str, TickerIntelligenceFile]) -> List[SecondOrderEffect]:
        """
        Analyze potential second-order effects of a decision
        """
        effects = []
        
        # Direct effects (first-order)
        direct_effects = self._identify_direct_effects(decision, context)
        
        # Indirect effects (second-order and beyond)
        for direct in direct_effects:
            indirect = self._cascade_effects(direct, context, ticker_intelligence)
            effects.extend(indirect)
        
        # Systemic effects
        systemic = self._identify_systemic_effects(decision, context, ticker_intelligence)
        effects.extend(systemic)
        
        # Register effects
        for effect in effects:
            self.effects_registry[effect.effect_id] = effect
            
        # Build causal chains
        if effects:
            chain = self._build_causal_chain(decision, effects)
            self.causal_chains.append(chain)
            
        return effects
    
    def _identify_direct_effects(self, decision: str, context: Dict) -> List[SecondOrderEffect]:
        """Identify immediate first-order effects"""
        # Simplified heuristic-based identification
        effects = []
        
        # Example patterns (would be more sophisticated in production)
        if "price cut" in decision.lower():
            effects.append(self._create_effect(
                decision, "Competitor price response expected", 
                EffectType.DIRECT, Decimal("0.8"), Decimal("0.6"), 7,
                context.get("affected_tickers", [])
            ))
            
        if "expansion" in decision.lower():
            effects.append(self._create_effect(
                decision, "Resource allocation strain possible",
                EffectType.DIRECT, Decimal("0.5"), Decimal("0.4"), 30,
                context.get("affected_tickers", [])
            ))
            
        return effects
    
    def _cascade_effects(self, initial_effect: SecondOrderEffect, 
                        context: Dict, tif_dict: Dict[str, TickerIntelligenceFile]) -> List[SecondOrderEffect]:
        """Cascade effects to identify second and third-order consequences"""
        cascaded = []
        
        # Second-order: effects of the first effect
        if initial_effect.impact_severity > Decimal("0.5"):
            second_order = self._create_effect(
                initial_effect.effect_description,
                f"Market perception shift due to {initial_effect.effect_description}",
                EffectType.INDIRECT,
                initial_effect.probability * Decimal("0.7"),
                initial_effect.impact_severity * Decimal("0.8"),
                initial_effect.time_horizon_days * 2,
                initial_effect.affected_tickers,
                chain_depth=2
            )
            cascaded.append(second_order)
            
            # Third-order (limited depth)
            if second_order.impact_severity > Decimal("0.3"):
                third_order = self._create_effect(
                    second_order.effect_description,
                    f"Competitive landscape adjustment",
                    EffectType.INDIRECT,
                    second_order.probability * Decimal("0.6"),
                    second_order.impact_severity * Decimal("0.7"),
                    second_order.time_horizon_days * 2,
                    initial_effect.affected_tickers,
                    chain_depth=3
                )
                cascaded.append(third_order)
                
        return cascaded
    
    def _identify_systemic_effects(self, decision: str, context: Dict,
                                   tif_dict: Dict[str, TickerIntelligenceFile]) -> List[SecondOrderEffect]:
        """Identify system-wide effects"""
        effects = []
        
        # Check for feedback loops
        if "leverage" in decision.lower() or "debt" in decision.lower():
            effects.append(self._create_effect(
                decision,
                "Potential feedback loop: financial stress -> credit downgrade -> higher costs",
                EffectType.FEEDBACK_LOOP,
                Decimal("0.4"),
                Decimal("0.8"),
                90,
                list(tif_dict.keys()),
                chain_depth=4
            ))
            
        # Unintended consequences
        if "layoff" in decision.lower() or "cutback" in decision.lower():
            effects.append(self._create_effect(
                decision,
                "Unintended: Innovation capacity reduction",
                EffectType.UNINTENDED_CONSEQUENCE,
                Decimal("0.6"),
                Decimal("0.5"),
                180,
                list(tif_dict.keys()),
                chain_depth=3
            ))
            
        return effects
    
    def _create_effect(self, source: str, description: str, effect_type: EffectType,
                      probability: Decimal, severity: Decimal, horizon: int,
                      tickers: List[str], chain_depth: int = 1) -> SecondOrderEffect:
        self.effect_counter += 1
        return SecondOrderEffect(
            effect_id=f"SOE-{self.effect_counter:06d}",
            source_event=source,
            effect_description=description,
            effect_type=effect_type,
            probability=probability,
            impact_severity=severity,
            time_horizon_days=horizon,
            affected_tickers=tickers,
            chain_depth=chain_depth,
            identified_at=datetime.now()
        )
    
    def _build_causal_chain(self, root: str, effects: List[SecondOrderEffect]) -> CausalChain:
        max_depth = max(e.chain_depth for e in effects) if effects else 0
        max_impact = max(e.impact_severity for e in effects) if effects else Decimal("0")
        all_tickers = set()
        for e in effects:
            all_tickers.update(e.affected_tickers)
            
        return CausalChain(
            root_cause=root,
            effects=effects,
            total_chain_length=max_depth,
            max_impact=max_impact,
            identified_tickers=all_tickers
        )
    
    def get_high_risk_effects(self, threshold: Decimal = Decimal("0.5")) -> List[SecondOrderEffect]:
        """Get effects exceeding risk threshold"""
        high_risk = []
        for effect in self.effects_registry.values():
            if effect.risk_score() > threshold:
                high_risk.append(effect)
        return sorted(high_risk, key=lambda e: float(e.risk_score()), reverse=True)


class NarrativeAgent:
    """
    Section 25: Narrative Consistency Agent
    Ensures analytical narratives remain consistent across sessions and components
    """
    
    def __init__(self):
        self.narrative_log: List[Dict[str, Any]] = []
        self.inconsistencies: List[NarrativeInconsistency] = []
        self.inconsistency_counter = 0
        self.narrative_state: Dict[str, str] = {}  # topic -> current narrative
        
    def record_narrative(self, topic: str, narrative: str, epistemic_state: EpistemicState,
                        confidence: ConfidenceLevel, source: str):
        """Record a narrative statement with metadata"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "topic": topic,
            "narrative": narrative,
            "epistemic_state": epistemic_state.value,
            "confidence": confidence.value,
            "source": source
        }
        self.narrative_log.append(entry)
        
        # Update current narrative state
        self.narrative_state[topic] = narrative
        
        # Check for inconsistencies
        self._check_consistency(topic, narrative, epistemic_state)
    
    def _check_consistency(self, topic: str, new_narrative: str, 
                          new_epistemic: EpistemicState):
        """Check new narrative against existing narratives for consistency"""
        # Find previous narratives on same topic
        previous = [
            entry for entry in self.narrative_log[:-1]
            if entry["topic"] == topic
        ]
        
        if not previous:
            return
            
        # Check for contradictions
        last_entry = previous[-1]
        
        # Epistemic violation check
        if self._is_epistemic_violation(last_entry["epistemic_state"], new_epistemic):
            self._flag_inconsistency(
                severity="severe",
                description=f"Epistemic state regression on {topic}",
                conflicting=[last_entry["narrative"], new_narrative],
                epistemic_violation=new_epistemic
            )
            
        # Direct contradiction check (simplified)
        if self._are_contradictory(last_entry["narrative"], new_narrative):
            self._flag_inconsistency(
                severity="critical",
                description=f"Direct contradiction on {topic}",
                conflicting=[last_entry["narrative"], new_narrative],
                epistemic_violation=None
            )
    
    def _is_epistemic_violation(self, old_state: str, new_state: EpistemicState) -> bool:
        """Detect problematic epistemic state transitions"""
        # Violation: claiming certainty after being speculative without evidence
        state_hierarchy = {
            "unknown": 0,
            "speculative": 1,
            "possible": 2,
            "probable": 3,
            "certain": 4
        }
        
        old_level = state_hierarchy.get(old_state, 0)
        new_level = state_hierarchy.get(new_state.value, 0)
        
        # Jumping multiple levels without intermediate justification is suspicious
        return new_level - old_level >= 3
    
    def _are_contradictory(self, narrative1: str, narrative2: str) -> bool:
        """Check if two narratives are contradictory"""
        # Simplified contradiction detection
        contradiction_pairs = [
            ("bullish", "bearish"),
            ("positive", "negative"),
            ("growth", "decline"),
            ("strong", "weak"),
            ("outperform", "underperform")
        ]
        
        n1_lower = narrative1.lower()
        n2_lower = narrative2.lower()
        
        for pair in contradiction_pairs:
            if pair[0] in n1_lower and pair[1] in n2_lower:
                return True
            if pair[1] in n1_lower and pair[0] in n2_lower:
                return True
                
        return False
    
    def _flag_inconsistency(self, severity: str, description: str,
                           conflicting: List[str], epistemic_violation: Optional[EpistemicState]):
        self.inconsistency_counter += 1
        inconsistency = NarrativeInconsistency(
            inconsistency_id=f"INC-{self.inconsistency_counter:06d}",
            severity=severity,
            description=description,
            conflicting_statements=conflicting,
            epistemic_violation=epistemic_violation,
            detected_at=datetime.now()
        )
        self.inconsistencies.append(inconsistency)
        
    def resolve_inconsistency(self, inconsistency_id: str, resolution: str):
        """Mark an inconsistency as resolved"""
        for inc in self.inconsistencies:
            if inc.inconsistency_id == inconsistency_id:
                inc.resolved = True
                inc.resolution_notes = resolution
                inc.resolution_required = False
                break
    
    def get_unresolved_inconsistencies(self) -> List[NarrativeInconsistency]:
        """Get all unresolved inconsistencies"""
        return [inc for inc in self.inconsistencies if not inc.resolved]
    
    def get_narrative_history(self, topic: str) -> List[Dict[str, Any]]:
        """Get narrative history for a specific topic"""
        return [entry for entry in self.narrative_log if entry["topic"] == topic]
