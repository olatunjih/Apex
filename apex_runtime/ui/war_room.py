"""
APEX v3 War Room UI - §38, §41, §57

Canvas Layer with 24 render types, Thought Process Inspector,
and multi-panel desktop/mobile layouts.

Spec Compliance:
- §38: Canvas Layer (24 render types)
- §41: War Room UI (3-panel desktop, mobile tabs)
- §57: Thought Process Inspector with per-step disagreement buttons
- §86: WebSocket event integration
"""

from __future__ import annotations
import json
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from collections import OrderedDict
import threading


# =============================================================================
# Canvas Render Types (§38.1)
# =============================================================================

class CanvasRenderType(str, Enum):
    """All 24 canvas render types from spec §38.1"""
    # Market Visualization
    CANDLESTICK_CHART = "candlestick_chart"
    VOLUME_PROFILE_CHART = "volume_profile_chart"
    OPTIONS_SURFACE = "options_surface"
    FOOTPRINT_CHART = "footprint_chart"
    
    # Analysis Cards
    TRADE_PLAN_CARD = "trade_plan_card"
    RESEARCH_NOTE_CARD = "research_note_card"
    NO_ACTION_CARD = "no_action_card"
    WHY_ENGINE_CARD = "why_engine_card"
    REFLECTION_CARD = "reflection_card"
    INTELLIGENCE_BRIEF_CARD = "intelligence_brief_card"
    
    # Portfolio Analytics
    PORTFOLIO_HEATMAP = "portfolio_heatmap"
    CORRELATION_MATRIX = "correlation_matrix"
    FACTOR_EXPOSURE_CHART = "factor_exposure_chart"
    PERFORMANCE_ATTRIBUTION = "performance_attribution"
    
    # Diagnostic Views
    ANALYSIS_TRAJECTORY = "analysis_trajectory"
    THESIS_HEALTH_CHART = "thesis_health_chart"
    BEHAVIORAL_PROFILE_VIEW = "behavioral_profile_view"
    CONFIG_DRIFT_VIEW = "config_drift_view"
    DISPOSITION_ANALYTICS = "disposition_analytics"
    FAILURE_PATTERN_MAP = "failure_pattern_map"
    
    # Advanced Dashboards
    INTERMARKET_DASHBOARD = "intermarket_dashboard"
    MTF_ALIGNMENT_VIEW = "mtf_alignment_view"
    REPORT_PREVIEW = "report_preview"
    
    # Error States
    CANVAS_PAYLOAD_ERROR = "canvas_payload_error"


@dataclass(frozen=True)
class CandlestickData:
    """OHLCV data for candlestick charts"""
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    vwap: Optional[Decimal] = None


@dataclass(frozen=True)
class VolumeProfileLevel:
    """Volume profile point of control data"""
    price: Decimal
    volume: Decimal
    buy_volume: Decimal
    sell_volume: Decimal
    poc: bool = False
    vah: bool = False  # Value Area High
    val: bool = False  # Value Area Low


@dataclass(frozen=True)
class OptionsChainData:
    """Options surface data"""
    strike: Decimal
    expiry: datetime
    call_iv: Optional[Decimal] = None
    put_iv: Optional[Decimal] = None
    call_oi: int = 0
    put_oi: int = 0
    call_volume: int = 0
    put_volume: int = 0
    gamma: Optional[Decimal] = None


@dataclass(frozen=True)
class FootprintData:
    """Footprint chart data (order flow)"""
    price: Decimal
    bid_volume: Decimal
    ask_volume: Decimal
    delta: Decimal
    imbalance_ratio: Optional[Decimal] = None
    absorbed: bool = False


# =============================================================================
# Analysis Card Data Structures
# =============================================================================

@dataclass(frozen=True)
class TradePlanLeg:
    """Individual leg of a trade plan"""
    ticker: str
    direction: str  # LONG/SHORT
    shares: Decimal
    entry_price: Decimal
    stop_price: Decimal
    take_profit: Decimal
    notional: Decimal
    role: str  # PRIMARY/HEDGE/SATELLITE


