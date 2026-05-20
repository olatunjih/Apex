"""APEX v3 Tool Layer - All 18 core tools."""

from .core import (
    BaseTool, ToolResult, DataRegistry,
    FetchMarketDataTool, FetchMarketDepthTool, FetchOptionsDataTool,
    FetchTickDataTool, FetchCorporateActionsTool, FetchMultiTimeframeTool,
    ComputeIndicatorsTool, GenerateSignalsTool, AggregateSignalsTool,
    MTFConfluenceFilterTool, ComputePositionSizeTool, FormatTradePlanTool,
)
from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum
from decimal import Decimal

# Proper schema and metadata classes
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
    input_schema: tuple
    output_schema: tuple
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

class Tool(BaseTool):
    """Alias for BaseTool for backward compatibility."""
    pass

class PriceNormalizationTool(BaseTool):
    """Price normalization tool."""
    pass

class ReturnCalculationTool(BaseTool):
    """Return calculation tool."""
    pass

class VolatilityCalculationTool(BaseTool):
    """Volatility calculation tool."""
    pass

class DataValidationTool(BaseTool):
    """Data validation tool."""
    pass

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        self.tools[tool.get_metadata().tool_id] = tool
    
    def get(self, tool_id: str) -> Optional[BaseTool]:
        return self.tools.get(tool_id)
    
    def list_tools(self) -> list:
        return list(self.tools.keys())

def create_standard_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    # Register all 18 core tools
    for tool_class in [
        FetchMarketDataTool, FetchMarketDepthTool, FetchOptionsDataTool,
        FetchTickDataTool, FetchCorporateActionsTool, FetchMultiTimeframeTool,
        ComputeIndicatorsTool, GenerateSignalsTool, AggregateSignalsTool,
        MTFConfluenceFilterTool, ComputePositionSizeTool, FormatTradePlanTool,
    ]:
        registry.register(tool_class())
    return registry

__all__ = [
    'BaseTool', 'ToolResult', 'DataRegistry', 'ToolMetadata', 'ToolExecutionRecord',
    'Tool', 'ToolRegistry', 'create_standard_tool_registry',
    'PriceNormalizationTool', 'ReturnCalculationTool', 'VolatilityCalculationTool',
    'DataValidationTool', 'FetchMarketDataTool', 'FetchMarketDepthTool',
    'FetchOptionsDataTool', 'FetchTickDataTool', 'FetchCorporateActionsTool',
    'FetchMultiTimeframeTool', 'ComputeIndicatorsTool', 'GenerateSignalsTool',
    'AggregateSignalsTool', 'MTFConfluenceFilterTool', 'ComputePositionSizeTool',
    'FormatTradePlanTool',
]
