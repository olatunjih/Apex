"""
APEX Tool Layer - Section 4
Stateless tools with type-safe I/O, no LLM calls, no side effects
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, TypeVar, Generic, Protocol
from threading import RLock
import hashlib
import json

try:
    from .errors import APEXError, ErrorCategory, ErrorSeverity, validation_error
    from .numerics import enforce_decimal
except ImportError:
    from errors import APEXError, ErrorCategory, ErrorSeverity, validation_error
    from numerics import enforce_decimal


class ToolCategory(Enum):
    """Categories of tools"""
    DATA_FETCH = "data_fetch"
    CALCULATION = "calculation"
    ANALYSIS = "analysis"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    AGGREGATION = "aggregation"


class ToolExecutionStatus(Enum):
    """Status of tool execution"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    INVALID_INPUT = "invalid_input"


@dataclass
class ToolInputSchema:
    """Schema definition for tool inputs"""
    name: str
    type_name: str
    required: bool
    description: str
    default: Any = None
    validation_rules: List[str] = field(default_factory=list)


@dataclass
class ToolOutputSchema:
    """Schema definition for tool outputs"""
    name: str
    type_name: str
    description: str
    nullable: bool = False


@dataclass
class ToolMetadata:
    """Metadata about a tool"""
    tool_id: str
    name: str
    description: str
    category: ToolCategory
    version: str
    author: str
    created_at: datetime
    input_schema: List[ToolInputSchema]
    output_schema: List[ToolOutputSchema]
    timeout_ms: int = 5000
    is_stateless: bool = True
    has_side_effects: bool = False
    requires_llm: bool = False  # Must be False per Section 4


@dataclass
class ToolExecutionRecord:
    """Record of a tool execution"""
    execution_id: str
    tool_id: str
    timestamp: datetime
    inputs: Dict[str, Any]
    outputs: Optional[Dict[str, Any]]
    status: ToolExecutionStatus
    duration_ms: int
    error_message: Optional[str] = None


T = TypeVar('T')