@dataclass(frozen=True)
class TradePlanCard:
    """Complete trade plan for canvas rendering"""
    plan_id: str
    plan_type: str  # SINGLE/SPREAD/IRON_CONDOR/etc
    ticker: str
    legs: List[TradePlanLeg]
    net_exposure: Decimal
    correlation_between_legs: Optional[Decimal] = None
    hedge_ratio: Optional[Decimal] = None
    entry_window: Tuple[datetime, datetime] = field(default_factory=lambda: (datetime.now(), datetime.now()))
    invalidation_conditions: List[str] = field(default_factory=list)
    confidence_decomposition: Dict[str, Decimal] = field(default_factory=dict)
    epistemic_classification: str = "adequate"
    behavioral_flags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class WhyEngineLayer:
    """Single layer of Why Engine output"""
    layer_name: str
    score: Decimal
    narrative: str
    key_factors: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class WhyEngineCard:
    """Why Engine explanation for canvas"""
    ticker: str
    decision: str
    final_confidence: Decimal
    layers: List[WhyEngineLayer]
    conflict_analysis: Optional[Dict[str, Any]] = None
    failure_patterns_applied: List[str] = field(default_factory=list)
    pil_context_incorporated: bool = False
    trace_id: str = ""


@dataclass(frozen=True)
class ReflectionCard:
    """Reflection Layer output for canvas"""
    ticker: str
    confidence_score: Decimal
    risk_grade: str  # A/B/C/D/F
    grade_rationale: str
    size_multiplier: Decimal
    key_risks: List[str]
    knowledge_context_applied: bool
    failure_history_impact: Decimal
    exception_assessment: Optional[str] = None
    what_would_change_this: List[str] = field(default_factory=list)
    llm_unavailable: bool = False


@dataclass(frozen=True)
class NoActionCard:
    """NO_ACTION / Abstain mode card"""
    ticker: str
    reason: str
    system_state: Dict[str, Any]
    what_would_change_this: List[str]
    research_card_available: bool = False
    retry_after_seconds: Optional[int] = None


# =============================================================================
# Portfolio & Analytics Data
# =============================================================================

@dataclass(frozen=True)
class PortfolioPosition:
    """Position data for heatmap"""
    ticker: str
    shares: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal
    heat_contribution: Decimal
    sector: str


@dataclass(frozen=True)
class CorrelationPair:
    """Correlation matrix entry"""
    ticker_a: str
    ticker_b: str
    correlation: Decimal
    lookback_days: int
    significance: Decimal


@dataclass(frozen=True)
class FactorExposure:
    """Factor exposure for a position or portfolio"""
    market_beta: Decimal
    smb: Decimal  # Size
    hml: Decimal  # Value
    momentum: Decimal
    quality: Decimal
    crowding_risk: Decimal


@dataclass(frozen=True)
class PerformanceAttribution:
    """Performance attribution breakdown"""
    total_return: Decimal
    market_beta_contribution: Decimal
    signal_alpha: Decimal
    timing_contribution: Decimal
    sector_allocation_effect: Decimal
    security_selection_effect: Decimal
    regime_breakdown: Dict[str, Decimal] = field(default_factory=dict)


# =============================================================================
# Diagnostic & Advanced Views
# =============================================================================

@dataclass(frozen=True)
class AnalysisTrajectoryStep:
    """Single step in analysis trajectory"""
    step_name: str
    confidence_before: Decimal
    confidence_after: Decimal
    directional_change: Optional[str] = None  # UPGRADE/DOWNGRADE/UNCHANGED
    contradiction_type: Optional[str] = None


@dataclass(frozen=True)
class ThesisHealthComponent:
    """Component health score for thesis"""
    component_name: str
    health_score: Decimal
    trend: str  # IMPROVING/STABLE/DEGRADING
    degradation_rate: Optional[Decimal] = None
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class BehavioralBiasEvent:
    """Detected behavioral bias"""
    bias_type: str  # REVENGE_TRADING/FIXATION/FOMO/etc
    severity: str  # LOW/MEDIUM/HIGH/CRITICAL
    detected_at: datetime
    context: Dict[str, Any]
    heeded: bool = False
    outcome: Optional[str] = None


