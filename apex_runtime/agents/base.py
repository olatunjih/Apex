"""
APEX v3 Multi-Agent Layer - Base Protocol & Registry
§6.1 Executive Controller, §8.1 Reactive Pipeline DAG, §43 Autonomy Matrix
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol
import uuid
import threading


class AgentType(Enum):
    """Agent classification per §43 Autonomy Matrix"""
    DATA = "data"
    SIGNAL = "signal"
    RISK = "risk"
    LEARNING = "learning"
    EVOLUTION = "evolution"
    CURIOSITY = "curiosity"
    BEHAVIORAL = "behavioral"
    NARRATIVE = "narrative"
    PIL_COORDINATOR = "pil_coordinator"
    EXECUTIVE = "executive"


class AutonomyLevel(Enum):
    """§43 Autonomy Levels"""
    PROHIBITED = "prohibited"
    ALWAYS_HUMAN = "always_human"
    REQUIRES_APPROVAL = "requires_approval"
    SUPERVISED_AUTONOMOUS = "supervised_autonomous"
    FULLY_AUTONOMOUS = "fully_autonomous"


@dataclass(frozen=True)
class AgentMessage:
    """Inter-agent communication protocol"""
    message_id: str
    sender_agent_id: str
    recipient_agent_id: Optional[str]
    message_type: str
    payload: Dict[str, Any]
    timestamp: datetime
    trace_id: str
    priority: int = 0
    requires_ack: bool = False
    ttl_seconds: int = 300
    
    @classmethod
    def create(cls, sender_id: str, recipient_id: Optional[str], 
               msg_type: str, payload: Dict[str, Any], 
               trace_id: str, priority: int = 0, 
               requires_ack: bool = False, ttl_seconds: int = 300) -> 'AgentMessage':
        return cls(
            message_id=str(uuid.uuid4()),
            sender_agent_id=sender_id,
            recipient_agent_id=recipient_id,
            message_type=msg_type,
            payload=payload,
            timestamp=datetime.utcnow(),
            trace_id=trace_id,
            priority=priority,
            requires_ack=requires_ack,
            ttl_seconds=ttl_seconds
        )


@dataclass
class AgentState:
    """Agent runtime state"""
    agent_id: str
    is_healthy: bool = True
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    current_task: Optional[str] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    avg_latency_ms: float = 0.0
    error_count: int = 0
    autonomy_level: AutonomyLevel = AutonomyLevel.FULLY_AUTONOMOUS


class AgentProtocol(Protocol):
    """Agent interface contract - §6.1"""
    
    agent_id: str
    agent_type: AgentType
    autonomy_level: AutonomyLevel
    
    async def initialize(self) -> bool: ...
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]: ...
    async def shutdown(self) -> bool: ...
    def get_state(self) -> AgentState: ...
    def health_check(self) -> bool: ...


@dataclass
class AgentCapability:
    """Agent capability declaration"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    latency_budget_ms: int
    autonomy_level: AutonomyLevel