class Tool(Protocol):
    """Protocol for all tools"""
    
    def get_metadata(self) -> ToolMetadata:
        """Return tool metadata"""
        ...
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool with given inputs"""
        ...
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """Validate inputs against schema"""
        ...


class BaseTool:
    """Base class providing common tool functionality"""
    
    def __init__(self):
        self._execution_history: List[ToolExecutionRecord] = []
        self._lock = RLock()
    
    def _generate_execution_id(self, tool_id: str, inputs: Dict[str, Any]) -> str:
        """Generate deterministic execution ID for idempotency"""
        content = f"{tool_id}:{json.dumps(inputs, sort_keys=True, default=str)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _record_execution(
        self,
        execution_id: str,
        tool_id: str,
        inputs: Dict[str, Any],
        outputs: Optional[Dict[str, Any]],
        status: ToolExecutionStatus,
        duration_ms: int,
        error_message: Optional[str] = None
    ):
        """Record execution for audit trail"""
        with self._lock:
            record = ToolExecutionRecord(
                execution_id=execution_id,
                tool_id=tool_id,
                timestamp=datetime.now(),
                inputs=inputs,
                outputs=outputs,
                status=status,
                duration_ms=duration_ms,
                error_message=error_message
            )
            self._execution_history.append(record)
            
            # Keep only last 1000 executions
            if len(self._execution_history) > 1000:
                self._execution_history = self._execution_history[-1000:]
    
    def get_execution_history(self, limit: int = 100) -> List[ToolExecutionRecord]:
        """Get recent execution history"""
        with self._lock:
            return self._execution_history[-limit:]


# Example concrete tools implementing Section 4 requirements

class PriceNormalizationTool(BaseTool):
    """
    Tool: Normalize price data to consistent precision.
    Category: TRANSFORMATION
    Stateless: Yes
    Side Effects: No
    LLM Calls: No
    """
    
    def __init__(self):
        super().__init__()
        self._metadata = ToolMetadata(
            tool_id="price_normalize_v1",
            name="Price Normalizer",
            description="Normalizes price values to standard precision (2 decimal places)",
            category=ToolCategory.TRANSFORMATION,
            version="1.0.0",
            author="APEX System",
            created_at=datetime.now(),
            input_schema=[
                ToolInputSchema("prices", "List[Decimal]", True, "List of price values"),
                ToolInputSchema("precision", "int", False, "Decimal precision", default=2)
            ],
            output_schema=[
                ToolOutputSchema("normalized_prices", "List[Decimal]", "Normalized price list")
            ],
            timeout_ms=1000,
            is_stateless=True,
            has_side_effects=False,
            requires_llm=False
        )
    
    def get_metadata(self) -> ToolMetadata:
        return self._metadata
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        if "prices" not in inputs:
            return False
        if not isinstance(inputs["prices"], list):
            return False
        return True
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        execution_id = self._generate_execution_id(self._metadata.tool_id, inputs)
        start_time = datetime.now()
        
        try:
            if not self.validate_inputs(inputs):
                raise validation_error("INVALID_TOOL_INPUTS", "Prices list is required")
            
            prices = inputs["prices"]
            precision = inputs.get("precision", 2)
            
            quantize_value = Decimal(10) ** -precision
            
            normalized = []
            for p in prices:
                if isinstance(p, Decimal):
                    normalized.append(p.quantize(quantize_value))
                else:
                    normalized.append(Decimal(str(p)).quantize(quantize_value))
            
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            self._record_execution(
                execution_id=execution_id,
                tool_id=self._metadata.tool_id,
                inputs=inputs,
                outputs={"normalized_prices": [str(p) for p in normalized]},
                status=ToolExecutionStatus.SUCCESS,
                duration_ms=duration_ms
            )
            
            return {"normalized_prices": normalized}
            
        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._record_execution(
                execution_id=execution_id,
                tool_id=self._metadata.tool_id,
                inputs=inputs,
                outputs=None,
                status=ToolExecutionStatus.FAILED,
                duration_ms=duration_ms,
                error_message=str(e)
            )
            raise


class ReturnCalculationTool(BaseTool):
    """
    Tool: Calculate returns from price series.
    Category: CALCULATION
    Stateless: Yes
    Side Effects: No
    LLM Calls: No
    """
    
    def __init__(self):
        super().__init__()
        self._metadata = ToolMetadata(
            tool_id="return_calc_v1",
            name="Return Calculator",
            description="Calculates simple and logarithmic returns from price series",
            category=ToolCategory.CALCULATION,
            version="1.0.0",
            author="APEX System",
            created_at=datetime.now(),
            input_schema=[
                ToolInputSchema("prices", "List[Decimal]", True, "Price series"),
                ToolInputSchema("return_type", "str", False, "simple or log", default="simple")
            ],
            output_schema=[
                ToolOutputSchema("returns", "List[Decimal]", "Calculated returns"),
                ToolOutputSchema("cumulative_return", "Decimal", "Total cumulative return")
            ],
            timeout_ms=2000,
            is_stateless=True,
            has_side_effects=False,
            requires_llm=False
        )
    
    def get_metadata(self) -> ToolMetadata:
        return self._metadata
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        if "prices" not in inputs:
            return False
        if not isinstance(inputs["prices"], list) or len(inputs["prices"]) < 2:
            return False
        return_type = inputs.get("return_type", "simple")
        if return_type not in ["simple", "log"]:
            return False
        return True
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        execution_id = self._generate_execution_id(self._metadata.tool_id, inputs)
        start_time = datetime.now()
        
        try:
            if not self.validate_inputs(inputs):
                raise validation_error("INVALID_TOOL_INPUTS", "Invalid inputs for return calculation")
            
            from math import log
            
            prices = [Decimal(str(p)) for p in inputs["prices"]]
            return_type = inputs.get("return_type", "simple")
            
            returns = []
            for i in range(1, len(prices)):
                if prices[i-1] == 0:
                    returns.append(Decimal("0"))
                    continue
                    
                if return_type == "simple":
                    r = (prices[i] - prices[i-1]) / prices[i-1]
                else:  # log return
                    r = Decimal(str(log(float(prices[i]) / float(prices[i-1]))))
                
                returns.append(r)
            
            # Cumulative return
            if return_type == "simple":
                cumulative = Decimal("1")
                for r in returns:
                    cumulative *= (Decimal("1") + r)
                cumulative -= Decimal("1")
            else:
                cumulative = sum(returns)
            
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            self._record_execution(
                execution_id=execution_id,
                tool_id=self._metadata.tool_id,
                inputs=inputs,
                outputs={
                    "returns": [str(r) for r in returns],
                    "cumulative_return": str(cumulative)
                },
                status=ToolExecutionStatus.SUCCESS,
                duration_ms=duration_ms
            )
            
            return {
                "returns": returns,
                "cumulative_return": cumulative
            }
            
        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._record_execution(
                execution_id=execution_id,
                tool_id=self._metadata.tool_id,
                inputs=inputs,
                outputs=None,
                status=ToolExecutionStatus.FAILED,
                duration_ms=duration_ms,
                error_message=str(e)
            )
            raise


class VolatilityCalculationTool(BaseTool):
    """
    Tool: Calculate volatility metrics.
    Category: CALCULATION
    Stateless: Yes
    Side Effects: No
    LLM Calls: No
    """
    
    def __init__(self):
        super().__init__()
        self._metadata = ToolMetadata(
            tool_id="volatility_calc_v1",
            name="Volatility Calculator",
            description="Calculates historical volatility from return series",
            category=ToolCategory.CALCULATION,
            version="1.0.0",
            author="APEX System",
            created_at=datetime.now(),
            input_schema=[
                ToolInputSchema("returns", "List[Decimal]", True, "Return series"),
                ToolInputSchema("annualization_factor", "int", False, "Periods per year", default=252),
                ToolInputSchema("window", "int", False, "Rolling window size", default=20)
            ],
            output_schema=[
                ToolOutputSchema("volatility", "Decimal", "Annualized volatility"),
                ToolOutputSchema("variance", "Decimal", "Variance of returns")
            ],
            timeout_ms=2000,
            is_stateless=True,
            has_side_effects=False,
            requires_llm=False
        )
    
    def get_metadata(self) -> ToolMetadata:
        return self._metadata
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        if "returns" not in inputs:
            return False
        if not isinstance(inputs["returns"], list) or len(inputs["returns"]) < 2:
            return False
        return True
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        execution_id = self._generate_execution_id(self._metadata.tool_id, inputs)
        start_time = datetime.now()
        
        try:
            if not self.validate_inputs(inputs):
                raise validation_error("INVALID_TOOL_INPUTS", "Invalid inputs for volatility calculation")
            
            returns = [float(r) for r in inputs["returns"]]
            annualization = inputs.get("annualization_factor", 252)
            
            # Calculate mean
            mean_return = sum(returns) / len(returns)
            
            # Calculate variance
            squared_diffs = [(r - mean_return) ** 2 for r in returns]
            variance = sum(squared_diffs) / len(squared_diffs)
            
            # Standard deviation
            std_dev = variance ** 0.5
            
            # Annualize
            annualized_vol = std_dev * (annualization ** 0.5)
            
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            self._record_execution(
                execution_id=execution_id,
                tool_id=self._metadata.tool_id,
                inputs=inputs,
                outputs={
                    "volatility": str(Decimal(str(annualized_vol))),
                    "variance": str(Decimal(str(variance)))
                },
                status=ToolExecutionStatus.SUCCESS,
                duration_ms=duration_ms
            )
            
            return {
                "volatility": Decimal(str(annualized_vol)),
                "variance": Decimal(str(variance))
            }
            
        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._record_execution(
                execution_id=execution_id,
                tool_id=self._metadata.tool_id,
                inputs=inputs,
                outputs=None,
                status=ToolExecutionStatus.FAILED,
                duration_ms=duration_ms,
                error_message=str(e)
            )
            raise


class DataValidationTool(BaseTool):
    """
    Tool: Validate data quality.
    Category: VALIDATION
    Stateless: Yes
    Side Effects: No
    LLM Calls: No
    """
    
    def __init__(self):
        super().__init__()
        self._metadata = ToolMetadata(
            tool_id="data_validate_v1",
            name="Data Validator",
            description="Validates data quality including gaps, outliers, and consistency",
            category=ToolCategory.VALIDATION,
            version="1.0.0",
            author="APEX System",
            created_at=datetime.now(),
            input_schema=[
                ToolInputSchema("data", "List[Any]", True, "Data series to validate"),
                ToolInputSchema("check_gaps", "bool", False, "Check for gaps", default=True),
                ToolInputSchema("check_outliers", "bool", False, "Check for outliers", default=True),
                ToolInputSchema("outlier_sigma", "float", False, "Sigma threshold", default=3.0)
            ],
            output_schema=[
                ToolOutputSchema("is_valid", "bool", "Overall validity"),
                ToolOutputSchema("issues", "List[str]", "List of identified issues"),
                ToolOutputSchema("statistics", "Dict", "Data statistics")
            ],
            timeout_ms=3000,
            is_stateless=True,
            has_side_effects=False,
            requires_llm=False
        )
    
    def get_metadata(self) -> ToolMetadata:
        return self._metadata
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        return "data" in inputs and isinstance(inputs["data"], list)
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        execution_id = self._generate_execution_id(self._metadata.tool_id, inputs)
        start_time = datetime.now()
        
        try:
            if not self.validate_inputs(inputs):
                raise validation_error("INVALID_TOOL_INPUTS", "Data list is required")
            
            data = inputs["data"]
            check_gaps = inputs.get("check_gaps", True)
            check_outliers = inputs.get("check_outliers", True)
            outlier_sigma = inputs.get("outlier_sigma", 3.0)
            
            issues = []
            
            # Check for empty data
            if len(data) == 0:
                issues.append("Empty data series")
                return {
                    "is_valid": False,
                    "issues": issues,
                    "statistics": {}
                }
            
            # Convert to floats for analysis
            try:
                numeric_data = [float(d) for d in data]
            except (ValueError, TypeError):
                issues.append("Non-numeric data detected")
                return {
                    "is_valid": False,
                    "issues": issues,
                    "statistics": {}
                }
            
            # Basic statistics
            mean_val = sum(numeric_data) / len(numeric_data)
            min_val = min(numeric_data)
            max_val = max(numeric_data)
            
            # Check for zeros or negatives if prices
            if all(d >= 0 for d in numeric_data):
                zero_count = sum(1 for d in numeric_data if d == 0)
                if zero_count > 0:
                    issues.append(f"Found {zero_count} zero values")
            
            # Check for outliers
            if check_outliers and len(numeric_data) > 3:
                # Calculate std dev
                variance = sum((x - mean_val) ** 2 for x in numeric_data) / len(numeric_data)
                std_dev = variance ** 0.5
                
                if std_dev > 0:
                    outliers = [
                        i for i, x in enumerate(numeric_data)
                        if abs(x - mean_val) > outlier_sigma * std_dev
                    ]
                    if outliers:
                        issues.append(f"Found {len(outliers)} outliers (>{outlier_sigma} sigma)")
            
            is_valid = len(issues) == 0
            
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            self._record_execution(
                execution_id=execution_id,
                tool_id=self._metadata.tool_id,
                inputs=inputs,
                outputs={
                    "is_valid": is_valid,
                    "issues": issues,
                    "statistics": {
                        "count": len(data),
                        "mean": str(Decimal(str(mean_val))),
                        "min": str(Decimal(str(min_val))),
                        "max": str(Decimal(str(max_val)))
                    }
                },
                status=ToolExecutionStatus.SUCCESS,
                duration_ms=duration_ms
            )
            
            return {
                "is_valid": is_valid,
                "issues": issues,
                "statistics": {
                    "count": len(data),
                    "mean": Decimal(str(mean_val)),
                    "min": Decimal(str(min_val)),
                    "max": Decimal(str(max_val))
                }
            }
            
        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._record_execution(
                execution_id=execution_id,
                tool_id=self._metadata.tool_id,
                inputs=inputs,
                outputs=None,
                status=ToolExecutionStatus.FAILED,
                duration_ms=duration_ms,
                error_message=str(e)
            )
            raise


class ToolRegistry:
    """
    Central registry for all tools.
    Section 4: Tool Layer
    """
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._lock = RLock()
    
    def register(self, tool: Tool) -> str:
        """Register a tool"""
        with self._lock:
            metadata = tool.get_metadata()
            
            if metadata.tool_id in self._tools:
                raise validation_error(
                    "TOOL_ALREADY_REGISTERED",
                    f"Tool {metadata.tool_id} is already registered"
                )
            
            # Enforce Section 4 constraints
            if not metadata.is_stateless:
                raise validation_error(
                    "TOOL_MUST_BE_STATELESS",
                    f"Tool {metadata.tool_id} must be stateless per Section 4"
                )
            
            if metadata.has_side_effects:
                raise validation_error(
                    "TOOL_NO_SIDE_EFFECTS",
                    f"Tool {metadata.tool_id} cannot have side effects per Section 4"
                )
            
            if metadata.requires_llm:
                raise validation_error(
                    "TOOL_NO_LLM_CALLS",
                    f"Tool {metadata.tool_id} cannot make LLM calls per Section 4"
                )
            
            self._tools[metadata.tool_id] = tool
            return metadata.tool_id
    
    def get_tool(self, tool_id: str) -> Optional[Tool]:
        """Get a registered tool"""
        with self._lock:
            return self._tools.get(tool_id)
    
    def list_tools(
        self, 
        category: Optional[ToolCategory] = None
    ) -> List[Tool]:
        """List registered tools"""
        with self._lock:
            tools = list(self._tools.values())
            if category:
                tools = [t for t in tools if t.get_metadata().category == category]
            return tools
    
    def execute_tool(
        self,
        tool_id: str,
        inputs: Dict[str, Any],
        timeout_ms: Optional[int] = None
    ) -> Dict[str, Any]:
        """Execute a tool by ID"""
        with self._lock:
            tool = self._tools.get(tool_id)
            if not tool:
                raise validation_error("TOOL_NOT_FOUND", f"Tool {tool_id} not found")
            
            metadata = tool.get_metadata()
            actual_timeout = timeout_ms or metadata.timeout_ms
            
            # Validate inputs
            if not tool.validate_inputs(inputs):
                raise validation_error("INVALID_TOOL_INPUTS", f"Invalid inputs for tool {tool_id}")
            
            # Execute with timeout (simplified - real impl would use threading)
            return tool.execute(inputs)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics"""
        with self._lock:
            return {
                "total_tools": len(self._tools),
                "tools_by_category": {
                    cat.value: sum(1 for t in self._tools.values() 
                                   if t.get_metadata().category == cat)
                    for cat in ToolCategory
                }
            }


def create_standard_tool_registry() -> ToolRegistry:
    """Create a registry with all standard tools"""
    registry = ToolRegistry()
    
    # Register all standard tools
    registry.register(PriceNormalizationTool())
    registry.register(ReturnCalculationTool())
    registry.register(VolatilityCalculationTool())
    registry.register(DataValidationTool())
    
    return registry


__all__ = [
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
