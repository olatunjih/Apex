"""
APEX v3 Canvas Engine - Section 38

Provides a plugin-based rendering system for 24 canvas render types.
Supports live updates via WebSocket-ready architecture.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol
from collections import OrderedDict
import threading


class CanvasRenderType(str, Enum):
    """24 canvas render types per §38."""
    
    # Market Visualization (6)
    CANDLESTICK_CHART = "candlestick_chart"
    VOLUME_PROFILE_CHART = "volume_profile_chart"
    OPTIONS_SURFACE = "options_surface"
    FOOTPRINT_CHART = "footprint_chart"
    MTF_ALIGNMENT_VIEW = "mtf_alignment_view"
    ORDER_FLOW_VISUALIZER = "order_flow_visualizer"
    
    # Analysis Cards (6)
    TRADE_PLAN_CARD = "trade_plan_card"
    RESEARCH_NOTE_CARD = "research_note_card"
    NO_ACTION_CARD = "no_action_card"
    WHY_ENGINE_CARD = "why_engine_card"
    REFLECTION_CARD = "reflection_card"
    INTELLIGENCE_BRIEF_CARD = "intelligence_brief_card"
    
    # Portfolio Views (5)
    PORTFOLIO_HEATMAP = "portfolio_heatmap"
    CORRELATION_MATRIX = "correlation_matrix"
    FACTOR_EXPOSURE_CHART = "factor_exposure_chart"
    THESIS_HEALTH_CHART = "thesis_health_chart"
    PERFORMANCE_ATTRIBUTION = "performance_attribution"
    
    # Diagnostics (4)
    ANALYSIS_TRAJECTORY = "analysis_trajectory"
    BEHAVIORAL_PROFILE_VIEW = "behavioral_profile_view"
    CONFIG_DRIFT_VIEW = "config_drift_view"
    DISPOSITION_ANALYTICS = "disposition_analytics"
    
    # Advanced (3)
    FAILURE_PATTERN_MAP = "failure_pattern_map"
    INTERMARKET_DASHBOARD = "intermarket_dashboard"
    REPORT_PREVIEW = "report_preview"
    
    # Error handling
    CANVAS_PAYLOAD_ERROR = "canvas_payload_error"


@dataclass(frozen=True)
class CanvasConfig:
    """Configuration for canvas rendering."""
    width: int = 1200
    height: int = 800
    theme: str = "dark"
    refresh_interval_ms: int = 1000
    show_grid: bool = True
    show_legend: bool = True
    timezone: str = "UTC"


@dataclass(frozen=True)
class RenderRequest:
    """Request to render a canvas component."""
    render_type: CanvasRenderType
    data: Dict[str, Any]
    config: CanvasConfig
    request_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class RenderResponse:
    """Response from canvas rendering."""
    render_type: CanvasRenderType
    request_id: str
    rendered_data: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None


class CanvasRenderer(Protocol):
    """Protocol for canvas renderers - plugin interface."""
    
    render_type: CanvasRenderType
    
    def render(self, data: Dict[str, Any], config: CanvasConfig) -> Dict[str, Any]:
        """Render data into canvas format."""
        ...
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate incoming data for this render type."""
        ...