@dataclass(frozen=True)
class ConfigDriftItem:
    """Configuration drift detection"""
    parameter_name: str
    original_value: Any
    current_value: Any
    drift_pct: Decimal
    material: bool
    impact_assessment: str


@dataclass(frozen=True)
class FailurePatternPoint:
    """Point on failure pattern map"""
    pattern_name: str
    occurrence_count: int
    failure_rate: Decimal
    statistical_significance: Decimal
    pattern_status: str  # EMERGING/CONFIRMED/DECAYING/REFUTED
    affected_strategies: List[str] = field(default_factory=list)


# =============================================================================
# Canvas Engine
# =============================================================================

@dataclass(frozen=True)
class CanvasPayload:
    """Complete canvas payload for a render type"""
    render_type: CanvasRenderType
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    trace_id: str = ""
    session_id: str = ""


@dataclass
class CanvasElement:
    """A single element on the canvas"""
    element_id: str
    render_type: CanvasRenderType
    payload: CanvasPayload
    x_position: int
    y_position: int
    width: int
    height: int
    z_index: int = 0
    is_collapsed: bool = False
    user_preferences: Dict[str, Any] = field(default_factory=dict)


class CanvasEngine:
    """
    Canvas Layer Engine - §38
    
    Manages canvas state, render type registry, and payload generation.
    Supports dynamic layout, user preferences, and WebSocket streaming.
    """
    
    def __init__(self, max_elements: int = 50):
        self._elements: OrderedDict[str, CanvasElement] = OrderedDict()
        self._max_elements = max_elements
        self._render_type_registry = self._build_render_type_registry()
        self._lock = threading.RLock()
        self._element_counter = 0
        self._canvas_history: List[Dict[str, Any]] = []
        
    def _build_render_type_registry(self) -> Dict[CanvasRenderType, Dict[str, Any]]:
        """Build registry of render type capabilities"""
        return {
            CanvasRenderType.CANDLESTICK_CHART: {
                "category": "market_viz",
                "min_width": 400,
                "min_height": 300,
                "data_type": CandlestickData,
                "supports_streaming": True,
            },
            CanvasRenderType.VOLUME_PROFILE_CHART: {
                "category": "market_viz",
                "min_width": 300,
                "min_height": 400,
                "data_type": VolumeProfileLevel,
                "supports_streaming": True,
            },
            CanvasRenderType.OPTIONS_SURFACE: {
                "category": "market_viz",
                "min_width": 500,
                "min_height": 400,
                "data_type": OptionsChainData,
                "supports_streaming": False,
            },
            CanvasRenderType.FOOTPRINT_CHART: {
                "category": "market_viz",
                "min_width": 400,
                "min_height": 500,
                "data_type": FootprintData,
                "supports_streaming": True,
            },
            CanvasRenderType.TRADE_PLAN_CARD: {
                "category": "analysis",
                "min_width": 350,
                "min_height": 250,
                "data_type": TradePlanCard,
                "supports_streaming": False,
            },
            CanvasRenderType.RESEARCH_NOTE_CARD: {
                "category": "analysis",
                "min_width": 400,
                "min_height": 300,
                "data_type": dict,
                "supports_streaming": False,
            },
            CanvasRenderType.NO_ACTION_CARD: {
                "category": "analysis",
                "min_width": 350,
                "min_height": 200,
                "data_type": NoActionCard,
                "supports_streaming": False,
            },
            CanvasRenderType.WHY_ENGINE_CARD: {
                "category": "analysis",
                "min_width": 400,
                "min_height": 350,
                "data_type": WhyEngineCard,
                "supports_streaming": False,
            },
            CanvasRenderType.REFLECTION_CARD: {
                "category": "analysis",
                "min_width": 400,
                "min_height": 300,
                "data_type": ReflectionCard,
                "supports_streaming": False,
            },
            CanvasRenderType.INTELLIGENCE_BRIEF_CARD: {
                "category": "analysis",
                "min_width": 450,
                "min_height": 350,
                "data_type": dict,
                "supports_streaming": True,
            },
            CanvasRenderType.PORTFOLIO_HEATMAP: {
                "category": "portfolio",
                "min_width": 500,
                "min_height": 400,
                "data_type": PortfolioPosition,
                "supports_streaming": True,
            },
            CanvasRenderType.CORRELATION_MATRIX: {
                "category": "portfolio",
                "min_width": 400,
                "min_height": 400,
                "data_type": CorrelationPair,
                "supports_streaming": False,
            },
            CanvasRenderType.FACTOR_EXPOSURE_CHART: {
                "category": "portfolio",
                "min_width": 400,
                "min_height": 300,
                "data_type": FactorExposure,
                "supports_streaming": False,
            },
            CanvasRenderType.PERFORMANCE_ATTRIBUTION: {
                "category": "portfolio",
                "min_width": 500,
                "min_height": 350,
                "data_type": PerformanceAttribution,
                "supports_streaming": False,
            },
            CanvasRenderType.ANALYSIS_TRAJECTORY: {
                "category": "diagnostic",
                "min_width": 450,
                "min_height": 300,
                "data_type": AnalysisTrajectoryStep,
                "supports_streaming": False,
            },
            CanvasRenderType.THESIS_HEALTH_CHART: {
                "category": "diagnostic",
                "min_width": 400,
                "min_height": 300,
                "data_type": ThesisHealthComponent,
                "supports_streaming": True,
            },
            CanvasRenderType.BEHAVIORAL_PROFILE_VIEW: {
                "category": "diagnostic",
                "min_width": 400,
                "min_height": 350,
                "data_type": BehavioralBiasEvent,
                "supports_streaming": False,
            },
            CanvasRenderType.CONFIG_DRIFT_VIEW: {
                "category": "diagnostic",
                "min_width": 450,
                "min_height": 300,
                "data_type": ConfigDriftItem,
                "supports_streaming": False,
            },
            CanvasRenderType.DISPOSITION_ANALYTICS: {
                "category": "diagnostic",
                "min_width": 400,
                "min_height": 300,
                "data_type": dict,
                "supports_streaming": False,
            },
            CanvasRenderType.FAILURE_PATTERN_MAP: {
                "category": "diagnostic",
                "min_width": 500,
                "min_height": 400,
                "data_type": FailurePatternPoint,
                "supports_streaming": False,
            },
            CanvasRenderType.INTERMARKET_DASHBOARD: {
                "category": "advanced",
                "min_width": 600,
                "min_height": 450,
                "data_type": dict,
                "supports_streaming": True,
            },
            CanvasRenderType.MTF_ALIGNMENT_VIEW: {
                "category": "advanced",
                "min_width": 450,
                "min_height": 350,
                "data_type": dict,
                "supports_streaming": False,
            },
            CanvasRenderType.REPORT_PREVIEW: {
                "category": "advanced",
                "min_width": 500,
                "min_height": 400,
                "data_type": dict,
                "supports_streaming": False,
            },
            CanvasRenderType.CANVAS_PAYLOAD_ERROR: {
                "category": "error",
                "min_width": 300,
                "min_height": 150,
                "data_type": dict,
                "supports_streaming": False,
            },
        }
    
    def add_element(
        self,
        render_type: CanvasRenderType,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        x: int = 0,
        y: int = 0,
        width: Optional[int] = None,
        height: Optional[int] = None,
        z_index: int = 0,
        trace_id: str = "",
        session_id: str = "",
    ) -> CanvasElement:
        """Add a new element to the canvas"""
        with self._lock:
            # Validate render type
            if render_type not in self._render_type_registry:
                raise ValueError(f"Unknown render type: {render_type}")
            
            registry_entry = self._render_type_registry[render_type]
            
            # Use default dimensions if not specified
            if width is None:
                width = registry_entry["min_width"]
            if height is None:
                height = registry_entry["min_height"]
            
            # Create payload
            payload = CanvasPayload(
                render_type=render_type,
                data=data,
                metadata=metadata or {},
                trace_id=trace_id,
                session_id=session_id,
            )
            
            # Generate element ID
            self._element_counter += 1
            element_id = f"elem_{self._element_counter:06d}"
            
            # Create element
            element = CanvasElement(
                element_id=element_id,
                render_type=render_type,
                payload=payload,
                x_position=x,
                y_position=y,
                width=width,
                height=height,
                z_index=z_index,
            )
            
            # Add to canvas (evict oldest if at capacity)
            if len(self._elements) >= self._max_elements:
                self._elements.popitem(last=False)
            
            self._elements[element_id] = element
            
            # Record in history
            self._canvas_history.append({
                "action": "ADD",
                "element_id": element_id,
                "render_type": render_type.value,
                "timestamp": datetime.now().isoformat(),
            })
            
            return element
    
    def update_element(
        self,
        element_id: str,
        data: Optional[Any] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        is_collapsed: Optional[bool] = None,
    ) -> Optional[CanvasElement]:
        """Update an existing canvas element"""
        with self._lock:
            if element_id not in self._elements:
                return None
            
            element = self._elements[element_id]
            
            # Update payload data if provided
            if data is not None:
                new_payload = CanvasPayload(
                    render_type=element.payload.render_type,
                    data=data,
                    metadata=element.payload.metadata,
                    timestamp=datetime.now(),
                    trace_id=element.payload.trace_id,
                    session_id=element.payload.session_id,
                )
                # Create new element with updated payload
                element = CanvasElement(
                    element_id=element.element_id,
                    render_type=element.render_type,
                    payload=new_payload,
                    x_position=x if x is not None else element.x_position,
                    y_position=y if y is not None else element.y_position,
                    width=width if width is not None else element.width,
                    height=height if height is not None else element.height,
                    z_index=element.z_index,
                    is_collapsed=is_collapsed if is_collapsed is not None else element.is_collapsed,
                    user_preferences=element.user_preferences,
                )
            else:
                # Just update position/size/collapse state
                element = CanvasElement(
                    element_id=element.element_id,
                    render_type=element.render_type,
                    payload=element.payload,
                    x_position=x if x is not None else element.x_position,
                    y_position=y if y is not None else element.y_position,
                    width=width if width is not None else element.width,
                    height=height if height is not None else element.height,
                    z_index=element.z_index,
                    is_collapsed=is_collapsed if is_collapsed is not None else element.is_collapsed,
                    user_preferences=element.user_preferences,
                )
            
            self._elements[element_id] = element
            
            self._canvas_history.append({
                "action": "UPDATE",
                "element_id": element_id,
                "timestamp": datetime.now().isoformat(),
            })
            
            return element
    
    def remove_element(self, element_id: str) -> bool:
        """Remove an element from the canvas"""
        with self._lock:
            if element_id not in self._elements:
                return False
            
            del self._elements[element_id]
            
            self._canvas_history.append({
                "action": "REMOVE",
                "element_id": element_id,
                "timestamp": datetime.now().isoformat(),
            })
            
            return True
    
    def get_element(self, element_id: str) -> Optional[CanvasElement]:
        """Get a specific element by ID"""
        with self._lock:
            return self._elements.get(element_id)
    
    def get_all_elements(self) -> List[CanvasElement]:
        """Get all canvas elements"""
        with self._lock:
            return list(self._elements.values())
    
    def get_elements_by_type(self, render_type: CanvasRenderType) -> List[CanvasElement]:
        """Get all elements of a specific render type"""
        with self._lock:
            return [e for e in self._elements.values() if e.render_type == render_type]
    
    def get_canvas_snapshot(self) -> Dict[str, Any]:
        """Get complete canvas state as dictionary"""
        with self._lock:
            return {
                "elements": [
                    {
                        "element_id": e.element_id,
                        "render_type": e.render_type.value,
                        "x": e.x_position,
                        "y": e.y_position,
                        "width": e.width,
                        "height": e.height,
                        "z_index": e.z_index,
                        "is_collapsed": e.is_collapsed,
                        "data_hash": hashlib.sha256(
                            json.dumps(self._serialize_data(e.payload.data), sort_keys=True).encode()
                        ).hexdigest()[:16],
                    }
                    for e in self._elements.values()
                ],
                "element_count": len(self._elements),
                "max_elements": self._max_elements,
                "history_length": len(self._canvas_history),
            }
    
    def _serialize_data(self, data: Any) -> Any:
        """Serialize data for JSON compatibility"""
        if isinstance(data, Decimal):
            return str(data)
        elif isinstance(data, datetime):
            return data.isoformat()
        elif isinstance(data, (list, tuple)):
            return [self._serialize_data(item) for item in data]
        elif isinstance(data, dict):
            return {k: self._serialize_data(v) for k, v in data.items()}
        elif hasattr(data, "__dataclass_fields__"):
            return {k: self._serialize_data(v) for k, v in data.__dict__.items()}
        else:
            return data
    
    def export_layout(self) -> str:
        """Export canvas layout as JSON string"""
        with self._lock:
            return json.dumps(self.get_canvas_snapshot(), indent=2)
    
    def clear_canvas(self) -> None:
        """Clear all elements from canvas"""
        with self._lock:
            self._elements.clear()
            self._canvas_history.append({
                "action": "CLEAR",
                "timestamp": datetime.now().isoformat(),
            })


