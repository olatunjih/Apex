"""
APEX v3 A2UI JSONL Protocol Handler - §38, §41, §86

Implements JSON Lines (JSONL) streaming protocol for real-time UI communication.
Supports bidirectional event streaming between backend and frontend.

Spec Compliance:
- §38: Canvas Layer event streaming
- §41: War Room UI real-time updates
- §86: WebSocket/JSONL event integration

Protocol Format:
    Each line is a complete JSON object with:
    - type: Event type (canvas_update, panel_bind, thought_step, etc.)
    - trace_id: Request/session trace identifier
    - timestamp: ISO 8601 UTC timestamp
    - sequence: Monotonically increasing sequence number
    - payload: Event-specific data
"""

from __future__ import annotations

import json
import time
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Protocol, AsyncIterator, Iterator
from collections import deque
import io


class EventType(str, Enum):
    """A2UI JSONL event types."""
    
    # Canvas Events (§38)
    CANVAS_ELEMENT_ADDED = "canvas_element_added"
    CANVAS_ELEMENT_UPDATED = "canvas_element_updated"
    CANVAS_ELEMENT_REMOVED = "canvas_element_removed"
    CANVAS_RENDER_COMPLETE = "canvas_render_complete"
    CANVAS_LAYOUT_CHANGED = "canvas_layout_changed"
    
    # Panel Events (§41)
    PANEL_CREATED = "panel_created"
    PANEL_RESIZED = "panel_resized"
    PANEL_CONTENT_BOUND = "panel_content_bound"
    PANEL_CONTENT_UPDATE = "panel_content_update"
    PANEL_TAB_SWITCHED = "panel_tab_switched"
    PANEL_COLLAPSED = "panel_collapsed"
    PANEL_EXPANDED = "panel_expanded"
    
    # Thought Process Inspector (§57)
    THOUGHT_STEP_RECORDED = "thought_step_recorded"
    THOUGHT_DISAGREEMENT_SUBMITTED = "thought_disagreement_submitted"
    THOUGHT_DISAGREEMENT_RESOLVED = "thought_disagreement_resolved"
    THOUGHT_TRACE_COMPLETE = "thought_trace_complete"
    
    # LLM Integration Events
    LLM_CALL_STARTED = "llm_call_started"
    LLM_CALL_COMPLETED = "llm_call_completed"
    LLM_STREAMING_CHUNK = "llm_streaming_chunk"
    LLM_RETRY = "llm_retry"
    LLM_FALLBACK = "llm_fallback"
    
    # Tool Execution Events
    TOOL_EXECUTION_STARTED = "tool_execution_started"
    TOOL_EXECUTION_COMPLETED = "tool_execution_completed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    TOOL_OUTPUT_AVAILABLE = "tool_output_available"
    
    # Memory/Cognitive Events
    MEMORY_UPSERTED = "memory_upserted"
    MEMORY_ACCESSED = "memory_accessed"
    MEMORY_EVICTED = "memory_evicted"
    FAILURE_RECORDED = "failure_recorded"
    
    # System Events
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    ACK = "ack"  # Acknowledgment


