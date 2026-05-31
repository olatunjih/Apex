"""APEX v3 Tool Layer - All core tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generic, Optional, TypeVar


@dataclass(frozen=True)
class ToolInputSchema:
    name: str
    field_type: type
    required: bool = True
    description: str = ""


@dataclass(frozen=True)
class ToolOutputSchema:
    name: str
    field_type: type
    description: str = ""


class ToolExecutionStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"


@dataclass(frozen=True)
class ToolMetadata:
    tool_id: str
    name: str
    version: str
    description: str
    input_schema: tuple[ToolInputSchema, ...]
    output_schema: tuple[ToolOutputSchema, ...]
    stateless: bool = True
    llm_free: bool = True


@dataclass
class ToolExecutionRecord:
    execution_id: str
    tool_id: str
    started_at: float
    completed_at: Optional[float]
    status: ToolExecutionStatus
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    duration_ms: float
    data_ids_read: tuple = ()
    data_ids_written: tuple = ()


T = TypeVar("T")


@dataclass
class ToolResult(Generic[T]):
    success: bool
    data_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

from .core import (
    AggregateSignalsTool,
    BaseTool,
    ComputeIndicatorsTool,
    ComputePositionSizeTool,
    DataRegistry,
    FetchCorporateActionsTool,
    FetchMarketDataTool,
    FetchMarketDepthTool,
    FetchMultiTimeframeTool,
    FetchOptionsDataTool,
    FetchTickDataTool,
    FormatTradePlanTool,
    GenerateSignalsTool,
    MTFConfluenceFilterTool,
)


class Tool(BaseTool):
    """Alias for BaseTool for backward compatibility."""


class PriceNormalizationTool(BaseTool):
    """Price normalization tool placeholder."""


class ReturnCalculationTool(BaseTool):
    """Return calculation tool placeholder."""


class VolatilityCalculationTool(BaseTool):
    """Volatility calculation tool placeholder."""


class DataValidationTool(BaseTool):
    """Data validation tool placeholder."""


class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        metadata = tool.get_metadata()
        if not metadata.stateless or not metadata.llm_free:
            raise ValueError(f"Tool {metadata.tool_id} violates isolation metadata")
        self.tools[metadata.tool_id] = tool

    def get(self, tool_id: str) -> Optional[BaseTool]:
        return self.tools.get(tool_id)

    def list_tools(self) -> list[str]:
        return list(self.tools.keys())


def create_standard_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool_class in [
        FetchMarketDataTool,
        FetchMarketDepthTool,
        FetchOptionsDataTool,
        FetchTickDataTool,
        FetchCorporateActionsTool,
        FetchMultiTimeframeTool,
        ComputeIndicatorsTool,
        GenerateSignalsTool,
        AggregateSignalsTool,
        MTFConfluenceFilterTool,
        ComputePositionSizeTool,
        FormatTradePlanTool,
    ]:
        registry.register(tool_class())
    return registry


__all__ = [
    "AggregateSignalsTool",
    "BaseTool",
    "ComputeIndicatorsTool",
    "ComputePositionSizeTool",
    "DataRegistry",
    "DataValidationTool",
    "FetchCorporateActionsTool",
    "FetchMarketDataTool",
    "FetchMarketDepthTool",
    "FetchMultiTimeframeTool",
    "FetchOptionsDataTool",
    "FetchTickDataTool",
    "FormatTradePlanTool",
    "GenerateSignalsTool",
    "MTFConfluenceFilterTool",
    "PriceNormalizationTool",
    "ReturnCalculationTool",
    "Tool",
    "ToolExecutionRecord",
    "ToolExecutionStatus",
    "ToolInputSchema",
    "ToolMetadata",
    "ToolOutputSchema",
    "ToolRegistry",
    "ToolResult",
    "VolatilityCalculationTool",
    "create_standard_tool_registry",
]