# =============================================================================
# Thought Process Inspector (§57)
# =============================================================================

@dataclass(frozen=True)
class StepDisagreement:
    """User disagreement with a pipeline step"""
    step_id: str
    step_name: str
    apex_conclusion: str
    user_conclusion: str
    user_reasoning: str
    disagreed_at: datetime
    analyst_tier: Optional[str] = None
    resolved: bool = False
    who_was_right: Optional[str] = None  # APEX/USER/UNRESOLVED


@dataclass
class ThoughtProcessInspector:
    """
    Thought Process Inspector - §57
    
    Displays per-step analysis with disagreement buttons.
    Tracks user feedback for learning.
    """
    
    def __init__(self):
        self._steps: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._disagreements: List[StepDisagreement] = []
        self._lock = threading.RLock()
        self._current_trace_id: Optional[str] = None
        
    def record_step(
        self,
        step_id: str,
        step_name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        confidence_before: Decimal,
        confidence_after: Decimal,
        duration_ms: float,
        latency_budget_ms: float,
        within_budget: bool,
        trace_id: str,
    ) -> None:
        """Record a pipeline step for inspection"""
        with self._lock:
            self._current_trace_id = trace_id
            self._steps[step_id] = {
                "step_id": step_id,
                "step_name": step_name,
                "input_data": input_data,
                "output_data": output_data,
                "confidence_before": confidence_before,
                "confidence_after": confidence_after,
                "confidence_delta": confidence_after - confidence_before,
                "duration_ms": duration_ms,
                "latency_budget_ms": latency_budget_ms,
                "within_budget": within_budget,
                "trace_id": trace_id,
                "recorded_at": datetime.now(),
                "user_disagreed": False,
            }
    
    def _serialize_for_json(self, data: Any) -> Any:
        """Serialize data for JSON (handle Decimal, datetime, etc.)"""
        if isinstance(data, Decimal):
            return str(data)
        elif isinstance(data, datetime):
            return data.isoformat()
        elif isinstance(data, (list, tuple)):
            return [self._serialize_for_json(item) for item in data]
        elif isinstance(data, dict):
            return {k: self._serialize_for_json(v) for k, v in data.items()}
        else:
            return data
    
    def submit_disagreement(
        self,
        step_id: str,
        user_conclusion: str,
        user_reasoning: str,
        analyst_tier: Optional[str] = None,
    ) -> Optional[StepDisagreement]:
        """Submit user disagreement with a step"""
        with self._lock:
            if step_id not in self._steps:
                return None
            
            step = self._steps[step_id]
            
            # Serialize output_data to handle Decimal and other non-JSON types
            serialized_output = self._serialize_for_json(step["output_data"])
            
            disagreement = StepDisagreement(
                step_id=step_id,
                step_name=step["step_name"],
                apex_conclusion=json.dumps(serialized_output),
                user_conclusion=user_conclusion,
                user_reasoning=user_reasoning,
                disagreed_at=datetime.now(),
                analyst_tier=analyst_tier,
            )
            
            self._disagreements.append(disagreement)
            step["user_disagreed"] = True
            
            return disagreement
    
    def resolve_disagreement(
        self,
        step_id: str,
        who_was_right: str,
    ) -> bool:
        """Resolve a disagreement after outcome is known"""
        with self._lock:
            for i, d in enumerate(self._disagreements):
                if d.step_id == step_id and not d.resolved:
                    self._disagreements[i] = StepDisagreement(
                        step_id=d.step_id,
                        step_name=d.step_name,
                        apex_conclusion=d.apex_conclusion,
                        user_conclusion=d.user_conclusion,
                        user_reasoning=d.user_reasoning,
                        disagreed_at=d.disagreed_at,
                        analyst_tier=d.analyst_tier,
                        resolved=True,
                        who_was_right=who_was_right,
                    )
                    return True
            return False
    
    def get_inspector_view(self, trace_id: str) -> Dict[str, Any]:
        """Get complete inspector view for a trace"""
        with self._lock:
            steps_for_trace = [
                s for s in self._steps.values() if s["trace_id"] == trace_id
            ]
            
            disagreements_for_trace = [
                d for d in self._disagreements
                if any(s["step_id"] == d.step_id and s["trace_id"] == trace_id for s in self._steps.values())
            ]
            
            return {
                "trace_id": trace_id,
                "steps": steps_for_trace,
                "step_count": len(steps_for_trace),
                "disagreements": [
                    {
                        "step_id": d.step_id,
                        "step_name": d.step_name,
                        "apex_conclusion": d.apex_conclusion,
                        "user_conclusion": d.user_conclusion,
                        "user_reasoning": d.user_reasoning,
                        "disagreed_at": d.disagreed_at.isoformat(),
                        "resolved": d.resolved,
                        "who_was_right": d.who_was_right,
                    }
                    for d in disagreements_for_trace
                ],
                "disagreement_count": len(disagreements_for_trace),
            }
    
    def get_disagreement_stats(self) -> Dict[str, Any]:
        """Get aggregate disagreement statistics"""
        with self._lock:
            total = len(self._disagreements)
            resolved = sum(1 for d in self._disagreements if d.resolved)
            apex_right = sum(1 for d in self._disagreements if d.who_was_right == "APEX")
            user_right = sum(1 for d in self._disagreements if d.who_was_right == "USER")
            
            return {
                "total_disagreements": total,
                "resolved": resolved,
                "unresolved": total - resolved,
                "apex_accuracy": apex_right / resolved if resolved > 0 else None,
                "user_accuracy": user_right / resolved if resolved > 0 else None,
            }


