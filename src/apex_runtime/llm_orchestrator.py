"""
Advanced LLM Orchestration Layer
Handles adaptive retries, fallback providers, context compression, and structured output validation.
"""
from __future__ import annotations
import time
import random
import json
import hashlib
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Callable, Protocol, Tuple
from enum import Enum
import threading


class LLMErrorType(Enum):
    RATE_LIMIT = "rate_limit"
    CONTEXT_LENGTH = "context_length"
    SERVER_ERROR = "server_error"
    AUTH_ERROR = "auth_error"
    TIMEOUT = "timeout"
    INVALID_RESPONSE = "invalid_response"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LLMProvider:
    """Configuration for an LLM provider."""
    name: str
    api_key_env: str
    base_url: str
    model_name: str
    max_tokens: int
    cost_per_1k_input: Decimal
    cost_per_1k_output: Decimal
    timeout_seconds: float
    priority: int  # Lower = higher priority


@dataclass
class LLMCallRecord:
    """Audit record for an LLM call."""
    trace_id: str
    provider_name: str
    model_name: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: Decimal
    success: bool
    error_type: Optional[LLMErrorType]
    retry_count: int
    timestamp: float = field(default_factory=time.time)


class CompressionStrategy(Protocol):
    def compress(self, messages: List[Dict[str, str]], target_tokens: int) -> List[Dict[str, str]]:
        """Compress message history to fit within token limit."""
        ...


class PriorityCompressionStrategy:
    """Compresses by removing older messages while preserving system/thesis."""
    
    def compress(self, messages: List[Dict[str, str]], target_tokens: int) -> List[Dict[str, str]]:
        if not messages:
            return messages
        
        # Keep system messages always
        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]
        
        # Simple truncation from oldest (beginning of other_msgs)
        # In production, this would use token counting
        max_other = max(0, len(other_msgs) - 2)  # Keep last 2 non-system messages
        
        compressed = system_msgs + other_msgs[-max_other:] if max_other > 0 else system_msgs
        return compressed


class RetryStrategy(Protocol):
    def should_retry(self, error_type: LLMErrorType, attempt: int) -> bool:
        ...
    
    def get_delay(self, attempt: int) -> float:
        ...


