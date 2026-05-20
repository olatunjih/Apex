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

# New core modules
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
    "AnalysisRequest",
    "IntentRouter",
    "ReactiveDecision",
    "ReactiveLayer",
    "WhyLayer",
    "NumericalPolicy",
    "DEFAULT_NUMERICAL_POLICY",
    "serialize_decimal",
    "WhyContext",
    "WhyEngine",
    "WhyExplanation",
    "ReflectionLayer",
    "ReflectionRecord",
    
    # Core models
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
    
    # Second-Order Analysis
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
]
