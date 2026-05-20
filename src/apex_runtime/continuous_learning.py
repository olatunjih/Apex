"""
Continuous Learning Loop with Outcome Ingestion, Pattern Extraction, and Policy Updates.
"""
from __future__ import annotations
import time
import hashlib
import threading
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
from collections import defaultdict


class OutcomeType(Enum):
    """Types of outcomes that can be ingested."""
    TRADE_PROFIT = "trade_profit"
    TRADE_LOSS = "trade_loss"
    SIGNAL_ACCURACY = "signal_accuracy"
    GUARDRAIL_INTERVENTION = "guardrail_intervention"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"


class PatternStatus(Enum):
    """Lifecycle status of a learned pattern."""
    EMERGING = "emerging"  # < 5 occurrences
    CONFIRMED = "confirmed"  # >= 5 occurrences, statistically significant
    DECAYING = "decaying"  # Accuracy declining
    REFUTED = "refuted"  # Contradicted by new evidence
    ARCHIVED = "archived"  # No longer relevant


@dataclass(frozen=True)
class OutcomeRecord:
    """Record of a real-world outcome."""
    outcome_id: str
    trace_id: str  # Links back to original decision
    outcome_type: OutcomeType
    value: Decimal  # P&L, accuracy score, etc.
    timestamp: float
    context: Dict[str, Any]  # Market regime, strategy, ticker, etc.
    expected_value: Optional[Decimal] = None


@dataclass
class LearnedPattern:
    """A pattern extracted from outcomes."""
    pattern_id: str
    description: str
    pattern_type: str  # e.g., "false_breakout_low_volume"
    signature: Dict[str, Any]  # Conditions that define the pattern
    occurrence_count: int
    success_count: int
    failure_count: int
    accuracy: float
    status: PatternStatus
    first_seen: float
    last_seen: float
    applicable_strategies: Set[str]
    confidence_adjustment: Decimal  # How much to adjust confidence when pattern detected
    times_applied: int = 0
    times_prevented_failure: int = 0
    net_impact: Decimal = Decimal("0")
    is_decaying: bool = False
    decay_rate: float = 0.0


@dataclass
class PolicyUpdate:
    """A policy parameter update based on learning."""
    parameter_name: str
    old_value: Any
    new_value: Any
    reason: str
    confidence: float  # Confidence in this update
    timestamp: float = field(default_factory=time.time)
    requires_approval: bool = True  # High-impact changes need human approval


class OutcomeIngestor:
    """Ingests and processes real-world outcomes."""
    
    def __init__(self, max_history: int = 10000):
        self._outcomes: List[OutcomeRecord] = []
        self._max_history = max_history
        self._lock = threading.RLock()
        self._outcome_counts: Dict[OutcomeType, int] = defaultdict(int)
    
    def ingest(
        self,
        trace_id: str,
        outcome_type: OutcomeType,
        value: Decimal,
        context: Dict[str, Any],
        expected_value: Optional[Decimal] = None,
    ) -> OutcomeRecord:
        """Ingest a new outcome record."""
        outcome_id = hashlib.sha256(
            f"{trace_id}:{time.time()}".encode()
        ).hexdigest()[:16]
        
        record = OutcomeRecord(
            outcome_id=outcome_id,
            trace_id=trace_id,
            outcome_type=outcome_type,
            value=value,
            timestamp=time.time(),
            context=context,
            expected_value=expected_value,
        )
        
        with self._lock:
            self._outcomes.append(record)
            self._outcome_counts[outcome_type] += 1
            
            # Bounded history
            if len(self._outcomes) > self._max_history:
                self._outcomes = self._outcomes[-self._max_history:]
        
        return record
    
    def get_outcomes(
        self,
        outcome_type: Optional[OutcomeType] = None,
        limit: int = 100,
    ) -> List[OutcomeRecord]:
        """Get recent outcomes, optionally filtered by type."""
        with self._lock:
            if outcome_type:
                filtered = [o for o in self._outcomes if o.outcome_type == outcome_type]
                return list(reversed(filtered[-limit:]))
            return list(reversed(self._outcomes[-limit:]))
    
    def get_outcome_stats(self) -> Dict[str, int]:
        """Get counts by outcome type."""
        with self._lock:
            return dict(self._outcome_counts)


