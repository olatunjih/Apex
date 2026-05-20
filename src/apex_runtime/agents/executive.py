"""
APEX v3 Multi-Agent Layer - Executive Controller & Health Monitoring
§6.1 Executive Controller, §8.1 DAG Execution, §28 Agent Drift Detection
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import uuid
import threading

from .base import (
    BaseAgent, AgentType, AutonomyLevel, AgentMessage,
    AgentCapability, AgentState, AgentRegistry, MessageBus
)


@dataclass
class DAGStep:
    """DAG step definition - §8.1"""
    step_id: str
    agent_capability: str
    latency_budget_ms: int
    timeout_ms: int
    retry_count: int = 0
    degradation_policy: str = "skip"  # skip, retry, fallback


@dataclass
class DAGExecution:
    """DAG execution state"""
    execution_id: str
    trace_id: str
    steps: List[DAGStep]
    current_step: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"  # pending, running, completed, failed, degraded
    step_results: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class LatencyBudget:
    """Latency budget tracking - §6.1"""
    total_budget_ms: int
    used_ms: float = 0.0
    remaining_ms: float = 0.0
    step_budgets: Dict[str, int] = field(default_factory=dict)
    
    def __post_init__(self):
        self.remaining_ms = float(self.total_budget_ms)


class ExecutiveController:
    """
    Executive Controller - §6.1, §8.1
    Orchestrates DAG execution across agents with latency budgets
    """
    
    def __init__(self, registry: Optional[AgentRegistry] = None, 
                 message_bus: Optional[MessageBus] = None):
        self.registry = registry or AgentRegistry()
        self.message_bus = message_bus or MessageBus()
        self._executions: Dict[str, DAGExecution] = {}
        self._lock = threading.RLock()
        
        # Default latency budgets per §6.1
        self._default_budgets = {
            "data_fetch": 100,
            "indicator_compute": 50,
            "signal_generate": 50,
            "signal_aggregate": 30,
            "mtf_filter": 40,
            "risk_assess": 20,
            "why_engine": 200,
            "reflection": 150,
            "guardrail_check": 20,
            "narrative_synthesis": 300
        }
    
    async def execute_dag(self, dag_id: str, steps: List[DAGStep],
                         context: Dict[str, Any],
                         total_budget_ms: int = 5000) -> DAGExecution:
        """Execute a DAG of agent steps - §8.1"""
        
        execution_id = f"dag_{uuid.uuid4().hex[:8]}"
        trace_id = str(uuid.uuid4())
        
        execution = DAGExecution(
            execution_id=execution_id,
            trace_id=trace_id,
            steps=steps,
            status="running",
            started_at=datetime.utcnow()
        )
        
        with self._lock:
            self._executions[execution_id] = execution
        
        budget = LatencyBudget(total_budget_ms=total_budget_ms)
        
        try:
            for i, step in enumerate(steps):
                execution.current_step = i
                
                # Check budget
                if budget.remaining_ms <= 0:
                    execution.status = "degraded"
                    execution.errors.append({
                        "step": step.step_id,
                        "error": "Budget exhausted",
                        "action": "Skipping remaining steps"
                    })
                    break
                
                # Execute step
                step_start = datetime.utcnow()
                result = await self._execute_step(step, context, trace_id, budget)
                
                step_latency = (datetime.utcnow() - step_start).total_seconds() * 1000
                execution.step_results[step.step_id] = {
                    "result": result,
                    "latency_ms": step_latency,
                    "within_budget": step_latency <= step.latency_budget_ms
                }
                
                # Check step latency budget
                if step_latency > step.latency_budget_ms:
                    execution.errors.append({
                        "step": step.step_id,
                        "error": f"Latency {step_latency:.1f}ms exceeds budget {step.latency_budget_ms}ms"
                    })
            
            execution.status = "completed" if not execution.errors else "degraded"
            execution.completed_at = datetime.utcnow()
            
        except Exception as e:
            execution.status = "failed"
            execution.errors.append({
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            execution.completed_at = datetime.utcnow()
        
        return execution
    
    async def _execute_step(self, step: DAGStep, context: Dict[str, Any],
                           trace_id: str, budget: LatencyBudget) -> Any:
        """Execute a single DAG step"""
        
        # Find agent with capability
        agent = self.registry.get_agent_by_capability(step.agent_capability)
        
        if not agent:
            raise ValueError(f"No agent found for capability: {step.agent_capability}")
        
        # Create message
        message = AgentMessage.create(
            sender_id="executive_controller",
            recipient_id=agent.agent_id,
            msg_type=step.step_id,
            payload=context,
            trace_id=trace_id,
            priority=5,
            requires_ack=True
        )
        
        # Send and wait for response
        self.message_bus.send(message)
        
        # Receive response with timeout
        responses = self.message_bus.receive(agent.agent_id, max_messages=1)
        
        if not responses:
            # Retry logic
            for attempt in range(step.retry_count):
                await asyncio.sleep(0.1 * (attempt + 1))
                self.message_bus.send(message)
                responses = self.message_bus.receive(agent.agent_id, max_messages=1)
                if responses:
                    break
            
            if not responses:
                raise TimeoutError(f"Step {step.step_id} timed out")
        
        # Update budget
        response = responses[0]
        latency = (datetime.utcnow() - message.timestamp).total_seconds() * 1000
        budget.used_ms += latency
        budget.remaining_ms = budget.total_budget_ms - budget.used_ms
        
        return response.payload
    
    def get_execution(self, execution_id: str) -> Optional[DAGExecution]:
        """Get execution by ID"""
        with self._lock:
            return self._executions.get(execution_id)
    
    def get_all_executions(self) -> List[DAGExecution]:
        """Get all executions"""
        with self._lock:
            return list(self._executions.values())
    
    def cleanup_old_executions(self, max_age_hours: int = 1) -> int:
        """Clean up old executions"""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        with self._lock:
            to_remove = [
                eid for eid, exec_data in self._executions.items()
                if exec_data.started_at and exec_data.started_at < cutoff
            ]
            
            for eid in to_remove:
                del self._executions[eid]
            
            return len(to_remove)


@dataclass
class AgentDriftMetrics:
    """Agent drift metrics - §28"""
    agent_id: str
    measurement_period: str
    decision_direction_ratio: float
    confidence_calibration_gap: float
    strategy_dominance: Dict[str, float]
    why_score_homogeneity: float
    reasoning_pattern_repetition: float
    drift_score: float
    is_drifting: bool


class AgentHealthMonitor:
    """
    Agent health and drift monitoring - §28 Agent Drift Detection
    """
    
    def __init__(self, registry: Optional[AgentRegistry] = None):
        self.registry = registry or AgentRegistry()
        self._baselines: Dict[str, Dict[str, float]] = {}
        self._metrics_history: Dict[str, List[AgentDriftMetrics]] = {}
        self._lock = threading.RLock()
        
        # Drift thresholds - §28
        self._drift_thresholds = {
            "decision_direction_ratio": 0.3,
            "confidence_calibration_gap": 0.15,
            "why_score_homogeneity": 0.8,
            "reasoning_pattern_repetition": 0.7
        }
    
    def capture_baseline(self, agent_id: str, metrics: Dict[str, float]) -> None:
        """Capture behavioral baseline for agent - §28"""
        with self._lock:
            self._baselines[agent_id] = metrics
    
    def measure_drift(self, agent_id: str, current_metrics: Dict[str, float]) -> AgentDriftMetrics:
        """Measure drift from baseline - §28"""
        
        baseline = self._baselines.get(agent_id, {})
        
        if not baseline:
            # No baseline, create one
            self.capture_baseline(agent_id, current_metrics)
            baseline = current_metrics
        
        # Calculate drift metrics
        decision_ratio_diff = abs(
            current_metrics.get("decision_direction_ratio", 0.5) -
            baseline.get("decision_direction_ratio", 0.5)
        )
        
        calibration_gap = abs(
            current_metrics.get("confidence_calibration", 0.0) -
            baseline.get("confidence_calibration", 0.0)
        )
        
        homogeneity = current_metrics.get("why_score_homogeneity", 0.0)
        repetition = current_metrics.get("reasoning_repetition", 0.0)
        
        # Composite drift score
        drift_components = [
            decision_ratio_diff / self._drift_thresholds["decision_direction_ratio"],
            calibration_gap / self._drift_thresholds["confidence_calibration_gap"],
            homogeneity / self._drift_thresholds["why_score_homogeneity"],
            repetition / self._drift_thresholds["reasoning_pattern_repetition"]
        ]
        
        drift_score = sum(drift_components) / len(drift_components)
        is_drifting = drift_score > 1.0
        
        metrics = AgentDriftMetrics(
            agent_id=agent_id,
            measurement_period="current",
            decision_direction_ratio=current_metrics.get("decision_direction_ratio", 0.5),
            confidence_calibration_gap=calibration_gap,
            strategy_dominance=current_metrics.get("strategy_dominance", {}),
            why_score_homogeneity=homogeneity,
            reasoning_pattern_repetition=repetition,
            drift_score=drift_score,
            is_drifting=is_drifting
        )
        
        # Store history
        with self._lock:
            if agent_id not in self._metrics_history:
                self._metrics_history[agent_id] = []
            self._metrics_history[agent_id].append(metrics)
            
            # Keep last 100 measurements
            if len(self._metrics_history[agent_id]) > 100:
                self._metrics_history[agent_id] = self._metrics_history[agent_id][-100:]
        
        return metrics
    
    def get_drift_alerts(self) -> List[Dict[str, Any]]:
        """Get drift alerts for all agents"""
        alerts = []
        
        with self._lock:
            for agent_id, history in self._metrics_history.items():
                if not history:
                    continue
                
                latest = history[-1]
                if latest.is_drifting:
                    alerts.append({
                        "agent_id": agent_id,
                        "drift_score": latest.drift_score,
                        "timestamp": datetime.utcnow().isoformat(),
                        "recommendation": "AGENT_DRIFT_DETECTED - Initiate root cause analysis"
                    })
        
        return alerts
    
    def get_agent_health_summary(self) -> Dict[str, Any]:
        """Get health summary for all registered agents"""
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "agents": {},
            "drift_alerts": self.get_drift_alerts()
        }
        
        for agent_id in self.registry.list_agents():
            agent = self.registry.get_agent(agent_id)
            if agent:
                state = agent.get_state()
                summary["agents"][agent_id] = {
                    "type": agent.agent_type.value,
                    "is_healthy": state.is_healthy,
                    "initialized": agent._initialized,
                    "tasks_completed": state.tasks_completed,
                    "tasks_failed": state.tasks_failed,
                    "avg_latency_ms": state.avg_latency_ms,
                    "error_count": state.error_count,
                    "autonomy_level": state.autonomy_level.value
                }
        
        return summary
