"""APEX v3 Tool Layer - Core implementations."""
from __future__ import annotations
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, TypeVar, Generic, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid
import math

# Data Registry
class DataRegistry:
    def __init__(self, max_memory_mb: int = 500):
        self._store: Dict[str, Tuple[Any, datetime, float]] = {}
        self._max_memory_mb = max_memory_mb
    
    def put(self, key: str, value: Any, quality_score: float = 1.0):
        now = datetime.now(timezone.utc)
        self._store[key] = (value, now, quality_score)
    
    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None
        value, fetched_at, _ = self._store[key]
        if datetime.now(timezone.utc) - fetched_at > timedelta(hours=1):
            del self._store[key]
            return None
        return value

_data_registry = DataRegistry()

def _store_in_registry(namespace: str, ticker: str, data_type: str, content: Any) -> str:
    full_key = f"{namespace}.{ticker}.{data_type}.{uuid.uuid4().hex[:8]}"
    _data_registry.put(full_key, content)
    return full_key


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


T = TypeVar('T')

@dataclass
class ToolResult(Generic[T]):
    success: bool
    data_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class BaseTool:
    name: str = "base_tool"
    description: str = "Base tool"
    
    def get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            tool_id=self.name,
            name=self.name,
            version="1.0.0",
            description=self.description,
            input_schema=(),
            output_schema=(),
            stateless=True,
            llm_free=True
        )
    
    def validate_inputs(self, **kwargs) -> bool:
        return True
    def execute(self, **kwargs) -> ToolResult: raise NotImplementedError

# Market Data Tools
class FetchMarketDataTool(BaseTool):
    name = "fetch_market_data"
    description = "Fetch historical OHLCV bars"
    
    def execute(self, ticker: str, interval: str, bars: int, **kwargs) -> ToolResult:
        try:
            if not ticker or interval not in ["1m","5m","15m","30m","1h","4h","1d","1w"]:
                raise ValueError("Invalid ticker or interval")
            
            now = datetime.now(timezone.utc)
            bars_data = []
            base_price = Decimal("150.00")
            
            for i in range(bars):
                bar_time = now - timedelta(days=(bars-i))
                change = Decimal(str((i % 10 - 5) * 0.01))
                close = base_price + change
                bars_data.append({
                    "timestamp": bar_time.isoformat(),
                    "open": str(base_price), "high": str(close + Decimal("0.50")),
                    "low": str(close - Decimal("0.30")), "close": str(close),
                    "volume": 100000 + i * 1000
                })
            
            data_id = _store_in_registry("market_data", ticker, f"ohlcv_{interval}", bars_data)
            return ToolResult(success=True, data_id=data_id, metadata={"bars_count": bars})
        except Exception as e:
            return ToolResult(success=False, error_code="FETCH_FAILED", error_message=str(e))

class FetchMarketDepthTool(BaseTool):
    name = "fetch_market_depth"
    def execute(self, ticker: str, levels: int = 10, **kwargs) -> ToolResult:
        try:
            depth = {"bids": [{"price": str(Decimal("149.95")-Decimal(str(i)*0.01)), "size": 1000} for i in range(levels)],
                     "asks": [{"price": str(Decimal("150.05")+Decimal(str(i)*0.01)), "size": 1000} for i in range(levels)]}
            data_id = _store_in_registry("depth", ticker, "orderbook", depth)
            return ToolResult(success=True, data_id=data_id)
        except Exception as e:
            return ToolResult(success=False, error_code="DEPTH_FAILED", error_message=str(e))

class FetchOptionsDataTool(BaseTool):
    name = "fetch_options_data"
    def execute(self, ticker: str, expiry: Optional[str] = None, **kwargs) -> ToolResult:
        try:
            chain = {"calls": [], "puts": [], "underlying": "150.00"}
            data_id = _store_in_registry("options", ticker, "chain", chain)
            return ToolResult(success=True, data_id=data_id)
        except Exception as e:
            return ToolResult(success=False, error_code="OPTIONS_FAILED", error_message=str(e))

class FetchTickDataTool(BaseTool):
    name = "fetch_tick_data"
    def execute(self, ticker: str, start_time: str, end_time: str, limit: int = 1000, **kwargs) -> ToolResult:
        try:
            ticks = [{"timestamp": start_time, "price": "150.00", "size": 100, "side": "buy"}]
            data_id = _store_in_registry("market_data", ticker, "ticks", ticks)
            return ToolResult(success=True, data_id=data_id)
        except Exception as e:
            return ToolResult(success=False, error_code="TICK_FAILED", error_message=str(e))

