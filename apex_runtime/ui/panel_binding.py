"""
APEX v3 Panel Content Binding System - §41

Provides declarative binding between UI panels and data sources.
Supports LLM streams, tool outputs, memory records, and canvas elements.

Spec Compliance:
- §41: War Room UI panel management
- §38: Canvas Layer integration
- §86: Real-time event streaming
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Protocol, Union, TypeVar
from collections import defaultdict
import weakref


class ContentType(str, Enum):
    """Types of content that can be bound to panels."""
    
    # Canvas types (§38)
    CANVAS = "canvas"
    CANVAS_ELEMENT = "canvas_element"
    
    # LLM types
    LLM_STREAM = "llm_stream"
    LLM_RESPONSE = "llm_response"
    LLM_CONVERSATION = "llm_conversation"
    
    # Tool types
    TOOL_OUTPUT = "tool_output"
    TOOL_EXECUTION_LOG = "tool_execution_log"
    
    # Memory/Cognitive types
    MEMORY_RECORD = "memory_record"
    FAILURE_MEMORY = "failure_memory"
    THESIS = "thesis"
    
    # Analysis types
    TRADE_PLAN = "trade_plan"
    WHY_EXPLANATION = "why_explanation"
    REFLECTION = "reflection"
    SIGNAL = "signal"
    
    # Diagnostic types
    HEALTH_STATUS = "health_status"
    METRICS = "metrics"
    LOG_STREAM = "log_stream"
    
    # Custom
    CUSTOM = "custom"


class BindingMode(str, Enum):
    """How content is bound to a panel."""
    
    # One-way bindings
    OBSERVE = "observe"  # Panel observes content changes (read-only)
    DISPLAY = "display"  # Panel displays static content snapshot
    
    # Two-way bindings
    SYNC = "sync"  # Panel and content stay in sync (bidirectional)
    EDIT = "edit"  # Panel can modify content
    
    # Streaming bindings
    STREAM = "stream"  # Continuous stream of content updates
    APPEND = "append"  # Append-only stream (e.g., logs, chat)


class UpdateStrategy(str, Enum):
    """Strategy for pushing updates to bound panels."""
    
    IMMEDIATE = "immediate"  # Push every update immediately
    DEBOUNCE = "debounce"  # Wait for pause in updates
    THROTTLE = "throttle"  # Max one update per interval
    BATCH = "batch"  # Collect updates and send in batches
    MANUAL = "manual"  # Only push when explicitly requested


@dataclass(frozen=True)
class BindingConfig:
    """Configuration for a content binding."""
    
    mode: BindingMode
    update_strategy: UpdateStrategy = UpdateStrategy.IMMEDIATE
    debounce_ms: int = 100  # For DEBOUNCE strategy
    throttle_ms: int = 500  # For THROTTLE strategy
    batch_size: int = 10  # For BATCH strategy
    batch_interval_ms: int = 1000  # For BATCH strategy
    filter_expr: Optional[str] = None  # Optional filter expression
    transform_fn: Optional[str] = None  # Optional transform function name
    include_metadata: bool = True
    compression_enabled: bool = False
    
    def validate(self) -> bool:
        """Validate configuration consistency."""
        if self.mode == BindingMode.STREAM and self.update_strategy not in (
            UpdateStrategy.IMMEDIATE, UpdateStrategy.THROTTLE
        ):
            return False
        
        if self.debounce_ms < 0 or self.throttle_ms < 0 or self.batch_size < 1:
            return False
        
        return True


@dataclass(frozen=True)
class ContentMetadata:
    """Metadata about bound content."""
    
    content_id: str
    content_type: ContentType
    created_at: datetime
    updated_at: datetime
    version: int = 0
    source: str = ""  # Originating component (LLM, tool, memory, etc.)
    tags: tuple = ()
    size_bytes: int = 0
    checksum: str = ""


T = TypeVar('T')


class ContentSource(Protocol[T]):
    """Protocol for content sources that can be bound to panels."""
    
    def get_content(self) -> T:
        """Get current content."""
        ...
    
    def subscribe(self, callback: Callable[[T], None]) -> Callable[[], None]:
        """Subscribe to content changes. Returns unsubscribe function."""
        ...
    
    def get_metadata(self) -> ContentMetadata:
        """Get content metadata."""
        ...


@dataclass
class BoundContent:
    """Represents content bound to a panel."""
    
    content_id: str
    content_type: ContentType
    source: ContentSource
    config: BindingConfig
    metadata: ContentMetadata
    bound_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    update_count: int = 0
    last_pushed_at: Optional[datetime] = None
    
    def _serialize_value(self, value: Any) -> Any:
        """Serialize value for JSON transport."""
        if isinstance(value, Decimal):
            return str(value)
        elif isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, Enum):
            return value.value
        elif hasattr(value, '__dataclass_fields__'):
            from dataclasses import asdict
            return asdict(value)
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        else:
            return value


@dataclass(frozen=True)
class PanelBindingEvent:
    """Event emitted when binding state changes."""
    
    event_type: str  # bound, unbound, updated, error
    panel_id: str
    content_id: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)


class UpdateThrottler:
    """Handles update throttling/debouncing/batching."""
    
    def __init__(self, config: BindingConfig):
        self._config = config
        self._lock = threading.Lock()
        self._last_update: Optional[datetime] = None
        self._pending_updates: List[Any] = []
        self._timer: Optional[threading.Timer] = None
        self._scheduled_time: float = 0
    
    def schedule_update(self, update: Any, callback: Callable[[Any], None]) -> None:
        """Schedule an update based on strategy."""
        with self._lock:
            now = time.time()
            
            if self._config.update_strategy == UpdateStrategy.IMMEDIATE:
                callback(update)
                self._last_update = datetime.now(timezone.utc)
            
            elif self._config.update_strategy == UpdateStrategy.DEBOUNCE:
                if self._timer:
                    self._timer.cancel()
                
                self._pending_updates = [update]
                self._timer = threading.Timer(
                    self._config.debounce_ms / 1000.0,
                    lambda: self._flush_pending(callback)
                )
                self._timer.start()
            
            elif self._config.update_strategy == UpdateStrategy.THROTTLE:
                if self._last_update is None or \
                   (now - self._scheduled_time) >= (self._config.throttle_ms / 1000.0):
                    callback(update)
                    self._last_update = datetime.now(timezone.utc)
                    self._scheduled_time = now
            
            elif self._config.update_strategy == UpdateStrategy.BATCH:
                self._pending_updates.append(update)
                
                if len(self._pending_updates) >= self._config.batch_size:
                    self._flush_pending(callback)
                elif self._timer is None or not self._timer.is_alive():
                    self._timer = threading.Timer(
                        self._config.batch_interval_ms / 1000.0,
                        lambda: self._flush_pending(callback)
                    )
                    self._timer.start()
            
            elif self._config.update_strategy == UpdateStrategy.MANUAL:
                self._pending_updates.append(update)
    
    def _flush_pending(self, callback: Callable[[Any], None]) -> None:
        """Flush pending updates."""
        with self._lock:
            if self._pending_updates:
                if self._config.update_strategy == UpdateStrategy.BATCH:
                    callback(self._pending_updates.copy())
                else:
                    # For debounce, send last update
                    callback(self._pending_updates[-1] if self._pending_updates else None)
                self._pending_updates.clear()
                self._last_update = datetime.now(timezone.utc)
    
    def flush_now(self, callback: Callable[[Any], None]) -> None:
        """Force flush all pending updates."""
        self._flush_pending(callback)
    
    def cancel_pending(self) -> None:
        """Cancel any pending updates."""
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            self._pending_updates.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get throttler statistics."""
        with self._lock:
            return {
                'strategy': self._config.update_strategy.value,
                'pending_count': len(self._pending_updates),
                'last_update': self._last_update.isoformat() if self._last_update else None,
                'timer_active': self._timer.is_alive() if self._timer else False,
            }