@dataclass(frozen=True)
class JSONLEvent:
    """
    Base JSONL event structure.
    
    All events follow this schema for consistency and parsing.
    """
    type: EventType
    trace_id: str
    timestamp: str
    sequence: int
    payload: Dict[str, Any]
    session_id: str = ""
    source: str = "backend"  # backend/frontend/system
    
    def to_jsonl(self) -> str:
        """Serialize to JSONL line format."""
        return json.dumps(self._to_dict(), separators=(',', ':'))
    
    def _to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper serialization."""
        return {
            'type': self.type.value,
            'trace_id': self.trace_id,
            'timestamp': self.timestamp,
            'sequence': self.sequence,
            'payload': self._serialize_payload(self.payload),
            'session_id': self.session_id,
            'source': self.source,
        }
    
    @staticmethod
    def _serialize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively serialize payload for JSON compatibility."""
        if not isinstance(payload, dict):
            return payload
        
        result = {}
        for key, value in payload.items():
            if isinstance(value, Decimal):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, Enum):
                result[key] = value.value
            elif hasattr(value, '__dataclass_fields__'):
                result[key] = asdict(value)
            elif isinstance(value, dict):
                result[key] = JSONLEvent._serialize_payload(value)
            elif isinstance(value, list):
                result[key] = [
                    JSONLEvent._serialize_payload(item) if isinstance(item, dict)
                    else str(item) if isinstance(item, Decimal)
                    else item.isoformat() if isinstance(item, datetime)
                    else item.value if isinstance(item, Enum)
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result
    
    @classmethod
    def from_jsonl(cls, line: str) -> JSONLEvent:
        """Parse from JSONL line format."""
        data = json.loads(line.strip())
        return cls(
            type=EventType(data['type']),
            trace_id=data['trace_id'],
            timestamp=data['timestamp'],
            sequence=data['sequence'],
            payload=data.get('payload', {}),
            session_id=data.get('session_id', ''),
            source=data.get('source', 'backend'),
        )


@dataclass
class SequenceCounter:
    """Thread-safe sequence counter for event ordering."""
    _value: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def next(self) -> int:
        """Get next sequence number."""
        with self._lock:
            self._value += 1
            return self._value
    
    def reset(self) -> None:
        """Reset counter."""
        with self._lock:
            self._value = 0


class JSONLEventBuffer:
    """
    Bounded buffer for JSONL events with overflow handling.
    
    Provides thread-safe enqueue/dequeue with configurable capacity.
    Supports multiple consumers via subscription.
    """
    
    def __init__(self, max_size: int = 10000):
        self._buffer: deque[JSONLEvent] = deque(maxlen=max_size)
        self._max_size = max_size
        self._lock = threading.RLock()
        self._subscribers: List[Callable[[JSONLEvent], None]] = []
        self._dropped_count = 0
    
    def append(self, event: JSONLEvent) -> bool:
        """
        Append event to buffer.
        
        Returns True if appended successfully, False if buffer was full
        and event was dropped (though with deque maxlen, it auto-evicts).
        """
        with self._lock:
            was_full = len(self._buffer) >= self._max_size
            self._buffer.append(event)
            
            if was_full:
                self._dropped_count += 1
            
            # Notify subscribers
            for callback in self._subscribers:
                try:
                    callback(event)
                except Exception:
                    pass  # Don't let subscriber errors break the pipeline
            
            return True
    
    def extend(self, events: List[JSONLEvent]) -> int:
        """Append multiple events. Returns count actually added."""
        count = 0
        for event in events:
            if self.append(event):
                count += 1
        return count
    
    def pop(self) -> Optional[JSONLEvent]:
        """Remove and return oldest event."""
        with self._lock:
            if not self._buffer:
                return None
            return self._buffer.popleft()
    
    def peek(self) -> Optional[JSONLEvent]:
        """View oldest event without removing."""
        with self._lock:
            if not self._buffer:
                return None
            return self._buffer[0]
    
    def drain(self, limit: Optional[int] = None) -> List[JSONLEvent]:
        """Remove and return up to `limit` events (or all if None)."""
        with self._lock:
            if limit is None:
                events = list(self._buffer)
                self._buffer.clear()
                return events
            else:
                events = [self._buffer.popleft() for _ in range(min(limit, len(self._buffer)))]
                return events
    
    def subscribe(self, callback: Callable[[JSONLEvent], None]) -> None:
        """Subscribe to new events."""
        with self._lock:
            self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[JSONLEvent], None]) -> None:
        """Unsubscribe from events."""
        with self._lock:
            self._subscribers = [cb for cb in self._subscribers if cb != callback]
    
    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        with self._lock:
            return {
                'size': len(self._buffer),
                'max_size': self._max_size,
                'utilization': len(self._buffer) / self._max_size if self._max_size > 0 else 0,
                'dropped_count': self._dropped_count,
                'subscriber_count': len(self._subscribers),
            }
    
    def clear(self) -> None:
        """Clear all events."""
        with self._lock:
            self._buffer.clear()


