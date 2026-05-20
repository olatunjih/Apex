"""APEX runtime package."""

from .cognitive import CognitiveLayer, CognitiveState, FailureRecord, MemoryRecord
from .config import RuntimeConfig
from .reactive import AnalysisRequest, IntentRouter, ReactiveDecision, ReactiveLayer, WhyLayer
from .errors import APEXError, ErrorCategory, ErrorSeverity
from .numerics import MonetaryValue, enforce_decimal
from .runtime import ApexRuntime, RuntimeEvent, RuntimePhase, RuntimeState
from .policy import NumericalPolicy, DEFAULT_NUMERICAL_POLICY, serialize_decimal
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
    ToolCategory, ToolExecutionStatus, ToolInputSchema, ToolOutputSchema,
    ToolMetadata, ToolExecutionRecord, Tool, BaseTool,
    PriceNormalizationTool, ReturnCalculationTool, VolatilityCalculationTool,
    DataValidationTool, ToolRegistry, create_standard_tool_registry
)

__all__ = [
    # Original exports
    "RuntimeConfig",
    "APEXError",
    "ErrorCategory",
    "ErrorSeverity",
    "MonetaryValue",
    "enforce_decimal",
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
    
    # Policy & Config
    "NumericalPolicy",
    "DEFAULT_NUMERICAL_POLICY",
    "serialize_decimal",
    
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
    "ToolCategory",
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
    "create_standard_tool_registry"
]