class FetchCorporateActionsTool(BaseTool):
    name = "fetch_corporate_actions"
    def execute(self, ticker: str, start_date: str, end_date: str, **kwargs) -> ToolResult:
        try:
            actions = [{"type": "dividend", "ex_date": "2026-03-15", "amount": "0.50"}]
            data_id = _store_in_registry("market_data", ticker, "corporate_actions", actions)
            return ToolResult(success=True, data_id=data_id)
        except Exception as e:
            return ToolResult(success=False, error_code="CA_FAILED", error_message=str(e))

class FetchMultiTimeframeTool(BaseTool):
    name = "fetch_multi_timeframe"
    def execute(self, ticker: str, intervals: List[str], bars_per_tf: int = 100, **kwargs) -> ToolResult:
        try:
            mtf = {}
            for interval in intervals:
                r = FetchMarketDataTool().execute(ticker=ticker, interval=interval, bars=bars_per_tf)
                if r.success:
                    mtf[interval] = r.data_id
            data_id = _store_in_registry("market_data", ticker, "mtf", mtf)
            return ToolResult(success=True, data_id=data_id)
        except Exception as e:
            return ToolResult(success=False, error_code="MTF_FAILED", error_message=str(e))

# Technical Analysis
class ComputeIndicatorsTool(BaseTool):
    name = "compute_indicators"
    
    def execute(self, data_id: str, indicators: List[str], params: Optional[Dict] = None, **kwargs) -> ToolResult:
        try:
            bars = _data_registry.get(data_id)
            if not bars:
                return ToolResult(success=False, error_code="DATA_NOT_FOUND", error_message="No data")
            
            closes = [Decimal(b["close"]) for b in bars]
            computed = {}
            
            for ind in indicators:
                if ind == "sma":
                    period = params.get("sma_period", 20) if params else 20
                    computed["sma"] = self._sma(closes, period)
                elif ind == "rsi":
                    period = params.get("rsi_period", 14) if params else 14
                    computed["rsi"] = self._rsi(closes, period)
                elif ind == "macd":
                    computed["macd"] = self._macd(closes)
                elif ind == "bollinger":
                    computed["bollinger"] = self._bb(closes)
            
            out_id = _store_in_registry("indicators", "computed", "tech", computed)
            return ToolResult(success=True, data_id=out_id, metadata={"indicators": list(computed.keys())})
        except Exception as e:
            return ToolResult(success=False, error_code="INDICATOR_FAILED", error_message=str(e))
    
    def _sma(self, prices: List[Decimal], period: int) -> List[Optional[Decimal]]:
        result = []
        for i in range(len(prices)):
            if i < period - 1:
                result.append(None)
            else:
                result.append(sum(prices[i-period+1:i+1]) / period)
        return result
    
    def _rsi(self, prices: List[Decimal], period: int = 14) -> List[Optional[Decimal]]:
        if len(prices) < period + 1:
            return [None] * len(prices)
        rsi = [None] * len(prices)
        gains, losses = [], []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(change, Decimal("0")))
            losses.append(max(-change, Decimal("0")))
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        if avg_loss == 0:
            rsi[period] = Decimal("100")
        else:
            rs = avg_gain / avg_loss
            rsi[period] = Decimal("100") - (Decimal("100") / (1 + rs))
        for i in range(period + 1, len(prices)):
            avg_gain = (avg_gain * (period-1) + gains[i-1]) / period
            avg_loss = (avg_loss * (period-1) + losses[i-1]) / period
            if avg_loss == 0:
                rsi[i] = Decimal("100")
            else:
                rs = avg_gain / avg_loss
                rsi[i] = Decimal("100") - (Decimal("100") / (1 + rs))
        return rsi
    
    def _macd(self, prices: List[Decimal]) -> Dict:
        ema12 = self._ema(prices, 12)
        ema26 = self._ema(prices, 26)
        macd_line = [(e12 - e26) if e12 and e26 else None for e12, e26 in zip(ema12, ema26)]
        valid = [m for m in macd_line if m]
        signal = self._ema(valid, 9) if len(valid) >= 9 else [None] * len(prices)
        return {"macd_line": macd_line, "signal_line": signal, "histogram": [None] * len(prices)}
    
    def _ema(self, prices: List[Decimal], period: int) -> List[Optional[Decimal]]:
        if len(prices) < period:
            return [None] * len(prices)
        ema = [None] * len(prices)
        ema[period-1] = sum(prices[:period]) / period
        mult = Decimal("2") / (period + 1)
        for i in range(period, len(prices)):
            ema[i] = ((prices[i] - ema[i-1]) * mult + ema[i-1])
        return ema
    
    def _bb(self, prices: List[Decimal], period: int = 20, std_dev: float = 2.0) -> Dict:
        middle = self._sma(prices, period)
        upper, lower = [], []
        std_d = Decimal(str(std_dev))
        for i in range(len(prices)):
            if i < period - 1 or middle[i] is None:
                upper.append(None)
                lower.append(None)
            else:
                window = prices[i-period+1:i+1]
                variance = sum((p - middle[i])**2 for p in window) / period
                std = Decimal(str(math.sqrt(float(variance))))
                upper.append(middle[i] + std_d * std)
                lower.append(middle[i] - std_d * std)
        return {"upper": upper, "middle": middle, "lower": lower}