# =============================================================================
# War Room Layout Manager
# =============================================================================

class LayoutMode(str, Enum):
    """UI layout modes"""
    DESKTOP_3_PANEL = "desktop_3_panel"
    MOBILE_TABS = "mobile_tabs"
    TABLET_SPLIT = "tablet_split"


@dataclass
class WarRoomLayout:
    """War Room UI layout configuration"""
    mode: LayoutMode
    panels: Dict[str, Dict[str, Any]]
    active_tab: Optional[str] = None
    portfolio_status_visible: bool = True
    thought_process_expanded: bool = True


class WarRoomLayoutManager:
    """
    War Room Layout Manager - §41
    
    Manages 3-panel desktop and mobile tab layouts.
    Handles panel resizing, tab switching, and state persistence.
    """
    
    def __init__(self):
        self._current_layout: Optional[WarRoomLayout] = None
        self._user_preferences: Dict[str, Any] = {}
        self._lock = threading.RLock()
        
    def create_desktop_layout(self) -> WarRoomLayout:
        """Create 3-panel desktop layout (Chat | Canvas | PIL Brief)"""
        with self._lock:
            layout = WarRoomLayout(
                mode=LayoutMode.DESKTOP_3_PANEL,
                panels={
                    "chat": {
                        "width_pct": 25,
                        "min_width_px": 300,
                        "visible": True,
                        "components": ["message_history", "input_box", "quick_actions"],
                    },
                    "canvas": {
                        "width_pct": 50,
                        "min_width_px": 500,
                        "visible": True,
                        "components": ["canvas_elements", "toolbar", "zoom_controls"],
                    },
                    "pil_brief": {
                        "width_pct": 25,
                        "min_width_px": 300,
                        "visible": True,
                        "components": ["regime_status", "opportunity_scout", "risk_sentinel", "calendar"],
                    },
                },
                active_tab=None,
                portfolio_status_visible=True,
                thought_process_expanded=True,
            )
            self._current_layout = layout
            return layout
    
    def create_mobile_layout(self) -> WarRoomLayout:
        """Create mobile tab layout"""
        with self._lock:
            layout = WarRoomLayout(
                mode=LayoutMode.MOBILE_TABS,
                panels={
                    "chat": {
                        "tab_order": 1,
                        "icon": "chat",
                        "label": "Chat",
                        "components": ["message_history", "input_box"],
                    },
                    "canvas": {
                        "tab_order": 2,
                        "icon": "chart",
                        "label": "Canvas",
                        "components": ["canvas_elements", "fullscreen_toggle"],
                    },
                    "pil_brief": {
                        "tab_order": 3,
                        "icon": "brief",
                        "label": "Intelligence",
                        "components": ["regime_status", "opportunities", "alerts"],
                    },
                    "portfolio": {
                        "tab_order": 4,
                        "icon": "portfolio",
                        "label": "Portfolio",
                        "components": ["positions", "heat", "pnl"],
                    },
                },
                active_tab="chat",
                portfolio_status_visible=False,
                thought_process_expanded=False,
            )
            self._current_layout = layout
            return layout
    
    def switch_tab(self, tab_name: str) -> bool:
        """Switch active tab in mobile mode"""
        with self._lock:
            if self._current_layout is None:
                return False
            if self._current_layout.mode != LayoutMode.MOBILE_TABS:
                return False
            if tab_name not in self._current_layout.panels:
                return False
            
            self._current_layout.active_tab = tab_name
            return True
    
    def resize_panel(self, panel_name: str, width_pct: float) -> bool:
        """Resize a panel in desktop mode"""
        with self._lock:
            if self._current_layout is None:
                return False
            if self._current_layout.mode != LayoutMode.DESKTOP_3_PANEL:
                return False
            if panel_name not in self._current_layout.panels:
                return False
            
            self._current_layout.panels[panel_name]["width_pct"] = width_pct
            return True
    
    def toggle_thought_process(self) -> bool:
        """Toggle thought process inspector visibility"""
        with self._lock:
            if self._current_layout is None:
                return False
            
            self._current_layout.thought_process_expanded = not self._current_layout.thought_process_expanded
            return True
    
    def get_layout_config(self) -> Optional[Dict[str, Any]]:
        """Get current layout configuration"""
        with self._lock:
            if self._current_layout is None:
                return None
            
            return {
                "mode": self._current_layout.mode.value,
                "panels": self._current_layout.panels,
                "active_tab": self._current_layout.active_tab,
                "portfolio_status_visible": self._current_layout.portfolio_status_visible,
                "thought_process_expanded": self._current_layout.thought_process_expanded,
            }


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Render Types
    "CanvasRenderType",
    # Data Classes
    "CandlestickData",
    "VolumeProfileLevel",
    "OptionsChainData",
    "FootprintData",
    "TradePlanLeg",
    "TradePlanCard",
    "WhyEngineLayer",
    "WhyEngineCard",
    "ReflectionCard",
    "NoActionCard",
    "PortfolioPosition",
    "CorrelationPair",
    "FactorExposure",
    "PerformanceAttribution",
    "AnalysisTrajectoryStep",
    "ThesisHealthComponent",
    "BehavioralBiasEvent",
    "ConfigDriftItem",
    "FailurePatternPoint",
    # Canvas Engine
    "CanvasPayload",
    "CanvasElement",
    "CanvasEngine",
    # Thought Process Inspector
    "StepDisagreement",
    "ThoughtProcessInspector",
    # War Room Layout
    "LayoutMode",
    "WarRoomLayout",
    "WarRoomLayoutManager",
]
