"""APEX v3 Tool Layer - All core tools."""

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
    ToolExecutionRecord,
    ToolExecutionStatus,
    ToolInputSchema,
    ToolMetadata,
    ToolOutputSchema,
    ToolResult,
)
from typing import Dict, Optional


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