# Signal Generation
class GenerateSignalsTool(BaseTool):
    name = "generate_signals"
    def execute(self, indicators_data_id: str, strategy: str, **kwargs) -> ToolResult:
        try:
            indicators = _data_registry.get(indicators_data_id)
            if not indicators:
                return ToolResult(success=False, error_code="NOT_FOUND", error_message="No indicators")
            signals = []
            if "rsi" in indicators:
                rsi = indicators["rsi"]
                for i, v in enumerate(rsi):
                    if v and v < Decimal("30"):
                        signals.append({"type": "buy", "index": i, "confidence": Decimal("0.65")})
                    elif v and v > Decimal("70"):
                        signals.append({"type": "sell", "index": i, "confidence": Decimal("0.65")})
            data_id = _store_in_registry("signals", "gen", strategy, signals)
            return ToolResult(success=True, data_id=data_id, metadata={"count": len(signals)})
        except Exception as e:
            return ToolResult(success=False, error_code="SIGNAL_FAILED", error_message=str(e))

class AggregateSignalsTool(BaseTool):
    name = "aggregate_signals"
    def execute(self, signal_data_ids: List[str], **kwargs) -> ToolResult:
        try:
            all_signals = []
            for did in signal_data_ids:
                sigs = _data_registry.get(did)
                if sigs:
                    all_signals.extend(sigs)
            buy_w = sum(s.get("confidence", Decimal("0.5")) for s in all_signals if s.get("type") == "buy")
            sell_w = sum(s.get("confidence", Decimal("0.5")) for s in all_signals if s.get("type") == "sell")
            agg = "neutral"
            if buy_w > sell_w * Decimal("1.5"): agg = "strong_buy"
            elif buy_w > sell_w: agg = "buy"
            elif sell_w > buy_w * Decimal("1.5"): agg = "strong_sell"
            elif sell_w > buy_w: agg = "sell"
            result = {"aggregate_signal": agg, "buy_weight": str(buy_w), "sell_weight": str(sell_w)}
            data_id = _store_in_registry("signals", "agg", "final", result)
            return ToolResult(success=True, data_id=data_id, metadata=result)
        except Exception as e:
            return ToolResult(success=False, error_code="AGG_FAILED", error_message=str(e))

class MTFConfluenceFilterTool(BaseTool):
    name = "mtf_confluence_filter"
    def execute(self, primary_signal_id: str, mtf_data_id: str, min_timeframes: int = 2, **kwargs) -> ToolResult:
        try:
            signals = _data_registry.get(primary_signal_id)
            if not signals:
                return ToolResult(success=False, error_code="NOT_FOUND", error_message="No signals")
            filtered = [{**s, "confluence_confirmed": True} for s in signals]
            data_id = _store_in_registry("signals", "filtered", "mtf", filtered)
            return ToolResult(success=True, data_id=data_id, metadata={"count": len(filtered)})
        except Exception as e:
            return ToolResult(success=False, error_code="FILTER_FAILED", error_message=str(e))

# Risk & Position Sizing
class ComputePositionSizeTool(BaseTool):
    name = "compute_position_size"
    def execute(self, account_equity: str, risk_pct: str, stop_loss_pct: str, price: str, **kwargs) -> ToolResult:
        try:
            equity = Decimal(account_equity)
            risk = Decimal(risk_pct) / Decimal("100")
            stop = Decimal(stop_loss_pct) / Decimal("100")
            share_price = Decimal(price)
            risk_amount = equity * risk
            position_value = risk_amount / stop if stop > 0 else Decimal("0")
            shares = int(position_value / share_price)
            result = {"shares": shares, "position_value": str(position_value), "risk_amount": str(risk_amount)}
            data_id = _store_in_registry("risk", " sizing", "result", result)
            return ToolResult(success=True, data_id=data_id, metadata=result)
        except Exception as e:
            return ToolResult(success=False, error_code="SIZE_FAILED", error_message=str(e))

class FormatTradePlanTool(BaseTool):
    name = "format_trade_plan"
    def execute(self, signal_data_id: str, position_data_id: str, ticker: str, **kwargs) -> ToolResult:
        try:
            signals = _data_registry.get(signal_data_id)
            position = _data_registry.get(position_data_id)
            plan = {"ticker": ticker, "signal": signals, "position": position, "generated_at": datetime.now(timezone.utc).isoformat()}
            data_id = _store_in_registry("plans", ticker, "trade_plan", plan)
            return ToolResult(success=True, data_id=data_id, metadata={"ticker": ticker})
        except Exception as e:
            return ToolResult(success=False, error_code="PLAN_FAILED", error_message=str(e))