class PanelContentBinding:
    """
    Manages binding between a panel and content source.
    
    Handles subscription, update propagation, and lifecycle.
    """
    
    def __init__(
        self,
        panel_id: str,
        content: BoundContent,
        push_callback: Callable[[str, Any], None],
    ):
        self._panel_id = panel_id
        self._content = content
        self._push_callback = push_callback
        self._throttler = UpdateThrottler(content.config)
        self._active = True
        self._unsubscribe: Optional[Callable[[], None]] = None
        self._error_count = 0
        self._lock = threading.Lock()
        
        # Start subscription if in observe/sync/stream mode
        if content.config.mode in (
            BindingMode.OBSERVE, BindingMode.SYNC, BindingMode.STREAM, BindingMode.APPEND
        ):
            self._start_subscription()
    
    def _start_subscription(self) -> None:
        """Start subscribing to content changes."""
        def on_update(value: Any):
            if not self._active:
                return
            
            try:
                serialized = self._content._serialize_value(value)
                
                def do_push(data):
                    with self._lock:
                        self._content.update_count += 1
                        self._content.last_pushed_at = datetime.now(timezone.utc)
                        self._push_callback(self._panel_id, data)
                
                self._throttler.schedule_update(serialized, do_push)
                self._error_count = 0
            except Exception as e:
                self._error_count += 1
                if self._error_count > 10:
                    self._active = False  # Stop on repeated errors
        
        try:
            self._unsubscribe = self._content.source.subscribe(on_update)
        except Exception as e:
            self._error_count += 1
    
    def push_now(self) -> Optional[Any]:
        """Push current content immediately."""
        try:
            content = self._content.source.get_content()
            serialized = self._content._serialize_value(content)
            self._push_callback(self._panel_id, serialized)
            
            with self._lock:
                self._content.update_count += 1
                self._content.last_pushed_at = datetime.now(timezone.utc)
            
            return serialized
        except Exception:
            return None
    
    def flush_pending(self) -> None:
        """Flush any pending updates."""
        def do_push(data):
            if data is not None:
                self._push_callback(self._panel_id, data)
        
        self._throttler.flush_now(do_push)
    
    def get_state(self) -> Dict[str, Any]:
        """Get current binding state."""
        with self._lock:
            return {
                'panel_id': self._panel_id,
                'content_id': self._content.content_id,
                'content_type': self._content.content_type.value,
                'mode': self._content.config.mode.value,
                'update_strategy': self._content.config.update_strategy.value,
                'update_count': self._content.update_count,
                'last_pushed_at': self._content.last_pushed_at.isoformat() if self._content.last_pushed_at else None,
                'active': self._active,
                'error_count': self._error_count,
                'throttler_stats': self._throttler.get_stats(),
            }
    
    def close(self) -> None:
        """Close the binding and cleanup resources."""
        self._active = False
        self._throttler.cancel_pending()
        
        if self._unsubscribe:
            try:
                self._unsubscribe()
            except Exception:
                pass
            self._unsubscribe = None