class PatternExtractor:
    """Extracts patterns from outcome history."""
    
    def __init__(self):
        self._patterns: Dict[str, LearnedPattern] = {}
        self._lock = threading.RLock()
        self._pattern_signatures: Dict[str, Dict[str, Any]] = {}
    
    def _generate_signature(self, context: Dict[str, Any]) -> str:
        """Generate a hashable signature from context."""
        # Simplified signature generation
        key_parts = []
        for k in sorted(context.keys()):
            if k in ["regime", "strategy_family", "ticker_sector", "volatility_regime"]:
                key_parts.append(f"{k}={context[k]}")
        return "|".join(key_parts)
    
    def extract_patterns(self, outcomes: List[OutcomeRecord]) -> List[LearnedPattern]:
        """Extract patterns from outcome history."""
        # Group outcomes by signature
        signature_outcomes: Dict[str, List[OutcomeRecord]] = defaultdict(list)
        
        for outcome in outcomes:
            sig = self._generate_signature(outcome.context)
            signature_outcomes[sig].append(outcome)
        
        new_patterns = []
        
        with self._lock:
            for sig, sig_outcomes in signature_outcomes.items():
                if len(sig_outcomes) < 3:  # Need minimum occurrences
                    continue
                
                # Calculate statistics
                losses = [o for o in sig_outcomes if o.outcome_type == OutcomeType.TRADE_LOSS]
                profits = [o for o in sig_outcomes if o.outcome_type == OutcomeType.TRADE_PROFIT]
                
                total = len(sig_outcomes)
                failure_count = len(losses)
                success_count = len(profits)
                accuracy = success_count / total if total > 0 else 0.0
                
                # Determine status
                if total < 5:
                    status = PatternStatus.EMERGING
                elif accuracy < 0.3:  # High failure rate
                    status = PatternStatus.DECAYING
                elif accuracy > 0.7 and total >= 10:
                    status = PatternStatus.CONFIRMED
                else:
                    status = PatternStatus.EMERGING
                
                # Create or update pattern
                pattern_id = f"pat_{hashlib.sha256(sig.encode()).hexdigest()[:8]}"
                
                if pattern_id in self._patterns:
                    # Update existing
                    pattern = self._patterns[pattern_id]
                    pattern.occurrence_count = total
                    pattern.success_count = success_count
                    pattern.failure_count = failure_count
                    pattern.accuracy = accuracy
                    pattern.status = status
                    pattern.last_seen = max(o.timestamp for o in sig_outcomes)
                    
                    # Check for decay
                    if pattern.is_decaying and accuracy < pattern.accuracy - 0.1:
                        pattern.decay_rate = (pattern.accuracy - accuracy) / max(1, total - pattern.occurrence_count)
                else:
                    # Create new pattern
                    pattern = LearnedPattern(
                        pattern_id=pattern_id,
                        description=f"Pattern in {sig}",
                        pattern_type="contextual",
                        signature={"raw": sig},
                        occurrence_count=total,
                        success_count=success_count,
                        failure_count=failure_count,
                        accuracy=accuracy,
                        status=status,
                        first_seen=min(o.timestamp for o in sig_outcomes),
                        last_seen=max(o.timestamp for o in sig_outcomes),
                        applicable_strategies=set(),
                        confidence_adjustment=Decimal(str(0.5 - accuracy)),  # Negative adjustment for low accuracy
                    )
                    self._patterns[pattern_id] = pattern
                    new_patterns.append(pattern)
        
        return new_patterns
    
    def get_patterns(
        self,
        status: Optional[PatternStatus] = None,
        min_accuracy: Optional[float] = None,
    ) -> List[LearnedPattern]:
        """Get patterns, optionally filtered."""
        with self._lock:
            patterns = list(self._patterns.values())
            
            if status:
                patterns = [p for p in patterns if p.status == status]
            if min_accuracy is not None:
                patterns = [p for p in patterns if p.accuracy >= min_accuracy]
            
            return patterns
    
    def find_matching_patterns(self, context: Dict[str, Any]) -> List[LearnedPattern]:
        """Find patterns that match the given context."""
        sig = self._generate_signature(context)
        
        with self._lock:
            matching = []
            for pattern in self._patterns.values():
                # Simple signature matching
                pattern_sig = pattern.signature.get("raw", "")
                if pattern_sig and all(part in sig for part in pattern_sig.split("|")):
                    matching.append(pattern)
            return matching


class PolicyUpdater:
    """Updates system policies based on learned patterns."""
    
    def __init__(self):
        self._current_policies: Dict[str, Any] = {
            "min_confidence_threshold": Decimal("0.65"),
            "max_position_size_pct": Decimal("0.05"),
            "max_portfolio_heat": Decimal("0.20"),
            "stop_loss_pct": Decimal("0.02"),
            "guardrail_sensitivity": 1.0,
        }
        self._update_history: List[PolicyUpdate] = []
        self._lock = threading.RLock()
        self._pending_updates: List[PolicyUpdate] = []
    
    def suggest_update(
        self,
        parameter_name: str,
        new_value: Any,
        reason: str,
        confidence: float,
        requires_approval: bool = True,
    ) -> PolicyUpdate:
        """Suggest a policy update based on learning."""
        with self._lock:
            old_value = self._current_policies.get(parameter_name)
            
            update = PolicyUpdate(
                parameter_name=parameter_name,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
                confidence=confidence,
                requires_approval=requires_approval,
            )
            
            if requires_approval:
                self._pending_updates.append(update)
            else:
                # Auto-apply low-risk updates
                self._apply_update(update)
            
            self._update_history.append(update)
            return update
    
    def _apply_update(self, update: PolicyUpdate) -> None:
        """Apply a policy update."""
        with self._lock:
            self._current_policies[update.parameter_name] = update.new_value
    
    def approve_update(self, update: PolicyUpdate) -> bool:
        """Approve and apply a pending update."""
        with self._lock:
            if update in self._pending_updates:
                self._pending_updates.remove(update)
                self._apply_update(update)
                return True
            return False
    
    def reject_update(self, update: PolicyUpdate) -> bool:
        """Reject a pending update."""
        with self._lock:
            if update in self._pending_updates:
                self._pending_updates.remove(update)
                return True
            return False
    
    def get_pending_updates(self) -> List[PolicyUpdate]:
        """Get updates awaiting approval."""
        with self._lock:
            return list(self._pending_updates)
    
    def get_current_policy(self, parameter_name: str) -> Any:
        """Get current value of a policy parameter."""
        with self._lock:
            return self._current_policies.get(parameter_name)
    
    def get_all_policies(self) -> Dict[str, Any]:
        """Get all current policy values."""
        with self._lock:
            return dict(self._current_policies)