class BaseCanvasRenderer:
    """Base class for canvas renderers with common functionality."""
    
    render_type: CanvasRenderType
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Default validation - checks for required 'data' key."""
        return isinstance(data, dict) and len(data) > 0
    
    def render(self, data: Dict[str, Any], config: CanvasConfig) -> Dict[str, Any]:
        """Default render implementation."""
        raise NotImplementedError("Subclasses must implement render()")


class CandlestickRenderer(BaseCanvasRenderer):
    """Renders candlestick charts with volume."""
    
    render_type = CanvasRenderType.CANDLESTICK_CHART
    
    def render(self, data: Dict[str, Any], config: CanvasConfig) -> Dict[str, Any]:
        candles = data.get('candles', [])
        indicators = data.get('indicators', {})
        
        return {
            'type': 'candlestick',
            'candles': candles,
            'indicators': indicators,
            'theme': config.theme,
            'grid': config.show_grid,
            'timezone': config.timezone,
        }


class VolumeProfileRenderer(BaseCanvasRenderer):
    """Renders volume profile charts."""
    
    render_type = CanvasRenderType.VOLUME_PROFILE_CHART
    
    def render(self, data: Dict[str, Any], config: CanvasConfig) -> Dict[str, Any]:
        profile = data.get('profile', [])
        poc = data.get('point_of_control', 0)
        value_area = data.get('value_area', {})
        
        return {
            'type': 'volume_profile',
            'profile': profile,
            'poc': poc,
            'value_area_high': value_area.get('high', 0),
            'value_area_low': value_area.get('low', 0),
            'theme': config.theme,
        }


class OptionsSurfaceRenderer(BaseCanvasRenderer):
    """Renders options surface visualization."""
    
    render_type = CanvasRenderType.OPTIONS_SURFACE
    
    def render(self, data: Dict[str, Any], config: CanvasConfig) -> Dict[str, Any]:
        chain = data.get('chain', [])
        gex = data.get('gex', {})
        
        return {
            'type': 'options_surface',
            'chain': chain,
            'gex_levels': gex,
            'max_pain': data.get('max_pain', 0),
            'theme': config.theme,
        }


class TradePlanCardRenderer(BaseCanvasRenderer):
    """Renders trade plan cards."""
    
    render_type = CanvasRenderType.TRADE_PLAN_CARD
    
    def render(self, data: Dict[str, Any], config: CanvasConfig) -> Dict[str, Any]:
        return {
            'type': 'trade_plan',
            'ticker': data.get('ticker', ''),
            'direction': data.get('direction', ''),
            'entry_price': data.get('entry_price'),
            'stop_price': data.get('stop_price'),
            'take_profit': data.get('take_profit'),
            'position_size': data.get('position_size'),
            'risk_reward': data.get('risk_reward'),
            'thesis': data.get('thesis', ''),
            'confidence': data.get('confidence', 0),
        }


class WhyEngineCardRenderer(BaseCanvasRenderer):
    """Renders Why Engine explanation cards."""
    
    render_type = CanvasRenderType.WHY_ENGINE_CARD
    
    def render(self, data: Dict[str, Any], config: CanvasConfig) -> Dict[str, Any]:
        layers = data.get('layers', {})
        
        return {
            'type': 'why_explanation',
            'ticker': data.get('ticker', ''),
            'intent': data.get('intent', ''),
            'layer_0_strategy': layers.get('strategy', ''),
            'layer_1_price': layers.get('price_structure', ''),
            'layer_2_volume': layers.get('volume_momentum', ''),
            'layer_3_regime': layers.get('regime', ''),
            'layer_4_behavioral': layers.get('behavioral', ''),
            'layer_5_historical': layers.get('historical', ''),
            'layer_6_cascade': layers.get('cascade', ''),
            'confidence': data.get('confidence', 0),
        }


class PortfolioHeatmapRenderer(BaseCanvasRenderer):
    """Renders portfolio heatmap visualization."""
    
    render_type = CanvasRenderType.PORTFOLIO_HEATMAP
    
    def render(self, data: Dict[str, Any], config: CanvasConfig) -> Dict[str, Any]:
        positions = data.get('positions', [])
        
        return {
            'type': 'heatmap',
            'positions': positions,
            'total_heat': data.get('total_heat', 0),
            'max_heat': data.get('max_heat', 0),
            'heat_pct': data.get('heat_percentage', 0),
            'theme': config.theme,
        }


class AnalysisTrajectoryRenderer(BaseCanvasRenderer):
    """Renders analysis trajectory waterfall chart."""
    
    render_type = CanvasRenderType.ANALYSIS_TRAJECTORY
    
    def render(self, data: Dict[str, Any], config: CanvasConfig) -> Dict[str, Any]:
        trajectory = data.get('trajectory', [])
        
        return {
            'type': 'waterfall',
            'trajectory': trajectory,
            'initial_confidence': data.get('initial_confidence', 0),
            'final_confidence': data.get('final_confidence', 0),
            'steps': len(trajectory),
            'theme': config.theme,
        }


class FailurePatternMapRenderer(BaseCanvasRenderer):
    """Renders failure pattern visualization."""
    
    render_type = CanvasRenderType.FAILURE_PATTERN_MAP
    
    def render(self, data: Dict[str, Any], config: CanvasConfig) -> Dict[str, Any]:
        patterns = data.get('patterns', [])
        
        return {
            'type': 'pattern_map',
            'patterns': patterns,
            'emerging_count': sum(1 for p in patterns if p.get('status') == 'emerging'),
            'confirmed_count': sum(1 for p in patterns if p.get('status') == 'confirmed'),
            'decaying_count': sum(1 for p in patterns if p.get('status') == 'decaying'),
            'theme': config.theme,
        }


class ErrorPayloadRenderer(BaseCanvasRenderer):
    """Renders error payloads."""
    
    render_type = CanvasRenderType.CANVAS_PAYLOAD_ERROR
    
    def render(self, data: Dict[str, Any], config: CanvasConfig) -> Dict[str, Any]:
        return {
            'type': 'error',
            'error_code': data.get('error_code', 'UNKNOWN'),
            'message': data.get('message', 'An error occurred'),
            'details': data.get('details', {}),
            'recovery_suggestions': data.get('suggestions', []),
            'theme': config.theme,
        }


class CanvasEngine:
    """
    Central canvas rendering engine with plugin architecture.
    
    Manages renderer registration, request routing, and live updates.
    Thread-safe with bounded LRU cache for performance.
    """
    
    def __init__(self, max_cache_size: int = 1000):
        self._renderers: Dict[CanvasRenderType, CanvasRenderer] = {}
        self._cache: OrderedDict[str, RenderResponse] = OrderedDict()
        self._max_cache_size = max_cache_size
        self._lock = threading.RLock()
        self._subscribers: Dict[CanvasRenderType, List[Callable]] = {}
        
        # Register built-in renderers
        self._register_builtin_renderers()
    
    def _register_builtin_renderers(self):
        """Register all built-in renderers."""
        renderers = [
            CandlestickRenderer(),
            VolumeProfileRenderer(),
            OptionsSurfaceRenderer(),
            TradePlanCardRenderer(),
            WhyEngineCardRenderer(),
            PortfolioHeatmapRenderer(),
            AnalysisTrajectoryRenderer(),
            FailurePatternMapRenderer(),
            ErrorPayloadRenderer(),
        ]
        for renderer in renderers:
            self.register_renderer(renderer)
    
    def register_renderer(self, renderer: CanvasRenderer) -> None:
        """Register a canvas renderer plugin."""
        with self._lock:
            self._renderers[renderer.render_type] = renderer
    
    def unregister_renderer(self, render_type: CanvasRenderType) -> bool:
        """Unregister a renderer. Returns True if found and removed."""
        with self._lock:
            if render_type in self._renderers:
                del self._renderers[render_type]
                return True
            return False
    
    def subscribe(self, render_type: CanvasRenderType, callback: Callable[[RenderResponse], None]) -> None:
        """Subscribe to live updates for a render type."""
        with self._lock:
            if render_type not in self._subscribers:
                self._subscribers[render_type] = []
            self._subscribers[render_type].append(callback)
    
    def unsubscribe(self, render_type: CanvasRenderType, callback: Callable) -> None:
        """Unsubscribe from live updates."""
        with self._lock:
            if render_type in self._subscribers:
                self._subscribers[render_type] = [
                    cb for cb in self._subscribers[render_type] if cb != callback
                ]
    
    def render(self, request: RenderRequest) -> RenderResponse:
        """Execute a render request."""
        with self._lock:
            # Check cache first
            cache_key = f"{request.render_type.value}:{request.request_id}"
            if cache_key in self._cache:
                return self._cache[cache_key]
            
            # Get renderer
            renderer = self._renderers.get(request.render_type)
            if not renderer:
                response = RenderResponse(
                    render_type=request.render_type,
                    request_id=request.request_id,
                    rendered_data={},
                    metadata={'error': 'renderer_not_found'},
                    timestamp=datetime.utcnow(),
                    success=False,
                    error_message=f"No renderer registered for {request.render_type}",
                )
                self._cache_response(cache_key, response)
                return response
            
            # Validate data
            if not renderer.validate_data(request.data):
                response = RenderResponse(
                    render_type=request.render_type,
                    request_id=request.request_id,
                    rendered_data={},
                    metadata={'error': 'validation_failed'},
                    timestamp=datetime.utcnow(),
                    success=False,
                    error_message="Data validation failed",
                )
                self._cache_response(cache_key, response)
                return response
            
            # Render
            try:
                rendered = renderer.render(request.data, request.config)
                response = RenderResponse(
                    render_type=request.render_type,
                    request_id=request.request_id,
                    rendered_data=rendered,
                    metadata={
                        'renderer': type(renderer).__name__,
                        'data_size': len(str(request.data)),
                    },
                    timestamp=datetime.utcnow(),
                    success=True,
                )
            except Exception as e:
                response = RenderResponse(
                    render_type=request.render_type,
                    request_id=request.request_id,
                    rendered_data={},
                    metadata={'error': 'render_exception'},
                    timestamp=datetime.utcnow(),
                    success=False,
                    error_message=str(e),
                )
            
            # Cache and notify
            self._cache_response(cache_key, response)
            self._notify_subscribers(request.render_type, response)
            
            return response
    
    def _cache_response(self, key: str, response: RenderResponse) -> None:
        """Cache response with LRU eviction."""
        if key in self._cache:
            del self._cache[key]
        self._cache[key] = response
        
        # Evict oldest if over limit
        while len(self._cache) > self._max_cache_size:
            self._cache.popitem(last=False)
    
    def _notify_subscribers(self, render_type: CanvasRenderType, response: RenderResponse) -> None:
        """Notify all subscribers of a new render response."""
        if render_type in self._subscribers:
            for callback in self._subscribers[render_type]:
                try:
                    callback(response)
                except Exception:
                    pass  # Don't let subscriber errors break the pipeline
    
    def get_registered_renderers(self) -> List[CanvasRenderType]:
        """Get list of registered render types."""
        with self._lock:
            return list(self._renderers.keys())
    
    def clear_cache(self) -> None:
        """Clear the render cache."""
        with self._lock:
            self._cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self._max_cache_size,
                'utilization': len(self._cache) / self._max_cache_size if self._max_cache_size > 0 else 0,
            }


# Convenience function for quick rendering
def render_canvas(
    render_type: CanvasRenderType,
    data: Dict[str, Any],
    config: Optional[CanvasConfig] = None,
    request_id: Optional[str] = None,
) -> RenderResponse:
    """Convenience function for one-off canvas rendering."""
    from uuid import uuid4
    
    engine = CanvasEngine()
    request = RenderRequest(
        render_type=render_type,
        data=data,
        config=config or CanvasConfig(),
        request_id=request_id or str(uuid4()),
    )
    return engine.render(request)
