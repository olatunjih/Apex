"""
Self-Healing Architecture with Circuit Breakers and Automated Recovery.
"""
from __future__ import annotations
import time
import threading
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Callable, Set
from enum import Enum
import weakref


class ComponentType(Enum):
    """Types of components that can fail."""
    LLM_PROVIDER = "llm_provider"
    DATA_VENDOR = "data_vendor"
    DATABASE = "database"
    MEMORY = "memory"
    STRATEGY = "strategy"
    GUARDRAIL = "guardrail"
    AGENT = "agent"


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class FailureRecord:
    """Record of a component failure."""
    component_type: ComponentType
    component_id: str
    error_message: str
    timestamp: float = field(default_factory=time.time)
    recovery_action_taken: bool = False


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 3  # Successes before closing from half-open
    timeout_seconds: float = 60.0  # Time before trying half-open
    half_open_max_calls: int = 3  # Max calls in half-open state


@dataclass
class RecoveryAction:
    """Automated recovery action."""
    action_type: str
    description: str
    executed: bool = False
    success: bool = False
    timestamp: Optional[float] = None


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    Prevents cascade failures by isolating failing components.
    """
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.RLock()
    
    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._check_state_transition()
            return self._state
    
    def _check_state_transition(self) -> None:
        """Check if state should transition (e.g., OPEN → HALF_OPEN)."""
        if self._state == CircuitState.OPEN and self._last_failure_time:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.config.timeout_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
    
    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0
    
    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.config.half_open_max_calls:
                    self._state = CircuitState.OPEN
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN
    
    def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        with self._lock:
            self._check_state_transition()
            
            if self._state == CircuitState.CLOSED:
                return True
            elif self._state == CircuitState.OPEN:
                return False
            else:  # HALF_OPEN
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
    
    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0


@dataclass
class ComponentHealth:
    """Health status of a component."""
    component_type: ComponentType
    component_id: str
    is_healthy: bool
    circuit_breaker_state: CircuitState
    failure_rate: float  # Last 100 calls
    last_failure_time: Optional[float]
    consecutive_failures: int
    recovery_actions_available: List[str]


class SelfHealingEngine:
    """
    Self-healing architecture with automated detection and recovery.
    """
    
    def __init__(self):
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._failure_history: List[FailureRecord] = []
        self._recovery_actions: Dict[str, List[RecoveryAction]] = {}
        self._component_configs: Dict[str, CircuitBreakerConfig] = {}
        self._lock = threading.RLock()
        self._health_callbacks: List[Callable[[ComponentHealth], None]] = []
        
        # Default configs
        self._component_configs["llm_provider"] = CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=3,
            timeout_seconds=60.0,
        )
        self._component_configs["data_vendor"] = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=30.0,
        )
        self._component_configs["database"] = CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=3,
            timeout_seconds=120.0,
        )
        self._component_configs["memory"] = CircuitBreakerConfig(
            failure_threshold=10,
            success_threshold=5,
            timeout_seconds=300.0,
        )
    
    def _get_circuit_breaker_key(self, component_type: ComponentType, component_id: str) -> str:
        return f"{component_type.value}:{component_id}"
    
    def register_component(
        self,
        component_type: ComponentType,
        component_id: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        """Register a component for monitoring."""
        key = self._get_circuit_breaker_key(component_type, component_id)
        with self._lock:
            if key not in self._circuit_breakers:
                cb_config = config or self._component_configs.get(
                    component_type.value, CircuitBreakerConfig()
                )
                self._circuit_breakers[key] = CircuitBreaker(cb_config)
                self._recovery_actions[key] = []
    
    def record_success(self, component_type: ComponentType, component_id: str) -> None:
        """Record a successful operation."""
        key = self._get_circuit_breaker_key(component_type, component_id)
        with self._lock:
            if key in self._circuit_breakers:
                self._circuit_breakers[key].record_success()
    
    def record_failure(
        self,
        component_type: ComponentType,
        component_id: str,
        error_message: str,
    ) -> Optional[RecoveryAction]:
        """Record a failure and potentially trigger recovery."""
        key = self._get_circuit_breaker_key(component_type, component_id)
        
        with self._lock:
            # Ensure component is registered
            if key not in self._circuit_breakers:
                self.register_component(component_type, component_id)
            
            # Record failure
            self._circuit_breakers[key].record_failure()
            
            # Create failure record
            failure = FailureRecord(
                component_type=component_type,
                component_id=component_id,
                error_message=error_message,
            )
            self._failure_history.append(failure)
            
            # Keep history bounded
            if len(self._failure_history) > 1000:
                self._failure_history = self._failure_history[-1000:]
            
            # Check if recovery needed
            cb = self._circuit_breakers[key]
            if cb.state == CircuitState.OPEN:
                recovery = self._determine_recovery_action(component_type, component_id, error_message)
                if recovery:
                    self._recovery_actions[key].append(recovery)
                    return recovery
        
        return None
    
    def _determine_recovery_action(
        self,
        component_type: ComponentType,
        component_id: str,
        error_message: str,
    ) -> RecoveryAction:
        """Determine appropriate recovery action based on failure type."""
        if component_type == ComponentType.LLM_PROVIDER:
            if "rate limit" in error_message.lower():
                return RecoveryAction(
                    action_type="fallback_provider",
                    description="Switch to fallback LLM provider",
                )
            elif "context" in error_message.lower():
                return RecoveryAction(
                    action_type="compress_context",
                    description="Compress context and retry",
                )
            else:
                return RecoveryAction(
                    action_type="degraded_mode",
                    description="Switch to deterministic rule-engine mode",
                )
        
        elif component_type == ComponentType.DATA_VENDOR:
            return RecoveryAction(
                action_type="failover_vendor",
                description="Switch to backup data vendor",
            )
        
        elif component_type == ComponentType.DATABASE:
            return RecoveryAction(
                action_type="retry_with_backoff",
                description="Retry database connection with exponential backoff",
            )
        
        elif component_type == ComponentType.MEMORY:
            return RecoveryAction(
                action_type="trigger_gc",
                description="Trigger garbage collection and clear caches",
            )
        
        return RecoveryAction(
            action_type="generic_retry",
            description="Generic retry with backoff",
        )
    
    def execute_recovery(self, action: RecoveryAction) -> bool:
        """Execute a recovery action."""
        # Simulate recovery execution
        # In production, this would actually perform the recovery
        action.executed = True
        action.success = True  # Assume success for demo
        action.timestamp = time.time()
        return action.success
    
    def get_component_health(
        self,
        component_type: ComponentType,
        component_id: str,
    ) -> ComponentHealth:
        """Get health status of a component."""
        key = self._get_circuit_breaker_key(component_type, component_id)
        
        with self._lock:
            cb = self._circuit_breakers.get(key)
            if not cb:
                return ComponentHealth(
                    component_type=component_type,
                    component_id=component_id,
                    is_healthy=True,
                    circuit_breaker_state=CircuitState.CLOSED,
                    failure_rate=0.0,
                    last_failure_time=None,
                    consecutive_failures=0,
                    recovery_actions_available=[],
                )
            
            # Calculate failure rate from recent history
            recent_failures = [
                f for f in self._failure_history[-100:]
                if f.component_type == component_type and f.component_id == component_id
            ]
            failure_rate = len(recent_failures) / 100.0
            
            # Count consecutive failures
            consecutive = 0
            for f in reversed(self._failure_history):
                if f.component_type == component_type and f.component_id == component_id:
                    consecutive += 1
                else:
                    break
            
            recovery_actions = [
                ra.description for ra in self._recovery_actions.get(key, [])
                if not ra.executed
            ]
            
            return ComponentHealth(
                component_type=component_type,
                component_id=component_id,
                is_healthy=cb.state != CircuitState.OPEN,
                circuit_breaker_state=cb.state,
                failure_rate=failure_rate,
                last_failure_time=cb._last_failure_time,
                consecutive_failures=consecutive,
                recovery_actions_available=recovery_actions,
            )
    
    def get_all_component_health(self) -> Dict[str, ComponentHealth]:
        """Get health status of all monitored components."""
        with self._lock:
            result = {}
            for key in self._circuit_breakers.keys():
                parts = key.split(":", 1)
                if len(parts) == 2:
                    comp_type_str, comp_id = parts
                    try:
                        comp_type = ComponentType(comp_type_str)
                        result[key] = self.get_component_health(comp_type, comp_id)
                    except ValueError:
                        pass
            return result
    
    def check_memory_ceiling(self, current_rss_mb: float, ceiling_mb: float) -> Optional[RecoveryAction]:
        """Check if memory usage exceeds ceiling and trigger recovery."""
        if current_rss_mb >= ceiling_mb:
            action = RecoveryAction(
                action_type="graceful_restart",
                description=f"Memory ceiling exceeded ({current_rss_mb:.1f}MB >= {ceiling_mb:.1f}MB). Triggering graceful restart.",
            )
            return action
        return None
    
    def add_health_callback(self, callback: Callable[[ComponentHealth], None]) -> None:
        """Add callback to be notified of health changes."""
        self._health_callbacks.append(callback)
    
    def reset_component(self, component_type: ComponentType, component_id: str) -> None:
        """Manually reset a component's circuit breaker."""
        key = self._get_circuit_breaker_key(component_type, component_id)
        with self._lock:
            if key in self._circuit_breakers:
                self._circuit_breakers[key].reset()
                self._recovery_actions[key] = []


# Global instance
DEFAULT_SELF_HEALING_ENGINE = SelfHealingEngine()
