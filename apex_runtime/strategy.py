"""
APEX Strategy Layer - Section 3
Strategy registry, selector, aggregator, and plugin system
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Protocol, Set
from threading import RLock
import uuid

try:
    from .errors import APEXError, ErrorCategory, ErrorSeverity, validation_error
    from .core_models import ConfidenceLevel, EpistemicState, TickerIntelligenceFile
    from .numerics import enforce_decimal
except ImportError:
    from errors import APEXError, ErrorCategory, ErrorSeverity, validation_error
    from core_models import ConfidenceLevel, EpistemicState, TickerIntelligenceFile
    from numerics import enforce_decimal


class StrategyType(Enum):
    """Types of trading strategies"""
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    TREND_FOLLOWING = "trend_following"
    STATISTICAL_ARBITRAGE = "statistical_arbitrage"
    EVENT_DRIVEN = "event_driven"
    MARKET_MAKING = "market_making"
    PAIRS_TRADING = "pairs_trading"
    VOLATILITY = "volatility"
    SEASONALITY = "seasonality"


class SignalStrength(Enum):
    """Signal strength levels"""
    VERY_WEAK = "very_weak"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


@dataclass
class StrategySignal:
    """Output from a strategy plugin"""
    signal_id: str
    strategy_id: str
    ticker: str
    timestamp: datetime
    direction: Optional[str]  # 'long', 'short', 'neutral'
    strength: SignalStrength
    confidence: Decimal  # 0.0 to 1.0
    target_price: Optional[Decimal]
    stop_loss: Optional[Decimal]
    time_horizon_days: int
    rationale: str
    epistemic_state: EpistemicState
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.confidence is not None:
            enforce_decimal(self.confidence, "confidence")
        if self.target_price is not None:
            enforce_decimal(self.target_price, "target_price")
        if self.stop_loss is not None:
            enforce_decimal(self.stop_loss, "stop_loss")


@dataclass
class StrategyMetadata:
    """Metadata about a strategy"""
    strategy_id: str
    name: str
    description: str
    strategy_type: StrategyType
    version: str
    author: str
    created_at: datetime
    min_confidence_threshold: Decimal
    max_position_size_pct: Decimal
    required_data_sources: List[str]
    compatible_timeframes: List[str]
    risk_parameters: Dict[str, Any] = field(default_factory=dict)


class StrategyPlugin(Protocol):
    """Protocol for strategy plugins"""
    
    def get_metadata(self) -> StrategyMetadata:
        """Return strategy metadata"""
        ...
    
    def analyze(self, ticker: str, context: Dict[str, Any]) -> Optional[StrategySignal]:
        """Analyze ticker and return signal if applicable"""
        ...
    
    def validate_inputs(self, context: Dict[str, Any]) -> bool:
        """Validate that required inputs are present"""
        ...


@dataclass
class RegisteredStrategy:
    """A registered strategy in the registry"""
    plugin: StrategyPlugin
    metadata: StrategyMetadata
    registered_at: datetime
    enabled: bool = True
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_error: Optional[str] = None
    last_executed: Optional[datetime] = None
    
    def record_execution(self, success: bool, error: Optional[str] = None):
        self.call_count += 1
        self.last_executed = datetime.now()
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
            self.last_error = error
    
    @property
    def success_rate(self) -> Decimal:
        if self.call_count == 0:
            return Decimal("0.0")
        return Decimal(str(self.success_count)) / Decimal(str(self.call_count))


class StrategyRegistry:
    """
    Central registry for all strategy plugins.
    Section 3: Strategy Architecture
    """
    
    def __init__(self):
        self._strategies: Dict[str, RegisteredStrategy] = {}
        self._lock = RLock()
        self._strategy_order: List[str] = []  # Maintains registration order
    
    def register(self, plugin: StrategyPlugin) -> str:
        """Register a strategy plugin"""
        with self._lock:
            metadata = plugin.get_metadata()
            
            if metadata.strategy_id in self._strategies:
                raise validation_error(
                    "STRATEGY_ALREADY_REGISTERED",
                    f"Strategy {metadata.strategy_id} is already registered"
                )
            
            registered = RegisteredStrategy(
                plugin=plugin,
                metadata=metadata,
                registered_at=datetime.now()
            )
            
            self._strategies[metadata.strategy_id] = registered
            self._strategy_order.append(metadata.strategy_id)
            
            return metadata.strategy_id
    
    def unregister(self, strategy_id: str) -> bool:
        """Unregister a strategy"""
        with self._lock:
            if strategy_id not in self._strategies:
                return False
            
            del self._strategies[strategy_id]
            self._strategy_order.remove(strategy_id)
            return True
    
    def get_strategy(self, strategy_id: str) -> Optional[RegisteredStrategy]:
        """Get a registered strategy"""
        with self._lock:
            return self._strategies.get(strategy_id)
    
    def list_strategies(
        self, 
        strategy_type: Optional[StrategyType] = None,
        enabled_only: bool = True
    ) -> List[RegisteredStrategy]:
        """List registered strategies with optional filtering"""
        with self._lock:
            result = []
            for sid in self._strategy_order:
                strat = self._strategies[sid]
                if enabled_only and not strat.enabled:
                    continue
                if strategy_type and strat.metadata.strategy_type != strategy_type:
                    continue
                result.append(strat)
            return result
    
    def enable_strategy(self, strategy_id: str) -> bool:
        """Enable a strategy"""
        with self._lock:
            if strategy_id not in self._strategies:
                return False
            self._strategies[strategy_id].enabled = True
            return True
    
    def disable_strategy(self, strategy_id: str) -> bool:
        """Disable a strategy"""
        with self._lock:
            if strategy_id not in self._strategies:
                return False
            self._strategies[strategy_id].enabled = False
            return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics"""
        with self._lock:
            total = len(self._strategies)
            enabled = sum(1 for s in self._strategies.values() if s.enabled)
            total_calls = sum(s.call_count for s in self._strategies.values())
            total_success = sum(s.success_count for s in self._strategies.values())
            
            return {
                "total_strategies": total,
                "enabled_strategies": enabled,
                "disabled_strategies": total - enabled,
                "total_executions": total_calls,
                "total_successes": total_success,
                "overall_success_rate": float(Decimal(str(total_success)) / Decimal(str(max(1, total_calls))))
            }