class ExponentialBackoffRetry:
    """Exponential backoff with jitter."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def should_retry(self, error_type: LLMErrorType, attempt: int) -> bool:
        if attempt >= self.max_retries:
            return False
        # Don't retry auth errors
        if error_type == LLMErrorType.AUTH_ERROR:
            return False
        return True
    
    def get_delay(self, attempt: int) -> float:
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter


class LLMOrchestrator:
    """
    Advanced LLM orchestration with retry, fallback, compression, and validation.
    """
    
    def __init__(
        self,
        providers: List[LLMProvider],
        retry_strategy: Optional[RetryStrategy] = None,
        compression_strategy: Optional[CompressionStrategy] = None,
        max_context_tokens: int = 128000,
        trace_id_generator: Optional[Callable[[], str]] = None,
    ):
        self.providers = sorted(providers, key=lambda p: p.priority)
        self.retry_strategy = retry_strategy or ExponentialBackoffRetry()
        self.compression_strategy = compression_strategy or PriorityCompressionStrategy()
        self.max_context_tokens = max_context_tokens
        self.trace_id_generator = trace_id_generator or (lambda: hashlib.sha256(f"{time.time()}".encode()).hexdigest()[:16])
        
        self._call_history: List[LLMCallRecord] = []
        self._lock = threading.RLock()
        self._cost_tracker: Dict[str, Decimal] = {}  # trace_id -> cost
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars per token)."""
        return len(text) // 4
    
    def _classify_error(self, exception: Exception) -> LLMErrorType:
        """Classify exception into error type."""
        msg = str(exception).lower()
        if "rate limit" in msg or "429" in msg:
            return LLMErrorType.RATE_LIMIT
        if "context" in msg or "token" in msg and "limit" in msg:
            return LLMErrorType.CONTEXT_LENGTH
        if "auth" in msg or "401" in msg or "403" in msg:
            return LLMErrorType.AUTH_ERROR
        if "timeout" in msg or "time out" in msg:
            return LLMErrorType.TIMEOUT
        if "500" in msg or "502" in msg or "503" in msg:
            return LLMErrorType.SERVER_ERROR
        return LLMErrorType.UNKNOWN
    
    def _simulate_llm_call(
        self,
        provider: LLMProvider,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> Tuple[str, int, int]:
        """
        Simulate LLM call for demonstration.
        In production, this would make actual API calls.
        """
        # Simulate latency
        time.sleep(random.uniform(0.1, 0.5))
        
        # Simulate response
        input_text = " ".join(m.get("content", "") for m in messages)
        input_tokens = self._estimate_tokens(input_text)
        
        # Generate mock response
        response_text = f"Response from {provider.model_name} based on {len(messages)} messages."
        output_tokens = self._estimate_tokens(response_text)
        
        return response_text, input_tokens, output_tokens
    
    def _calculate_cost(
        self,
        provider: LLMProvider,
        input_tokens: int,
        output_tokens: int,
    ) -> Decimal:
        """Calculate cost in USD."""
        input_cost = (Decimal(input_tokens) / 1000) * provider.cost_per_1k_input
        output_cost = (Decimal(output_tokens) / 1000) * provider.cost_per_1k_output
        return input_cost + output_cost
    
    def _attempt_structured_output(
        self,
        provider: LLMProvider,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        validation_fn: Callable[[str], Any],
        max_repair_attempts: int = 2,
    ) -> Tuple[Any, int, int, int]:
        """
        Attempt to get valid structured output with self-repair.
        Returns: (parsed_result, input_tokens, output_tokens, repair_attempts)
        """
        last_error = None
        
        for attempt in range(max_repair_attempts + 1):
            try:
                response_text, input_tokens, output_tokens = self._simulate_llm_call(
                    provider, messages, temperature, max_tokens
                )
                
                # Validate
                parsed = validation_fn(response_text)
                return parsed, input_tokens, output_tokens, attempt
                
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                # Feed error back to LLM for repair
                repair_msg = {
                    "role": "user",
                    "content": f"Previous response failed validation: {str(e)}. Please fix and return valid JSON only."
                }
                messages = messages + [repair_msg]
                
                # Compress if needed
                total_tokens = sum(self._estimate_tokens(m.get("content", "")) for m in messages)
                if total_tokens > self.max_context_tokens * 0.9:
                    messages = self.compression_strategy.compress(messages, self.max_context_tokens)
        
        raise ValueError(f"Failed to generate valid output after {max_repair_attempts} repair attempts: {last_error}")
    
    def execute(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        validate_response: Optional[Callable[[str], Any]] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute LLM call with retry, fallback, and validation.
        
        Args:
            messages: Chat messages
            temperature: Sampling temperature
            max_tokens: Max output tokens
            validate_response: Optional validation function for structured output
            trace_id: Optional trace ID for tracking
            
        Returns:
            Dict with 'response', 'provider', 'input_tokens', 'output_tokens', 'cost', 'trace_id'
        """
        trace_id = trace_id or self.trace_id_generator()
        start_time = time.time()
        
        current_messages = list(messages)
        current_provider_idx = 0
        retry_count = 0
        last_error = None
        
        while current_provider_idx < len(self.providers):
            provider = self.providers[current_provider_idx]
            
            # Check context length and compress if needed
            total_tokens = sum(self._estimate_tokens(m.get("content", "")) for m in current_messages)
            if total_tokens > self.max_context_tokens * 0.9:
                current_messages = self.compression_strategy.compress(current_messages, self.max_context_tokens)
            
            try:
                if validate_response:
                    # Structured output with self-repair
                    result, input_tokens, output_tokens, repair_attempts = self._attempt_structured_output(
                        provider, current_messages, temperature, max_tokens, validate_response
                    )
                else:
                    # Standard call
                    response_text, input_tokens, output_tokens = self._simulate_llm_call(
                        provider, current_messages, temperature, max_tokens
                    )
                    result = response_text
                
                # Success
                latency_ms = (time.time() - start_time) * 1000
                cost = self._calculate_cost(provider, input_tokens, output_tokens)
                
                record = LLMCallRecord(
                    trace_id=trace_id,
                    provider_name=provider.name,
                    model_name=provider.model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    cost_usd=cost,
                    success=True,
                    error_type=None,
                    retry_count=retry_count,
                )
                
                with self._lock:
                    self._call_history.append(record)
                    self._cost_tracker[trace_id] = cost
                
                return {
                    "response": result,
                    "provider": provider.name,
                    "model": provider.model_name,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": cost,
                    "trace_id": trace_id,
                    "latency_ms": latency_ms,
                }
                
            except Exception as e:
                error_type = self._classify_error(e)
                last_error = e
                
                # Check retry strategy
                if self.retry_strategy.should_retry(error_type, retry_count):
                    delay = self.retry_strategy.get_delay(retry_count)
                    time.sleep(delay)
                    retry_count += 1
                    continue
                
                # Try fallback provider
                current_provider_idx += 1
                retry_count = 0  # Reset retry count for new provider
        
        # All providers exhausted
        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")
    
    def get_call_history(self, limit: int = 100) -> List[LLMCallRecord]:
        """Get recent call history."""
        with self._lock:
            return list(reversed(self._call_history[-limit:]))
    
    def get_total_cost(self, trace_id: Optional[str] = None) -> Decimal:
        """Get total cost, optionally filtered by trace_id."""
        with self._lock:
            if trace_id:
                return self._cost_tracker.get(trace_id, Decimal("0"))
            return sum(self._cost_tracker.values(), Decimal("0"))


# Default providers configuration
DEFAULT_PROVIDERS = [
    LLMProvider(
        name="primary",
        api_key_env="ANTHROPIC_API_KEY",
        base_url="https://api.anthropic.com",
        model_name="claude-sonnet-4-5-20250929",
        max_tokens=8192,
        cost_per_1k_input=Decimal("0.003"),
        cost_per_1k_output=Decimal("0.015"),
        timeout_seconds=30.0,
        priority=1,
    ),
    LLMProvider(
        name="fallback",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com",
        model_name="gpt-4o-mini",
        max_tokens=4096,
        cost_per_1k_input=Decimal("0.00015"),
        cost_per_1k_output=Decimal("0.0006"),
        timeout_seconds=20.0,
        priority=2,
    ),
]
