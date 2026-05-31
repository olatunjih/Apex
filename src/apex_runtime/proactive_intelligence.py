"""
APEX Proactive Intelligence Layer (PIL)
Implements: Section 19 - Learning Engine, Section 20 - Knowledge Application Engine
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .core_models import EpistemicState, ConfidenceLevel, TickerIntelligenceFile


class PatternType(Enum):
    """Types of patterns the PIL can recognize"""
    MARKET_REGIME = "market_regime"
    SEASONAL = "seasonal"
    CORRELATION = "correlation"
    ANOMALY = "anomaly"
    THESIS_INVALIDATION = "thesis_invalidation"
    SUCCESS_PATTERN = "success_pattern"
    FAILURE_PATTERN = "failure_pattern"


@dataclass
class LearnedPattern:
    """A pattern learned by the PIL"""
    pattern_id: str
    pattern_type: PatternType
    description: str
    confidence: Decimal
    first_observed: datetime
    last_observed: datetime
    occurrence_count: int
    success_rate: Decimal  # How often this pattern led to correct outcomes
    applicable_tickers: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update(self, success: bool):
        """Update pattern statistics based on new observation"""
        self.last_observed = datetime.now()
        self.occurrence_count += 1
        # Exponential moving average for success rate
        alpha = Decimal("0.1")
        outcome = Decimal("1") if success else Decimal("0")
        self.success_rate = (alpha * outcome) + ((Decimal("1") - alpha) * self.success_rate)


@dataclass
class KnowledgeApplication:
    """Record of applied knowledge"""
    timestamp: datetime
    ticker: str
    pattern_used: str
    decision_context: str
    outcome: Optional[str] = None  # "success", "failure", "pending"
    lesson_learned: Optional[str] = None


class LearningEngine:
    """
    Section 19: Learning Engine
    Continuously learns from market data, decisions, and outcomes
    """
    
    def __init__(self, persistence_enabled: bool = False):
        self.patterns: Dict[str, LearnedPattern] = {}
        self.learning_events: List[Dict[str, Any]] = []
        self.pattern_counter = 0
        self.persistence_enabled = persistence_enabled
        
    def register_pattern(self, pattern_type: PatternType, description: str,
                        initial_confidence: Decimal, tickers: List[str],
                        metadata: Dict[str, Any] = None) -> str:
        """Register a newly discovered pattern"""
        self.pattern_counter += 1
        pattern_id = f"PAT-{self.pattern_counter:06d}"
        
        pattern = LearnedPattern(
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            description=description,
            confidence=initial_confidence,
            first_observed=datetime.now(),
            last_observed=datetime.now(),
            occurrence_count=1,
            success_rate=Decimal("0.5"),  # Neutral starting point
            applicable_tickers=tickers,
            metadata=metadata or {}
        )
        
        self.patterns[pattern_id] = pattern
        self._log_learning_event("pattern_registered", pattern_id, description)
        return pattern_id
    
    def observe_outcome(self, pattern_id: str, success: bool, context: Dict[str, Any]):
        """Observe an outcome and update pattern learning"""
        if pattern_id not in self.patterns:
            return
            
        pattern = self.patterns[pattern_id]
        pattern.update(success)
        
        # Decay confidence if pattern becomes unreliable
        if pattern.success_rate < Decimal("0.3"):
            pattern.confidence *= Decimal("0.9")
            
        self._log_learning_event("outcome_observed", pattern_id, {
            "success": success,
            "updated_success_rate": float(pattern.success_rate),
            "context": context
        })
    
    def find_relevant_patterns(self, ticker: str, context: Dict[str, Any],
                              min_confidence: Decimal = Decimal("0.6")) -> List[LearnedPattern]:
        """Find patterns relevant to current context"""
        relevant = []
        for pattern in self.patterns.values():
            if pattern.confidence < min_confidence:
                continue
            if ticker in pattern.applicable_tickers or "*" in pattern.applicable_tickers:
                if self._pattern_matches_context(pattern, context):
                    relevant.append(pattern)
        
        # Sort by confidence and success rate
        relevant.sort(key=lambda p: float(p.confidence * p.success_rate), reverse=True)
        return relevant
    
    def _pattern_matches_context(self, pattern: LearnedPattern, context: Dict) -> bool:
        """Check if pattern matches current context"""
        # Simplified matching - would be more sophisticated in production
        pattern_meta = pattern.metadata
        for key, value in pattern_meta.items():
            if key in context and context[key] != value:
                return False
        return True
    
    def _log_learning_event(self, event_type: str, pattern_id: str, details: Any):
        self.learning_events.append({
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "pattern_id": pattern_id,
            "details": details
        })


class KnowledgeApplicationEngine:
    """
    Section 20: Knowledge Application Engine
    Applies learned patterns to current decision-making
    """
    
    def __init__(self, learning_engine: LearningEngine):
        self.learning_engine = learning_engine
        self.applications: List[KnowledgeApplication] = []
        
    def apply_knowledge(self, ticker: str, tif: TickerIntelligenceFile,
                       context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply learned knowledge to current situation
        Returns recommendations and confidence adjustments
        """
        patterns = self.learning_engine.find_relevant_patterns(ticker, context)
        
        if not patterns:
            return {
                "recommendations": [],
                "confidence_adjustment": Decimal("0"),
                "patterns_applied": 0
            }
        
        recommendations = []
        total_weight = Decimal("0")
        weighted_adjustment = Decimal("0")
        
        for pattern in patterns[:5]:  # Top 5 patterns
            weight = pattern.confidence * pattern.success_rate
            total_weight += weight
            
            # Calculate confidence adjustment based on pattern
            if pattern.success_rate > Decimal("0.7"):
                adjustment = weight * Decimal("0.1")  # Boost confidence
            elif pattern.success_rate < Decimal("0.3"):
                adjustment = -weight * Decimal("0.1")  # Reduce confidence
            else:
                adjustment = Decimal("0")
                
            weighted_adjustment += adjustment
            
            recommendations.append({
                "pattern_id": pattern.pattern_id,
                "description": pattern.description,
                "confidence": float(pattern.confidence),
                "success_rate": float(pattern.success_rate),
                "recommendation": self._generate_recommendation(pattern, context)
            })
        
        final_adjustment = weighted_adjustment / total_weight if total_weight > 0 else Decimal("0")
        
        # Record application
        application = KnowledgeApplication(
            timestamp=datetime.now(),
            ticker=ticker,
            pattern_used=", ".join([p.pattern_id for p in patterns[:3]]),
            decision_context=str(context.get("decision_context", "unknown"))
        )
        self.applications.append(application)
        
        return {
            "recommendations": recommendations,
            "confidence_adjustment": final_adjustment,
            "patterns_applied": len(patterns)
        }
    
    def _generate_recommendation(self, pattern: LearnedPattern, context: Dict) -> str:
        """Generate specific recommendation based on pattern"""
        if pattern.pattern_type == PatternType.THESIS_INVALIDATION:
            return "Consider thesis invalidation based on historical pattern"
        elif pattern.pattern_type == PatternType.SUCCESS_PATTERN:
            return "Historical success suggests maintaining current approach"
        elif pattern.pattern_type == PatternType.FAILURE_PATTERN:
            return "Historical failure suggests reconsidering approach"
        elif pattern.pattern_type == PatternType.ANOMALY:
            return "Anomaly detected - increase scrutiny"
        else:
            return f"Apply pattern: {pattern.description}"
    
    def record_outcome(self, application_index: int, success: bool, lesson: str = None):
        """Record outcome of applied knowledge"""
        if application_index >= len(self.applications):
            return
            
        app = self.applications[application_index]
        app.outcome = "success" if success else "failure"
        app.lesson_learned = lesson
        
        # Feed back to learning engine
        if app.pattern_used:
            for pattern_id in app.pattern_used.split(", "):
                self.learning_engine.observe_outcome(
                    pattern_id.strip(), 
                    success,
                    {"lesson": lesson}
                )