class BaseAgent(ABC):
    """Base agent implementation - §6.1, §8.1"""
    
    def __init__(self, agent_id: Optional[str] = None):
        self.agent_id = agent_id or f"{self.__class__.__name__}_{uuid.uuid4().hex[:8]}"
        self.agent_type = self._get_agent_type()
        self.autonomy_level = self._get_autonomy_level()
        self._state = AgentState(agent_id=self.agent_id)
        self._capabilities: List[AgentCapability] = []
        self._initialized = False
        self._lock = threading.RLock()
        
    @abstractmethod
    def _get_agent_type(self) -> AgentType:
        """Return agent type"""
        pass
    
    @abstractmethod
    def _get_autonomy_level(self) -> AutonomyLevel:
        """Return autonomy level per §43"""
        pass
    
    @abstractmethod
    async def _process_message_impl(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Implementation of message processing"""
        pass
    
    async def initialize(self) -> bool:
        """Initialize agent"""
        with self._lock:
            if self._initialized:
                return True
            
            try:
                await self._initialize_impl()
                self._initialized = True
                self._state.is_healthy = True
                self._state.last_heartbeat = datetime.utcnow()
                return True
            except Exception as e:
                self._state.is_healthy = False
                self._state.error_count += 1
                raise
    
    async def _initialize_impl(self) -> None:
        """Override for custom initialization"""
        pass
    
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process message with error handling"""
        start_time = datetime.utcnow()
        
        with self._lock:
            self._state.current_task = message.message_type
            self._state.last_heartbeat = datetime.utcnow()
        
        try:
            response = await self._process_message_impl(message)
            
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            with self._lock:
                self._state.tasks_completed += 1
                self._state.avg_latency_ms = (
                    (self._state.avg_latency_ms * (self._state.tasks_completed - 1) + latency_ms)
                    / self._state.tasks_completed
                )
                self._state.current_task = None
            
            return response
            
        except Exception as e:
            with self._lock:
                self._state.tasks_failed += 1
                self._state.error_count += 1
                self._state.current_task = None
            raise
    
    async def shutdown(self) -> bool:
        """Graceful shutdown"""
        with self._lock:
            try:
                await self._shutdown_impl()
                self._initialized = False
                return True
            except Exception:
                return False
    
    async def _shutdown_impl(self) -> None:
        """Override for custom shutdown"""
        pass
    
    def get_state(self) -> AgentState:
        """Get current state"""
        with self._lock:
            return AgentState(
                agent_id=self._state.agent_id,
                is_healthy=self._state.is_healthy,
                last_heartbeat=self._state.last_heartbeat,
                current_task=self._state.current_task,
                tasks_completed=self._state.tasks_completed,
                tasks_failed=self._state.tasks_failed,
                avg_latency_ms=self._state.avg_latency_ms,
                error_count=self._state.error_count,
                autonomy_level=self._state.autonomy_level
            )
    
    def health_check(self) -> bool:
        """Quick health check"""
        with self._lock:
            return self._state.is_healthy and self._initialized
    
    def register_capability(self, capability: AgentCapability) -> None:
        """Register agent capability"""
        self._capabilities.append(capability)
    
    def get_capabilities(self) -> List[AgentCapability]:
        """Get registered capabilities"""
        return list(self._capabilities)


class AgentRegistry:
    """Central agent registry - §6.1"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._agents: Dict[str, BaseAgent] = {}
                    cls._instance._capabilities: Dict[str, str] = {}
                    cls._instance._lock = threading.RLock()
        return cls._instance
    
    def register(self, agent: BaseAgent) -> bool:
        """Register an agent"""
        with self._lock:
            if agent.agent_id in self._agents:
                return False
            
            self._agents[agent.agent_id] = agent
            
            for cap in agent.get_capabilities():
                self._capabilities[cap.name] = agent.agent_id
            
            return True
    
    def unregister(self, agent_id: str) -> bool:
        """Unregister an agent"""
        with self._lock:
            if agent_id not in self._agents:
                return False
            
            agent = self._agents[agent_id]
            
            for cap in agent.get_capabilities():
                if cap.name in self._capabilities and self._capabilities[cap.name] == agent_id:
                    del self._capabilities[cap.name]
            
            del self._agents[agent_id]
            return True
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get agent by ID"""
        with self._lock:
            return self._agents.get(agent_id)
    
    def get_agent_by_capability(self, capability_name: str) -> Optional[BaseAgent]:
        """Get agent that provides a capability"""
        with self._lock:
            agent_id = self._capabilities.get(capability_name)
            if agent_id:
                return self._agents.get(agent_id)
            return None
    
    def list_agents(self) -> List[str]:
        """List all registered agent IDs"""
        with self._lock:
            return list(self._agents.keys())
    
    def list_agents_by_type(self, agent_type: AgentType) -> List[str]:
        """List agents by type"""
        with self._lock:
            return [
                aid for aid, agent in self._agents.items()
                if agent.agent_type == agent_type
            ]
    
    def health_check_all(self) -> Dict[str, bool]:
        """Health check all agents"""
        with self._lock:
            return {aid: agent.health_check() for aid, agent in self._agents.items()}
    
    async def shutdown_all(self) -> Dict[str, bool]:
        """Shutdown all agents"""
        with self._lock:
            agents_copy = dict(self._agents)
        
        results = {}
        for aid, agent in agents_copy.items():
            results[aid] = await agent.shutdown()
        
        return results


class MessageBus:
    """Inter-agent message bus - §6.1, §8.1"""
    
    def __init__(self, max_queue_size: int = 10000):
        self._queues: Dict[str, List[AgentMessage]] = {}
        self._max_queue_size = max_queue_size
        self._lock = threading.RLock()
        self._message_log: List[AgentMessage] = []
        self._log_max_size = 10000
    
    def send(self, message: AgentMessage) -> bool:
        """Send message to agent queue"""
        with self._lock:
            recipient = message.recipient_agent_id
            
            if recipient is None:
                for agent_id in self._queues.keys():
                    self._enqueue(agent_id, message)
            else:
                self._enqueue(recipient, message)
            
            self._message_log.append(message)
            if len(self._message_log) > self._log_max_size:
                self._message_log = self._message_log[-self._log_max_size:]
            
            return True
    
    def _enqueue(self, agent_id: str, message: AgentMessage) -> None:
        """Enqueue message for agent"""
        if agent_id not in self._queues:
            self._queues[agent_id] = []
        
        queue = self._queues[agent_id]
        
        if len(queue) >= self._max_queue_size:
            if message.priority < 5:
                queue.pop(0)
        
        queue.append(message)
    
    def receive(self, agent_id: str, max_messages: int = 10) -> List[AgentMessage]:
        """Receive messages for agent"""
        with self._lock:
            if agent_id not in self._queues:
                return []
            
            queue = self._queues[agent_id]
            messages = queue[:max_messages]
            self._queues[agent_id] = queue[max_messages:]
            
            return messages
    
    def get_queue_size(self, agent_id: str) -> int:
        """Get queue size for agent"""
        with self._lock:
            return len(self._queues.get(agent_id, []))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get message bus statistics"""
        with self._lock:
            return {
                "total_queues": len(self._queues),
                "queue_sizes": {aid: len(q) for aid, q in self._queues.items()},
                "total_messages_logged": len(self._message_log),
                "max_queue_size": self._max_queue_size
            }
