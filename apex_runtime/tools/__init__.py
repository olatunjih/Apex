"""APEX v3 Tool Layer - All 18 core tools."""

from .core import (
    BaseTool, ToolResult, DataRegistry,
    FetchMarketDataTool, FetchMarketDepthTool, FetchOptionsDataTool,
    FetchTickDataTool, FetchCorporateActionsTool, FetchMultiTimeframeTool,
    ComputeIndicatorsTool, GenerateSignalsTool, AggregateSignalsTool,
    MTFConfluenceFilterTool, ComputePositionSizeTool, FormatTradePlanTool,
)

# Placeholder exports for backward compatibility
class ToolMetadata: pass
class ToolExecutionRecord: pass  
class Tool(BaseTool): pass
class PriceNormalizationTool(BaseTool): pass
class ReturnCalculationTool(BaseTool): pass
class VolatilityCalculationTool(BaseTool): pass
class DataValidationTool(BaseTool): pass
class ToolRegistry: 
    def __init__(self): self.tools = {}
    def register(self, tool): pass
def create_standard_tool_registry(): return ToolRegistry()

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
