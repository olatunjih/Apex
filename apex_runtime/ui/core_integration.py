"""
APEX v3 Core Integration Layer - §38, §41, §57, §86

Integrates LLM orchestration, tool execution, memory/cognitive layer,
and UI protocol handling into a unified coordination layer.

Spec Compliance:
- §38: Canvas Layer integration with live updates
- §41: War Room UI panel binding management
- §57: Thought Process Inspector integration
- §86: JSONL event streaming
- §9: Why Engine integration
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Protocol, TypeVar
from collections import deque
import io

# Import from sibling modules
from .jsonl_protocol import (
    A2UIProtocolHandler,
    EventType,
    JSONLEvent,
    create_protocol_handler,
)
from .panel_binding import (
    PanelBindingManager,
    BindingConfig,
    BindingMode,
    UpdateStrategy,
    ContentType,
    SimpleContentSource,
    StreamContentSource,
    ContentMetadata,
    ContentSource,
    create_binding_manager,
)


class IntegrationPhase(str, Enum):
    """Phases of the integration lifecycle."""
    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    AWAITING_USER_INPUT = "awaiting_user_input"
    SHUTTING_DOWN = "shutting_down"
    ERROR = "error"


@dataclass(frozen=True)
class IntegrationContext:
    """
    Context object passed through the integration pipeline.
    
    Carries state between LLM calls, tool executions, and UI updates.
    """
    session_id: str
    trace_id: str
    user_intent: str
    ticker: Optional[str] = None
    phase: IntegrationPhase = IntegrationPhase.INITIALIZING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # State carriers
    llm_messages: tuple = ()  # Conversation history
    tool_results: tuple = ()  # Executed tool results
    memory_records: tuple = ()  # Retrieved/updated memory
    canvas_elements: tuple = ()  # Active canvas elements
    
    # Metrics
    llm_call_count: int = 0
    tool_call_count: int = 0
    total_latency_ms: float = 0.0
    total_cost_usd: Decimal = Decimal("0")
    
    # User interaction
    user_disagreements: tuple = ()  # Submitted disagreements
    confidence_score: float = 0.0
    
    def with_updates(self, **kwargs) -> IntegrationContext:
        """Create updated copy."""
        updates = {
            'updated_at': datetime.now(timezone.utc),
            **kwargs
        }
        return IntegrationContext(
            session_id=self.session_id,
            trace_id=self.trace_id,
            user_intent=self.user_intent,
            ticker=self.ticker or kwargs.get('ticker'),
            phase=kwargs.get('phase', self.phase),
            created_at=self.created_at,
            updated_at=updates['updated_at'],
            llm_messages=kwargs.get('llm_messages', self.llm_messages),
            tool_results=kwargs.get('tool_results', self.tool_results),
            memory_records=kwargs.get('memory_records', self.memory_records),
            canvas_elements=kwargs.get('canvas_elements', self.canvas_elements),
            llm_call_count=kwargs.get('llm_call_count', self.llm_call_count),
            tool_call_count=kwargs.get('tool_call_count', self.tool_call_count),
            total_latency_ms=kwargs.get('total_latency_ms', self.total_latency_ms),
            total_cost_usd=kwargs.get('total_cost_usd', self.total_cost_usd),
            user_disagreements=kwargs.get('user_disagreements', self.user_disagreements),
            confidence_score=kwargs.get('confidence_score', self.confidence_score),
        )


T = TypeVar('T')


class LLMProvider(Protocol):
    """Protocol for LLM provider integration."""
    
    def call(
        self,
        messages: List[Dict[str, str]],
        trace_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Call LLM and return response."""
        ...
    
    def stream(
        self,
        messages: List[Dict[str, str]],
        trace_id: str,
        **kwargs
    ):
        """Stream LLM response."""
        ...


class ToolExecutor(Protocol):
    """Protocol for tool execution."""
    
    def execute(
        self,
        tool_id: str,
        inputs: Dict[str, Any],
        trace_id: str,
    ) -> Dict[str, Any]:
        """Execute a tool and return result."""
        ...
    
    def list_tools(self) -> List[str]:
        """List available tools."""
        ...