class PanelBindingManager:
    """
    Central manager for all panel-content bindings.
    
    Provides registration, lookup, and bulk operations.
    """
    
    def __init__(self):
        self._bindings: Dict[str, Dict[str, PanelContentBinding]] = defaultdict(dict)
        self._content_registry: Dict[str, ContentSource] = {}
        self._event_callbacks: List[Callable[[PanelBindingEvent], None]] = []
        self._lock = threading.RLock()
        self._binding_counter = 0
    
    def register_content_source(
        self,
        content_id: str,
        source: ContentSource,
    ) -> None:
        """Register a content source for binding."""
        with self._lock:
            self._content_registry[content_id] = source
            self._emit_event(PanelBindingEvent(
                event_type='content_registered',
                panel_id='',
                content_id=content_id,
                timestamp=datetime.now(timezone.utc),
                details={'source_type': type(source).__name__},
            ))
    
    def unregister_content_source(self, content_id: str) -> bool:
        """Unregister a content source."""
        with self._lock:
            if content_id in self._content_registry:
                del self._content_registry[content_id]
                self._emit_event(PanelBindingEvent(
                    event_type='content_unregistered',
                    panel_id='',
                    content_id=content_id,
                    timestamp=datetime.now(timezone.utc),
                ))
                return True
            return False
    
    def bind_panel_to_content(
        self,
        panel_id: str,
        content_id: str,
        config: BindingConfig,
        push_callback: Callable[[str, Any], None],
    ) -> Optional[PanelContentBinding]:
        """Bind a panel to a content source."""
        with self._lock:
            source = self._content_registry.get(content_id)
            if not source:
                self._emit_event(PanelBindingEvent(
                    event_type='error',
                    panel_id=panel_id,
                    content_id=content_id,
                    timestamp=datetime.now(timezone.utc),
                    details={'error': 'content_not_found'},
                ))
                return None
            
            if not config.validate():
                self._emit_event(PanelBindingEvent(
                    event_type='error',
                    panel_id=panel_id,
                    content_id=content_id,
                    timestamp=datetime.now(timezone.utc),
                    details={'error': 'invalid_config'},
                ))
                return None
            
            metadata = source.get_metadata()
            bound_content = BoundContent(
                content_id=content_id,
                content_type=metadata.content_type,
                source=source,
                config=config,
                metadata=metadata,
            )
            
            binding = PanelContentBinding(panel_id, bound_content, push_callback)
            self._bindings[panel_id][content_id] = binding
            
            self._binding_counter += 1
            binding_id = f"binding_{self._binding_counter}"
            
            self._emit_event(PanelBindingEvent(
                event_type='bound',
                panel_id=panel_id,
                content_id=content_id,
                timestamp=datetime.now(timezone.utc),
                details={'binding_id': binding_id, 'mode': config.mode.value},
            ))
            
            return binding
    
    def unbind_panel(
        self,
        panel_id: str,
        content_id: Optional[str] = None,
    ) -> int:
        """
        Unbind panel from content.
        
        If content_id is None, unbinds all content from the panel.
        Returns count of bindings removed.
        """
        with self._lock:
            if panel_id not in self._bindings:
                return 0
            
            if content_id:
                binding = self._bindings[panel_id].pop(content_id, None)
                if binding:
                    binding.close()
                    self._emit_event(PanelBindingEvent(
                        event_type='unbound',
                        panel_id=panel_id,
                        content_id=content_id,
                        timestamp=datetime.now(timezone.utc),
                    ))
                    return 1
                return 0
            else:
                count = len(self._bindings[panel_id])
                for binding in self._bindings[panel_id].values():
                    binding.close()
                
                del self._bindings[panel_id]
                self._emit_event(PanelBindingEvent(
                    event_type='unbound',
                    panel_id=panel_id,
                    content_id='*',
                    timestamp=datetime.now(timezone.utc),
                    details={'bindings_removed': count},
                ))
                return count
    
    def get_binding(self, panel_id: str, content_id: str) -> Optional[PanelContentBinding]:
        """Get a specific binding."""
        with self._lock:
            return self._bindings.get(panel_id, {}).get(content_id)
    
    def get_panel_bindings(self, panel_id: str) -> List[PanelContentBinding]:
        """Get all bindings for a panel."""
        with self._lock:
            return list(self._bindings.get(panel_id, {}).values())
    
    def get_content_bindings(self, content_id: str) -> List[PanelContentBinding]:
        """Get all panels bound to a content source."""
        with self._lock:
            result = []
            for panel_bindings in self._bindings.values():
                if content_id in panel_bindings:
                    result.append(panel_bindings[content_id])
            return result
    
    def push_to_panel(self, panel_id: str, content_id: str) -> Optional[Any]:
        """Force push current content to a panel."""
        with self._lock:
            binding = self._bindings.get(panel_id, {}).get(content_id)
            if binding:
                return binding.push_now()
            return None
    
    def push_all_pending(self, panel_id: Optional[str] = None) -> int:
        """Flush all pending updates."""
        with self._lock:
            count = 0
            panels = [panel_id] if panel_id else list(self._bindings.keys())
            
            for pid in panels:
                for binding in self._bindings.get(pid, {}).values():
                    binding.flush_pending()
                    count += 1
            
            return count
    
    def subscribe_events(
        self,
        callback: Callable[[PanelBindingEvent], None],
    ) -> None:
        """Subscribe to binding events."""
        with self._lock:
            self._event_callbacks.append(callback)
    
    def unsubscribe_events(
        self,
        callback: Callable[[PanelBindingEvent], None],
    ) -> None:
        """Unsubscribe from binding events."""
        with self._lock:
            self._event_callbacks = [
                cb for cb in self._event_callbacks if cb != callback
            ]
    
    def _emit_event(self, event: PanelBindingEvent) -> None:
        """Emit a binding event to subscribers."""
        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception:
                pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        with self._lock:
            total_bindings = sum(len(bindings) for bindings in self._bindings.values())
            
            return {
                'total_panels': len(self._bindings),
                'total_bindings': total_bindings,
                'total_content_sources': len(self._content_registry),
                'panels': {
                    pid: len(bindings) for pid, bindings in self._bindings.items()
                },
            }
    
    def get_all_states(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get state of all bindings."""
        with self._lock:
            result = {}
            for panel_id, bindings in self._bindings.items():
                result[panel_id] = [b.get_state() for b in bindings.values()]
            return result


# Helper classes for common content sources

class SimpleContentSource(ContentSource[T]):
    """Simple content source wrapping a value with optional callbacks."""
    
    def __init__(
        self,
        content_type: ContentType,
        initial_value: T,
        content_id: Optional[str] = None,
        source: str = "",
    ):
        import uuid
        self._content_id = content_id or f"content_{uuid.uuid4().hex[:8]}"
        self._content_type = content_type
        self._value = initial_value
        self._source = source
        self._subscribers: List[Callable[[T], None]] = []
        self._version = 0
        self._created_at = datetime.now(timezone.utc)
        self._updated_at = self._created_at
        self._lock = threading.Lock()
    
    def get_content(self) -> T:
        with self._lock:
            return self._value
    
    def set_content(self, value: T) -> None:
        with self._lock:
            self._value = value
            self._version += 1
            self._updated_at = datetime.now(timezone.utc)
            
            # Notify subscribers
            for callback in self._subscribers:
                try:
                    callback(value)
                except Exception:
                    pass
    
    def subscribe(self, callback: Callable[[T], None]) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)
            
            def unsubscribe():
                with self._lock:
                    if callback in self._subscribers:
                        self._subscribers.remove(callback)
            
            return unsubscribe
    
    def get_metadata(self) -> ContentMetadata:
        with self._lock:
            return ContentMetadata(
                content_id=self._content_id,
                content_type=self._content_type,
                created_at=self._created_at,
                updated_at=self._updated_at,
                version=self._version,
                source=self._source,
            )


class StreamContentSource(ContentSource[List[T]]):
    """Content source for append-only streams (logs, chat, etc.)."""
    
    def __init__(
        self,
        content_type: ContentType,
        content_id: Optional[str] = None,
        max_items: int = 10000,
    ):
        import uuid
        self._content_id = content_id or f"stream_{uuid.uuid4().hex[:8]}"
        self._content_type = content_type
        self._items: List[T] = []
        self._max_items = max_items
        self._subscribers: List[Callable[[List[T]], None]] = []
        self._created_at = datetime.now(timezone.utc)
        self._updated_at = self._created_at
        self._lock = threading.Lock()
    
    def append(self, item: T) -> None:
        with self._lock:
            self._items.append(item)
            
            # Trim if over limit
            if len(self._items) > self._max_items:
                self._items = self._items[-self._max_items:]
            
            self._updated_at = datetime.now(timezone.utc)
            
            # Notify subscribers with full list (for append mode)
            for callback in self._subscribers:
                try:
                    callback(self._items.copy())
                except Exception:
                    pass
    
    def get_content(self) -> List[T]:
        with self._lock:
            return self._items.copy()
    
    def subscribe(self, callback: Callable[[List[T]], None]) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)
            
            def unsubscribe():
                with self._lock:
                    if callback in self._subscribers:
                        self._subscribers.remove(callback)
            
            return unsubscribe
    
    def get_metadata(self) -> ContentMetadata:
        with self._lock:
            return ContentMetadata(
                content_id=self._content_id,
                content_type=self._content_type,
                created_at=self._created_at,
                updated_at=self._updated_at,
                version=len(self._items),
                size_bytes=sum(len(str(item)) for item in self._items),
            )
    
    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._updated_at = datetime.now(timezone.utc)


def create_binding_manager() -> PanelBindingManager:
    """Create a new panel binding manager."""
    return PanelBindingManager()
