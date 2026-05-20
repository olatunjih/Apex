"""
APEX v3 Multi-Agent Layer - Specialized Agents
§6.1 Executive Controller, §7.1 PIL Subsystems, §23 Behavioral Guardian
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .base import (
    BaseAgent, AgentType, AutonomyLevel, AgentMessage, 
    AgentCapability, AgentState
)


@dataclass
class DataFetchRequest:
    """Data agent request"""
    ticker: str
    data_type: str  # ohlcv, depth, options, tick
    interval: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


@dataclass
class DataFetchResponse:
    """Data agent response"""
    data_id: str
    ticker: str
    data_type: str
    fetched_at: datetime
    record_count: int
    quality_score: float
    error: Optional[str] = None


class DataAgent(BaseAgent):
    """
    Data fetching and validation agent - §5.1 Data Registry
    Autonomy: FULLY_AUTONOMOUS for data fetch
    """
    
    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self._data_registry: Dict[str, Any] = {}
        
        # Register capabilities
        self.register_capability(AgentCapability(
            name="fetch_market_data",
            description="Fetch OHLCV market data",
            input_schema={"ticker": "str", "interval": "str"},
            output_schema={"data_id": "str", "bars": "list"},
            latency_budget_ms=100,
            autonomy_level=AutonomyLevel.FULLY_AUTONOMOUS
        ))
    
    def _get_agent_type(self) -> AgentType:
        return AgentType.DATA
    
    def _get_autonomy_level(self) -> AutonomyLevel:
        return AutonomyLevel.FULLY_AUTONOMOUS
    
    async def _process_message_impl(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.message_type == "FETCH_DATA":
            req = DataFetchRequest(**message.payload)
            response = await self._fetch_data(req)
            
            return AgentMessage.create(
                sender_id=self.agent_id,
                recipient_id=message.sender_agent_id,
                msg_type="DATA_RESPONSE",
                payload={
                    "data_id": response.data_id,
                    "ticker": response.ticker,
                    "record_count": response.record_count,
                    "quality_score": response.quality_score,
                    "error": response.error
                },
                trace_id=message.trace_id,
                priority=message.priority + 1
            )
        
        return None
    
    async def _fetch_data(self, request: DataFetchRequest) -> DataFetchResponse:
        """Simulate data fetch - would integrate with real data sources"""
        try:
            # In production: call actual data vendor APIs
            data_id = f"{request.ticker}.{request.data_type}.{datetime.utcnow().isoformat()}"
            
            # Simulate data fetch
            record_count = 100  # Placeholder
            quality_score = 0.95
            
            # Store in registry
            self._data_registry[data_id] = {
                "ticker": request.ticker,
                "data_type": request.data_type,
                "fetched_at": datetime.utcnow(),
                "record_count": record_count
            }
            
            return DataFetchResponse(
                data_id=data_id,
                ticker=request.ticker,
                data_type=request.data_type,
                fetched_at=datetime.utcnow(),
                record_count=record_count,
                quality_score=quality_score
            )
            
        except Exception as e:
            return DataFetchResponse(
                data_id="",
                ticker=request.ticker,
                data_type=request.data_type,
                fetched_at=datetime.utcnow(),
                record_count=0,
                quality_score=0.0,
                error=str(e)
            )


@dataclass
class SignalGenerationRequest:
    """Signal agent request"""
    ticker: str
    indicators: Dict[str, Any]
    regime_context: Dict[str, Any]


@dataclass
class StrategySignal:
    """Generated signal"""
    signal_id: str
    strategy_id: str
    ticker: str
    direction: str  # LONG, SHORT, NEUTRAL
    strength: Decimal
    signal_type: str  # HARD, SOFT
    timeframe: str
    generated_at: datetime
    regime_fitness: float


class SignalAgent(BaseAgent):
    """
    Signal generation agent - §3.2 Signal Schema
    Autonomy: FULLY_AUTONOMOUS for signal generation
    """
    
    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self._active_strategies: List[str] = []
        
        self.register_capability(AgentCapability(
            name="generate_signals",
            description="Generate trading signals from indicators",
            input_schema={"ticker": "str", "indicators": "dict"},
            output_schema={"signals": "list"},
            latency_budget_ms=50,
            autonomy_level=AutonomyLevel.FULLY_AUTONOMOUS
        ))
    
    def _get_agent_type(self) -> AgentType:
        return AgentType.SIGNAL
    
    def _get_autonomy_level(self) -> AutonomyLevel:
        return AutonomyLevel.FULLY_AUTONOMOUS
    
    async def _process_message_impl(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.message_type == "GENERATE_SIGNALS":
            req = SignalGenerationRequest(**message.payload)
            signals = await self._generate_signals(req)
            
            return AgentMessage.create(
                sender_id=self.agent_id,
                recipient_id=message.sender_agent_id,
                msg_type="SIGNALS_RESPONSE",
                payload={
                    "signals": [
                        {
                            "signal_id": s.signal_id,
                            "ticker": s.ticker,
                            "direction": s.direction,
                            "strength": str(s.strength),
                            "regime_fitness": s.regime_fitness
                        }
                        for s in signals
                    ]
                },
                trace_id=message.trace_id,
                priority=message.priority + 1
            )
        
        return None
    
    async def _generate_signals(self, request: SignalGenerationRequest) -> List[StrategySignal]:
        """Generate signals based on indicators - simplified"""
        import uuid
        
        signals = []
        
        # In production: run actual strategy plugins
        for strategy_id in self._active_strategies:
            # Simplified signal logic
            direction = "NEUTRAL"
            strength = Decimal("0.0")
            
            if request.indicators.get("rsi", 50) < 30:
                direction = "LONG"
                strength = Decimal("0.6")
            elif request.indicators.get("rsi", 50) > 70:
                direction = "SHORT"
                strength = Decimal("0.6")
            
            if strength > 0:
                signals.append(StrategySignal(
                    signal_id=f"sig_{uuid.uuid4().hex[:8]}",
                    strategy_id=strategy_id,
                    ticker=request.ticker,
                    direction=direction,
                    strength=strength,
                    signal_type="HARD",
                    timeframe="1D",
                    generated_at=datetime.utcnow(),
                    regime_fitness=request.regime_context.get("fitness_score", 0.5)
                ))
        
        return signals


@dataclass
class RiskAssessmentRequest:
    """Risk agent request"""
    ticker: str
    proposed_position: Dict[str, Any]
    portfolio_state: Dict[str, Any]


@dataclass
class RiskAssessmentResponse:
    """Risk assessment result"""
    approved: bool
    risk_score: float
    guardrail_violations: List[Dict[str, Any]]
    max_position_size: Decimal
    rationale: str


class RiskAgent(BaseAgent):
    """
    Risk assessment and guardrail enforcement agent - §15 Guardrails
    Autonomy: SUPERVISED_AUTONOMOUS (can reject, human can override)
    """
    
    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self._max_portfolio_heat = Decimal("0.06")
        self._max_position_heat = Decimal("0.02")
        
        self.register_capability(AgentCapability(
            name="assess_risk",
            description="Assess position risk and enforce guardrails",
            input_schema={"ticker": "str", "position": "dict", "portfolio": "dict"},
            output_schema={"approved": "bool", "risk_score": "float"},
            latency_budget_ms=20,
            autonomy_level=AutonomyLevel.SUPERVISED_AUTONOMOUS
        ))
    
    def _get_agent_type(self) -> AgentType:
        return AgentType.RISK
    
    def _get_autonomy_level(self) -> AutonomyLevel:
        return AutonomyLevel.SUPERVISED_AUTONOMOUS
    
    async def _process_message_impl(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.message_type == "ASSESS_RISK":
            req = RiskAssessmentRequest(**message.payload)
            response = await self._assess_risk(req)
            
            return AgentMessage.create(
                sender_id=self.agent_id,
                recipient_id=message.sender_agent_id,
                msg_type="RISK_RESPONSE",
                payload={
                    "approved": response.approved,
                    "risk_score": response.risk_score,
                    "guardrail_violations": response.guardrail_violations,
                    "max_position_size": str(response.max_position_size),
                    "rationale": response.rationale
                },
                trace_id=message.trace_id,
                priority=5  # High priority for risk decisions
            )
        
        return None
    
    async def _assess_risk(self, request: RiskAssessmentRequest) -> RiskAssessmentResponse:
        """Assess risk against guardrails G1-G11"""
        violations = []
        
        # G3: Position size check
        proposed_notional = Decimal(str(request.proposed_position.get("notional", 0)))
        max_notional = Decimal("100000")  # Configurable
        if proposed_notional > max_notional:
            violations.append({
                "guardrail": "G3",
                "violation": f"Notional {proposed_notional} exceeds max {max_notional}"
            })
        
        # G4: Portfolio heat check
        current_heat = Decimal(str(request.portfolio_state.get("current_heat", 0)))
        proposed_heat = Decimal(str(request.proposed_position.get("heat", 0)))
        if current_heat + proposed_heat > self._max_portfolio_heat:
            violations.append({
                "guardrail": "G4",
                "violation": f"Portfolio heat {current_heat + proposed_heat} exceeds max {self._max_portfolio_heat}"
            })
        
        # G7: Confidence threshold
        confidence = request.proposed_position.get("confidence", 0)
        if confidence < 0.5:
            violations.append({
                "guardrail": "G7",
                "violation": f"Confidence {confidence} below adaptive threshold"
            })
        
        approved = len(violations) == 0
        risk_score = len(violations) * 0.2
        
        return RiskAssessmentResponse(
            approved=approved,
            risk_score=risk_score,
            guardrail_violations=violations,
            max_position_size=self._max_position_heat,
            rationale="Approved" if approved else f"Rejected: {len(violations)} guardrail violations"
        )


@dataclass
class LearningUpdate:
    """Learning engine update"""
    pattern_type: str
    pattern_data: Dict[str, Any]
    outcome: Optional[Dict[str, Any]] = None


class LearningAgent(BaseAgent):
    """
    Learning engine agent - §19 Learning Engine
    Autonomy: SUPERVISED_AUTONOMOUS (patterns require HITL validation)
    """
    
    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self._learned_patterns: List[Dict[str, Any]] = []
        
        self.register_capability(AgentCapability(
            name="learn_pattern",
            description="Register and learn from patterns",
            input_schema={"pattern_type": "str", "pattern_data": "dict"},
            output_schema={"pattern_id": "str"},
            latency_budget_ms=30,
            autonomy_level=AutonomyLevel.SUPERVISED_AUTONOMOUS
        ))
    
    def _get_agent_type(self) -> AgentType:
        return AgentType.LEARNING
    
    def _get_autonomy_level(self) -> AutonomyLevel:
        return AutonomyLevel.SUPERVISED_AUTONOMOUS
    
    async def _process_message_impl(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.message_type == "LEARN_PATTERN":
            update = LearningUpdate(**message.payload)
            pattern_id = await self._learn_pattern(update)
            
            return AgentMessage.create(
                sender_id=self.agent_id,
                recipient_id=message.sender_agent_id,
                msg_type="LEARN_ACK",
                payload={"pattern_id": pattern_id},
                trace_id=message.trace_id
            )
        
        elif message.message_type == "FIND_PATTERNS":
            context = message.payload.get("context", {})
            patterns = await self._find_patterns(context)
            
            return AgentMessage.create(
                sender_id=self.agent_id,
                recipient_id=message.sender_agent_id,
                msg_type="PATTERNS_RESPONSE",
                payload={"patterns": patterns},
                trace_id=message.trace_id
            )
        
        return None
    
    async def _learn_pattern(self, update: LearningUpdate) -> str:
        """Register a learned pattern"""
        import uuid
        pattern_id = f"pat_{uuid.uuid4().hex[:8]}"
        
        pattern = {
            "pattern_id": pattern_id,
            "pattern_type": update.pattern_type,
            "pattern_data": update.pattern_data,
            "outcome": update.outcome,
            "learned_at": datetime.utcnow(),
            "times_applied": 0,
            "success_rate": 0.5  # Prior
        }
        
        self._learned_patterns.append(pattern)
        return pattern_id
    
    async def _find_patterns(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find relevant patterns for context"""
        # Simplified matching
        ticker = context.get("ticker")
        regime = context.get("regime")
        
        matches = []
        for pattern in self._learned_patterns:
            score = 0.5
            if pattern["pattern_data"].get("ticker") == ticker:
                score += 0.2
            if pattern["pattern_data"].get("regime") == regime:
                score += 0.2
            
            if score > 0.6:
                matches.append({
                    "pattern_id": pattern["pattern_id"],
                    "score": score,
                    "pattern_type": pattern["pattern_type"]
                })
        
        return matches[:5]  # Top 5