class MemoryStore(Protocol):
    """Protocol for memory/cognitive storage."""
    
    def get_thesis(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get thesis for a ticker."""
        ...
    
    def upsert_thesis(
        self,
        ticker: str,
        thesis: str,
        confidence: float,
        **kwargs
    ) -> str:
        """Store/update thesis."""
        ...
    
    def get_failures(self, ticker: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get failure history for a ticker."""
        ...
    
    def record_failure(
        self,
        ticker: str,
        reason: str,
        strategy: str,
        realized_return_bps: float,
    ) -> str:
        """Record a failure."""
        ...


class CanvasRenderer(Protocol):
    """Protocol for canvas rendering."""
    
    def render(
        self,
        render_type: str,
        data: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Render canvas element."""
        ...


@dataclass
class PipelineStep:
    """A step in the integration pipeline."""
    
    name: str
    handler: Callable[[IntegrationContext], IntegrationContext]
    description: str = ""
    optional: bool = False
    emits_event: Optional[EventType] = None
    
    def execute(self, context: IntegrationContext) -> IntegrationContext:
        """Execute this step."""
        try:
            result = self.handler(context)
            return result
        except Exception as e:
            if self.optional:
                # Log but continue
                return context
            raise


class IntegrationPipeline:
    """
    Main integration pipeline coordinating LLM, tools, memory, and UI.
    
    Provides a configurable sequence of processing steps with full
    observability via JSONL events.
    """
    
    def __init__(
        self,
        session_id: str,
        llm_provider: Optional[LLMProvider] = None,
        tool_executor: Optional[ToolExecutor] = None,
        memory_store: Optional[MemoryStore] = None,
        canvas_renderer: Optional[CanvasRenderer] = None,
        output_stream: Optional[io.TextIOBase] = None,
    ):
        self._session_id = session_id
        self._trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        
        # Components
        self._llm_provider = llm_provider
        self._tool_executor = tool_executor
        self._memory_store = memory_store
        self._canvas_renderer = canvas_renderer
        
        # Protocol handler for JSONL events
        self._protocol_handler = create_protocol_handler(
            session_id=session_id,
            trace_id=self._trace_id,
        )
        
        # Panel binding manager
        self._binding_manager = create_binding_manager()
        
        # Pipeline configuration
        self._steps: List[PipelineStep] = []
        self._active = False
        self._lock = threading.RLock()
        
        # Output stream for JSONL
        self._output_stream = output_stream
        if self._output_stream:
            self._setup_stream_output()
        
        # Register default steps
        self._register_default_steps()
    
    def _setup_stream_output(self) -> None:
        """Set up streaming output to file-like object."""
        def push_events(event: JSONLEvent):
            try:
                self._output_stream.write(event.to_jsonl())
                self._output_stream.write('\n')
                self._output_stream.flush()
            except Exception:
                pass
        
        self._protocol_handler.subscribe(push_events)
    
    def _register_default_steps(self) -> None:
        """Register default pipeline steps."""
        # These are stubs - actual implementation would integrate with real components
        self._steps.append(PipelineStep(
            name="initialize_context",
            handler=self._step_initialize_context,
            description="Initialize processing context",
        ))
        
        self._steps.append(PipelineStep(
            name="retrieve_memory",
            handler=self._step_retrieve_memory,
            description="Retrieve relevant memory records",
            optional=True,
        ))
        
        self._steps.append(PipelineStep(
            name="execute_tools",
            handler=self._step_execute_tools,
            description="Execute required tools",
            optional=True,
            emits_event=EventType.TOOL_EXECUTION_COMPLETED,
        ))
        
        self._steps.append(PipelineStep(
            name="llm_reasoning",
            handler=self._step_llm_reasoning,
            description="LLM reasoning and synthesis",
            emits_event=EventType.LLM_CALL_COMPLETED,
        ))
        
        self._steps.append(PipelineStep(
            name="update_memory",
            handler=self._step_update_memory,
            description="Update memory with new insights",
            optional=True,
            emits_event=EventType.MEMORY_UPSERTED,
        ))
        
        self._steps.append(PipelineStep(
            name="render_canvas",
            handler=self._step_render_canvas,
            description="Render canvas visualizations",
            optional=True,
            emits_event=EventType.CANVAS_RENDER_COMPLETE,
        ))
        
        self._steps.append(PipelineStep(
            name="emit_response",
            handler=self._step_emit_response,
            description="Emit final response to UI",
        ))
    
    def _step_initialize_context(self, ctx: IntegrationContext) -> IntegrationContext:
        """Initialize context with session metadata."""
        self._protocol_handler.emit_heartbeat()
        return ctx.with_updates(phase=IntegrationPhase.PROCESSING)
    
    def _step_retrieve_memory(self, ctx: IntegrationContext) -> IntegrationContext:
        """Retrieve memory records for the ticker."""
        if not self._memory_store or not ctx.ticker:
            return ctx
        
        try:
            thesis = self._memory_store.get_thesis(ctx.ticker)
            failures = self._memory_store.get_failures(ctx.ticker, limit=5)
            
            self._protocol_handler.emit_memory_accessed(ctx.ticker, "read")
            
            return ctx.with_updates(
                memory_records=(thesis,) if thesis else (),
            )
        except Exception:
            return ctx
    
    def _step_execute_tools(self, ctx: IntegrationContext) -> IntegrationContext:
        """Execute tools based on intent."""
        if not self._tool_executor:
            return ctx
        
        # Determine which tools to run based on intent
        # This is a simplified example
        tools_to_run = self._determine_tools_for_intent(ctx.user_intent, ctx.ticker)
        
        results = []
        for tool_id, inputs in tools_to_run:
            start_time = time.time()
            
            self._protocol_handler.emit_tool_execution_started(tool_id, inputs)
            
            try:
                result = self._tool_executor.execute(tool_id, inputs, ctx.trace_id)
                latency_ms = (time.time() - start_time) * 1000
                
                self._protocol_handler.emit_tool_execution_completed(
                    tool_id, result.get('execution_id', ''), latency_ms,
                    {'summary': str(result)[:200]}
                )
                
                results.append(result)
            except Exception as e:
                self._protocol_handler.emit_tool_execution_failed(
                    tool_id, "execution_error", str(e)
                )
        
        return ctx.with_updates(
            tool_results=tuple(results),
            tool_call_count=len(results),
        )
    
    def _step_llm_reasoning(self, ctx: IntegrationContext) -> IntegrationContext:
        """Perform LLM-based reasoning."""
        if not self._llm_provider:
            return ctx.with_updates(confidence_score=0.5)  # Default confidence
        
        start_time = time.time()
        
        # Build messages from context
        messages = list(ctx.llm_messages) if ctx.llm_messages else []
        
        # Add system message with context
        system_msg = self._build_system_message(ctx)
        messages.insert(0, system_msg)
        
        # Add user intent
        messages.append({"role": "user", "content": ctx.user_intent})
        
        self._protocol_handler.emit_llm_call_started(
            provider="primary",
            model="claude-sonnet-4-5-20250929",
            prompt_tokens=sum(len(m.get('content', '')) // 4 for m in messages),
        )
        
        try:
            response = self._llm_provider.call(messages, ctx.trace_id)
            latency_ms = (time.time() - start_time) * 1000
            
            completion_tokens = len(response.get('content', '')) // 4
            cost_usd = Decimal(str(response.get('cost_usd', '0')))
            
            self._protocol_handler.emit_llm_call_completed(
                provider="primary",
                model="claude-sonnet-4-5-20250929",
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                cost_usd=str(cost_usd),
            )
            
            return ctx.with_updates(
                llm_messages=tuple(messages + [{"role": "assistant", "content": response.get('content', '')}]),
                llm_call_count=ctx.llm_call_count + 1,
                total_latency_ms=ctx.total_latency_ms + latency_ms,
                total_cost_usd=ctx.total_cost_usd + cost_usd,
                confidence_score=response.get('confidence', 0.5),
            )
        except Exception as e:
            self._protocol_handler.emit_error("llm_error", str(e))
            return ctx.with_updates(confidence_score=0.3)
    
    def _step_update_memory(self, ctx: IntegrationContext) -> IntegrationContext:
        """Update memory with new insights."""
        if not self._memory_store or not ctx.ticker:
            return ctx
        
        # Extract thesis from LLM response
        last_message = ctx.llm_messages[-1] if ctx.llm_messages else {}
        thesis_text = last_message.get('content', '')[:1000]  # Truncate
        
        try:
            memory_id = self._memory_store.upsert_thesis(
                ticker=ctx.ticker,
                thesis=thesis_text,
                confidence=ctx.confidence_score,
            )
            
            thesis_hash = uuid.uuid4().hex[:16]
            self._protocol_handler.emit_memory_upserted(
                ctx.ticker, thesis_hash, ctx.confidence_score
            )
            
            return ctx
        except Exception:
            return ctx
    
    def _step_render_canvas(self, ctx: IntegrationContext) -> IntegrationContext:
        """Render canvas visualizations."""
        if not self._canvas_renderer:
            return ctx
        
        # Determine what to render based on context
        elements_to_render = self._determine_canvas_elements(ctx)
        
        rendered_elements = []
        for element_config in elements_to_render:
            try:
                rendered = self._canvas_renderer.render(
                    element_config['render_type'],
                    element_config['data'],
                    element_config.get('config', {}),
                )
                
                element_id = element_config.get('element_id', f"elem_{uuid.uuid4().hex[:8]}")
                
                self._protocol_handler.emit_canvas_element_added(
                    element_id,
                    element_config['render_type'],
                    element_config.get('config', {}),
                    element_config.get('position', {'x': 0, 'y': 0}),
                )
                
                self._protocol_handler.emit_canvas_render_complete(
                    element_id,
                    element_config['render_type'],
                    latency_ms=0,  # Would measure actual render time
                )
                
                rendered_elements.append({
                    'element_id': element_id,
                    'rendered': rendered,
                })
            except Exception:
                pass
        
        return ctx.with_updates(
            canvas_elements=tuple(rendered_elements),
        )
    
    def _step_emit_response(self, ctx: IntegrationContext) -> IntegrationContext:
        """Emit final response to UI."""
        # Set up panel bindings for the response content
        
        # Create content sources for different response types
        if ctx.llm_messages:
            llm_source = SimpleContentSource(
                content_type=ContentType.LLM_RESPONSE,
                initial_value=ctx.llm_messages[-1],
                source="integration_pipeline",
            )
            self._binding_manager.register_content_source(
                f"llm_response_{ctx.trace_id}", llm_source
            )
        
        if ctx.canvas_elements:
            canvas_source = SimpleContentSource(
                content_type=ContentType.CANVAS,
                initial_value=list(ctx.canvas_elements),
                source="integration_pipeline",
            )
            self._binding_manager.register_content_source(
                f"canvas_{ctx.trace_id}", canvas_source
            )
        
        return ctx.with_updates(phase=IntegrationPhase.AWAITING_USER_INPUT)
    
    def _determine_tools_for_intent(
        self,
        intent: str,
        ticker: Optional[str],
    ) -> List[tuple[str, Dict[str, Any]]]:
        """Determine which tools to run based on intent."""
        tools = []
        
        # Simple heuristic-based tool selection
        if any(word in intent.lower() for word in ['price', 'chart', 'graph']):
            if ticker:
                tools.append(("fetch_market_data", {"ticker": ticker, "interval": "1d", "bars": 100}))
        
        if any(word in intent.lower() for word in ['indicator', 'rsi', 'macd', 'sma']):
            if ticker:
                tools.append(("compute_indicators", {"ticker": ticker, "indicators": ["RSI", "MACD"]}))
        
        if any(word in intent.lower() for word in ['signal', 'recommendation', 'trade']):
            tools.append(("generate_signals", {"context": intent}))
        
        return tools
    
    def _determine_canvas_elements(self, ctx: IntegrationContext) -> List[Dict[str, Any]]:
        """Determine which canvas elements to render."""
        elements = []
        
        # Always show candlestick chart if we have ticker
        if ctx.ticker:
            elements.append({
                'element_id': f"chart_{ctx.ticker}",
                'render_type': 'candlestick_chart',
                'data': {'ticker': ctx.ticker},
                'config': {'width': 800, 'height': 400},
                'position': {'x': 0, 'y': 0},
            })
        
        # Show trade plan if confidence is high
        if ctx.confidence_score >= 0.7:
            elements.append({
                'render_type': 'trade_plan_card',
                'data': {
                    'ticker': ctx.ticker,
                    'confidence': ctx.confidence_score,
                },
                'config': {},
                'position': {'x': 0, 'y': 1},
            })
        
        # Show why explanation
        if ctx.llm_messages:
            elements.append({
                'render_type': 'why_engine_card',
                'data': {'explanation': ctx.llm_messages[-1].get('content', '')[:500]},
                'config': {},
                'position': {'x': 1, 'y': 0},
            })
        
        return elements
    
    def _build_system_message(self, ctx: IntegrationContext) -> Dict[str, str]:
        """Build system message for LLM."""
        context_parts = [
            "You are APEX, an advanced trading analysis system.",
            f"Session: {ctx.session_id}",
            f"Trace: {ctx.trace_id}",
        ]
        
        if ctx.ticker:
            context_parts.append(f"Analyzing ticker: {ctx.ticker}")
        
        if ctx.memory_records:
            context_parts.append("Previous thesis available.")
        
        if ctx.tool_results:
            context_parts.append(f"Tool results available: {len(ctx.tool_results)} executions.")
        
        return {
            "role": "system",
            "content": "\n".join(context_parts),
        }
    
    def add_step(
        self,
        name: str,
        handler: Callable[[IntegrationContext], IntegrationContext],
        description: str = "",
        optional: bool = False,
        before: Optional[str] = None,
        after: Optional[str] = None,
    ) -> None:
        """Add a custom step to the pipeline."""
        step = PipelineStep(
            name=name,
            handler=handler,
            description=description,
            optional=optional,
        )
        
        with self._lock:
            if before:
                for i, existing in enumerate(self._steps):
                    if existing.name == before:
                        self._steps.insert(i, step)
                        return
            elif after:
                for i, existing in enumerate(self._steps):
                    if existing.name == after:
                        self._steps.insert(i + 1, step)
                        return
            else:
                self._steps.append(step)
    
    def remove_step(self, name: str) -> bool:
        """Remove a step from the pipeline."""
        with self._lock:
            for i, step in enumerate(self._steps):
                if step.name == name:
                    self._steps.pop(i)
                    return True
            return False
    
    def execute(self, user_intent: str, ticker: Optional[str] = None) -> IntegrationContext:
        """Execute the full pipeline."""
        context = IntegrationContext(
            session_id=self._session_id,
            trace_id=self._trace_id,
            user_intent=user_intent,
            ticker=ticker,
        )
        
        self._active = True
        
        try:
            for step in self._steps:
                if not self._active:
                    break
                
                if step.emits_event:
                    # Emit step start event
                    pass
                
                context = step.execute(context)
            
            return context
        except Exception as e:
            self._protocol_handler.emit_error("pipeline_error", str(e))
            context = context.with_updates(phase=IntegrationPhase.ERROR)
            return context
        finally:
            self._active = False
    
    def bind_panel(
        self,
        panel_id: str,
        content_id: str,
        mode: BindingMode = BindingMode.OBSERVE,
        update_strategy: UpdateStrategy = UpdateStrategy.IMMEDIATE,
        push_callback: Optional[Callable[[str, Any], None]] = None,
    ) -> Optional[Any]:
        """Bind a panel to content."""
        config = BindingConfig(
            mode=mode,
            update_strategy=update_strategy,
        )
        
        def default_push(pid, data):
            self._protocol_handler.emit_panel_content_update(pid, {'delta': data})
        
        return self._binding_manager.bind_panel_to_content(
            panel_id, content_id, config,
            push_callback or default_push,
        )
    
    def get_binding_manager(self) -> PanelBindingManager:
        """Get the panel binding manager."""
        return self._binding_manager
    
    def get_protocol_handler(self) -> A2UIProtocolHandler:
        """Get the JSONL protocol handler."""
        return self._protocol_handler
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return {
            'session_id': self._session_id,
            'trace_id': self._trace_id,
            'active': self._active,
            'step_count': len(self._steps),
            'steps': [s.name for s in self._steps],
            'protocol_stats': self._protocol_handler.get_buffer_stats(),
            'binding_stats': self._binding_manager.get_stats(),
        }
    
    def shutdown(self) -> None:
        """Shutdown the pipeline."""
        self._active = False
        self._protocol_handler.shutdown()


def create_integration_pipeline(
    session_id: Optional[str] = None,
    llm_provider: Optional[LLMProvider] = None,
    tool_executor: Optional[ToolExecutor] = None,
    memory_store: Optional[MemoryStore] = None,
    canvas_renderer: Optional[CanvasRenderer] = None,
    output_stream: Optional[io.TextIOBase] = None,
) -> IntegrationPipeline:
    """Create a new integration pipeline."""
    return IntegrationPipeline(
        session_id=session_id or f"session_{uuid.uuid4().hex[:8]}",
        llm_provider=llm_provider,
        tool_executor=tool_executor,
        memory_store=memory_store,
        canvas_renderer=canvas_renderer,
        output_stream=output_stream,
    )


# Convenience classes for mock/testing implementations

class MockLLMProvider:
    """Mock LLM provider for testing."""
    
    def call(self, messages: List[Dict[str, str]], trace_id: str, **kwargs) -> Dict[str, Any]:
        return {
            'content': f"Mock response for: {messages[-1]['content'][:50]}...",
            'confidence': 0.75,
            'cost_usd': '0.001',
        }
    
    def stream(self, messages: List[Dict[str, str]], trace_id: str, **kwargs):
        yield {"chunk": "mock", "text": "streaming response"}


class MockToolExecutor:
    """Mock tool executor for testing."""
    
    def execute(self, tool_id: str, inputs: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        return {
            'execution_id': f"exec_{uuid.uuid4().hex[:8]}",
            'success': True,
            'data': {'mock': 'result'},
        }
    
    def list_tools(self) -> List[str]:
        return ['fetch_market_data', 'compute_indicators', 'generate_signals']


class MockMemoryStore:
    """Mock memory store for testing."""
    
    def __init__(self):
        self._theses: Dict[str, Dict[str, Any]] = {}
        self._failures: Dict[str, List[Dict[str, Any]]] = {}
    
    def get_thesis(self, ticker: str) -> Optional[Dict[str, Any]]:
        return self._theses.get(ticker)
    
    def upsert_thesis(
        self,
        ticker: str,
        thesis: str,
        confidence: float,
        **kwargs
    ) -> str:
        thesis_id = f"thesis_{uuid.uuid4().hex[:8]}"
        self._theses[ticker] = {
            'id': thesis_id,
            'thesis': thesis,
            'confidence': confidence,
        }
        return thesis_id
    
    def get_failures(self, ticker: str, limit: int = 10) -> List[Dict[str, Any]]:
        return self._failures.get(ticker, [])[:limit]
    
    def record_failure(
        self,
        ticker: str,
        reason: str,
        strategy: str,
        realized_return_bps: float,
    ) -> str:
        failure_id = f"failure_{uuid.uuid4().hex[:8]}"
        if ticker not in self._failures:
            self._failures[ticker] = []
        self._failures[ticker].append({
            'id': failure_id,
            'reason': reason,
            'strategy': strategy,
            'realized_return_bps': realized_return_bps,
        })
        return failure_id


class MockCanvasRenderer:
    """Mock canvas renderer for testing."""
    
    def render(
        self,
        render_type: str,
        data: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            'render_type': render_type,
            'data': data,
            'config': config,
            'status': 'rendered',
        }