class StrategySelector:
    """
    Selects appropriate strategies for a given analysis request.
    Section 3: Strategy Architecture
    """
    
    def __init__(self, registry: StrategyRegistry):
        self.registry = registry
        self._selection_history: List[Dict[str, Any]] = []
    
    def select_for_ticker(
        self,
        ticker: str,
        context: Dict[str, Any],
        strategy_types: Optional[List[StrategyType]] = None,
        min_confidence: Optional[Decimal] = None
    ) -> List[RegisteredStrategy]:
        """Select strategies appropriate for analyzing a ticker"""
        candidates = self.registry.list_strategies(enabled_only=True)
        
        # Filter by strategy type if specified
        if strategy_types:
            candidates = [
                s for s in candidates 
                if s.metadata.strategy_type in strategy_types
            ]
        
        # Filter by minimum confidence threshold
        if min_confidence is not None:
            candidates = [
                s for s in candidates
                if s.metadata.min_confidence_threshold <= min_confidence
            ]
        
        # Filter by required data sources
        required_sources = context.get("available_data_sources", [])
        candidates = [
            s for s in candidates
            if all(src in required_sources for src in s.metadata.required_data_sources)
        ]
        
        # Sort by success rate (higher first)
        candidates.sort(key=lambda s: float(s.success_rate), reverse=True)
        
        # Record selection
        self._selection_history.append({
            "timestamp": datetime.now(),
            "ticker": ticker,
            "selected_count": len(candidates),
            "selected_ids": [s.metadata.strategy_id for s in candidates]
        })
        
        return candidates
    
    def get_selection_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent selection history"""
        return self._selection_history[-limit:]


@dataclass
class AggregatedSignal:
    """Aggregated signal from multiple strategies"""
    ticker: str
    timestamp: datetime
    aggregated_direction: Optional[str]
    aggregated_strength: SignalStrength
    aggregated_confidence: Decimal
    contributing_signals: List[StrategySignal]
    strategy_count: int
    consensus_score: Decimal  # 0.0 to 1.0, how much strategies agree
    dissent_details: str
    epistemic_state: EpistemicState


class StrategyAggregator:
    """
    Aggregates signals from multiple strategies into a unified view.
    Section 3: Strategy Architecture
    """
    
    def __init__(self):
        self._aggregation_history: List[AggregatedSignal] = []
    
    def aggregate_signals(
        self,
        ticker: str,
        signals: List[StrategySignal],
        aggregation_method: str = "weighted_average"
    ) -> Optional[AggregatedSignal]:
        """Aggregate multiple strategy signals"""
        if not signals:
            return None
        
        timestamp = datetime.now()
        
        # Group by direction
        long_signals = [s for s in signals if s.direction == "long"]
        short_signals = [s for s in signals if s.direction == "short"]
        neutral_signals = [s for s in signals if s.direction == "neutral"]
        
        # Determine aggregated direction
        long_weight = sum(float(s.confidence) * len(long_signals) for s in long_signals) if long_signals else 0
        short_weight = sum(float(s.confidence) * len(short_signals) for s in short_signals) if short_signals else 0
        
        if long_weight > short_weight * 1.2:  # 20% threshold for consensus
            agg_direction = "long"
            direction_signals = long_signals
        elif short_weight > long_weight * 1.2:
            agg_direction = "short"
            direction_signals = short_signals
        elif long_signals or short_signals:
            agg_direction = "neutral"
            direction_signals = long_signals + short_signals
        else:
            agg_direction = "neutral"
            direction_signals = neutral_signals
        
        # Calculate aggregated confidence (weighted average)
        if direction_signals:
            total_weight = sum(float(s.confidence) for s in direction_signals)
            avg_confidence = Decimal(str(total_weight / len(direction_signals)))
        else:
            avg_confidence = Decimal("0.0")
        
        # Calculate consensus score
        if len(signals) > 1:
            directions = [s.direction for s in signals]
            same_direction = sum(1 for d in directions if d == agg_direction)
            consensus = Decimal(str(same_direction)) / Decimal(str(len(signals)))
        else:
            consensus = Decimal("1.0")
        
        # Determine aggregated strength
        strength_votes = {}
        for s in signals:
            strength_votes[s.strength] = strength_votes.get(s.strength, 0) + 1
        agg_strength = max(strength_votes.keys(), key=lambda k: strength_votes[k])
        
        # Check for epistemic consistency
        epistemic_states = [s.epistemic_state for s in signals]
        if all(es == epistemic_states[0] for es in epistemic_states):
            agg_epistemic = epistemic_states[0]
        else:
            # Use most conservative state
            state_order = [EpistemicState.UNKNOWN, EpistemicState.SPECULATIVE, 
                          EpistemicState.POSSIBLE, EpistemicState.PROBABLE, EpistemicState.CERTAIN]
            agg_epistemic = min(epistemic_states, key=lambda s: state_order.index(s))
        
        # Generate dissent details
        if len(set(s.direction for s in signals)) > 1:
            dissent = f"Disagreement: {len(long_signals)} long, {len(short_signals)} short, {len(neutral_signals)} neutral"
        else:
            dissent = "No significant dissent"
        
        aggregated = AggregatedSignal(
            ticker=ticker,
            timestamp=timestamp,
            aggregated_direction=agg_direction,
            aggregated_strength=agg_strength,
            aggregated_confidence=avg_confidence,
            contributing_signals=signals,
            strategy_count=len(signals),
            consensus_score=consensus,
            dissent_details=dissent,
            epistemic_state=agg_epistemic
        )
        
        self._aggregation_history.append(aggregated)
        return aggregated
    
    def get_aggregation_history(self, ticker: Optional[str] = None, limit: int = 50) -> List[AggregatedSignal]:
        """Get recent aggregation history"""
        history = self._aggregation_history[-limit*2:]  # Get extra for filtering
        if ticker:
            history = [h for h in history if h.ticker == ticker]
        return history[-limit:]


@dataclass
class StrategyPerformanceMetrics:
    """Performance metrics for a strategy"""
    strategy_id: str
    period_start: datetime
    period_end: datetime
    total_signals: int
    profitable_signals: int
    losing_signals: int
    neutral_signals: int
    total_return_bps: Decimal
    avg_return_per_signal_bps: Decimal
    win_rate: Decimal
    max_drawdown_bps: Decimal
    sharpe_ratio: Optional[Decimal]
    avg_holding_period_days: Decimal


class StrategyPerformanceTracker:
    """Tracks performance of strategies over time"""
    
    def __init__(self):
        self._signal_outcomes: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = RLock()
    
    def record_signal(self, signal: StrategySignal):
        """Record a signal for later performance tracking"""
        with self._lock:
            if signal.strategy_id not in self._signal_outcomes:
                self._signal_outcomes[signal.strategy_id] = []
            
            self._signal_outcomes[signal.strategy_id].append({
                "signal_id": signal.signal_id,
                "timestamp": signal.timestamp,
                "ticker": signal.ticker,
                "direction": signal.direction,
                "strength": signal.strength.value,
                "confidence": str(signal.confidence),
                "target_price": str(signal.target_price) if signal.target_price else None,
                "stop_loss": str(signal.stop_loss) if signal.stop_loss else None,
                "outcome_recorded": False,
                "actual_return_bps": None,
                "outcome_timestamp": None
            })
    
    def record_outcome(
        self, 
        signal_id: str, 
        actual_return_bps: Decimal,
        outcome_timestamp: Optional[datetime] = None
    ):
        """Record the actual outcome of a signal"""
        enforce_decimal(actual_return_bps, "actual_return_bps")
        
        with self._lock:
            for outcomes in self._signal_outcomes.values():
                for outcome in outcomes:
                    if outcome["signal_id"] == signal_id:
                        outcome["outcome_recorded"] = True
                        outcome["actual_return_bps"] = str(actual_return_bps)
                        outcome["outcome_timestamp"] = outcome_timestamp or datetime.now()
                        return
            
            raise validation_error(
                "SIGNAL_NOT_FOUND",
                f"Signal {signal_id} not found for outcome recording"
            )
    
    def get_performance_metrics(
        self,
        strategy_id: str,
        period_days: int = 30
    ) -> Optional[StrategyPerformanceMetrics]:
        """Calculate performance metrics for a strategy"""
        with self._lock:
            if strategy_id not in self._signal_outcomes:
                return None
            
            cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            from datetime import timedelta
            cutoff = cutoff - timedelta(days=period_days)
            
            outcomes = [
                o for o in self._signal_outcomes[strategy_id]
                if o["timestamp"] >= cutoff and o["outcome_recorded"]
            ]
            
            if not outcomes:
                return None
            
            profitable = sum(1 for o in outcomes if float(o["actual_return_bps"]) > 0)
            losing = sum(1 for o in outcomes if float(o["actual_return_bps"]) < 0)
            neutral = sum(1 for o in outcomes if float(o["actual_return_bps"]) == 0)
            
            returns = [Decimal(o["actual_return_bps"]) for o in outcomes]
            total_return = sum(returns)
            avg_return = total_return / len(returns) if returns else Decimal("0")
            win_rate = Decimal(str(profitable)) / Decimal(str(len(outcomes)))
            
            # Simple drawdown calculation
            cumulative = Decimal("0")
            peak = Decimal("0")
            max_dd = Decimal("0")
            for r in returns:
                cumulative += r
                if cumulative > peak:
                    peak = cumulative
                dd = peak - cumulative
                if dd > max_dd:
                    max_dd = dd
            
            return StrategyPerformanceMetrics(
                strategy_id=strategy_id,
                period_start=cutoff,
                period_end=datetime.now(),
                total_signals=len(outcomes),
                profitable_signals=profitable,
                losing_signals=losing,
                neutral_signals=neutral,
                total_return_bps=total_return,
                avg_return_per_signal_bps=avg_return,
                win_rate=win_rate,
                max_drawdown_bps=max_dd,
                sharpe_ratio=None,  # Would need more sophisticated calc
                avg_holding_period_days=Decimal("0")  # Would need holding period data
            )


# Example strategy plugin implementation
class ExampleMomentumStrategy:
    """Example momentum strategy plugin"""
    
    def __init__(self):
        self._metadata = StrategyMetadata(
            strategy_id="momentum_basic_v1",
            name="Basic Momentum",
            description="Simple momentum strategy based on price trends",
            strategy_type=StrategyType.MOMENTUM,
            version="1.0.0",
            author="APEX System",
            created_at=datetime.now(),
            min_confidence_threshold=Decimal("0.3"),
            max_position_size_pct=Decimal("0.05"),
            required_data_sources=["price", "volume"],
            compatible_timeframes=["1d", "4h", "1h"],
            risk_parameters={"max_loss_pct": 0.02}
        )
    
    def get_metadata(self) -> StrategyMetadata:
        return self._metadata
    
    def analyze(self, ticker: str, context: Dict[str, Any]) -> Optional[StrategySignal]:
        """Analyze ticker for momentum signals"""
        # This is a real implementation skeleton
        # In production, this would contain actual momentum logic
        
        price_data = context.get("price_data")
        if not price_data:
            return None
        
        # Simplified momentum check
        if len(price_data) < 20:
            return None
        
        recent_prices = price_data[-10:]
        older_prices = price_data[-20:-10]
        
        recent_avg = sum(recent_prices) / len(recent_prices)
        older_avg = sum(older_prices) / len(older_prices)
        
        momentum = (recent_avg - older_avg) / older_avg if older_avg != 0 else 0
        
        if abs(momentum) < 0.01:  # Less than 1% momentum
            return None
        
        direction = "long" if momentum > 0 else "short"
        strength = SignalStrength.MODERATE if abs(momentum) < 0.03 else SignalStrength.STRONG
        
        return StrategySignal(
            signal_id=str(uuid.uuid4()),
            strategy_id=self._metadata.strategy_id,
            ticker=ticker,
            timestamp=datetime.now(),
            direction=direction,
            strength=strength,
            confidence=Decimal(str(min(0.9, 0.5 + abs(momentum) * 5))),
            target_price=None,
            stop_loss=None,
            time_horizon_days=5,
            rationale=f"Momentum detected: {momentum:.2%} over 10 periods",
            epistemic_state=EpistemicState.PROBABLE,
            metadata={"momentum_value": momentum}
        )
    
    def validate_inputs(self, context: Dict[str, Any]) -> bool:
        return "price_data" in context and len(context.get("price_data", [])) >= 20


__all__ = [
    "StrategyType",
    "SignalStrength",
    "StrategySignal",
    "StrategyMetadata",
    "StrategyPlugin",
    "RegisteredStrategy",
    "StrategyRegistry",
    "StrategySelector",
    "AggregatedSignal",
    "StrategyAggregator",
    "StrategyPerformanceMetrics",
    "StrategyPerformanceTracker",
    "ExampleMomentumStrategy"
]