class BehavioralAgent(BaseAgent):
    """
    Behavioral Guardian agent - §23 Behavioral Biases
    Autonomy: SUPERVISED_AUTONOMOUS (can warn, human decides)
    """
    
    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self._trade_history: List[Dict[str, Any]] = []
        self._bias_warnings: List[Dict[str, Any]] = []
        
        self.register_capability(AgentCapability(
            name="detect_bias",
            description="Detect behavioral biases in trading patterns",
            input_schema={"user_id": "str", "action": "dict"},
            output_schema={"biases": "list"},
            latency_budget_ms=25,
            autonomy_level=AutonomyLevel.SUPERVISED_AUTONOMOUS
        ))
    
    def _get_agent_type(self) -> AgentType:
        return AgentType.BEHAVIORAL
    
    def _get_autonomy_level(self) -> AutonomyLevel:
        return AutonomyLevel.SUPERVISED_AUTONOMOUS
    
    async def _process_message_impl(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.message_type == "CHECK_BIAS":
            user_id = message.payload.get("user_id")
            action = message.payload.get("action", {})
            biases = await self._detect_biases(user_id, action)
            
            return AgentMessage.create(
                sender_id=self.agent_id,
                recipient_id=message.sender_agent_id,
                msg_type="BIAS_RESPONSE",
                payload={"biases": biases},
                trace_id=message.trace_id,
                priority=4
            )
        
        return None
    
    async def _detect_biases(self, user_id: str, action: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect behavioral biases"""
        biases = []
        
        # REVENGE_TRADING: Trade within N minutes of loss
        if action.get("action_type") == "OPEN_POSITION":
            recent_losses = [
                t for t in self._trade_history[-10:]
                if t.get("realized_pnl", 0) < 0
            ]
            
            if len(recent_losses) >= 2:
                biases.append({
                    "bias_type": "REVENGE_TRADING",
                    "severity": "HIGH",
                    "evidence": f"{len(recent_losses)} recent losses detected",
                    "recommendation": "Consider pausing trading activity"
                })
        
        # FIXATION: Same ticker analysis count
        ticker = action.get("ticker")
        if ticker:
            same_ticker_count = sum(
                1 for t in self._trade_history[-20:]
                if t.get("ticker") == ticker
            )
            if same_ticker_count > 5:
                biases.append({
                    "bias_type": "FIXATION",
                    "severity": "MEDIUM",
                    "evidence": f"Analyzed {ticker} {same_ticker_count} times recently",
                    "recommendation": "Diversify analysis across tickers"
                })
        
        return biases


class PILCoordinatorAgent(BaseAgent):
    """
    Proactive Intelligence Layer Coordinator - §7.1 PIL Subsystems
    Autonomy: FULLY_AUTONOMOUS for intelligence gathering
    """
    
    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self._intelligence_brief: Dict[str, Any] = {}
        self._subsystem_states: Dict[str, Dict[str, Any]] = {}
        
        self.register_capability(AgentCapability(
            name="generate_intelligence_brief",
            description="Coordinate PIL subsystems and generate brief",
            input_schema={"cycle_id": "str"},
            output_schema={"brief": "dict"},
            latency_budget_ms=500,
            autonomy_level=AutonomyLevel.FULLY_AUTONOMOUS
        ))
    
    def _get_agent_type(self) -> AgentType:
        return AgentType.PIL_COORDINATOR
    
    def _get_autonomy_level(self) -> AutonomyLevel:
        return AutonomyLevel.FULLY_AUTONOMOUS
    
    async def _process_message_impl(self, message: AgentMessage) -> Optional[AgentMessage]:
        if message.message_type == "RUN_PIL_CYCLE":
            cycle_id = message.payload.get("cycle_id")
            brief = await self._run_pil_cycle(cycle_id)
            
            return AgentMessage.create(
                sender_id=self.agent_id,
                recipient_id=message.sender_agent_id,
                msg_type="PIL_BRIEF",
                payload={"brief": brief},
                trace_id=message.trace_id
            )
        
        return None
    
    async def _run_pil_cycle(self, cycle_id: str) -> Dict[str, Any]:
        """Run PIL cycle across all subsystems"""
        # In production: coordinate Regime Intelligence, Opportunity Scout, etc.
        brief = {
            "cycle_id": cycle_id,
            "generated_at": datetime.utcnow().isoformat(),
            "regime_assessment": {
                "classification": "neutral",
                "confidence": 0.65,
                "volatility_regime": "normal",
                "breadth": "mixed"
            },
            "opportunity_set": [],
            "risk_alerts": [],
            "calendar_events": [],
            "narrative_shifts": []
        }
        
        self._intelligence_brief = brief
        return brief
