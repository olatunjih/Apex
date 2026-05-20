"""APEX runtime package."""

from .cognitive import CognitiveLayer, CognitiveState, FailureRecord, MemoryRecord
from .config import RuntimeConfig, validate_runtime_config
from .reactive import AnalysisRequest, IntentRouter, ReactiveDecision, ReactiveLayer, WhyLayer
from .errors import APEXError, ErrorCategory, ErrorSeverity, validation_error
from .numerics import MonetaryValue, enforce_decimal, serialize_decimal, NumericalPolicy, DEFAULT_NUMERICAL_POLICY, validate_numerical_policy
from .runtime import ApexRuntime, RuntimeEvent, RuntimePhase, RuntimeState
from .policy import NumericalPolicy as PolicyNumericalPolicy, DEFAULT_NUMERICAL_POLICY as PolicyDefaultNumericalPolicy
from .why_engine import WhyContext, WhyEngine, WhyExplanation
from .reflection import ReflectionLayer, ReflectionRecord

# Core domain models
from .core_models import (
    EpistemicState, ConfidenceLevel, KnowledgeBoundary, ThesisChange,
    TickerIntelligenceFile, Guardrails, GuardrailResult, AbstainModeState
)
from .proactive_intelligence import (
    PatternType, LearnedPattern, KnowledgeApplication,
    LearningEngine, KnowledgeApplicationEngine
)
from .second_order_analysis import (
    EffectType, SecondOrderEffect, CausalChain, NarrativeInconsistency,
    SecondOrderAnalysis, NarrativeAgent
)
from .ethical_framework import (
    AxiomViolationSeverity, EthicalAxiom, AxiomEvaluationResult,
    HumanFeedback, ExpertIntelligence, EthicalFramework, HumanFeedbackEngine
)
from .analytical_debt import (
    DebtCategory, AnalyticalDebtItem, ComponentHealthScore, ThesisLifecycleEvent,
    AnalyticalDebtDashboard, ThesisLifecycleManager
)

# Strategy Layer (Section 3)
from .strategy import (
    StrategyType, SignalStrength, StrategySignal, StrategyMetadata,
    StrategyPlugin, RegisteredStrategy, StrategyRegistry, StrategySelector,
    AggregatedSignal, StrategyAggregator, StrategyPerformanceMetrics,
    StrategyPerformanceTracker, ExampleMomentumStrategy
)

# Tool Layer (Section 4)
from .tools import (
    ToolMetadata, ToolExecutionRecord, Tool, BaseTool, ToolExecutionStatus,
    ToolInputSchema, ToolOutputSchema, PriceNormalizationTool, ReturnCalculationTool,
    VolatilityCalculationTool, DataValidationTool, ToolRegistry, create_standard_tool_registry,
    DataRegistry, ToolResult, FetchMarketDataTool, ComputeIndicatorsTool, GenerateSignalsTool
)

# Memory Management (Section 1.7)
from .memory_guard import MemoryGuard, MemorySnapshot, MemoryAlert, BoundedCache, DEFAULT_MEMORY_GUARD

# Health & Signals (Sections 1.5, 1.8)
from .health import HealthChecker, HealthCheckResult, HealthResponse, start_health_server, DEFAULT_HEALTH_CHECKER
from .signal_handler import SignalHandler, SignalHandlerContext, DEFAULT_SIGNAL_HANDLER

# Observability (Section 32)
from .observability import (
    StructuredLogger, LogRedactor, MetricsRegistry, Tracer, CostTracker,
    DEFAULT_METRICS, DEFAULT_TRACER, DEFAULT_COST_TRACKER
)

__all__ = [
    # Original exports
    "RuntimeConfig",
    "APEXError",
    "ErrorCategory",
    "ErrorSeverity",
    "validation_error",
    "MonetaryValue",
    "enforce_decimal",
    "serialize_decimal",
    "NumericalPolicy",
    "DEFAULT_NUMERICAL_POLICY",
    "validate_numerical_policy",
    "ApexRuntime",
    "RuntimeEvent",
    "RuntimePhase",
    "RuntimeState",
    "CognitiveLayer",
    "CognitiveState",
    "MemoryRecord",
    "FailureRecord",
    "ReactiveLayer",
    "ReactiveDecision",
    "AnalysisRequest",
    "IntentRouter",
    "WhyLayer",
    "WhyContext",
    "WhyExplanation",
    "ReflectionLayer",
    "ReflectionRecord",
    
    # Core Models
    "EpistemicState",
    "ConfidenceLevel",
    "KnowledgeBoundary",
    "ThesisChange",
    "TickerIntelligenceFile",
    "Guardrails",
    "GuardrailResult",
    "AbstainModeState",
    
    # Proactive Intelligence
    "PatternType",
    "LearnedPattern",
    "KnowledgeApplication",
    "LearningEngine",
    "KnowledgeApplicationEngine",
    
    # Second Order Analysis
    "EffectType",
    "SecondOrderEffect",
    "CausalChain",
    "NarrativeInconsistency",
    "SecondOrderAnalysis",
    "NarrativeAgent",
    
    # Ethical Framework
    "AxiomViolationSeverity",
    "EthicalAxiom",
    "AxiomEvaluationResult",
    "HumanFeedback",
    "ExpertIntelligence",
    "EthicalFramework",
    "HumanFeedbackEngine",
    
    # Analytical Debt
    "DebtCategory",
    "AnalyticalDebtItem",
    "ComponentHealthScore",
    "ThesisLifecycleEvent",
    "AnalyticalDebtDashboard",
    "ThesisLifecycleManager",
    
    # Strategy Layer
    "StrategyType",
    "SignalStrength",
    "StrategySignal",
    "StrategyMetadata",
    "StrategyPlugin",
    "RegisteredStrategy",
    "StrategyRegistry",
    "StrategySelector",
    "AggregatedSignal",
    "StrategyAggregator",
    "StrategyPerformanceMetrics",
    "StrategyPerformanceTracker",
    "ExampleMomentumStrategy",
    
    # Tool Layer
    "ToolExecutionStatus",
    "ToolInputSchema",
    "ToolOutputSchema",
    "ToolMetadata",
    "ToolExecutionRecord",
    "Tool",
    "BaseTool",
    "PriceNormalizationTool",
    "ReturnCalculationTool",
    "VolatilityCalculationTool",
    "DataValidationTool",
    "ToolRegistry",
    "create_standard_tool_registry",
    "DataRegistry",
    "ToolResult",
    "FetchMarketDataTool",
    "ComputeIndicatorsTool",
    "GenerateSignalsTool",
    
    # Memory Management (Section 1.7)
    "MemoryGuard",
    "MemorySnapshot",
    "MemoryAlert",
    "BoundedCache",
    "DEFAULT_MEMORY_GUARD",
    
    # Health & Signals (Sections 1.5, 1.8)
    "HealthChecker",
    "HealthCheckResult",
    "HealthResponse",
    "start_health_server",
    "DEFAULT_HEALTH_CHECKER",
    "SignalHandler",
    "SignalHandlerContext",
    "DEFAULT_SIGNAL_HANDLER",
    
    # Observability (Section 32)
    "StructuredLogger",
    "LogRedactor",
    "MetricsRegistry",
    "Tracer",
    "CostTracker",
    "DEFAULT_METRICS",
    "DEFAULT_TRACER",
    "DEFAULT_COST_TRACKER",
]
