"""
APEX v3 UI Layer - §38, §41, §57, §63, §72

User interface components including:
- War Room GUI (Canvas Layer with 24 render types)
- Thought Process Inspector
- CLI Interface
- Notification System integration

Spec Compliance:
- §38: Canvas Layer (24 render types)
- §41: War Room UI (desktop/mobile layouts)
- §57: Thought Process Inspector with disagreement tracking
- §63: Notification system
- §72: Report generation
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
    CanvasEngine,
    # Thought Process Inspector
    StepDisagreement,
    ThoughtProcessInspector,
    # War Room Layout
    LayoutMode,
    WarRoomLayout,
    WarRoomLayoutManager,
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
    # CLI Components
    "CLICategory",
    "TableFormatter",
    "ColorFormatter",
    "CLISession",
    "ApexCLI",
    "run_cli",
    "execute_command",
]
