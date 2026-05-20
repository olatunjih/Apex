"""
APEX v3 UI Layer - §38, §41, §57, §63, §72, §86

User interface components including:
- War Room GUI (Canvas Layer with 24 render types)
- Thought Process Inspector
- CLI Interface
- Notification System integration
- A2UI JSONL Protocol Handler
- Panel Content Binding System
- Core Integration Layer (LLM, tools, memory)

Spec Compliance:
- §38: Canvas Layer (24 render types)
- §41: War Room UI (desktop/mobile layouts)
- §57: Thought Process Inspector with disagreement tracking
- §63: Notification system
- §72: Report generation
- §86: WebSocket/JSONL event streaming
"""

from apex_runtime.ui.war_room import (
    # Render Types
    CanvasRenderType,
    # Data Classes
    CandlestickData,
    VolumeProfileLevel,
    OptionsChainData,
    FootprintData,
    TradePlanLeg,
    TradePlanCard,
    WhyEngineLayer,
    WhyEngineCard,
    ReflectionCard,
    NoActionCard,
    PortfolioPosition,
    CorrelationPair,
    FactorExposure,
    PerformanceAttribution,
    AnalysisTrajectoryStep,
    ThesisHealthComponent,
    BehavioralBiasEvent,
    ConfigDriftItem,
    FailurePatternPoint,
    # Canvas Engine
    CanvasPayload,
    CanvasElement,
    # Thought Process Inspector
    StepDisagreement,
    ThoughtProcessInspector,
    # War Room Layout
    LayoutMode,
    WarRoomLayout,
    WarRoomLayoutManager,
)

from apex_runtime.ui.canvas_engine import (
    CanvasEngine as CanvasEngineNew,
    CanvasRenderer,
    BaseCanvasRenderer,
    CanvasConfig,
    RenderRequest,
    RenderResponse,
    CandlestickRenderer,
    VolumeProfileRenderer,
    OptionsSurfaceRenderer,
    TradePlanCardRenderer,
    WhyEngineCardRenderer,
    PortfolioHeatmapRenderer,
    AnalysisTrajectoryRenderer,
    FailurePatternMapRenderer,
    ErrorPayloadRenderer,
    render_canvas,
)

from apex_runtime.ui.jsonl_protocol import (
    # Event Types
    EventType,
    JSONLEvent,
    # Buffer & Stream
    JSONLEventBuffer,
    JSONLStreamWriter,
    JSONLStreamReader,
    # Protocol Handler
    A2UIProtocolHandler,
    create_protocol_handler,
    create_jsonl_writer,
    create_jsonl_reader,
)

from apex_runtime.ui.panel_binding import (
    # Content Types
    ContentType,
    BindingMode,
    UpdateStrategy,
    # Configuration
    BindingConfig,
    ContentMetadata,
    # Sources
    ContentSource,
    SimpleContentSource,
    StreamContentSource,
    # Management
    PanelBindingManager,
    PanelContentBinding,
    PanelBindingEvent,
    create_binding_manager,
)

from apex_runtime.ui.core_integration import (
    # Pipeline
    IntegrationPipeline,
    IntegrationContext,
    IntegrationPhase,
    PipelineStep,
    # Protocols
    LLMProvider,
    ToolExecutor,
    MemoryStore,
    CanvasRenderer as CanvasRendererProtocol,
    # Creation
    create_integration_pipeline,
    # Mock implementations for testing
    MockLLMProvider,
    MockToolExecutor,
    MockMemoryStore,
    MockCanvasRenderer,
)

from apex_runtime.ui.cli import (
    CLICategory,
    TableFormatter,
    ColorFormatter,
    CLISession,
    ApexCLI,
    run_cli,
    execute_command,
)


__all__ = [
    # Canvas Render Types
    "CanvasRenderType",
    # Canvas Data Classes
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
    # Canvas Engine (war_room)
    "CanvasPayload",
    "CanvasElement",
    # Canvas Engine (canvas_engine)
    "CanvasEngineNew",
    "CanvasRenderer",
    "BaseCanvasRenderer",
    "CanvasConfig",
    "RenderRequest",
    "RenderResponse",
    "CandlestickRenderer",
    "VolumeProfileRenderer",
    "OptionsSurfaceRenderer",
    "TradePlanCardRenderer",
    "WhyEngineCardRenderer",
    "PortfolioHeatmapRenderer",
    "AnalysisTrajectoryRenderer",
    "FailurePatternMapRenderer",
    "ErrorPayloadRenderer",
    "render_canvas",
    # Thought Process Inspector
    "StepDisagreement",
    "ThoughtProcessInspector",
    # War Room Layout
    "LayoutMode",
    "WarRoomLayout",
    "WarRoomLayoutManager",
    # JSONL Protocol
    "EventType",
    "JSONLEvent",
    "JSONLEventBuffer",
    "JSONLStreamWriter",
    "JSONLStreamReader",
    "A2UIProtocolHandler",
    "create_protocol_handler",
    "create_jsonl_writer",
    "create_jsonl_reader",
    # Panel Binding
    "ContentType",
    "BindingMode",
    "UpdateStrategy",
    "BindingConfig",
    "ContentMetadata",
    "ContentSource",
    "SimpleContentSource",
    "StreamContentSource",
    "PanelBindingManager",
    "PanelContentBinding",
    "PanelBindingEvent",
    "create_binding_manager",
    # Core Integration
    "IntegrationPipeline",
    "IntegrationContext",
    "IntegrationPhase",
    "PipelineStep",
    "LLMProvider",
    "ToolExecutor",
    "MemoryStore",
    "CanvasRendererProtocol",
    "create_integration_pipeline",
    "MockLLMProvider",
    "MockToolExecutor",
    "MockMemoryStore",
    "MockCanvasRenderer",
    # CLI Components
    "CLICategory",
    "TableFormatter",
    "ColorFormatter",
    "CLISession",
    "ApexCLI",
    "run_cli",
    "execute_command",
]