class JSONLStreamWriter:
    """
    JSONL stream writer for file-like objects.
    
    Writes events as newline-delimited JSON with optional flushing.
    Thread-safe with sequence management.
    """
    
    def __init__(
        self,
        output: io.TextIOBase,
        session_id: str = "",
        trace_id: str = "",
        auto_flush: bool = True,
    ):
        self._output = output
        self._session_id = session_id
        self._trace_id = trace_id
        self._auto_flush = auto_flush
        self._sequence = SequenceCounter()
        self._lock = threading.Lock()
        self._event_count = 0
        self._started_at = datetime.now(timezone.utc)
    
    def write(self, event_type: EventType, payload: Dict[str, Any]) -> JSONLEvent:
        """Write an event to the stream."""
        event = JSONLEvent(
            type=event_type,
            trace_id=self._trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            sequence=self._sequence.next(),
            payload=payload,
            session_id=self._session_id,
            source='backend',
        )
        
        with self._lock:
            self._output.write(event.to_jsonl())
            self._output.write('\n')
            
            if self._auto_flush:
                self._output.flush()
            
            self._event_count += 1
        
        return event
    
    def write_batch(self, events: List[tuple[EventType, Dict[str, Any]]]) -> int:
        """Write multiple events atomically. Returns count written."""
        with self._lock:
            for event_type, payload in events:
                event = JSONLEvent(
                    type=event_type,
                    trace_id=self._trace_id,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    sequence=self._sequence.next(),
                    payload=payload,
                    session_id=self._session_id,
                    source='backend',
                )
                self._output.write(event.to_jsonl())
                self._output.write('\n')
                self._event_count += 1
            
            if self._auto_flush:
                self._output.flush()
        
        return len(events)
    
    def flush(self) -> None:
        """Flush the output stream."""
        with self._lock:
            self._output.flush()
    
    def close(self) -> None:
        """Close the stream with session end event."""
        self.write(EventType.SESSION_ENDED, {'reason': 'stream_closed'})
        with self._lock:
            self._output.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get writer statistics."""
        with self._lock:
            return {
                'event_count': self._event_count,
                'session_id': self._session_id,
                'trace_id': self._trace_id,
                'started_at': self._started_at.isoformat(),
                'duration_seconds': (datetime.now(timezone.utc) - self._started_at).total_seconds(),
            }


class JSONLStreamReader:
    """
    JSONL stream reader for parsing incoming events.
    
    Provides iterator interface over JSONL lines with validation.
    """
    
    def __init__(self, input_stream: io.TextIOBase):
        self._input = input_stream
        self._line_count = 0
        self._error_count = 0
        self._last_error: Optional[str] = None
    
    def __iter__(self) -> Iterator[JSONLEvent]:
        return self
    
    def __next__(self) -> JSONLEvent:
        line = self._input.readline()
        if not line:
            raise StopIteration
        
        self._line_count += 1
        
        try:
            return JSONLEvent.from_jsonl(line)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self._error_count += 1
            self._last_error = str(e)
            raise
    
    def read_until(self, predicate: Callable[[JSONLEvent], bool], timeout: float = 30.0) -> Optional[JSONLEvent]:
        """Read events until one matches predicate or timeout expires."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                event = next(self)
                if predicate(event):
                    return event
            except StopIteration:
                return None
            except Exception:
                continue
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get reader statistics."""
        return {
            'line_count': self._line_count,
            'error_count': self._error_count,
            'last_error': self._last_error,
        }


class A2UIProtocolHandler:
    """
    Main A2UI JSONL protocol handler.
    
    Coordinates event generation, buffering, and streaming.
    Provides high-level API for UI components to emit events.
    
    Usage:
        handler = A2UIProtocolHandler(session_id="sess_123", trace_id="trace_456")
        
        # Canvas update
        handler.emit_canvas_update(
            element_id="chart_1",
            render_type="candlestick_chart",
            data={"candles": [...]}
        )
        
        # Panel binding
        handler.emit_panel_bind(
            panel_id="main_canvas",
            content_type="canvas",
            content_id="chart_1"
        )
        
        # Get JSONL stream
        for event in handler.stream_events():
            process(event)
    """
    
    def __init__(
        self,
        session_id: str = "",
        trace_id: str = "",
        buffer_size: int = 10000,
    ):
        self._session_id = session_id
        self._trace_id = trace_id
        self._buffer = JSONLEventBuffer(max_size=buffer_size)
        self._sequence = SequenceCounter()
        self._lock = threading.RLock()
        self._active = True
        
        # Emit session start event
        self._emit_system_event(EventType.SESSION_STARTED, {
            'session_id': session_id,
            'trace_id': trace_id,
            'started_at': datetime.now(timezone.utc).isoformat(),
        })
    
    def _emit_system_event(self, event_type: EventType, payload: Dict[str, Any]) -> JSONLEvent:
        """Emit a system event."""
        event = JSONLEvent(
            type=event_type,
            trace_id=self._trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            sequence=self._sequence.next(),
            payload=payload,
            session_id=self._session_id,
            source='system',
        )
        self._buffer.append(event)
        return event
    
    def emit_canvas_element_added(
        self,
        element_id: str,
        render_type: str,
        config: Dict[str, Any],
        position: Dict[str, int],
    ) -> JSONLEvent:
        """Emit canvas element added event."""
        return self._emit_system_event(EventType.CANVAS_ELEMENT_ADDED, {
            'element_id': element_id,
            'render_type': render_type,
            'config': config,
            'position': position,
        })
    
    def emit_canvas_element_updated(
        self,
        element_id: str,
        updates: Dict[str, Any],
    ) -> JSONLEvent:
        """Emit canvas element updated event."""
        return self._emit_system_event(EventType.CANVAS_ELEMENT_UPDATED, {
            'element_id': element_id,
            'updates': updates,
        })
    
    def emit_canvas_element_removed(self, element_id: str) -> JSONLEvent:
        """Emit canvas element removed event."""
        return self._emit_system_event(EventType.CANVAS_ELEMENT_REMOVED, {
            'element_id': element_id,
        })
    
    def emit_canvas_render_complete(
        self,
        element_id: str,
        render_type: str,
        latency_ms: float,
    ) -> JSONLEvent:
        """Emit canvas render complete event."""
        return self._emit_system_event(EventType.CANVAS_RENDER_COMPLETE, {
            'element_id': element_id,
            'render_type': render_type,
            'latency_ms': latency_ms,
        })
    
    def emit_canvas_layout_changed(
        self,
        layout_mode: str,
        elements: List[str],
    ) -> JSONLEvent:
        """Emit canvas layout changed event."""
        return self._emit_system_event(EventType.CANVAS_LAYOUT_CHANGED, {
            'layout_mode': layout_mode,
            'elements': elements,
        })
    
    def emit_panel_created(
        self,
        panel_id: str,
        panel_type: str,
        config: Dict[str, Any],
    ) -> JSONLEvent:
        """Emit panel created event."""
        return self._emit_system_event(EventType.PANEL_CREATED, {
            'panel_id': panel_id,
            'panel_type': panel_type,
            'config': config,
        })
    
    def emit_panel_resized(
        self,
        panel_id: str,
        width_pct: float,
        height_pct: float,
    ) -> JSONLEvent:
        """Emit panel resized event."""
        return self._emit_system_event(EventType.PANEL_RESIZED, {
            'panel_id': panel_id,
            'width_pct': width_pct,
            'height_pct': height_pct,
        })
    
    def emit_panel_content_bound(
        self,
        panel_id: str,
        content_type: str,
        content_id: str,
        binding_config: Dict[str, Any],
    ) -> JSONLEvent:
        """Emit panel content bound event."""
        return self._emit_system_event(EventType.PANEL_CONTENT_BOUND, {
            'panel_id': panel_id,
            'content_type': content_type,
            'content_id': content_id,
            'binding_config': binding_config,
        })
    
    def emit_panel_content_update(
        self,
        panel_id: str,
        content_delta: Dict[str, Any],
    ) -> JSONLEvent:
        """Emit panel content update event."""
        return self._emit_system_event(EventType.PANEL_CONTENT_UPDATE, {
            'panel_id': panel_id,
            'content_delta': content_delta,
        })
    
    def emit_panel_tab_switched(
        self,
        tab_name: str,
        previous_tab: Optional[str],
    ) -> JSONLEvent:
        """Emit panel tab switched event."""
        return self._emit_system_event(EventType.PANEL_TAB_SWITCHED, {
            'tab_name': tab_name,
            'previous_tab': previous_tab,
        })
    
    def emit_thought_step_recorded(
        self,
        step_name: str,
        confidence_before: float,
        confidence_after: float,
        directional_change: Optional[str],
    ) -> JSONLEvent:
        """Emit thought step recorded event."""
        return self._emit_system_event(EventType.THOUGHT_STEP_RECORDED, {
            'step_name': step_name,
            'confidence_before': confidence_before,
            'confidence_after': confidence_after,
            'directional_change': directional_change,
        })
    
    def emit_thought_disagreement_submitted(
        self,
        step_name: str,
        disagreement_type: str,
        user_comment: str,
    ) -> JSONLEvent:
        """Emit thought disagreement submitted event."""
        return self._emit_system_event(EventType.THOUGHT_DISAGREEMENT_SUBMITTED, {
            'step_name': step_name,
            'disagreement_type': disagreement_type,
            'user_comment': user_comment,
        })
    
    def emit_thought_disagreement_resolved(
        self,
        step_name: str,
        resolution: str,
        confidence_adjustment: float,
    ) -> JSONLEvent:
        """Emit thought disagreement resolved event."""
        return self._emit_system_event(EventType.THOUGHT_DISAGREEMENT_RESOLVED, {
            'step_name': step_name,
            'resolution': resolution,
            'confidence_adjustment': confidence_adjustment,
        })
    
    def emit_thought_trace_complete(
        self,
        total_steps: int,
        final_confidence: float,
    ) -> JSONLEvent:
        """Emit thought trace complete event."""
        return self._emit_system_event(EventType.THOUGHT_TRACE_COMPLETE, {
            'total_steps': total_steps,
            'final_confidence': final_confidence,
        })
    
    def emit_llm_call_started(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
    ) -> JSONLEvent:
        """Emit LLM call started event."""
        return self._emit_system_event(EventType.LLM_CALL_STARTED, {
            'provider': provider,
            'model': model,
            'prompt_tokens': prompt_tokens,
        })
    
    def emit_llm_call_completed(
        self,
        provider: str,
        model: str,
        completion_tokens: int,
        latency_ms: float,
        cost_usd: str,
    ) -> JSONLEvent:
        """Emit LLM call completed event."""
        return self._emit_system_event(EventType.LLM_CALL_COMPLETED, {
            'provider': provider,
            'model': model,
            'completion_tokens': completion_tokens,
            'latency_ms': latency_ms,
            'cost_usd': cost_usd,
        })
    
    def emit_llm_streaming_chunk(
        self,
        chunk_index: int,
        token_count: int,
        text: str,
    ) -> JSONLEvent:
        """Emit LLM streaming chunk event."""
        return self._emit_system_event(EventType.LLM_STREAMING_CHUNK, {
            'chunk_index': chunk_index,
            'token_count': token_count,
            'text': text,
        })
    
    def emit_llm_retry(
        self,
        attempt: int,
        error_type: str,
        delay_seconds: float,
    ) -> JSONLEvent:
        """Emit LLM retry event."""
        return self._emit_system_event(EventType.LLM_RETRY, {
            'attempt': attempt,
            'error_type': error_type,
            'delay_seconds': delay_seconds,
        })
    
    def emit_llm_fallback(
        self,
        from_provider: str,
        to_provider: str,
        reason: str,
    ) -> JSONLEvent:
        """Emit LLM fallback event."""
        return self._emit_system_event(EventType.LLM_FALLBACK, {
            'from_provider': from_provider,
            'to_provider': to_provider,
            'reason': reason,
        })
    
    def emit_tool_execution_started(
        self,
        tool_id: str,
        input_data: Dict[str, Any],
    ) -> JSONLEvent:
        """Emit tool execution started event."""
        return self._emit_system_event(EventType.TOOL_EXECUTION_STARTED, {
            'tool_id': tool_id,
            'input_data': input_data,
        })
    
    def emit_tool_execution_completed(
        self,
        tool_id: str,
        execution_id: str,
        duration_ms: float,
        output_summary: Dict[str, Any],
    ) -> JSONLEvent:
        """Emit tool execution completed event."""
        return self._emit_system_event(EventType.TOOL_EXECUTION_COMPLETED, {
            'tool_id': tool_id,
            'execution_id': execution_id,
            'duration_ms': duration_ms,
            'output_summary': output_summary,
        })
    
    def emit_tool_execution_failed(
        self,
        tool_id: str,
        error_code: str,
        error_message: str,
    ) -> JSONLEvent:
        """Emit tool execution failed event."""
        return self._emit_system_event(EventType.TOOL_EXECUTION_FAILED, {
            'tool_id': tool_id,
            'error_code': error_code,
            'error_message': error_message,
        })
    
    def emit_tool_output_available(
        self,
        tool_id: str,
        data_id: str,
        data_type: str,
    ) -> JSONLEvent:
        """Emit tool output available event."""
        return self._emit_system_event(EventType.TOOL_OUTPUT_AVAILABLE, {
            'tool_id': tool_id,
            'data_id': data_id,
            'data_type': data_type,
        })
    
    def emit_memory_upserted(
        self,
        ticker: str,
        thesis_hash: str,
        confidence: float,
    ) -> JSONLEvent:
        """Emit memory upserted event."""
        return self._emit_system_event(EventType.MEMORY_UPSERTED, {
            'ticker': ticker,
            'thesis_hash': thesis_hash,
            'confidence': confidence,
        })
    
    def emit_memory_accessed(
        self,
        ticker: str,
        access_type: str,  # read/write/update
    ) -> JSONLEvent:
        """Emit memory accessed event."""
        return self._emit_system_event(EventType.MEMORY_ACCESSED, {
            'ticker': ticker,
            'access_type': access_type,
        })
    
    def emit_memory_evicted(
        self,
        ticker: str,
        reason: str,
    ) -> JSONLEvent:
        """Emit memory evicted event."""
        return self._emit_system_event(EventType.MEMORY_EVICTED, {
            'ticker': ticker,
            'reason': reason,
        })
    
    def emit_failure_recorded(
        self,
        failure_id: str,
        ticker: str,
        strategy: str,
        realized_return_bps: float,
    ) -> JSONLEvent:
        """Emit failure recorded event."""
        return self._emit_system_event(EventType.FAILURE_RECORDED, {
            'failure_id': failure_id,
            'ticker': ticker,
            'strategy': strategy,
            'realized_return_bps': realized_return_bps,
        })
    
    def emit_heartbeat(self) -> JSONLEvent:
        """Emit heartbeat event."""
        return self._emit_system_event(EventType.HEARTBEAT, {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'buffer_size': len(self._buffer),
        })
    
    def emit_error(
        self,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> JSONLEvent:
        """Emit error event."""
        return self._emit_system_event(EventType.ERROR, {
            'error_code': error_code,
            'message': message,
            'details': details or {},
        })
    
    def stream_events(self) -> Iterator[JSONLEvent]:
        """Stream events from buffer as they arrive."""
        while self._active:
            event = self._buffer.pop()
            if event:
                yield event
            else:
                time.sleep(0.01)  # Small sleep to avoid busy-waiting
    
    def drain_events(self, limit: Optional[int] = None) -> List[JSONLEvent]:
        """Drain events from buffer."""
        return self._buffer.drain(limit=limit)
    
    def subscribe(self, callback: Callable[[JSONLEvent], None]) -> None:
        """Subscribe to new events."""
        self._buffer.subscribe(callback)
    
    def unsubscribe(self, callback: Callable[[JSONLEvent], None]) -> None:
        """Unsubscribe from events."""
        self._buffer.unsubscribe(callback)
    
    def get_buffer_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        return self._buffer.get_stats()
    
    def shutdown(self) -> None:
        """Shutdown the protocol handler."""
        self._active = False
        self._emit_system_event(EventType.SESSION_ENDED, {
            'reason': 'shutdown',
            'final_buffer_size': len(self._buffer),
        })
    
    @property
    def session_id(self) -> str:
        return self._session_id
    
    @property
    def trace_id(self) -> str:
        return self._trace_id
    
    @property
    def is_active(self) -> bool:
        return self._active


# Convenience functions for quick usage

def create_jsonl_writer(
    output: io.TextIOBase,
    session_id: str = "",
    trace_id: str = "",
) -> JSONLStreamWriter:
    """Create a JSONL stream writer."""
    return JSONLStreamWriter(output=output, session_id=session_id, trace_id=trace_id)


def create_jsonl_reader(input_stream: io.TextIOBase) -> JSONLStreamReader:
    """Create a JSONL stream reader."""
    return JSONLStreamReader(input_stream=input_stream)


def create_protocol_handler(
    session_id: str = "",
    trace_id: str = "",
    buffer_size: int = 10000,
) -> A2UIProtocolHandler:
    """Create an A2UI protocol handler."""
    return A2UIProtocolHandler(
        session_id=session_id,
        trace_id=trace_id,
        buffer_size=buffer_size,
    )