class ContinuousLearningLoop:
    """
    Main continuous learning loop orchestrator.
    Ingests outcomes, extracts patterns, and updates policies.
    """
    
    def __init__(self):
        self.ingestor = OutcomeIngestor()
        self.pattern_extractor = PatternExtractor()
        self.policy_updater = PolicyUpdater()
        self._lock = threading.RLock()
        self._learning_iterations = 0
        self._last_learning_time: Optional[float] = None
    
    def ingest_outcome(
        self,
        trace_id: str,
        outcome_type: OutcomeType,
        value: Decimal,
        context: Dict[str, Any],
        expected_value: Optional[Decimal] = None,
    ) -> OutcomeRecord:
        """Ingest a new outcome."""
        return self.ingestor.ingest(
            trace_id=trace_id,
            outcome_type=outcome_type,
            value=value,
            context=context,
            expected_value=expected_value,
        )
    
    def run_learning_cycle(self) -> Tuple[List[LearnedPattern], List[PolicyUpdate]]:
        """Run a complete learning cycle."""
        with self._lock:
            self._learning_iterations += 1
            self._last_learning_time = time.time()
            
            # Get recent outcomes
            outcomes = self.ingestor.get_outcomes(limit=1000)
            
            # Extract patterns
            new_patterns = self.pattern_extractor.extract_patterns(outcomes)
            
            # Generate policy updates based on confirmed patterns
            updates = []
            confirmed_patterns = self.pattern_extractor.get_patterns(
                status=PatternStatus.CONFIRMED,
                min_accuracy=0.7,
            )
            
            for pattern in confirmed_patterns:
                if pattern.confidence_adjustment != Decimal("0"):
                    # Suggest adjusting confidence threshold for this pattern's context
                    update = self.policy_updater.suggest_update(
                        parameter_name="min_confidence_threshold",
                        new_value=self.policy_updater.get_current_policy("min_confidence_threshold") + pattern.confidence_adjustment * Decimal("0.1"),
                        reason=f"Pattern {pattern.pattern_id} shows {pattern.accuracy:.1%} accuracy in {pattern.description}",
                        confidence=pattern.accuracy,
                        requires_approval=True,
                    )
                    updates.append(update)
            
            # Check for loss streaks and suggest defensive adjustments
            recent_losses = self.ingestor.get_outcomes(
                outcome_type=OutcomeType.TRADE_LOSS,
                limit=10,
            )
            if len(recent_losses) >= 5:
                # Suggest reducing position size
                current_size = self.policy_updater.get_current_policy("max_position_size_pct")
                update = self.policy_updater.suggest_update(
                    parameter_name="max_position_size_pct",
                    new_value=current_size * Decimal("0.8"),  # Reduce by 20%
                    reason=f"Recent loss streak: {len(recent_losses)} consecutive losses",
                    confidence=0.8,
                    requires_approval=True,
                )
                updates.append(update)
            
            return new_patterns, updates
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of learning state."""
        with self._lock:
            outcome_stats = self.ingestor.get_outcome_stats()
            patterns = self.pattern_extractor.get_patterns()
            pending_updates = self.policy_updater.get_pending_updates()
            
            confirmed_count = len([p for p in patterns if p.status == PatternStatus.CONFIRMED])
            decaying_count = len([p for p in patterns if p.status == PatternStatus.DECAYING])
            
            return {
                "learning_iterations": self._learning_iterations,
                "last_learning_time": self._last_learning_time,
                "total_outcomes": sum(outcome_stats.values()),
                "outcome_breakdown": outcome_stats,
                "total_patterns": len(patterns),
                "confirmed_patterns": confirmed_count,
                "decaying_patterns": decaying_count,
                "pending_policy_updates": len(pending_updates),
            }
    
    def find_relevant_patterns(self, context: Dict[str, Any]) -> List[LearnedPattern]:
        """Find patterns relevant to the given context."""
        return self.pattern_extractor.find_matching_patterns(context)


# Global instance
DEFAULT_LEARNING_LOOP = ContinuousLearningLoop()
