"""
APEX v3 - Observability Stack (§32)
Structured JSON logging, Prometheus metrics, OpenTelemetry traces, Log Redaction
"""
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from contextlib import contextmanager
from functools import wraps

# --- Log Redaction (§33.4, §32.2) ---

SENSITIVE_PATTERNS = [
    (re.compile(r'api[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', re.I), '[REDACTED_API_KEY]'),
    (re.compile(r'password["\']?\s*[:=]\s*["\']?([^\s"\']+)["\']?', re.I), '[REDACTED_PASSWORD]'),
    (re.compile(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'), '[REDACTED_CC]'),
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[REDACTED_SSN]'),
    (re.compile(r'Bearer\s+[a-zA-Z0-9_\-\.]+'), 'Bearer [REDACTED_TOKEN]'),
]

class LogRedactor(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in SENSITIVE_PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        if record.args:
            try:
                record.args = tuple(
                    pattern.sub(replacement, str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                    for pattern, replacement in SENSITIVE_PATTERNS
                ) or record.args
            except Exception:
                pass
        return True

# --- Structured Logging (§32.1) ---

@dataclass
class StructuredLogRecord:
    timestamp: str
    level: str
    component: str
    trace_id: str
    span_id: str
    session_id: str
    message: str
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)

class StructuredLogger(logging.Logger):
    def __init__(self, name: str, component: str = "UNKNOWN"):
        super().__init__(name)
        self.component = component
        self.addFilter(LogRedactor())
        
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(message)s')) # We format manually
        self.addHandler(handler)
        self.setLevel(logging.INFO)

    def _log(self, level, msg, extra=None, **kwargs):
        trace_id = kwargs.pop('trace_id', getattr(self, '_trace_id', str(uuid.uuid4())))
        span_id = kwargs.pop('span_id', str(uuid.uuid4()))
        session_id = kwargs.pop('session_id', getattr(self, '_session_id', 'global'))
        
        record = StructuredLogRecord(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            level=logging.getLevelName(level),
            component=self.component,
            trace_id=trace_id,
            span_id=span_id,
            session_id=session_id,
            message=str(msg),
            extra=extra or {}
        )
        super()._log(level, record.to_json(), (), **kwargs)

    def set_context(self, trace_id: str, session_id: str):
        self._trace_id = trace_id
        self._session_id = session_id

logging.setLoggerClass(StructuredLogger)

# --- Prometheus Metrics (§32.3) ---

@dataclass
class MetricSample:
    name: str
    value: float
    labels: Dict[str, str]
    timestamp: float

class MetricsRegistry:
    def __init__(self):
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._samples: List[MetricSample] = []

    def inc_counter(self, name: str, labels: Optional[Dict[str, str]] = None, value: float = 1.0):
        key = f"{name}{str(labels)}"
        self._counters[key] = self._counters.get(key, 0) + value
        self._samples.append(MetricSample(name, self._counters[key], labels or {}, time.time()))

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        key = f"{name}{str(labels)}"
        self._gauges[key] = value
        self._samples.append(MetricSample(name, value, labels or {}, time.time()))

    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        key = f"{name}{str(labels)}"
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        self._samples.append(MetricSample(name, value, labels or {}, time.time()))

    def generate_prometheus_output(self) -> str:
        lines = []
        for sample in self._samples[-1000:]: # Last 1000 samples
            label_str = ",".join(f'{k}="{v}"' for k, v in sample.labels.items())
            lines.append(f"{sample.name}{{{label_str}}} {sample.value}")
        return "\n".join(lines)

DEFAULT_METRICS = MetricsRegistry()

# --- OpenTelemetry Tracing (§32.4) ---

@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    start_time: float
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "OK" # OK, ERROR

    def finish(self, status: str = "OK"):
        self.end_time = time.time()
        self.status = status

class Tracer:
    def __init__(self):
        self.active_spans: Dict[str, Span] = {}
        self.finished_spans: List[Span] = []

    def start_span(self, name: str, parent_span_id: Optional[str] = None, attributes: Optional[Dict] = None) -> Span:
        trace_id = str(uuid.uuid4()) # In real impl, propagate from header
        span_id = str(uuid.uuid4())
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            start_time=time.time(),
            attributes=attributes or {}
        )
        self.active_spans[span_id] = span
        return span

    @contextmanager
    def trace(self, name: str, parent_span_id: Optional[str] = None, attributes: Optional[Dict] = None):
        span = self.start_span(name, parent_span_id, attributes)
        try:
            yield span
            span.finish("OK")
        except Exception as e:
            span.finish("ERROR")
            span.attributes['error.message'] = str(e)
            raise
        finally:
            self.finished_spans.append(span)
            if span.span_id in self.active_spans:
                del self.active_spans[span.span_id]

DEFAULT_TRACER = Tracer()

# --- Cost Tracker (§31, §90) ---

@dataclass
class CostEntry:
    component: str
    category: str # LLM, API, DATA
    amount_usd: float
    timestamp: float
    trace_id: str

class CostTracker:
    def __init__(self, daily_budget_usd: float = 100.0):
        self.daily_budget_usd = daily_budget_usd
        self.entries: List[CostEntry] = []
        self.current_spend_usd = 0.0
        self.budget_exhausted = False

    def record_cost(self, component: str, category: str, amount_usd: float, trace_id: str):
        if self.budget_exhausted:
            raise PermissionError(f"Daily budget of ${self.daily_budget_usd} exhausted.")
        
        entry = CostEntry(component, category, amount_usd, time.time(), trace_id)
        self.entries.append(entry)
        self.current_spend_usd += amount_usd
        
        if self.current_spend_usd >= (self.daily_budget_usd * 0.95):
            self.budget_exhausted = True
            # Trigger PIL pause in real impl
            
        DEFAULT_METRICS.set_gauge("apex_budget_llm_cost_usd_total", self.current_spend_usd)

DEFAULT_COST_TRACKER = CostTracker()
