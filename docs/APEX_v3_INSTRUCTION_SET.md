# APEX v3 — Unified Architecture Specification
### AI Agent Trader: Self-Improving, Epistemically Honest, Behaviorally Aware Trading Intelligence

> **Version:** 3.0 | **Status:** Authoritative — supersedes all prior versions  
> **Scope:** This is the single complete specification for APEX. Everything is here. Nothing is deferred.  
> **Advisory Constraint:** APEX generates research signals and structured trade plans. It **never executes orders.** This is permanent and cannot be overridden by configuration, instruction, or autonomous action.

---

## SYSTEM IDENTITY

APEX is a dual-mode trading intelligence that runs continuously in the background (Proactive Intelligence Layer) while simultaneously serving on-demand analysis requests (Reactive Intelligence Layer). It learns from its own failures, from human experts, from external sources, and from observed analyst methodology. It monitors its own analytical health, tracks its knowledge boundaries, and guards users against behavioral biases. It forgets knowledge that becomes stale. It maintains an evolving view on every ticker across sessions. It never pretends to know what it doesn't know.

**What makes APEX different from a signal generator:** A signal generator produces outputs. APEX produces outputs *and* understands why it produced them, remembers when similar outputs were wrong, adjusts its confidence based on evidence quality, tells users when it should not be trusted, and continuously improves the underlying intelligence that generates those outputs.

---

## CORE ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   APEX v3                                        │
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐   │
│  │                        DUAL INTELLIGENCE SYSTEM                            │   │
│  │                                                                            │   │
│  │   PROACTIVE INTELLIGENCE LAYER (PIL)  ◄── Bridge ──►  REACTIVE LAYER     │   │
│  │   Continuous background monitoring            On-demand analysis          │   │
│  │   ├─ Regime Intelligence                      ├─ Intent Router (3-tier)   │   │
│  │   ├─ Strategy Readiness Monitor               ├─ Compiled Workflows       │   │
│  │   ├─ Opportunity Scout                        ├─ Why Engine (5 layers)    │   │
│  │   ├─ Calendar Intelligence                    ├─ Reflection Layer         │   │
│  │   ├─ Narrative Monitor                        ├─ NarrativeAgent           │   │
│  │   └─ Risk Sentinel                            └─ Position Confirmation    │   │
│  └───────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐   │
│  │                      INTELLIGENCE SUBSTRATE                                │   │
│  │                                                                            │   │
│  │  Failure Memory  │  Learning Engine  │  Knowledge Application Engine      │   │
│  │  Expert Observer │  Abstraction Store│  Cross-Session Continuity          │   │
│  │  Human Feedback  │  Behavioral Guard │  Analytical Debt Monitor           │   │
│  └───────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────────────┐    │
│  │  STRATEGY LAYER  │  │   TOOL LAYER    │  │      DATA REGISTRY           │    │
│  │  Registry        │  │  Stateless tools│  │  In-memory + TTL eviction    │    │
│  │  Selector        │  │  Type-safe I/O  │  │  Memory-bounded              │    │
│  │  Aggregator      │  │  No LLM calls   │  │  Concurrency-safe            │    │
│  │  Plugins (N)     │  │  No side effects│  │  Namespace-isolated          │    │
│  └─────────────────┘  └─────────────────┘  └──────────────────────────────┘    │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │  GUARDRAIL LAYER  G1─G11 (non-bypassable)  │  ETHICAL FRAMEWORK (8 axioms)│   │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │                    OBSERVABILITY STACK                                     │    │
│  │  Structured JSON Logs │ Prometheus Metrics │ OpenTelemetry Traces         │    │
│  │  Cost Tracking │ Health Endpoints │ Analytical Debt Dashboard              │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## SECTION 1: FOUNDATIONAL INVARIANTS

These are non-negotiable correctness requirements. Every other section depends on them being satisfied.

### 1.1 Decimal Arithmetic for All Monetary Values

Python's `float` uses IEEE 754 binary arithmetic. `0.1 + 0.2 == 0.30000000000000004`. Every P&L calculation, every position size, every heat percentage, every commission, every stop level — all are silently wrong with float arithmetic. This is not a style preference; it is a correctness requirement.

```python
from decimal import Decimal, ROUND_HALF_UP, getcontext
getcontext().prec = 28

# WRONG — never do this for money:
position_size = 100000.0 * 0.02       # float arithmetic
heat = realized_pnl / portfolio_value  # float arithmetic

# CORRECT — always Decimal for money:
position_size = Decimal('100000.00') * Decimal('0.02')
price = Decimal('149.985').quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

**Numerical Policy (applied everywhere):**
```yaml
numerical_policy:
  monetary_type: Decimal       # prices, P&L, heat, commissions, sizing, notional
  monetary_precision: 28
  price_display_precision: 2
  percentage_precision: 6
  rounding_mode: ROUND_HALF_UP
  indicator_type: float64      # RSI, ATR, correlation — OK as float
  confidence_type: float64     # confidence scores — OK as float
  database_monetary_column: "NUMERIC(28,10)"  # never FLOAT or DOUBLE
  json_monetary_serialization: "string"        # preserve precision in transit
```

**G11 — Numerical Type Gate:** Guardrail G11 validates that every monetary field arriving at any tool boundary is typed as `Decimal`. A `float` where `Decimal` is expected raises `NumericalTypeViolation` immediately. Silent coercion is never performed.

### 1.2 Exactly-Once Processing

Every state-mutating event carries a unique idempotency key. Processing the same event twice produces the same result without duplicate side effects.

```python
class IdempotentProcessor:
    def process(self, event: Event) -> Result:
        if self.already_processed(event.idempotency_key):
            return self.get_cached_result(event.idempotency_key)
        with self.db.transaction():           # atomic: state + outbox
            result = self._do_process(event)
            self.mark_processed(event.idempotency_key, result)
            self.write_to_outbox(event.idempotency_key, result)
        return result
```

**Transactional Outbox Pattern:** State changes and event publication happen in the same database transaction. A background worker reads the outbox and delivers events. If the system crashes after the transaction commits but before delivery, the outbox worker retries on restart — no events are lost, no events are duplicated.

**Dead Letter Queue:** Events that cannot be processed after configured retries are written to `dead_letter_queue`. DLQ growth above the configured threshold triggers a `DLQ_GROWING` alert. Events can be replayed after the underlying cause is resolved.

**Coverage:** Every POST endpoint requires an `Idempotency-Key` header. PIL events carry cycle-number keys. Data feed ticks carry exchange sequence numbers as deduplication keys.

### 1.3 Clock Authority

```yaml
time_authority:
  source: ntp
  servers: ["time.google.com", "time.aws.com"]
  max_drift_ms: 50
  sync_interval_seconds: 60
  internal_precision: microsecond
  storage_timezone: UTC
  display_timezone: user_configured_iana
```

The server refuses to start if clock drift exceeds `max_drift_ms`. Every `AuditTrail` record captures both application-layer and database-layer timestamps; discrepancies above the configured tolerance are flagged. All internal timestamps are UTC. Timezone conversion happens only at the display layer.

### 1.4 Startup Sequence (Gated, Ordered)

```
Phase 0 — PRE-FLIGHT:
  ① Clock drift < max_drift_ms (abort if not)
  ② Load all configuration → schema + range + cross-field validation (abort if invalid)
  ③ Verify no plaintext credentials in any config file
  ④ Verify numerical_policy is correct

Phase 1 — STORAGE:
  ⑤ Connect to database; verify schema version
  ⑥ Acquire distributed migration lock
  ⑦ Apply all pending migrations in sequence
  ⑧ Release migration lock
  ⑨ Connect to shared cache; verify connectivity
  ⑩ Initialize Data Registry

Phase 2 — INTELLIGENCE LOADING:
  ⑪ Load strategy plugins; validate each against full Plugin Interface contract
  ⑫ Log and skip invalid plugins (do NOT abort startup)
  ⑬ Load ML models; verify checksums against Model Registry
  ⑭ Load prompt templates

Phase 3 — STATE RECONSTRUCTION:
  ⑮ Reconstruct StrategicMemory from database (positions, heat, correlation)
  ⑯ PIL warm-start: load most recent pil_state_snapshot
  ⑰ Validate PIL state; flag PIL_COLD_START if snapshot exceeds max_snapshot_age

Phase 4 — EXTERNAL CONNECTIONS:
  ⑱ Connect to all data vendors; run health probes
  ⑲ Configure circuit breakers; load state from shared cache
  ⑳ Verify LLM provider connectivity; configure failover chain

Phase 5 — SERVICES:
  ㉑ Start PIL scheduler (emits PIL_STARTING)
  ㉒ Start Evolution Engine (if enabled)
  ㉓ Start WebSocket event bus
  ㉔ Accept HTTP requests
  ㉕ Mark READY; emit SESSION_STARTED
  ㉖ Write STARTUP_COMPLETE to AuditTrail
```

**Degraded startup:** Data vendor unavailable → start in analysis mode with `DataQualityWarning`. LLM unavailable → start in deterministic-only mode. These do not abort startup.

### 1.5 Shutdown Sequence (7-Phase)

```
Phase 1: Stop accepting new work (immediate)
Phase 2: Notify WebSocket clients (SHUTDOWN_IMMINENT event)
Phase 3: Drain in-flight HTTP and WebSocket requests (with timeout)
Phase 4: Checkpoint PIL and Evolution Engine (write partial snapshot)
Phase 5: Flush StrategicMemory and AuditTrail writes to database
Phase 6: Close all connections (WebSocket, database pool, cache)
Phase 7: Write SHUTDOWN_COMPLETE to AuditTrail; exit 0
```

If total duration exceeds configured timeout sum, force-exit and log to stderr. Next startup detects absent `SHUTDOWN_COMPLETE` and applies additional warm-start validation.

**Signal handling:**
```python
signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT,  graceful_shutdown)
signal.signal(signal.SIGHUP,  reload_configuration)
signal.signal(signal.SIGUSR1, dump_debug_state)
signal.signal(signal.SIGUSR2, toggle_verbose_logging)
```

### 1.6 Error Taxonomy

Every error is classified before reaching the caller. Raw exceptions never propagate to LLM context or API responses.

```python
class APEXError:
    code: str              # "DATA_FETCH_TIMEOUT", "SCHEMA_VALIDATION_FAILED"
    category: str          # see taxonomy below
    severity: str          # "critical" | "high" | "medium" | "low"
    retryable: bool
    max_retries: int
    retry_delay_ms: int    # initial; doubles on each retry (capped at max_retry_delay_ms)
    user_visible: bool
    user_message: str      # plain English; never exposes internals
    internal_message: str
    recovery_action: str
    trace_id: str
```

| Category | Retry? | Recovery |
|----------|--------|----------|
| `transient` (network timeout) | Yes, exponential backoff | Auto-retry |
| `permanent` (invalid ticker) | No | Return error to user |
| `configuration` (missing key) | No | Alert admin; halt component |
| `upstream_failure` (vendor down) | Yes, with failover | Switch to backup |
| `rate_limit` (quota exceeded) | Yes, after `Retry-After` | Throttle + queue |
| `data_quality` (anomalous price) | No | Flag + skip with warning |
| `resource` (OOM, disk full) | No | Shed load + alert |
| `concurrency` (lock conflict) | Yes, with jitter | Retry with randomized delay |
| `numerical_type` (float for money) | No | Raise immediately; never coerce |
| `llm_provider` | Yes, failover chain | LLM failover |
| `budget_exhausted` | No | Queue for next period; notify |

**Standard API error response:**
```json
{
  "status": "error",
  "error": {
    "code": "PORTFOLIO_GATE_REJECTED",
    "message": "Aggregate heat would exceed cap",
    "detail": {"current_heat": "0.18", "projected_heat": "0.22", "cap": "0.20"},
    "trace_id": "abc-123"
  },
  "data": null
}
```

### 1.7 Memory Management

APEX is a long-running process. Python's garbage collector does not prevent all leaks.

```python
class MemoryGuard:
    """Runs every N minutes (configured) in a background thread."""
    def check(self):
        snapshot = tracemalloc.take_snapshot()
        growth = self.compare_to_baseline(snapshot)
        if growth.rate_mb_per_hour > self.config.memory.leak_alert_threshold_mb_per_hour:
            logger.warning("Memory leak detected", extra={"top_allocations": growth.top_allocations})
            self.emit_event("MEMORY_LEAK_SUSPECTED", growth)
        rss_mb = psutil.Process().memory_info().rss / 1024 / 1024
        if rss_mb > self.config.memory.max_rss_mb:
            logger.critical("Memory ceiling exceeded — initiating graceful restart")
            self.emit_event("MEMORY_CEILING_EXCEEDED", {"rss_mb": rss_mb})
            shutdown_manager.initiate_graceful_restart()
```

**Rules:**
- Every cache, queue, and buffer has a configured maximum size enforced at insertion
- Event listener collections use `weakref.WeakSet()` to prevent circular reference leaks
- Log handlers are removed before adding new ones on config reload
- All data structures stored in the Data Registry are bounded

**Process supervision (systemd):**
```ini
[Service]
Type=notify
ExecStart=/usr/bin/python3 -m apex.main
Restart=on-failure
RestartSec=10
WatchdogSec=60
TimeoutStopSec=120
MemoryMax=8G
CPUQuota=400%
```

### 1.8 Health Endpoints

```
GET /health/live    → 200 {"status": "alive"}  (always, if process running)
GET /health/ready   → 200 {"status": "ready", "checks": {...}}  when all critical checks pass
                    → 503 {"status": "not_ready", "checks": {...}}  when critical check fails
GET /health/startup → 200 {"status": "started"}  after Phase 5 of startup
                    → 503 {"status": "starting", "phase": N}
```

---

## SECTION 2: CONFIGURATION ARCHITECTURE

### 2.1 Resolution Priority (Highest First)
```
1. Session overrides        — per-request values
2. User configuration       — account-level settings in database
3. Strategy configuration   — strategy-specific parameters in strategy store
4. Environment variables    — deployment-level settings via .env or secrets manager
5. Schema defaults          — declared once in config schema; last resort only
```

Application code always calls the config resolver, never a literal. The resolver returns a typed, schema-validated value.

### 2.2 Configuration Categories

**Risk Parameters:** Portfolio heat limits (Decimal), per-trade risk percentages (Decimal), notional concentration caps (Decimal), correlation thresholds, circuit breaker levels, regime multipliers, position timeout rules. All schema-validated with bounds.

**LLM Provider Chain:**
```yaml
llm:
  providers:
    - name: primary
      model: claude-sonnet-4-6
      priority: 1
    - name: fallback
      model: claude-haiku-4-5
      priority: 2
  circuit_breaker:
    failure_threshold: 3
    cooldown_seconds: 60
  failover_behavior:
    reflection_layer: deterministic_only_with_flag
    narrative_agent: structured_output_no_narrative
    tier3_routing: tier2_fallback
```

**Database Connection Pool:**
```yaml
database:
  pool_min_connections: 2
  pool_max_connections: 20
  connection_max_age_seconds: 3600
  connection_idle_timeout_seconds: 300
  statement_timeout_ms: 5000
  default_isolation: read_committed
  portfolio_isolation: repeatable_read
  order_isolation: serializable
```

**Data Registry:**
```yaml
data_registry:
  max_memory_mb: 2048
  eviction_policy: lru_ttl
  memory_warning_pct: 0.80
  memory_critical_pct: 0.95
```

**WebSocket Backpressure:**
```yaml
websocket:
  inbound_rate_limit_per_second: 10
  outbound_buffer_max_events: 500
  buffer_warning_threshold: 400
  buffer_drop_policy:
    retain: ["CIRCUIT_BREAKER", "POSITION_ALERT", "SHUTDOWN_IMMINENT"]
    drop: ["CANVAS_UPDATE", "INTELLIGENCE_BRIEF_UPDATE", "HEARTBEAT"]
```

### 2.3 Configuration Validation

Every configuration file is schema-validated, range-validated, and cross-field validated at startup. A misconfigured `max_position_pct: 1.5` (meant 1.5%, typed as 1.5 = 150%) is caught before any computation. The validator requires:
- Range bounds on every numeric field
- Cross-field constraints (`stop_loss_pct < max_position_pct`)
- Semantic validation (if `mode: live` then `broker_api_key` must be non-empty)
- Diff display on change (show exactly what changed and require confirmation)
- Configuration audit trail (who changed what, when)

---

## SECTION 3: STRATEGY ARCHITECTURE

### 3.1 Strategy Plugin Interface (Full Contract)

Every trading strategy is a self-contained plugin. The system is strategy-agnostic. All parameters are resolved from the strategy store at runtime — no hardcoded values.

```python
class StrategyPlugin(Protocol):
    # Identity
    def id(self) -> str: ...
    def name(self) -> str: ...
    def version(self) -> str: ...
    def family(self) -> str: ...  # "trend_following" | "mean_reversion" | ...
    def description(self) -> str: ...

    # Parameter Schema
    def parameter_schema(self) -> ParameterSchema: ...
    def get_parameters(self) -> dict: ...  # resolved from strategy store

    # Indicator Declaration
    def required_indicators(self) -> list[IndicatorDeclaration]: ...
    def optional_indicators(self) -> list[IndicatorDeclaration]: ...

    # Signal Generation (deterministic — same inputs → same outputs)
    def generate_signals(self, context: StrategyContext) -> list[Signal]: ...

    # Regime Fitness
    def regime_fitness(self, regime: RegimeState) -> float: ...  # 0-1
    def regime_fitness_curve(self) -> dict[str, float]: ...

    # Exit Logic
    def check_exit_conditions(self, position: Position, context: StrategyContext) -> ExitSignal | None: ...

    # Position Sizing
    def sizing_approach(self) -> SizingDeclaration: ...

    # Proactive Triggers
    def proactive_triggers(self) -> list[ProactiveTrigger]: ...
    def evaluate_trigger(self, trigger_id: str, context: StrategyContext) -> TriggerResult: ...

    # Resource Limits
    def resource_limits(self) -> PluginResourceRequirements: ...
    # max_cpu_time_ms, max_memory_mb, max_indicator_series

    # Learning Interface
    def get_learning_requirements(self) -> list[LearningRequirement]: ...
    def ingest_knowledge(self, knowledge: KnowledgeItem) -> IngestionResult: ...
    def evaluate_knowledge_impact(self, knowledge_id: str) -> ImpactAssessment: ...
```

**Sandboxing:** Plugins execute in a restricted environment. `builtins.__import__` is replaced with a guarded version. Authorized modules: `numpy`, `pandas`, `scipy`, `decimal`, `math`, `datetime`, `collections`, `typing`, APEX indicator library. Blocked: `eval`, `exec`, `compile`, `subprocess`, `os`, `sys`, `socket`, `ctypes`. All plugin exceptions are caught and converted to `plugin_error` — raw exceptions never escape.

**Determinism Requirement:** `generate_signals()` is deterministic. Given the same `data_id`, `indicators_id`, configuration snapshot, and `mode`, the output is byte-identical. This is verified by the parity test in CI.

### 3.2 Signal Schema

```python
class Signal:
    signal_id: str
    strategy_id: str
    ticker: str
    direction: str           # "long" | "short"
    strength: Decimal        # 0-1
    signal_type: str         # "HARD" | "SOFT"
    timeframe: str
    generated_at: datetime   # UTC
    idempotency_key: str
    regime_fitness: float
    indicators_used: list[str]
    unavailability_flags: dict[str, str]  # indicators that failed
    raw_signal_data: dict    # stored by opaque data_id reference
```

### 3.3 Signal Aggregator

Aggregation modes: `strongest`, `consensus`, `union`, `weighted_blend`. The aggregator respects the configured mode and produces a `CompositeSignal` with a confidence trajectory and metadata about how many strategies contributed.

**Partial input handling:** When one or more strategies fail during signal generation:
```yaml
partial_aggregation_policy:
  min_strategies_for_aggregation: 1
  confidence_penalty_per_missing: 0.05
  flag_partial: true
  log_missing_strategies: true
```

The output explicitly discloses which strategies failed and why.

### 3.4 MTF Confluence Filter

After aggregation, before sizing, the MTF Confluence plugin evaluates whether higher and lower timeframe evidence supports the signal. This is the canonical execution order in the pipeline DAG:

```
Signal Generation → Signal Aggregation → MTF Confluence Filter → Sizing → Guardrails → Trade Plan
```

Suppressed signals by MTF filter emit `MTF_SUPPRESSION` WebSocket events.

### 3.5 Strategy Families — All Plugin Contracts

The following strategy families have fully specified plugin implementations. Each specifies its required/optional indicators, regime fitness curve, entry conditions, exit logic, sizing declaration, and proactive trigger declarations:

- **Trend Following** — ADX + directional bias, multi-MA alignment, Supertrend
- **Mean Reversion** — Bollinger Band deviation, RSI reversal, VWAP deviation filter
- **Breakout** — Volume-confirmed breakout with ATR expansion
- **Pairs Trading** — Cointegration-based spread trading with Kalman hedge ratio
- **Volatility Expansion** — Squeeze momentum (BB inside KC), LULD awareness
- **Event-Driven** — Earnings, Fed, macro event positioning with calendar gating
- **Factor-Based Rotation** — Fama-French factor exposure signals
- **Macro Rotation** — Yield curve regime + sector ETF rotation
- **Order Flow** — CVD, absorption, OBI, footprint analysis
- **Price Action** — Candlestick pattern-driven entries with context scoring
- **Volume Profile** — POC/VAH/VAL interaction, HVN/LVN bounce
- **MTF Confluence** — Multi-timeframe alignment confirmation layer

### 3.6 Strategy Warm-Up

Newly activated strategies have zero live performance history. During warm-up:
```yaml
strategy_warmup:
  warmup_signals: 20
  warmup_days: 14
  backtest_confidence_basis: true
  narrative_disclosure: "warm-up period — readiness based on backtest, not live results"
```

Evolution Engine monitoring is suspended during warm-up. Readiness Monitor notes the warm-up status in every brief.

---

## SECTION 4: TOOL LAYER

### 4.1 Tool Contract Rules

- Every tool is **stateless** — same inputs produce same outputs
- Tools are **side-effect-free** — no database writes, no LLM calls, no network I/O
- Tools are **typed** — all inputs and outputs are schema-validated
- Tools **do not call each other** — they are called sequentially by the pipeline
- Raw data never traverses LLM context — tools exchange opaque `data_id` strings
- All monetary fields in tool I/O are `Decimal`

### 4.2 Core Tool Catalog

| Tool | Inputs | Outputs |
|------|--------|---------|
| `fetch_market_data` | ticker, interval, period, use_adjusted, check_corporate_actions | data_id, metadata, corporate_action_flags |
| `compute_indicators` | data_id, indicator_families, strategy_ids, mode | indicators_id, computed_families, unavailability_flags |
| `generate_signals` | indicators_id, strategy_ids, mode, config_snapshot_id | signals (list[Signal]), partial_flag |
| `aggregate_signals` | signals, aggregation_mode, strategy_weights | composite_signal, confidence, partial_flag |
| `mtf_confluence_filter` | composite_signal, mtf_context | filtered_signal, suppressed_flag, suppression_reason |
| `compute_position_size` | signal, portfolio_state, config_snapshot | shares (Decimal), notional (Decimal), sizing_basis |
| `format_trade_plan` | signal, sizing, why_engine_output, reflection_output | TradePlan |
| `run_backtest` | strategy_id, data_id, parameter_set, mode=backtest | BacktestResult |
| `fetch_market_depth` | ticker, levels | depth_id, bid_ask_spread, imbalance |
| `fetch_options_data` | ticker, expiration_range | options_id, pcr, gex, iv_rank, skew |
| `compute_volume_profile` | data_id, session_type | vp_id, poc, vah, val, hvn_list, lvn_list |
| `fetch_corporate_actions` | ticker, lookback_days | actions (list), next_action_date |
| `check_ssr_status` | ticker, current_price, prior_close | ssr_active, ssr_until |
| `check_halt_status` | ticker | halted, halt_reason, expected_resume |
| `compute_settlement_date` | trade_date, calendar | settlement_date |

### 4.3 Multi-Instrument Trade Plan Schema

For strategies that produce multi-leg outputs (Pairs Trading, Factor Rotation, Macro Rotation):

```python
class TradePlan:
    plan_id: str
    plan_type: str           # "single" | "pair" | "basket" | "options_spread"
    legs: list[TradeLeg]     # exactly 1 for single; N for others
    net_exposure: Decimal
    correlation_between_legs: float | None
    hedge_ratio: Decimal | None
    entry_window: str
    invalidation_conditions: list[str]
    cascade_analysis: SecondOrderAnalysis | None
    knowledge_context: KnowledgeContext
    confidence_decomposition: ConfidenceDecomposition
    epistemic_assessment: EpistemicAssessment
    behavioral_flags: list[BehavioralFlag]

class TradeLeg:
    ticker: str
    direction: str           # "long" | "short"
    shares: Decimal
    entry_price: Decimal | None
    stop_price: Decimal
    take_profit: Decimal
    notional: Decimal
    role: str                # "primary" | "hedge" | "basket_member"
```

### 4.4 Ticker Symbol Validation

All user-supplied and LLM-generated ticker symbols are validated before entering any pipeline:
- Normalize: strip whitespace, uppercase
- Check against known universe (configured ticker list or exchange feed)
- Handle variants: `BRK.B == BRK-B == BRK/B`
- Suggest corrections for common mistakes: `GOOGLE` → suggest `GOOG` or `GOOGL`
- `HallucinatedTickerError` is always logged to AuditTrail as `security.llm_hallucination`

---

## SECTION 5: DATA LAYER

### 5.1 Data Registry

The Data Registry is the in-memory key-value store with TTL eviction. All data structures within it are bounded. No unbounded growth is permitted.

```
Key format:    {namespace}.{ticker}.{data_type}.{interval}.{timestamp}
Namespaces:    market_data | indicators | signals | options | depth | vp | il | sentiment
Provenance:    every entry tracks: fetched_at, source, quality_score, tool_version
Concurrency:   namespace-level locking; atomicity within namespace guaranteed
```

**Memory pressure response:**
- At 80% ceiling: emit `DATA_REGISTRY_MEMORY_WARNING`; block speculative (PIL) puts
- At 95% ceiling: evict oldest `proactive.*` entries regardless of TTL

### 5.2 Data Quality Scoring

Every data item receives a quality score at ingestion:
```python
class DataQuality:
    completeness: float     # 0-1; fraction of expected fields present
    freshness_ms: int       # milliseconds since data was current
    consistency: float      # 0-1; passes cross-source validation checks
    anomaly_score: float    # 0-1; higher = more suspicious
    overall: float          # weighted composite
```

Anomaly detection checks for: negative volume, zero price, impossibly large price moves, missing required fields, timestamp gaps.

### 5.3 Corporate Actions Engine

Stock splits, dividends, mergers, acquisitions, delistings, spin-offs, and symbol changes corrupt all historical indicators and model features. The Corporate Actions Engine runs on every `fetch_market_data` call.

**On corporate action detection:**
1. Detect: compare current data against previously stored data for same key
2. Validate: verify ratio/amount/date against configured secondary source
3. Adjust: apply price adjustment factors to all historical data in Data Registry
4. Cascade: invalidate all derived indicators, signals, and ML features
5. Update positions: adjust open position shares, stop, and take-profit proportionally
6. Alert: emit `CORPORATE_ACTION_APPLIED` WebSocket event
7. Audit: write `corporate_action.*` to AuditTrail

**Symbol Lineage:**
```python
class SymbolLineage:
    current_symbol: str
    prior_symbols: list[dict]  # {symbol, effective_from, effective_to, reason}
    data_continuity: bool
```

All lookups by prior symbol resolve to current symbol. FACEBOOK → META is handled transparently.

### 5.4 Exchange Mechanics

**LULD (Limit Up-Limit Down):** When a ticker's trading status is `halted`, all signal generation is suspended. `TICKER_HALT_DETECTED` is emitted. Signal generation resumes after `reopening_auction_delay_bars` following resumption.

**Market-wide circuit breakers:**
- Level 1 (7% SPY drop): 15-min halt → `MARKET_CIRCUIT_BREAKER_L1` → pause all signal generation
- Level 2 (13% drop): additional halt
- Level 3 (20% drop): day-long halt → all signal generation suspended

**Short Sale Restriction (SSR):** When a stock drops ≥10% from prior close, SSR activates. Short signals generated while SSR is active are suppressed with `SSR_ACTIVE` rejection reason.

**Ex-Dividend Handling:** Historical close prices use adjusted prices by default (`use_adjusted: true`). On ex-dividend dates, signals generated primarily from overnight gap analysis are suppressed with `EX_DATE_GAP_SUPPRESSED`. The Calendar Intelligence subsystem tracks ex-dates for all watchlist tickers and emits `EX_DATE_APPROACHING` advisories.

### 5.5 Settlement Cycle (T+1)

US equities settle T+1 (next NYSE business day). APEX tracks settlement for all positions:

```python
class CashAvailabilityChecker:
    def check_available_cash(self, user_id: str) -> Decimal:
        settled_cash = self.get_settled_cash(user_id)
        pending_purchases = self.get_pending_settlement_debits(user_id)
        pending_proceeds = self.get_pending_settlement_credits(user_id)
        return settled_cash - pending_purchases + pending_proceeds
```

Free-riding (using unsettled proceeds) is blocked by the cash availability check before position confirmation.

### 5.6 Business Day Calendar

All period parameters (`indicator.sma.period: 20`) mean 20 **trading days** unless explicitly marked `_calendar_days`. Settlement, expiration, and event proximity calculations use NYSE business day calendar including all NYSE holidays (not just federal holidays).

### 5.7 Data Vendor Failover and Restatement

**Failover chain:**
```
Primary vendor → [circuit breaker] → Secondary vendor → [circuit breaker] → Emergency fallback
```
Health-check polling runs on configured interval. Automatic failover with `data_quality_warning` flag.

**Restatement handling:** On each cache refresh, current fetch is compared against cached value. When a restatement is detected:
1. Log `DATA_RESTATEMENT_DETECTED` with ticker, field, old/new values
2. Invalidate all derived entries that depend on the restated data
3. Flag affected indicators, signals, and model features as `requires_recomputation`
4. Emit `DATA_RESTATEMENT_ALERT` if any open position's analysis was affected

---

## SECTION 6: COGNITIVE ARCHITECTURE

### 6.1 Executive Controller

The ExecutiveController manages DAG execution for every reactive pipeline. It enforces component latency budgets and applies configured degradation when budgets are exceeded.

```yaml
internal_slas:
  intent_routing:         {max_ms: 50,   degradation: skip_tier3_return_tier2}
  data_fetch:             {max_ms: 500,  degradation: use_cached_with_staleness_flag}
  indicator_computation:  {max_ms: 400,  degradation: return_partial_with_flags}
  signal_generation:      {max_ms: 300,  degradation: skip_slowest_strategy}
  signal_aggregation:     {max_ms: 100,  timeout_action: return_partial_with_flag}
  why_engine:             {max_ms: 2000, degradation: skip_narrative_return_scores_only}
  reflection_layer:       {max_ms: 1500, degradation: use_deterministic_score_only}
  canvas_rendering:       {max_ms: 200,  timeout_action: emit_placeholder}
  total_reactive_budget:  {max_ms: 5000}
```

Every budget violation is logged as a metric and contributes to the `analytical_debt` score.

**Configuration snapshotting:** When a sizing calculation begins, it captures the current configuration state as an immutable snapshot. User config changes mid-calculation use the old values; new values apply to the next request.

### 6.2 StrategicMemory Concurrency

StrategicMemory is the most concurrency-sensitive component. Lock ordering convention: all portfolio state mutations acquire locks in **alphabetical order of ticker symbol**. This prevents deadlocks between concurrent position updates.

**Double-close prevention:**
```
T=0ms: PIL detects exit signal for AAPL → acquires lock → closes position → releases lock
T=1ms: User clicks "Close AAPL" → attempts lock → blocked
T=7ms: Lock released → user request acquires lock → detects position already closed
→ returns "already_closed" (not an error)
```

### 6.3 Three-Tier Intent Router

```
Tier 1 — Keyword/pattern matching (< 5ms):
  Handles ~40% of requests. Exact patterns, no LLM.
  Examples: "what is AAPL's RSI", "show portfolio heat"

Tier 2 — Structural classifier (< 20ms):
  Handles ~45% of requests. ML intent classifier.
  Routes to compiled workflow by intent type.

Tier 3 — LLM intent synthesis (< 50ms):
  Handles ~15% of requests. Complex multi-intent queries.
  Falls back to Tier 1+2 when LLM unavailable.
```

ReAct is used only when no compiled workflow matches the resolved intent — not as a fallback after trying multiple workflows.

---

## SECTION 7: DUAL INTELLIGENCE SYSTEM

### 7.1 Proactive Intelligence Layer (PIL)

The PIL runs continuously on a configured schedule. It operates independently of user requests and builds the intelligence brief that enriches all reactive analyses.

**PIL Subsystems:**

**① Regime Intelligence:** Classifies the current market regime using volatility, breadth, sector rotation, and intermarket data. Regime classifications drive strategy gating — strategies only active when their `regime_fitness()` exceeds the configured threshold. Regime transitions trigger `REGIME_CHANGE` events.

**② Strategy Readiness Monitor:** For each active strategy, computes a readiness score from recent performance metrics (Brier score, calibration, drawdown, streak). During warm-up, uses backtest data. Emits `STRATEGY_READY` and `STRATEGY_DEGRADING` events. Flags strategy combinations with high signal correlation as redundant.

**③ Opportunity Scout:** Scans the configured universe for developing setups. Evaluates each ticker's proactive triggers across all active strategies. Emits `OPPORTUNITY_BRIEF` events. Incorporates the Knowledge Application Engine — active failure patterns, learned factors, and expert views inform the scan. Also evaluates Redemption Candidates (previously suppressed signals whose conditions for re-evaluation have been met).

**④ Calendar Intelligence:** Tracks earnings dates, Fed meetings, FOMC cycle, options expirations, index rebalances, and ex-dividend dates for all universe tickers. Emits `UPCOMING_EVENT` advisories. Applies event gating — blocks or flags signals during high-risk event windows.

**⑤ Narrative Monitor:** Tracks narrative evolution for all monitored tickers. Detects sentiment shifts, news pattern changes, and analyst consensus movements. Cross-references against the TickerIntelligenceFile to flag thesis-relevant changes.

**⑥ Risk Sentinel:** Monitors portfolio heat, correlation clustering, circuit breaker proximity, and open thesis health. Emits `HEAT_WARNING`, `CORRELATION_SPIKE`, `THESIS_INVALIDATED`, and `THESIS_WEAKENING` events. Integrates with the Position Thesis Monitor (Section 17).

**Knowledge-enhanced PIL cycle:** Before each subsystem runs, the Knowledge Application Engine loads all active failure patterns, learned factors, expert views, and learning abstractions. These are injected into subsystem processing without requiring explicit human instruction.

### 7.2 PIL State Persistence and Warm-Start

After each cycle, PIL state is serialized to a snapshot:
```python
class PILStateSnapshot:
    snapshot_id: str
    session_name: str
    captured_at: datetime
    quality: str            # "full" | "partial" (on abort)
    regime_state: RegimeState
    hypothesis_queue: list[Hypothesis]
    active_watches: list[TickerWatch]
    speculative_cache: dict     # pre-fetched data for anticipated requests
    intelligence_brief: IntelligenceBrief
```

On startup, the most recent snapshot is loaded. If snapshot age exceeds `max_snapshot_age`, a cold PIL start is initiated and `PIL_COLD_START` is emitted.

### 7.3 Reactive Intelligence Layer (RIL)

The RIL serves on-demand requests. Every request creates a traceable pipeline with a `trace_id` that follows it through all components. The RIL Bridge shares context bidirectionally with the PIL — user queries can update PIL directives, and PIL intelligence enriches reactive analyses.

### 7.4 Bridge & Directive Management

Directives carry: `scope` (ticker/sector/global), `priority` (explicit user > implicit pattern), `supersedes` (prior directive_id). Resolution: ticker-specific overrides sector-level for the named ticker; more recent supersedes older of same scope.

---

## SECTION 8: EXECUTION PIPELINES

### 8.1 Reactive Pipeline DAG

```
User Request
    │
    ▼ Intent Router (3-tier)
    │
    ▼ Context Hydration
    │  ├─ Load TickerIntelligenceFile (cross-session continuity)
    │  ├─ Load KnowledgeContext (failure patterns, learned factors, expert views)
    │  └─ Load EpistemicAssessment (data coverage, model fitness, experience)
    │
    ▼ Data Fetch (with corporate action check, quality scoring)
    │
    ▼ Indicator Computation (with unavailability_flags)
    │
    ▼ Signal Generation (deterministic, sandboxed plugins)
    │
    ▼ Signal Aggregation (with partial-input handling)
    │
    ▼ MTF Confluence Filter
    │
    ▼ Position Sizing (Decimal arithmetic throughout)
    │
    ▼ Stepwise Disagreement Evaluation (after each above step)
    │  └─ Early termination check
    │
    ▼ Why Engine (5 layers + preamble, failure-aware)
    │
    ▼ Reflection Layer (failure-aware, knowledge-informed)
    │
    ▼ Guardrail Layer (G1-G11, non-bypassable)
    │
    ▼ Behavioral Guardian Check
    │
    ▼ Second-Order Cascade Analysis
    │
    ▼ Abstain/No-Action Decision (if conditions met)
    │
    ▼ NarrativeAgent (consistency-enforced, epistemic-aware)
    │
    ▼ Canvas Rendering
    │
    ▼ Trade Plan / Research Note / NO_ACTION output
    │
    ▼ Signal Disposition Tracking
```

### 8.2 Backtest-to-Live Parity Verification

The backtest engine and live reactive pipeline are two code paths that must produce identical signals for identical data. Parity is verified on every CI build:

1. Load canonical historical dataset (from `tests/canonical_data/`)
2. Run through backtest engine (`mode: backtest`)
3. Run same data bar-by-bar through live pipeline via Replay Mode (`mode: live`)
4. Assert signals are identical: same ticker, direction, bar index
5. Any deviation fails the build with a detailed diff report

```yaml
backtest_parity:
  canonical_datasets:
    - {name: bull_trend_2023, ticker: SPY, interval: 1d}
    - {name: bear_trend_2022, ...}
    - {name: ranging_2024, ...}
    - {name: high_volatility_2020, ...}
    - {name: regime_transition_2021, ...}
  tolerance: 0            # zero tolerance — signals must be identical
  fail_build_on_deviation: true
```

---

## SECTION 9: WHY ENGINE

The Why Engine produces a **5-layer causal analysis** with a **strategy context preamble** (Layer 0). Every layer produces both a score and a narrative.

### 9.1 Layer Structure

**Layer 0 — Strategy Context Preamble (processed before all layers):**
What strategy generated this signal? What are its ideal conditions? How does the current setup compare to the strategy's ideal entry? This shapes how each subsequent layer is narrated.

**Layer 1 — Price Structure:**
Trend analysis, key level proximity, support/resistance interaction, chart pattern context, bar character scoring. Score reflects how well price structure supports the signal direction.

**Layer 2 — Volume and Momentum:**
OBV trend, CVD divergence, volume relative to historical, RSI trajectory, momentum regime. Divergences between price and volume/momentum are explicitly flagged.

**Layer 3 — Market Regime:**
Regime classification, regime fitness score for the generating strategy, regime transition probability, size multiplier derived from regime fitness. PIL regime context is incorporated.

**Layer 4 — Behavioral Finance (SOFT signals):**
Sentiment composite (news + social + analyst consensus), options positioning (GEX, PCR, skew), unusual options activity, expert consensus from the Expert Analyst Integration system. All SOFT-typed. Marked null if data unavailable. PIL sentiment context incorporated.

**Layer 5 — Historical Analogs (Failure-Aware):**
Standard analog search separated into successes and failures. For failures: root causes and the conditions that differentiated failures from successes. Win rate, confidence interval, sample count, reliability tier. Failure patterns from the Failure Memory System are integrated.

### 9.2 Why Engine Extended Output Schema

```python
class WhyEngineOutput:
    strategy_context_preamble: dict         # Layer 0
    layer1: LayerOutput                     # Price Structure
    layer2: LayerOutput                     # Volume/Momentum
    layer3: LayerOutput                     # Regime
    layer4: LayerOutput                     # Behavioral
    layer5: LayerOutput                     # Historical Analogs (failure-aware)
    composite_score: float
    conflict_analysis: ConflictAnalysis     # intra-system disagreement
    feature_attribution: dict | None        # SHAP values if available
    pil_context_incorporated: bool
    mtf_filter_result: dict | None
    failure_patterns_applied: list[str]     # failure_pattern_ids
    cascade_analysis: SecondOrderAnalysis | None  # Layer 6
```

### 9.3 Why Engine Scan-Scoped Caching

When a Universe Scan runs across N tickers, intermediate results (regime, breadth, intermarket data) are computed once and reused across all tickers in the scan. The cache is scoped to the scan — it does not persist across scans or to the Data Registry.

### 9.4 Why Engine Conflict Resolution

When layers produce contradictory assessments:
```python
class ConflictAnalysis:
    conflict_type: str      # "directional" | "magnitude" | "regime_signal_mismatch" | ...
    severity: float         # 0-1
    conflicting_layers: list[str]
    resolution: str         # "higher_weight_layer_wins" | "conservative_composite" | ...
    confidence_impact: float
    narrative: str          # explicit disclosure of the conflict
```

All conflicts are disclosed in the output, never silently resolved.

---

## SECTION 10: STEPWISE DISAGREEMENT TRACKING

The pipeline is linear but evidence is not. Without stepwise tracking, the user sees only the final confidence number — not how it got there.

### 10.1 Confidence Trajectory

Every pipeline step updates a running confidence trajectory:
```
confidence_trajectory:
  after_signal_generation: 0.82   ← strategy's own confidence
  after_regime_detection:  0.61   ← regime fitness penalty
  after_sentiment:         0.48   ← sentiment contradiction
  after_options_analysis:  0.39   ← smart money counter-signal
  after_why_engine:        0.42   ← composite (some layers helped)
  after_reflection:        0.38
  final:                   0.38
  trajectory_direction:    "declining"
  max_confidence_drawdown: 0.44
  inflection_step:         "regime_detection"
```

### 10.2 Step-to-Step Contradiction Classification

| Type | Meaning |
|------|---------|
| `directional` | Step output opposes signal direction |
| `magnitude` | Agrees on direction, disagrees on strength |
| `confirming_prior` | Third+ consecutive counter-signal |
| `reversing_prior` | Resolves a prior contradiction |
| `orthogonal` | New risk dimension (e.g., earnings in 2 days) |
| `quality_degradation` | Step's data quality undermines confidence |

### 10.3 Cumulative Disagreement Score

```
score = Σ(step_severity × step_weight) / Σ(step_weight)

0.00–0.20: "clean"             → unanimous support
0.20–0.40: "minor_friction"    → some hedging but supportive
0.40–0.60: "contested"         → significant disagreement
0.60–0.80: "adversarial"       → most evidence opposes signal
0.80–1.00: "consensus_against" → pipeline says NO
```

### 10.4 Early Termination

```yaml
stepwise_disagreement:
  early_termination:
    enabled: true
    min_confidence_to_continue: 0.25
    min_steps_before_termination: 3
    termination_action: downgrade_to_research
    # "abort_with_summary" | "downgrade_to_research" | "continue_flagged"
  reflection:
    trajectory_ceiling_grade: C
    monotonic_decline_threshold: 3
```

`downgrade_to_research` reframes as: "Technical setup is real; environment opposes it; monitor for regime change."

### 10.5 Canvas Render Type: `analysis_trajectory`

Waterfall chart showing incremental impact of each pipeline step. Green = supporting, red = opposing. Inflection step highlighted. Embedded in every trade plan card.

---

## SECTION 11: REFLECTION LAYER

The Reflection Layer is the final qualitative evaluation before the Guardrail Layer. It is **failure-aware** — it queries the Failure Memory System before evaluating any signal.

### 11.1 Failure-Aware Reflection Sequence

```
① Current signal arrives for reflection: AAPL BUY, mean_reversion, 0.78 strength

② Query Failure Memory Store:
   "Find failures where strategy_family=mean_reversion AND
    regime similar to current AND ticker sector matches AND
    key_indicator_state similarity > configured threshold"

③ Failure Memory returns matches with similarity scores

④ Reflection prompt includes failure context:
   "PRIOR FAILURE CONTEXT:
    3 similar setups failed recently (combined failure rate 74%).
    Evaluate whether current signal has materially different conditions.
    If not, apply configured grade ceiling."

⑤ Reflection output includes:
   - failure_history_impact (similar_failures, combined_failure_rate, grade_ceiling_applied)
   - exception_assessment (are current conditions materially different?)
   - what_would_change_this (conditions that would lift the suppression)
```

### 11.2 Reflection Output Schema

```python
class ReflectionOutput:
    confidence_score: float
    risk_grade: str          # A | B | C | D | F
    grade_rationale: str
    size_multiplier: Decimal # 0-1; regime-adjusted
    key_risks: list[str]
    knowledge_context_applied: bool
    failure_history_impact: dict | None
    exception_assessment: str | None
    what_would_change_this: list[str]
    llm_unavailable: bool    # true if LLM failover was active
```

**LLM unavailable behavior:** Use deterministic scoring only. Flag grade as `llm_unavailable`. Apply one-level downgrade. Never block the pipeline.

---

## SECTION 12: DECISION CONTRACT

Every signal, trade plan, and analytical output carries a `DecisionContract` — a typed, machine-verifiable record of what APEX decided and why.

```python
class DecisionContract(BaseModel):
    id: str
    timestamp: datetime                       # UTC
    context_hash: str                         # hash of input features
    decision: str                             # "bullish" | "bearish" | "neutral" | "NO_ACTION"
    confidence: Decimal
    confidence_decomposition: ConfidenceDecomposition
    risk_score: Decimal
    reasoning: list[str]                      # ordered chain of reasoning steps
    supporting_signals: list[str]
    contradicting_signals: list[str]
    constraints_checked: list[str]
    guardrail_passed: bool
    strategy_ids: list[str]
    regime_at_decision: str
    trace_id: str
    is_partial_aggregation: bool
    llm_unavailable: bool
    failure_patterns_applied: list[str]
    knowledge_context_id: str
    epistemic_classification: str
    cumulative_disagreement_score: float
    confidence_trajectory: list[dict]
```

---

## SECTION 13: CONFIDENCE DECOMPOSITION

A single confidence number hides the sources of uncertainty. Decomposition makes uncertainty actionable.

```json
{
  "model_confidence": 0.82,
  "model_confidence_basis": "strategy_signal_strength",
  "data_quality": 0.91,
  "data_quality_factors": ["completeness", "freshness", "consistency"],
  "signal_agreement": 0.78,
  "contributing_strategies": 3,
  "drift_penalty": -0.05,
  "drift_kl_divergence": 0.23,
  "regime_fit": 0.65,
  "historical_base_rate": 0.58,
  "analog_sample_size": 47,
  "expert_consensus": 0.72,
  "expert_count": 2,
  "failure_pattern_penalty": -0.12,
  "matching_failure_rate": 0.74,
  "final_confidence": 0.38,
  "computation": "weighted_average_of_components"
}
```

**Display rules:** Final confidence shown alongside decomposition. Any component deviating > 0.15 from final is highlighted. Drift and failure pattern penalties are always shown if non-zero.

---

## SECTION 14: ABSTAIN / NO-DECISION MODE

The system must be capable of not producing output. A system that always generates a recommendation causes harm under uncertainty.

### 14.1 Decision Eligibility Filtering

```python
class MetaDecision:
    should_act: bool
    reason: str
    system_state: str  # "stable" | "degraded" | "uncertain" | "conflicting"
```

Conditions that trigger abstain: epistemic score below threshold, LLM unavailable AND query requires synthesis, all active strategies in warm-up AND query requests live recommendation, circuit breaker active.

### 14.2 NO_ACTION Output

```json
{
  "decision": "NO_ACTION",
  "reason": "Confidence below safe threshold after regime opposition and failure pattern match",
  "confidence": 0.21,
  "abstain_factors": ["confidence_below_threshold", "failure_pattern_match", "regime_opposition"],
  "what_would_change_this": [
    "Regime transition to ranging (breadth improving above configured threshold)",
    "Sentiment reversal (score above -0.2)",
    "Absence of matching failure pattern"
  ]
}
```

`NO_ACTION` outputs render as research cards (not trade plan cards) in the War Room.

---

## SECTION 15: GUARDRAIL LAYER (G1–G11)

All guardrails are non-bypassable. They form a mandatory sequence. A failure at any gate produces a structured rejection with full audit trail entry. Configuration changes to guardrail thresholds take effect on the next evaluation cycle, not retroactively.

**G1 — Schema Validation:** Every tool input and output validated against declared schema. Type errors, missing required fields, and invalid enum values are rejected before any computation.

**G2 — Security Gate:** Prompt injection detection on all user-supplied content. LLM hallucinated ticker validation. Sensitive data scrubbing from LLM prompts (no portfolio position sizes, account balance, or user PII in prompts).

**G3 — Position Size Gate:** `notional ≤ max_notional_per_trade` (Decimal). `risk_pct ≤ max_risk_per_trade_pct` (Decimal). Both checked; both must pass.

**G4 — Portfolio Heat Gate:** `current_heat + new_heat ≤ max_portfolio_heat` (Decimal). Computed from current state — never a cached accumulation. Always a live calculation from open positions.

**G5 — Concentration Gate:** No single ticker exceeds `max_ticker_concentration_pct`. No single sector exceeds `max_sector_concentration_pct`. Both checked as Decimal.

**G6 — Correlation Gate:** When new position correlation with existing positions exceeds `max_correlation_threshold`, the position is rejected or flagged. Uses rolling correlation matrix from StrategicMemory.

**G7 — Confidence Sufficiency Gate:** If `final_confidence < min_confidence_threshold`, output is labeled "Insufficient Data — not a trade recommendation." Does not block the output, but mandates the label. Threshold is adaptive (see G7.1 below).

**G8 — Regime Fitness Gate:** If `regime_fitness < min_regime_fitness`, the signal is suppressed or downgraded. Strategy is excluded from aggregation for this cycle.

**G9 — Market Hours Gate:** Signals are only generated during configured market sessions. Pre-market and after-hours signals are flagged with liquidity warnings. Halt detection blocks signals for halted tickers.

**G10 — Ethical Compliance Gate:** Verifies the signal does not violate any of the 8 Constitutional Axioms (Section 21). No market manipulation patterns, no look-ahead, no insider-information characteristics.

**G11 — Numerical Type Gate (New):** Validates that every monetary field in every tool input and output is typed as `Decimal`. Raises `NumericalTypeViolation` before any computation. Runs before G1.

### 15.1 Adaptive Guardrails (G7 extended)

```python
def compute_adaptive_threshold(base_threshold: Decimal, context: MarketContext) -> Decimal:
    drift_modifier    = Decimal('-0.05') * Decimal(str(context.drift_score))
    vol_modifier      = Decimal('-0.03') * Decimal(str(context.volatility_zscore))
    health_modifier   = Decimal('-0.04') * (Decimal('1') - Decimal(str(context.model_health)))
    quality_modifier  = Decimal('0.02') * Decimal(str(context.data_quality_score))
    adjustment = clamp(drift_modifier + vol_modifier + health_modifier + quality_modifier,
                       Decimal('-0.15'), Decimal('0.05'))
    return base_threshold + adjustment
```

High drift → stricter. Low data quality → force "Insufficient Data" regardless of score. Adaptive thresholds are computed fresh on each evaluation; the computed value and its inputs are included in the guardrail output.

---

## SECTION 16: EPISTEMIC HUMILITY

APEX formally assesses its own knowledge boundaries before generating any analysis.

```python
class EpistemicAssessment:
    data_coverage: dict          # ohlcv_history, tick_data, options_data, sentiment_data
    model_fitness: dict          # strategy_fitness_for_regime, sample_size_in_regime
    experience_level: dict       # prior_analyses_on_ticker, outcome_data_available
    known_blind_spots: list[dict]  # {blind_spot, impact, mitigation}
    epistemic_score: float       # 0-1; how well-equipped am I?
    epistemic_classification: str
    # "well_equipped" | "adequate" | "limited" | "operating_blind" | "novel_territory"
```

**Narrative rules:**
- `operating_blind` or `novel_territory`: Lead with `⚠️ IMPORTANT: This analysis has significant knowledge limitations.`
- `limited`: `Note: This analysis is constrained by [specific gaps].`
- `adequate` or `well_equipped`: No epistemic preamble

---

## SECTION 17: CROSS-SESSION ANALYTICAL CONTINUITY

APEX maintains an evolving view on every analyzed ticker across sessions.

### 17.1 Ticker Intelligence File

```python
class TickerIntelligenceFile:
    ticker: str
    current_thesis: dict            # direction, confidence, driver, age_days, trace_id
    thesis_history: list[dict]      # {date, direction, confidence, driver, trigger, trace_id}
    pending_setups: list[dict]      # developing setups with completion estimates
    open_questions: list[dict]      # unanswered questions affecting the thesis
    related_tickers: list[dict]     # {ticker, relationship, correlation, thesis_alignment}
    ticker_failure_patterns: list[str]  # failure_pattern_ids specific to this ticker
    active_expert_views: list[dict]
```

### 17.2 Thesis Change Narration

```
Direction reversal (bearish → bullish):
  "My view on AAPL has REVERSED from bearish to bullish. The key driver of
   this change was [specific factor]. 3 days ago I was bearish at 0.71 confidence.
   Today's analysis at 0.64 bullish confidence reflects [what changed]."

Confidence shift (same direction, > 0.2):
  "My conviction on AAPL has [strengthened/weakened] significantly from [X] to [Y]
   because [specific factor]."

No material change:
  "My view on AAPL is unchanged since [date] — still [direction] at [confidence].
   The conditions that drove this view remain intact: [brief recap]."
```

### 17.3 Position Thesis Lifecycle Monitor

Runs on each PIL cycle for every open position. Re-evaluates each component of the entry thesis against current data:

```python
component_status: "intact" | "weakened" | "invalidated" | "strengthened"
overall_health: float  # 0-1; aggregate across components
```

When `overall_health < config.thesis_exit_threshold`:
```
Emit THESIS_INVALIDATED:
  "The thesis for your AAPL long has deteriorated:
   - Regime: ranging at entry → bear trend now (INVALIDATED)
   - RSI: oversold at entry → neutral now (WEAKENED)
   - Sentiment: neutral at entry → strongly negative now (INVALIDATED)
   
   Thesis health: 0.18 (critical). The stop has not been hit, but the
   reasons for this trade no longer hold. Consider proactive exit."
```

---

## SECTION 18: FAILURE MEMORY SYSTEM

The Reflection Layer is amnesiac. The Failure Memory System provides institutional memory of what went wrong and why.

### 18.1 Failure Record

```python
class FailureRecord:
    failure_id: str
    signal_id: str
    strategy_id: str
    ticker: str
    direction: str
    signal_context: dict      # regime, confidence_trajectory, why_engine_scores, indicators
    outcome: dict             # entry/exit price, realized_r, MAE, MFE, exit_reason
    root_cause: dict          # primary_cause, secondary_causes, auto_diagnosis
    fingerprint: dict         # regime, strategy_family, strength_bucket, sector, vol_regime
    lesson: FailureLesson | None
```

### 18.2 Root Cause Taxonomy

```
DIRECTIONAL: regime_opposition | sentiment_reversal | event_shock | trend_exhaustion |
             false_breakout | correlation_breakdown | external_factor_missed

TIMING: premature_entry | stop_too_tight | delayed_move | choppy_execution

SIZING: oversized_for_volatility | undersized_missed_move | correlation_concentration

DATA QUALITY: stale_data | missing_data | anomalous_data | survivorship_in_analog

MODEL: indicator_miscalibration | regime_misclassification |
       confidence_overestimation | strategy_environment_mismatch
```

### 18.3 Failure Lesson

```python
class FailureLesson:
    lesson_id: str
    lesson_type: str    # "condition_to_avoid" | "weight_adjustment" | "missing_filter" |
                        # "parameter_recalibration" | "new_exit_condition" | "sizing_adjustment"
    condition: dict     # machine-readable: when does this lesson apply?
    action: dict        # machine-readable: what should the system do?
    summary: str        # human-readable
    abstraction: str    # "specific" | "pattern" | "universal"
    supporting_failures: list[str]
    confidence: float
    statistical_significance: float  # p-value
    times_applied: int
    times_prevented_failure: int
    net_impact: float
    status: str         # "proposed" | "validated" | "active" | "deprecated" | "refuted"
```

### 18.4 Failure Pattern Aggregation

When N similar failures accumulate (N from config), they form a `FailurePattern` with a `pattern_name`, aggregate `failure_rate`, and integrated lesson. Patterns are classified as `emerging | confirmed | decaying | refuted`. Decaying patterns (losing reliability over time) trigger revalidation.

### 18.5 Why Engine Layer 5 — Failure-Aware Analogs

Historical analog search separates results into successes and failures. For failures: identifies the specific conditions that differentiated failures from successes. Reports the ONE condition that most reliably distinguishes the outcomes.

---

## SECTION 19: LEARNING ENGINE

### 19.1 Learning Lifecycle

```
Market Data → Features → Prediction → DecisionContract + WhyEngine
→ Market Outcome → Evaluation + Reflection + Failure Memory
→ Learning Engine → Model/Strategy/Policy Updates → Next Decision improves
```

### 19.2 Learning Engine Core

```python
class LearningEngine:
    def process(self, decision: DecisionContract, outcome: MarketOutcome) -> LearningResult:
        reflection = self.reflect(decision, outcome)
        self.update_strategy_weights(reflection)
        self.update_confidence_calibration(reflection)
        self.update_agent_reputation(reflection)
        if self.drift_detected(decision.strategy_id):
            self.trigger_retraining(decision.strategy_id)
        if self.performance_dropped(decision.strategy_id, window=self.config.learning.window):
            self.adjust_guardrail_thresholds(decision.strategy_id)
        return LearningResult(...)
```

### 19.3 Strategy Weight Adaptation

```python
weight_new = weight_old * performance_score * decay_factor
# performance_score: from recent accuracy, calibration, regime fit
# decay_factor: reduces influence of stale performance data
```

### 19.4 Retraining Triggers

**Hard triggers (immediate):** Accuracy below configured floor for configured consecutive window; feature drift (KL divergence) above threshold; calibration error above threshold.

**Soft triggers (scheduled proposal):** Regime change detected; performance in specific subgroup (sector, regime, interval) below tolerance.

### 19.5 Retraining Pipeline

```
Trigger → Collect Data (point-in-time universe, no look-ahead)
→ Rebuild Features → Train Model → Walk-Forward Validate
→ Shadow Deploy → Validate Statistical Significance → Promote (supervised) or Discard
```

### 19.6 Confidence Recalibration

When the calibration curve shows systematic overconfidence (predicted 80% → actual 60%):
1. Fit Platt scaling or isotonic regression calibration function from resolved outcomes
2. Apply as post-processing step to all confidence outputs
3. Track calibration curves per strategy family and per regime
4. Emit `CONFIDENCE_RECALIBRATED`; update Evolution Engine baselines

### 19.7 Learning Speed Modes

```yaml
learning:
  speed_mode: balanced   # "conservative" | "balanced" | "aggressive"
```

---

## SECTION 20: KNOWLEDGE APPLICATION ENGINE

When APEX has learned something — from failures, from experts, from MCP services, from content — that knowledge must be actively applied to future analyses. Without the Knowledge Application Engine, learned knowledge sits in tables but doesn't inform decisions.

### 20.1 Knowledge Context Schema

```python
class KnowledgeContext:
    context_id: str
    generated_for: str           # trace_id of the analysis

    failure_warnings: list[dict] # {pattern_id, failure_rate, similarity_score, lesson_summary}
    learned_factors: list[dict]  # {factor, source, relevance, current_value, implication}
    expert_consensus: dict | None  # {direction, weighted_scores, top_expert_view}
    applicable_abstractions: list[dict]  # {abstraction_id, name, relevance, application_notes}
    confidence_adjustments: list[dict]   # {source, adjustment, reason}
    net_confidence_adjustment: float
    knowledge_richness_score: float  # 0-1; how much relevant knowledge was available
```

### 20.2 Application Sequence

Before every reactive pipeline execution and on every PIL cycle:
1. Query Failure Memory for matching failure patterns
2. Query Knowledge Graph for relevant learned factors
3. Query Expert Signal history for active expert views
4. Query Learning Abstraction Store for applicable methodologies
5. Compile KnowledgeContext and inject into pipeline

### 20.3 Learning Abstraction Store

All learned knowledge is stored as hierarchical, articulable `LearningAbstraction` objects:

```python
class LearningAbstraction:
    abstraction_id: str
    statement: str               # "I have learned that..."
    knowledge_type: str          # "methodology" | "factor" | "pattern" | "risk_rule" | ...
    application_rule: dict       # machine-readable rule for Knowledge Application Engine
    applicable_strategies: list[str]
    measured_improvement: float
    provenance: dict             # discovery_method, source_id, discovery_chain
    validation: dict             # method, result, confidence, statistical_significance
    hitl_status: str             # "pending" | "approved" | "rejected" | "modified"
    status: str                  # "draft" | "validated" | "approved" | "active" | "deprecated"
    times_applied: int
    net_accuracy_impact: float
    is_decaying: bool
    decay_rate: float | None
```

**Abstraction decay:** The `AbstractionDecayMonitor` runs weekly. When accuracy drops below the configured deprecation threshold, the abstraction is deprecated, removed from the Knowledge Application Engine, and the user is notified. Deprecated knowledge is **archived**, not deleted — market cycles may make it valid again.

**APEX articulates its learning when asked:**
> "Over the past 30 days, I've acquired 7 new validated learnings: [list with sources, evidence, and application count]"

---

## SECTION 21: HUMAN FEEDBACK & EXPERT INTELLIGENCE

### 21.1 Step-Level Disagreement

Users can disagree with any specific pipeline step — not just the final grade:

```python
class StepDisagreement:
    disagreement_id: str
    trace_id: str
    step_id: str                 # "signal_generation" | "regime_detection" | ...
    analyst_id: str
    analyst_tier: str            # "user" | "senior_analyst" | "expert"
    analyst_track_record: dict | None
    apex_conclusion: dict
    apex_confidence: float
    human_conclusion: str        # "agree" | "disagree_direction" | "disagree_magnitude" |
                                 # "disagree_missing_factor" | "disagree_interpretation"
    human_reasoning: str
    human_suggested_factors: list[str]
    market_context_snapshot_id: str  # frozen context at disagreement time
    outcome: dict | None
    who_was_right: str | None    # "apex" | "human" | "neither" | "both_partially"
```

**War Room UI:** The Thought Process Inspector shows a `[Disagree]` button at every step panel. Clicking opens a structured form with direction, confidence, reasoning, and suggested missing factors.

### 21.2 Analyst Profile & Reputation

```python
class AnalystProfile:
    analyst_id: str
    tier: str
    track_record: dict          # total_disagreements, accuracy_when_disagreeing
    accuracy_by_step: dict      # per pipeline step
    accuracy_by_regime: dict
    calibration_score: float
    inferred_expertise: list[str]
    disagreement_weight: float  # 0-1; how much to trust this analyst
```

### 21.3 Disagreement Learning Pipeline

```
① Human submits step disagreement
② Store with frozen context snapshot
③ Wait for market outcome (configured window)
④ Resolution Engine evaluates who was correct
   ├── Human correct + identified missing factor → Curiosity Engine research proposal
   ├── Human correct + weight miscalibration → Evolution Engine parameter retune proposal
   ├── Human correct + stale data → Flag to adapter monitoring
   └── APEX correct → Update analyst track record
⑤ Aggregate patterns across many disagreements → surface to PIL brief
```

### 21.4 Expert Signal Channel

```python
class ExpertSignal:
    signal_type: str    # "thesis" | "warning" | "factor_alert" | "regime_call" | "sector_rotation"
    ticker: str | None
    direction: str | None
    confidence: float
    reasoning: str
    factors: list[dict]
    suggested_integration: str  # "override_regime" | "adjust_sentiment" | "add_to_context" |
                                # "watchlist_alert" | "research_hypothesis"
    signal_type_classification: str  # always "SOFT"
```

**Injection points:** Expert signals are injected at the pipeline stage matching `suggested_integration`. Regime override signals go to the Regime Intelligence subsystem. Sentiment signals are blended with computed sentiment.

### 21.5 Expert Observation Engine (Autonomous)

APEX autonomously monitors known top analysts' public outputs — market calls, methodology patterns, accuracy by domain. Without requiring the analyst to interact with APEX directly:

1. Observe methodology patterns in public calls (indicators used, conditions described)
2. Extract as `MethodologyPattern` (approach_type, conditions, applicable_context)
3. Generate testable hypothesis from the pattern
4. Run validation backtest autonomously
5. Create `LearningAbstraction` if validated
6. Queue for HITL validation — human validates what APEX taught itself

### 21.6 MCP Learning Integration

External intelligence services connect via MCP (Model Context Protocol):

**Mode 1 — Query-on-Demand:** APEX queries an external service to validate its analysis. Disagreements are tracked for accuracy like human analyst disagreements.

**Mode 2 — Continuous Feed:** Intelligence streams enrich the PIL brief as SOFT signals with provenance tracking.

**Mode 3 — Learning Session:** APEX identifies a knowledge gap, queries the MCP service with a structured learning request, receives a scoring function or methodology, validates it via backtest, and queues for HITL approval.

All MCP tool outputs are always SOFT-typed, validated against APEX's own analysis, and subject to a configured maximum influence weight.

### 21.7 Content Learning Pipeline

APEX extracts knowledge from analyst videos, research papers, and commentary:

```
Content Source → Transcript/Text Extraction
→ Knowledge Extractor (LLM-powered)
→ Knowledge Classifier ({knowledge_type, actionability, relevant_components})
→ Validation Backtest
→ HITL Validation Queue
→ Integration (if approved)
```

For video content: chart extraction at timestamps, methodology description at time ranges, market calls tracked as ExpertSignals.

### 21.8 HITL Validation Queue

All autonomously learned knowledge passes through a human validation queue before integration:

```python
class ValidationItem:
    item_type: str              # "failure_lesson" | "expert_methodology" | "mcp_discovery" | ...
    learning_summary: str       # human-readable
    evidence_package: dict      # source, backtest_results, statistical_tests
    proposed_changes: list[dict]  # which components would change and how
    priority_score: float       # based on expected impact and evidence quality
    status: str                 # "pending" | "approved" | "rejected" | "modified"
```

**Auto-approval policy:** High-confidence learnings from highly-trusted sources can be auto-approved when: confidence ≥ threshold, backtest sample ≥ minimum, p-value ≤ threshold, source credibility ≥ threshold, change type in allowed list. Auto-approved items still notify the user and can be vetoed within a configured window.

---

## SECTION 22: KNOWLEDGE FORGETTING

Learned knowledge becomes stale. Markets change structurally. A pattern valid for a decade may be permanently invalidated by regulatory or microstructure changes.

**Triggers for forgetting:**
- `abstraction_decay`: Accuracy below deprecation threshold for sustained period
- `structural_market_change`: External change invalidates assumptions (e.g., settlement changed from T+2 to T+1)
- `failure_pattern_reversal`: The pattern now produces false positives
- `expert_source_degradation`: Contributing analyst's accuracy has declined significantly
- `contradicting_new_evidence`: Stronger new evidence directly contradicts existing abstraction

**Forgetting is not deletion:** Deprecated knowledge is archived with the reason. It can be restored when market conditions change. All forgetting events are logged to AuditTrail and the user is notified.

---

## SECTION 23: USER BEHAVIORAL GUARDIAN

Markets are adversarial to human psychology. APEX analyzes markets; the Behavioral Guardian analyzes the user.

### 23.1 Behavioral Bias Detection

```
REVENGE_TRADING: trade_within(N minutes of loss) AND size ≥ prior_loss_size AND same_direction
  Action: warning_before_confirmation
  Warning: "You're requesting a trade shortly after a loss, in the same direction,
            at the same or larger size."

FIXATION: same_ticker_analyses_today > configured_max
  Action: gentle_redirect
  Warning: "You've analyzed [ticker] N times today. My current thesis is [summary]."

FOMO_ENTRY: signal_strength < threshold AND confirmation_speed < rush_threshold
            AND ticker_had_large_move_today
  Action: confirmation_friction (extra confirmation step)

OVERTRADING: trades_today > configured_max AND z_score > configured_threshold
  Action: advisory_banner

CONFIRMATION_BIAS: dismissed 3+ opposing signals then confirmed weaker supporting signal
  Action: balanced_reanalysis_offer

LOSS_AVERSION_HOLD: thesis_health < threshold AND unrealized_pnl < 0 AND bars_held > max
  Action: thesis_review_prompt
```

### 23.2 Behavioral Friction in Confirmation

When bias detected, the Position Confirmation Workflow adds friction:
```
┌────────────────────────────────────────────────────┐
│ ⚠️ BEHAVIORAL CHECK                                │
│ APEX detected a potential behavioral pattern.       │
│ "You're requesting a trade 12 minutes after a loss,│
│  in the same direction, at 20% larger size."       │
│ [I've considered this — Proceed] [Let me reconsider]│
└────────────────────────────────────────────────────┘
```

### 23.3 Behavioral Profile & Longitudinal Tracking

```python
class BehavioralProfile:
    behavioral_tendencies: dict      # frequency of each bias type
    bias_override_outcomes: dict     # when_ignored vs when_heeded: {win_rate, sample}
    behavioral_trend: str           # "improving" | "stable" | "worsening"
    most_costly_bias: str
    most_improved_bias: str
```

This is the most powerful feedback for users: "When you heeded the revenge trading warning, your next 5 trades averaged +0.8R. When you ignored it, -0.4R."

---

## SECTION 24: SECOND-ORDER REASONING

APEX analyzes the current state. It also reasons about what happens next — in both directions.

```python
class SecondOrderAnalysis:
    signal_id: str
    ticker: str

    success_cascade: list[dict]   # if signal is RIGHT: cascade effects on portfolio
    failure_cascade: list[dict]   # if signal is WRONG: cascade risks
    portfolio_impact: dict        # projected_heat, correlation_risk, circuit_breaker_proximity

    # per cascade item:
    # {affected_entity, expected_effect, probability, impact_magnitude, actionable, preparation}
```

**Why Engine Layer 6 — Cascade Analysis:** Identifies all entities affected by this signal's outcome. Aggregates into portfolio-level impact. Identifies preparation actions. Included in every trade plan narrative.

---

## SECTION 25: NARRATIVE AGENT

### 25.1 Core Responsibilities

Synthesizes all pipeline outputs into a coherent, user-facing narrative. Adapts format based on signal quality, disagreement level, and epistemic assessment.

### 25.2 Disagreement-Aware Format

When `cumulative_disagreement_classification` is "adversarial" or "consensus_against":

**Standard format:** "AAPL shows a bullish RSI setup. However, the regime is bearish. Grade C."

**Disagreement-aware format:**
> "AAPL's technical setup is individually strong (signal strength 0.82) — textbook mean-reversion entry. However, the analysis progressively deteriorated through three consecutive counter-signals:
>
> 1. **Regime opposition** (confidence 0.82 → 0.61): Bear trend...
> 2. **Sentiment opposition** (0.61 → 0.48): 12 negative headlines...
> 3. **Smart money opposition** (0.48 → 0.39): Put/call at 92nd percentile...
>
> **The technical setup is real. The environment opposes it.** The conditions that would validate this entry: [list]"

### 25.3 Narrative Consistency Enforcement

Before every synthesis, the NarrativeAgent checks the TickerIntelligenceFile and the last 5 narratives for this ticker. Contradictions are classified:

- `legitimate_change`: Material data change justifies the shift → narrate explicitly
- `emphasis_drift`: Underlying data unchanged but different aspects emphasized → normalize
- `model_inconsistency`: Different pipeline runs produce different regime classifications → cache LLM assessment within configured window

**Indicator language standardization:**
```yaml
indicator_language_map:
  rsi:
    0-20:  "deeply oversold"    # always — never "approaching oversold"
    20-30: "oversold"
    40-60: "neutral"            # always — never "mid-range momentum"
    70-80: "overbought"
    80-100: "deeply overbought"
  trend_strength:
    adx_25-40: "moderate trend" # always — never "trending"
```

### 25.4 Explanation Depth Levels

```
Level 1 (Novice):   "AAPL looks good because it's trending up with strong volume"
Level 2 (Inter.):   "Bullish: RSI momentum + volume breakout + sector strength"
Level 3 (Expert):   "Long signal: RSI(14)=62.3 crossing 60 threshold, volume z-score=2.1..."
Level 4 (Quant):    Full SHAP decomposition + factor exposure + statistical significance
```

User-configurable depth. Auto-detected from query complexity when not set.

---

## SECTION 26: EVOLUTION ENGINE

The Evolution Engine monitors APEX's analytical accuracy and proposes improvements via shadow deployment.

### 26.1 Performance Monitor

Evaluates per strategy: Brier score, accuracy by regime, calibration error, signal correlation with other strategies. Hedge pair strategies are evaluated at the pair level, not individually. `hedge_effectiveness` tracks rolling correlation between pair P&L streams.

### 26.2 Shadow Deployment

New model variants or parameter sets run in shadow alongside production. After the configured shadow period and minimum signal count, statistical significance is computed. If improvement is significant: Evolution Engine generates a promotion proposal. If not: discarded with logged rationale.

### 26.3 Root Cause Analysis

When performance degrades, the Evolution Engine generates a structured root cause analysis task: `indicator_recalibration`, `regime_model_drift`, `parameter_drift`, `strategy_environment_mismatch`, or `training_data_staleness`.

### 26.4 Evolution Engine Self-Observability

```python
class EvolutionEngineDashboard:
    proposals_generated_this_month: int
    proposals_promoted: int
    proposals_rejected: int
    promotion_accuracy: float    # % of promoted changes that improved performance
    average_shadow_duration_days: float
    budget_consumed_pct: float
    is_improving_apex: bool      # meta-assessment
```

If `promotion_accuracy` drops below the configured floor, the Evolution Engine generates a self-assessment alert.

---

## SECTION 27: CURIOSITY ENGINE

When performance plateaus or specific knowledge gaps are identified, the Curiosity Engine generates structured research proposals.

### 27.1 Research Proposal Schema

```python
class ResearchProposal:
    proposal_id: str
    source: str         # "evolution_engine" | "curiosity_engine" | "human_disagreement" |
                        # "expert_observation" | "failure_pattern" | "active_learning"
    hypothesis: str
    research_questions: list[str]
    proposed_validation: dict   # {method, dataset, metrics, success_criteria}
    budget_estimate: Decimal
    priority: str
    status: str
```

### 27.2 Research ROI Tracking

```python
class CuriosityROIReport:
    proposals_generated: int
    proposals_validated: int    # led to actionable improvements
    proposals_refuted: int
    budget_consumed_usd: Decimal
    cost_per_validated_improvement: Decimal
    roi_score: float
```

---

## SECTION 28: AGENT DRIFT DETECTION

APEX's analytical behavior can drift over time — becoming systematically overconfident, biased toward momentum, or homogeneous in reasoning.

### 28.1 Behavioral Baseline

Captured during the first configured observation period after deployment:
```python
class BehavioralBaseline:
    decision_distribution: dict  # {bullish: float, bearish: float, neutral: float, no_action: float}
    avg_confidence_by_regime: dict
    signal_type_distribution: dict
    why_engine_score_distribution: dict
    reasoning_vocabulary_fingerprint: dict
```

### 28.2 Drift Detection Metrics

| Metric | Alert Threshold |
|--------|----------------|
| Decision direction ratio (too many bullish over N days) | Configurable |
| Confidence calibration gap (predicted vs actual) | Configurable |
| Strategy dominance (one strategy > X% of signals) | Configurable |
| Why Engine score homogeneity (scores too similar across conditions) | Configurable |
| Reasoning pattern repetition | Configurable |

When drift is detected: emit `AGENT_DRIFT_DETECTED`; Evolution Engine generates `agent_bias_investigation` root cause analysis task.

---

## SECTION 29: ANALYTICAL DEBT DASHBOARD

```python
class AnalyticalDebtDashboard:
    model_staleness: dict         # days since last validation per strategy
    calibration_drift: dict       # confidence vs realized accuracy gap per strategy
    failure_lesson_backlog: dict  # unprocessed failures without lessons
    learning_abstraction_decay: dict  # active abstractions with declining accuracy
    hitl_queue_age: dict          # oldest unreviewed learning in validation queue
    data_source_health: dict      # degrading adapters
    analytical_health_score: float  # 0-1; weighted composite
    health_classification: str    # "healthy" | "attention" | "degrading" | "critical"
    health_trend: str             # "improving" | "stable" | "declining"
```

Included in every PIL intelligence brief. Alerts emitted when any category exceeds its threshold.

---

## SECTION 30: FINANCIAL RISK ARCHITECTURE

### 30.1 Commission & Fee Modeling

```python
class CommissionModel:
    def calculate(self, order: Order) -> Decimal:
        broker_commission = self._broker_commission(order)              # Decimal
        sec_fee = order.quantity * order.price * Decimal('0.0000278')  # sell-side only
        taf_fee = min(order.quantity * Decimal('0.000166'), Decimal('8.30'))  # sell-side
        exchange_fee = self._exchange_fee(order)                        # Decimal
        clearing_fee = Decimal('0.00020') * order.quantity              # NSCC
        return broker_commission + sec_fee + taf_fee + exchange_fee + clearing_fee
```

All fees are Decimal. Cost model is configurable per broker without code changes.

### 30.2 Risk-Free Rate Integration

```yaml
risk_free_rate:
  source: FRED
  series: DTB3        # 3-month T-bill
  update_frequency: daily
  fallback_value: "0.05"   # Decimal string; 5% if data unavailable
  application: annualized_compounded
```

Used in: Sharpe ratio, Sortino ratio, alpha calculation, option pricing. Fetched daily by Calendar Intelligence and stored in Data Registry.

### 30.3 Factor Exposure Tracking

```python
class PortfolioFactorExposure:
    market_beta: float
    size_factor: float    # SMB
    value_factor: float   # HML
    momentum_factor: float
    quality_factor: float
    crowding_risk: str    # "LOW" | "MEDIUM" | "HIGH" | "EXTREME"
    crowded_factors: list[str]
```

Computed on each PIL cycle. High crowding risk triggers advisory alert — APEX's edge may be diminished when too many participants are positioned identically.

### 30.4 Tail Risk Assessment

```python
class TailRiskAssessment:
    cvar_95pct: Decimal
    cvar_99pct: Decimal
    historical_stress_scenarios: list[dict]
    # {scenario_name, portfolio_impact, worst_single_day}
    # Scenarios: 2008_GFC, 2020_COVID, 2010_Flash_Crash
    correlation_crisis_mode: dict
    tail_hedge_recommendations: list[str]
```

---

## SECTION 31: COST VISIBILITY & BUDGET TRACKING

```python
class DailyCostReport:
    llm_api_calls: dict        # {count, cost: Decimal, budget: Decimal, remaining: Decimal}
    data_vendor_calls: dict    # {count, cost: Decimal, budget: Decimal}
    total_daily_cost: Decimal
    cost_per_signal: Decimal
    cost_per_trade_plan: Decimal
    monthly_budget: Decimal
    monthly_spend_to_date: Decimal
    projected_monthly_spend: Decimal
    budget_alert: str | None   # "OVER_BUDGET_PROJECTED" | "APPROACHING_LIMIT"
```

Every LLM call and external API call is tagged with the component that generated it. Attribution breakdown available at `GET /admin/cost/attribution`.

```yaml
budget:
  daily_llm_budget_usd: "100.00"
  alert_threshold_pct: 0.80
  hard_stop_threshold_pct: 0.95    # PIL and Evolution Engine pause
  reactive_reserve_pct: 0.20       # always reserve 20% for user requests
```

---

## SECTION 32: OBSERVABILITY STACK

### 32.1 Structured Logging (JSON, Every Line)

```json
{
  "timestamp": "2026-05-18T14:32:11.432Z",
  "level": "INFO",
  "component": "why_engine.layer3",
  "trace_id": "abc-123-def-456",
  "span_id": "7890xyz",
  "session_id": "sess-001",
  "message": "Regime detection complete",
  "extra": {"regime": "bear_trend", "fitness_score": 0.25, "duration_ms": 47}
}
```

**Log redaction (runs on every log entry):**
```python
PATTERNS = [
    (r'api[_-]?key[":\s=]+\S+', 'api_key=***REDACTED***'),
    (r'password[":\s=]+\S+', 'password=***REDACTED***'),
    (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '***CARD***'),
    (r'"balance"\s*:\s*[\d.]+', '"balance": ***REDACTED***'),
]
```

### 32.2 Metrics (Prometheus-Compatible)

```
apex_pipeline_latency_ms          (histogram, labels: intent_type, strategy_id)
apex_pipeline_requests_total      (counter, labels: intent_type, outcome)
apex_gate_rejections_total        (counter, labels: gate_id, reason)
apex_pil_cycle_duration_ms        (histogram, labels: session_name)
apex_budget_llm_cost_usd_total    (counter)
apex_portfolio_heat_pct           (gauge)
apex_model_brier_score            (gauge, labels: strategy_id)
apex_model_drift_kl_divergence    (gauge, labels: strategy_id)
apex_circuit_breaker_activations_total (counter)
```

### 32.3 Distributed Tracing (OpenTelemetry)

Every request receives a `trace_id` that follows it through every component. Every component creates spans with relevant attributes. Sampling: 100% of slow requests (> configured threshold), 100% of errors, 10% of all others. p50/p95/p99 tracked per pipeline stage.

---

## SECTION 33: SECURITY

### 33.1 Authentication & Authorization

- JWT tokens with configured expiry
- Token refresh protocol for long-running WebSocket sessions (client sends refresh before expiry; server validates and issues new token; expired tokens close WebSocket with `4401 Token Expired`)
- CSRF protection: `SameSite=Strict` on all cookies
- Role-based access control: analyst, trader, admin

### 33.2 Strategy Plugin Security

- Runtime sandbox with allowlisted imports
- CPU time limit and memory limit per plugin execution (`resource_limits()` contract)
- No network or filesystem access
- All exceptions caught and converted to `plugin_error`

### 33.3 Webhook Security

Every webhook request includes `X-APEX-Signature: HMAC-SHA256(webhook_secret, request_body)`. Webhook secrets are configured per-user in the secrets manager.

### 33.4 Data Sovereignty

```yaml
data_sovereignty:
  llm_provider_data_policy: no_portfolio_data_in_prompts
  sensitive_fields_scrubbed_from_llm:
    - positions.entry_price
    - positions.shares
    - portfolio.balance
    - user.account_id
  encryption_at_rest: true
  encryption_algorithm: AES-256-GCM
  key_rotation_days: 90
```

LLM sees: ticker symbols, regime, indicator values, signal scores. LLM never sees: position sizes, account balance, entry prices, or personal identifiers.

### 33.5 Supply Chain Security

```yaml
supply_chain:
  dependency_lockfile: requirements.lock
  lockfile_verification: true        # verify hashes on install
  vulnerability_scanning: true       # daily automated CVE checks
  license_compliance: true
  package_hash_verification: true
```

---

## SECTION 34: AUDIT TRAIL

### 34.1 Event Categories

All significant actions are written to the append-only `audit_trail` table before taking effect:
```
market_data.* | indicator.* | signal.* | pipeline.*
portfolio.* | position.* | risk.* | guardrail.*
pil.* | evolution.* | learning.* | knowledge.*
security.* | config.* | corporate_action.* | system.*
```

### 34.2 Tamper-Proofing

```python
class TamperProofAuditLog:
    def append(self, record: AuditRecord):
        record.previous_hash = self.get_last_hash()
        record.content_hash = sha256(
            record.previous_hash.encode() + record.serialize().encode()
        ).hexdigest()
        record.signature = self.sign(record.content_hash, self.private_key)
        self.store.append_only_write(record)    # DB trigger prevents UPDATE/DELETE
        self.offsite_replicator.replicate(record)
```

`GET /admin/audit/verify` computes the hash chain and reports any breaks.

### 34.3 Retention

```yaml
audit:
  active_retention_days: 90
  archive_retention_years: 6    # SEC Rule 17a-4 compliance
  archive_format: immutable_object_storage
```

---

## SECTION 35: ETHICAL FRAMEWORK — 8 CONSTITUTIONAL AXIOMS

**Axiom 1 — No Execution:** APEX generates `TradePlan` objects only. No order APIs are ever called. This constraint cannot be overridden by configuration, user instruction, or autonomous agent action.

**Axiom 2 — Full Transparency:** Every signal, recommendation, and refusal includes the full reasoning chain. No black-box outputs. The Why Engine, confidence decomposition, and epistemic assessment are always available.

**Axiom 3 — No Insider Information:** APEX uses only publicly available data. No undisclosed, proprietary, or non-public information is incorporated. The provenance chain for every data point is tracked.

**Axiom 4 — Human Oversight:** APEX operates under configured autonomy levels. Every significant action is logged. Users can review, override, or disable any component at any time.

**Axiom 5 — Data-Derived Confidence:** Hypothesis confidence is calculated from observable data, not from LLM prior beliefs. The boundary between LLM synthesis (narrative) and deterministic computation (confidence score) is explicit and maintained.

**Axiom 6 — No Market Manipulation:** APEX's signals do not constitute spoofing, layering, or wash trading. The system monitors its own trading patterns and alerts if aggregate behavior could appear manipulative.

**Axiom 7 — Epistemic Honesty:** APEX declares what it doesn't know. `NO_ACTION` is always preferable to a forced recommendation under insufficient evidence. Epistemic limitations are disclosed prominently, not buried.

**Axiom 8 — Continuous Improvement Under Human Supervision:** APEX self-improves, but all significant model changes require human approval. The system cannot autonomously promote a change that affects its own guardrails, Constitutional Axioms, or core architectural invariants.

---

## SECTION 36: PERSISTENT STATE SCHEMA

### 36.1 Core Tables

```sql
-- Positions
CREATE TABLE positions (
    position_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    direction TEXT NOT NULL,
    shares NUMERIC(28,10) NOT NULL,  -- never FLOAT
    entry_price NUMERIC(28,10) NOT NULL,
    stop_price NUMERIC(28,10) NOT NULL,
    take_profit NUMERIC(28,10) NOT NULL,
    notional NUMERIC(28,10) NOT NULL,
    status TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    config_snapshot_id TEXT NOT NULL,
    entry_thesis JSONB NOT NULL,
    thesis_health NUMERIC(5,4),
    settlement_date DATE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

-- Signals
CREATE TABLE signals (
    signal_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    direction TEXT NOT NULL,
    strength NUMERIC(5,4) NOT NULL,  -- never FLOAT for this
    generated_at TIMESTAMPTZ NOT NULL,
    disposition TEXT,
    confirm_status TEXT,
    trace_id TEXT NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

-- Audit Trail (append-only, triggers prevent UPDATE/DELETE)
CREATE TABLE audit_trail (
    record_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    component TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    previous_hash TEXT,
    content_hash TEXT NOT NULL,
    signature TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    db_recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 36.2 Learning & Intelligence Tables

```sql
-- Failure Memory
CREATE TABLE failure_records (...);
CREATE TABLE failure_lessons (...);
CREATE TABLE failure_patterns (...);

-- Knowledge & Learning
CREATE TABLE learning_abstractions (...);
CREATE TABLE knowledge_items (...);
CREATE TABLE learning_sessions (...);
CREATE TABLE hitl_validation_queue (...);

-- Expert & Human Intelligence
CREATE TABLE analyst_profiles (...);
CREATE TABLE step_disagreements (...);
CREATE TABLE expert_signals (...);

-- Cross-Session Continuity
CREATE TABLE ticker_intelligence_files (...);
CREATE TABLE thesis_health_records (...);

-- Strategy & Evolution
CREATE TABLE strategy_performance (...);
CREATE TABLE shadow_portfolios (...);
CREATE TABLE shadow_positions (...);
CREATE TABLE hypotheses (...);
```

### 36.3 Required Indexes

```sql
CREATE INDEX idx_positions_strategy_status ON positions(strategy_id, status);
CREATE INDEX idx_positions_ticker_status ON positions(ticker, status);
CREATE INDEX idx_signals_ticker_strategy_time ON signals(ticker, strategy_id, generated_at);
CREATE INDEX idx_signals_disposition ON signals(disposition);
CREATE INDEX idx_audit_event_time ON audit_trail(event_type, recorded_at);
CREATE INDEX idx_failure_records_ticker ON failure_records(ticker, strategy_id);
CREATE INDEX idx_failure_patterns_status ON failure_patterns(status);
```

### 36.4 Transaction Isolation

```yaml
database:
  isolation:
    default_reads: read_committed
    portfolio_calculations: repeatable_read    # prevents non-repeatable reads during heat calc
    position_mutations: serializable           # highest integrity for position state changes
    order_operations: serializable
    reporting_queries: read_committed
```

**Deadlock handling:** Lock ordering convention (alphabetical ticker). Statement timeout: 5000ms. Automatic retry on `DeadlockDetected` with jitter (max 5 retries). Deadlock frequency tracked as metric; exceeding threshold triggers alert.

### 36.5 Table Partitioning

```sql
-- High-volume tables partitioned by month
CREATE TABLE pil_events PARTITION BY RANGE (generated_at);
CREATE TABLE signals PARTITION BY RANGE (generated_at);
-- audit_trail: append-only + monthly partitions for query performance
```

---

## SECTION 37: API CATALOG

### 37.1 Core Endpoints

```
GET  /portfolio                          Portfolio overview
GET  /portfolio/positions                Open positions with thesis health
POST /portfolio/positions                Confirm position (requires Idempotency-Key)
GET  /portfolio/positions/{id}           Single position
PATCH /portfolio/positions/{id}          Update position (stop, TP adjustment)

GET  /portfolio/heat                     Current heat computation (live, never cached)
GET  /portfolio/correlation              Correlation matrix
GET  /portfolio/factor-exposure          Factor exposure analysis
GET  /portfolio/tail-risk               CVaR and stress scenario results
GET  /portfolio/paper                    Paper portfolio
POST /portfolio/paper/positions          Paper position

GET  /portfolio/hedge-pairs              Hedge pair definitions
POST /portfolio/hedge-pairs              Create hedge pair
DELETE /portfolio/hedge-pairs/{id}       Remove hedge pair

POST /intelligence/analyze               Single ticker analysis
POST /intelligence/universe-scan         Multi-ticker scan
POST /intelligence/compare               Strategy comparison

GET  /intelligence/brief                 Current PIL intelligence brief
GET  /intelligence/hypotheses            Active hypotheses
POST /intelligence/directives            Send directive to PIL

GET  /intelligence/failure-patterns      Active failure patterns
GET  /intelligence/learning-abstractions Validated learning abstractions
PATCH /intelligence/learning-abstractions/{id}/status   Approve/reject abstraction
GET  /intelligence/expert-signals        Active expert signals
POST /intelligence/expert-signals        Submit expert signal
POST /intelligence/disagreements         Submit step-level disagreement
GET  /intelligence/ticker/{ticker}/file  Ticker Intelligence File

GET  /signals                            Signal history
PATCH /signals/{id}/disposition          Update signal disposition
GET  /strategies                         Active strategies
POST /strategies/{id}/activate           Activate strategy
POST /strategies/{id}/deactivate         Deactivate strategy
GET  /strategies/{id}/drift              Config drift from reference
GET  /strategies/{id}/performance        Performance attribution

POST /replay/sessions                    Start replay session
POST /replay/sessions/{id}/step          Advance one bar
POST /replay/sessions/{id}/pause         Pause replay
DELETE /replay/sessions/{id}             End replay

POST /reports                            Generate report
GET  /reports/{id}                       Retrieve report

GET  /admin/health/deep                  Deep health check with all component status
GET  /admin/cost/daily                   Daily cost breakdown
GET  /admin/cost/attribution             Cost attribution by component
GET  /admin/audit/verify                 Verify audit trail hash chain
GET  /admin/behavioral-profile/{user_id} User behavioral analytics

GET  /users/{id}/behavioral-profile      Behavioral profile summary
GET  /notifications/preferences          Notification preferences
PATCH /notifications/preferences         Update preferences

GET  /team/review-queue                  Team review queue
POST /team/review-queue/{id}/approve     Approve review item
POST /team/review-queue/{id}/reject      Reject review item

GET  /ws                                 WebSocket (token + last_event_id + subscribe filter)
```

### 37.2 Idempotency Requirements

All state-mutating POST endpoints require `Idempotency-Key` header. Server stores response keyed by the value for configured TTL. Duplicate requests within TTL return cached response without re-execution. Missing header on mutating endpoint returns `400 IDEMPOTENCY_KEY_REQUIRED`.

### 37.3 WebSocket Event Catalog

Complete event type catalog (all events emitted to connected clients):

```
INTELLIGENCE_BRIEF_UPDATE     PIL_CYCLE_COMPLETE          OPPORTUNITY_BRIEF
SIGNAL_GENERATED              SIGNAL_SUPPRESSED           MTF_SUPPRESSION
POSITION_OPENED               POSITION_CLOSED             POSITION_UPDATED
HEAT_WARNING                  HEAT_CRITICAL               CIRCUIT_BREAKER_TRIGGERED
THESIS_INVALIDATED            THESIS_WEAKENING            THESIS_UPDATED
REGIME_CHANGE                 STRATEGY_READY              STRATEGY_DEGRADING
TRADE_PLAN_READY              TRADE_PLAN_UPDATED          NO_ACTION_ISSUED
CANVAS_UPDATE                 ANALYSIS_TRAJECTORY_UPDATE
CORPORATE_ACTION_APPLIED      TICKER_HALT_DETECTED        SSR_ACTIVATED
DATA_RESTATEMENT_ALERT        DATA_REGISTRY_MEMORY_WARNING
AGENT_DRIFT_DETECTED          LLM_UNAVAILABLE             LLM_PROVIDER_FAILOVER
BUDGET_WARNING                MEMORY_LEAK_SUSPECTED
DISAGREEMENT_SUBMITTED        DISAGREEMENT_RESOLVED
EXPERT_SIGNAL_RECEIVED        LEARNING_SESSION_COMPLETE
KNOWLEDGE_VALIDATED           KNOWLEDGE_INTEGRATED
LEARNING_ABSTRACTION_CREATED  ABSTRACTION_DEPRECATED
BEHAVIORAL_BIAS_DETECTED
HEARTBEAT                     SESSION_STARTED             SESSION_RESUMED
SHUTDOWN_IMMINENT             RATE_LIMITED
```

---

## SECTION 38: CANVAS LAYER

The Canvas Layer renders visual artifacts for every pipeline output. All render types are registered handlers; unknown types render a placeholder.

### 38.1 Render Types (Complete)

```
candlestick_chart        volume_profile_chart      options_surface
trade_plan_card          research_note_card        no_action_card
why_engine_card          reflection_card           intelligence_brief_card
portfolio_heatmap        correlation_matrix        factor_exposure_chart
analysis_trajectory      thesis_health_chart       behavioral_profile_view
config_drift_view        disposition_analytics     failure_pattern_map
performance_attribution  intermarket_dashboard
report_preview           canvas_payload_error
```

**Error state:** When a payload passes handler registration but fails schema validation, render a `canvas_payload_error` placeholder with render_type, validation error summary, and source attribution. Emit `CANVAS_PAYLOAD_ERROR`.

**Chart data windowing:** `max_visible_bars` config limits initial render. Historical data loads on scroll.

---

## SECTION 39: DEPLOYMENT & OPERATIONS

### 39.1 CI/CD Pipeline (7 Stages)

```
Stage 1: Static Analysis (type checking, lint, security scan)
Stage 2: Unit Tests (with numerical type validation tests)
Stage 3: Backtest-to-Live Parity Verification (mandatory)
Stage 4: Integration Tests (database isolation: transaction-rollback per test)
Stage 5: Strategy Compliance Tests (all plugins against full interface contract)
Stage 6: Security Tests (prompt injection, CSRF, auth, HMAC)
Stage 7: Performance Tests (3 load profiles: single-user, team, stress)
```

Any stage failure blocks deployment.

### 39.2 Blue-Green Deployment

Zero-downtime deployments via blue-green. Health check on new instance before traffic cutover. Instant rollback: disable new instance and re-enable old. Backward-compatible database migrations only (never drop a column; add with default).

### 39.3 Backup/Restore

```yaml
operations:
  backup:
    schedule: "0 2 * * *"   # 2am daily
    retention_days: 30
    destination: configured_object_storage
    verify_restore: true
    rpo_target_minutes: 5
    rto_target_minutes: 15
```

### 39.4 Observability Integration

- Logs: structured JSON, rotated, shipped to configured log aggregation service
- Metrics: Prometheus endpoint at `/metrics`
- Traces: OTLP exporter to configured tracing backend

### 39.5 Incident Management

SEV1 (system down) → SEV4 (minor degradation). Automated runbooks triggered per incident type. Post-mortem template for all SEV1-SEV2 incidents. Incident history database for searchable pattern analysis.

---

## SECTION 40: PAPER TRADING, REPLAY, AND SIMULATION

### 40.1 Paper Trading

Shadow portfolio runs in parallel with full risk enforcement applied. `dual` mode: paper and live simultaneously. In dual mode, paper position status is `pending_live_confirm` until live position is confirmed. If live position is rejected or expires, the paper position closes with `live_confirmation_failed`.

### 40.2 Replay Mode

Bar-by-bar historical replay through the live pipeline. Look-ahead prohibition enforced identically to live mode. Used for backtest-to-live parity verification and user education.

```
POST /replay/sessions         → Start session with dataset, strategy, starting_bar
POST /replay/sessions/{id}/step → Advance one bar; returns pipeline outputs
POST /replay/sessions/{id}/pause
DELETE /replay/sessions/{id}
```

### 40.3 Simulation Sandbox

Before deploying a new strategy or parameter set, run it in simulation against configured historical scenarios and stress conditions. Returns: stability score, variance in outcome, scenario-by-scenario breakdown.

---

## SECTION 41: WAR ROOM UI

The War Room is the primary interface. Desktop-first with responsive tablet layout (panels stack vertically) and mobile tab layout (Chat | Canvas | PIL | Portfolio).

### 41.1 Panel Layout (Desktop)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ WAR ROOM                                           [Portfolio Status Bar] │
├──────────────────┬──────────────────────────┬───────────────────────────┤
│  LEFT PANEL      │    CANVAS REGION         │    RIGHT PANEL             │
│                  │                          │                            │
│  Chat Interface  │  Primary visualization   │  PIL Intelligence Brief   │
│  History         │  (trade plans, charts,   │  Strategy Status          │
│  Query Builder   │   why engine, trajectory │  Active Signals            │
│                  │   cards, etc.)           │  Learning Queue            │
├──────────────────┴──────────────────────────┴───────────────────────────┤
│ THOUGHT PROCESS INSPECTOR (expandable, with per-step Disagree buttons)  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 41.2 Accessibility

WCAG 2.1 AA compliance: color-blind safe palettes, keyboard navigation for all interactions, screen reader support with ARIA labels, minimum 4.5:1 contrast ratio.

---

## SECTION 42: MULTI-USER & TEAM FEATURES

```yaml
team:
  roles:
    - viewer: read-only War Room access; no signal confirmation
    - analyst: full analysis; can submit disagreements and expert signals
    - trader: analyst + can confirm positions
    - admin: full access + configuration management + user management

  review_workflow:
    enabled: bool
    grade_threshold_for_review: B    # grades above this bypass review queue
    review_required_for: ["Grade A signals", "position size > configured threshold"]
```

Shared watchlists, shared PIL brief, per-user behavioral profiles, per-analyst track records.

---

## SECTION 43: AUTONOMY MATRIX

```yaml
autonomy:
  pil_hypothesis_generation: fully_autonomous
  pil_intelligence_brief: fully_autonomous
  data_fetching: fully_autonomous
  indicator_computation: fully_autonomous
  signal_generation: fully_autonomous
  signal_suppression_by_guardrail: fully_autonomous
  evolution_shadow_deployment: fully_autonomous
  curiosity_research: supervised_autonomous   # within budget, proposal visible
  learning_abstraction_creation: supervised_autonomous  # always to HITL queue
  strategy_parameter_tuning: requires_approval
  strategy_activation: requires_approval
  model_promotion: requires_approval
  guardrail_threshold_change: requires_approval
  constitutional_axiom_change: requires_human_override  # cannot be automated
  position_confirmation: always_human
  order_execution: prohibited_by_architecture
```

---

## APPENDIX A: PROHIBITED PATTERNS

**Numerical:**
- Never use `float` for any monetary value
- Never silently coerce `float` to `Decimal` — raise `NumericalTypeViolation`
- Never store monetary values as `FLOAT` or `DOUBLE` in the database
- Never compare monetary values with `==` on floats — use `Decimal` exact comparison

**Processing:**
- Never process a state-mutating event without an idempotency check
- Never write state to the database without also writing to the outbox table (same transaction)
- Never publish an event without first writing it to the outbox

**Financial Domain:**
- Never compute indicators across a corporate action boundary without price adjustment
- Never generate a short signal when SSR is active
- Never use calendar days where trading days are required
- Never include portfolio position sizes, account balance, or user PII in LLM prompts

**Architecture:**
- Tools never call each other
- Tools never call the LLM
- Strategy plugins never access the Data Registry directly
- Raw exceptions never propagate to LLM context
- `NO_ACTION` is always preferable to a forced recommendation under insufficient evidence

**Security:**
- Never log API keys, passwords, or financial data in plaintext
- Never trust user-supplied ticker symbols without validation against known universe
- Never bypass the LLM prompt injection firewall for "trusted" inputs
- Never promote a change that modifies Constitutional Axioms autonomously

---

## APPENDIX B: GLOSSARY

| Term | Definition |
|------|-----------|
| **Abstain Mode** | System state where APEX explicitly produces `NO_ACTION` with documented reasons |
| **Agent Drift** | Gradual change in APEX's analytical behavior over time, independent of parameter changes |
| **Analytical Debt** | Intelligence quality declining through stale models, uncalibrated confidence, ignored failure patterns |
| **Behavioral Guardian** | Subsystem monitoring user interaction patterns for behavioral bias |
| **Confidence Decomposition** | Breakdown of confidence into constituent components |
| **Corporate Actions Engine** | Subsystem detecting and applying splits, dividends, mergers, delistings |
| **Cross-Session Continuity** | APEX maintaining evolving views on tickers across sessions |
| **DecisionContract** | The unified typed output schema that every APEX decision must conform to |
| **Epistemic Humility** | APEX's formal assessment of its own knowledge boundaries |
| **Exactly-Once Processing** | Processing the same event twice produces the same result without duplicate side effects |
| **Failure Memory** | Persistent store of classified failures with lessons and similarity fingerprints |
| **Idempotency Key** | Client-generated unique identifier enabling duplicate request detection |
| **Knowledge Application Engine** | Component that proactively injects learned knowledge into every analysis |
| **Learning Abstraction** | A human-readable, machine-applicable statement of what APEX has learned |
| **LULD** | Limit Up-Limit Down — US exchange rules that halt trading on rapid price moves |
| **NumericalTypeViolation** | Error raised when a monetary value is typed as `float` instead of `Decimal` |
| **Redemption Candidate** | Previously suppressed signal whose conditions for re-evaluation have been met |
| **Settlement Date** | Date trade is finalized (T+1 for US equities since May 2024) |
| **SSR** | Short Sale Restriction — uptick-only short selling when stock drops ≥10% from prior close |
| **Stepwise Disagreement** | Progressive confidence trajectory tracked as each pipeline step adds evidence |
| **Ticker Intelligence File** | Per-ticker persistent record of APEX's evolving analytical view |
| **Transactional Outbox** | Pattern ensuring state changes and event publication happen atomically |

---

## APPENDIX C: IMPLEMENTATION PRIORITY

### Tier 0 — Foundation (Build Before Anything Else)

| # | Item | Why It Blocks Everything |
|---|------|--------------------------|
| 0.1 | **Decimal arithmetic for all monetary values** | Every financial calculation is silently wrong without this |
| 0.2 | **State management & StrategicMemory concurrency model** | Race conditions corrupt portfolio state |
| 0.3 | **Exactly-once processing guarantees** | Duplicate signals and positions without this |
| 0.4 | **Clock synchronization & time authority** | Audit trail integrity, replay, TCA all depend on this |
| 0.5 | **Configuration validation** | Misconfigured `max_position_pct: 1.5` (meant 1.5%) causes catastrophic loss |
| 0.6 | **Error taxonomy & retry semantics** | Inconsistent retry behavior creates unreliable system |
| 0.7 | **Startup/shutdown sequences** | Every restart without these is a potential data corruption event |
| 0.8 | **Observability: logs + metrics + traces** | Cannot debug or operate production without all three |
| 0.9 | **Memory management & process supervision** | Long-running processes leak without this |
| 0.10 | **Signal handling (SIGTERM, SIGHUP)** | Without this, `kill <pid>` corrupts state mid-transaction |

### Tier 1 — Before Live Market Data

Corporate actions engine, ex-dividend handling, exchange halt/LULD awareness, settlement cycle (T+1), business day calendar, log redaction, LLM provider failover chain, API endpoint idempotency, backtest-to-live parity verification, data vendor reconciliation after restatement.

### Tier 2 — Before Multi-User Deployment

Database transaction isolation, distributed tracing, audit log tamper-proofing, cost visibility dashboard, agent drift detection, WebSocket backpressure, LLM output schema validation.

### Tier 3 — Intelligence & Learning (The Next Leap)

Failure Memory System, Learning Engine, cross-session continuity, stepwise disagreement tracking, human disagreement capture, expert integration, autonomous expert observation, Knowledge Application Engine, Learning Abstraction Store, user behavioral guardian, epistemic humility, knowledge forgetting, second-order reasoning.

---

## APPENDIX D: DEPENDENCY GRAPH

```
Tier 0 (Foundation):
  Decimal arithmetic → ALL monetary calculations
  State management → Portfolio gate, position confirmation, correlation tracking
  Exactly-once → Position creation, signal publication, PIL events
  Clock sync → Audit trail, TCA, replay, all timestamps
  Config validation → ALL components
  Error taxonomy → ALL components
  Startup/shutdown → ALL components
  Observability → ALL components
  Memory management → ALL long-running components
  Signal handling → Graceful shutdown

Tier 1 (Data Integrity — depends on Tier 0):
  Corporate actions → fetch_market_data, compute_indicators, StrategicMemory
  Ex-dividend → candlestick indicators, signal generation
  LULD/halts → signal generation, PIL risk sentinel
  Settlement (T+1) → position confirmation, cash availability
  Business day calendar → all period calculations, T+1
  LLM failover → Reflection Layer, Why Engine, NarrativeAgent
  Idempotency → position confirmation, PIL event publication

Tier 2 (Intelligence — depends on Tier 0+1):
  Failure Memory → Reflection Layer, Why Engine Layer 5
  Learning Engine → Evolution Engine, strategy weights, calibration
  Cross-session continuity → NarrativeAgent, PIL opportunity scout
  Stepwise disagreement → Executive controller DAG, reflection
  Human disagreement → analyst profile, curiosity engine
  Expert integration → Why Engine Layer 4, PIL bridge
  Behavioral guardian → position confirmation workflow
  Epistemic humility → NarrativeAgent, abstain mode
```

---

## APPENDIX E: ENVIRONMENT VARIABLES

```bash
# Database
DATABASE_URL=postgresql://...
DATABASE_POOL_MIN=2
DATABASE_POOL_MAX=20

# Cache
REDIS_URL=redis://...

# LLM
ANTHROPIC_API_KEY=...        # via secrets manager; never in plaintext config
LLM_PRIMARY_MODEL=claude-sonnet-4-6

# Data Vendors
DATA_VENDOR_PRIMARY_KEY=...  # via secrets manager
DATA_VENDOR_FALLBACK_KEY=... # via secrets manager

# Deployment
APEX_ENV=production          # production | staging | development
LOG_LEVEL=INFO
METRICS_PORT=9090

# Budgets
DAILY_LLM_BUDGET_USD=100.00
DAILY_API_BUDGET_CALLS=10000

# Memory
MAX_RSS_MB=8192
MEMORY_LEAK_ALERT_MB_PER_HOUR=50
```

---

*APEX v3 — Single Unified Architecture Specification*  
*All systems described above are part of one integrated architecture.*  
*Nothing is deferred. Nothing is listed without its implementation path.*  
*This document supersedes APEX Instruction Set v2 and all gap analysis sessions.*

---

# PART II: TECHNICAL ANALYSIS ENGINE

---

## SECTION 44: MARKET MICROSTRUCTURE & ORDER BOOK LAYER

Microstructure signals operate on tick-level and depth data — the most granular available view of supply and demand. They are HARD signals when sourced from exchange feeds, SOFT when from aggregated third-party services.

### 44.1 Tool: `fetch_tick_data`

**Inputs:** ticker, start_time, end_time, include_trades (bool), include_quotes (bool), provider

**Outputs:** `tick_data_id`, record_count, first_timestamp, last_timestamp, source, quality_score

**Logic expectations:** Every tick record carries: timestamp (microsecond precision when available), price, size, aggressor side (buy/sell when determinable), exchange, and condition codes. Trade records and quote records are stored under separate namespaced keys within the `tick_data_id` registry entry.

### 44.2 Tool: `fetch_market_depth`

**Inputs:** ticker, levels (from config: 5, 10, 20), snapshot_interval (from config), provider

**Outputs:** `depth_id`, bid_ask_spread (Decimal), imbalance_pct, timestamp

**Logic expectations:** The depth data contains per-level bid/ask price and size. When the provider delivers order book snapshots at the configured interval, these are stored as a time-series of depth states. The bid-ask spread is computed as ask price minus bid price at Level 1, expressed in Decimal.

### 44.3 Tool: `compute_order_flow_indicators`

**Inputs:** `tick_data_id`, `depth_id` (optional), active strategy set, param overrides

**Outputs:** `order_flow_id`, computed indicator keys, unavailability_flags

**Computed indicators:**

**Volume Delta (VD) and Cumulative Volume Delta (CVD):** VD is the difference between buy-aggressor volume and sell-aggressor volume for each bar. CVD is the running cumulative sum of VD across the session. Divergence between CVD trend and price trend signals absorption (price falls while buyers are dominant) or distribution (price rises while sellers are dominant). Requires tick data with aggressor-side classification.

**Order Book Imbalance (OBI):** Computed as (total bid volume − total sell volume) / (total bid volume + total sell volume) across the configured depth levels. OBI near +1 indicates heavy buy-side pressure; near −1 indicates heavy sell-side pressure. Rolling OBI over the configured window produces a time-series signal.

**Bid-Ask Spread Z-Score:** The current spread normalized against its rolling mean and standard deviation over the configured lookback. Elevated spread z-scores indicate low liquidity, periods of uncertainty, or market maker risk aversion — all reasons to be cautious about entering.

**Absorption:** Detects when large sell volume (high negative delta) fails to push price lower, or when large buy volume fails to push price higher. Absorption signals the presence of contra-side institutional interest at a price level and is a leading indicator of reversal or stall. The detection algorithm compares the CVD delta in a configured time window against the corresponding price change.

**Footprint Bar Representation:** When tick data is available, each bar is decomposed into price-level volume buckets showing volume traded at each price increment within the bar, split by side. The imbalance at each level (top-of-bar selling volume versus bottom-of-bar buying volume) identifies stacked imbalances and points of control within the bar.

**Iceberg Detection:** When depth data is available, large, repeatedly-replenished orders at a static price level that absorb contra-side flow without depleting are flagged as potential iceberg orders. The detection threshold (minimum replenishment count, minimum size) is a strategy parameter.

### 44.4 Canvas Render Types

**`footprint_chart`:** Delta-colored footprint bars with CVD sub-pane. Each price level within a bar shows buy/sell volume. Positive delta bars are colored green-spectrum; negative delta bars red-spectrum. Stacked imbalances are annotated.

**`market_depth`:** Order book depth ladder (Level 2) with configurable display modes: ladder view (bid/ask levels as rows), heatmap (volume intensity over time and price), or time-series (OBI rolling series). Iceberg and absorption flags are shown inline.

**`depth_heatmap`:** 2D bid/ask volume grid over time and price. Hot spots (high volume concentrations) are rendered with a configured color gradient. Used for identifying price levels where significant activity is clustering before a move.

---

## SECTION 45: CANDLESTICK & PRICE ACTION PATTERNS

All patterns are computed as time-series outputs of `compute_indicators`. All thresholds are strategy configuration values.

### 45.1 Bar Character Scoring (per bar)

| Metric | Formula | Range | Meaning |
|--------|---------|-------|---------|
| Close Location Value (CLV) | `(close − low − (high − close)) / (high − low)` | −1 to +1 | +1 = closed at high; −1 = closed at low |
| Body-to-Range Ratio | `|close − open| / (high − low)` | 0 to 1 | 1 = Marubozu; 0 = Doji |
| Upper Tail Ratio | `(high − max(open, close)) / (high − low)` | 0 to 1 | proportion consumed by upper wick |
| Lower Tail Ratio | `(min(open, close) − low) / (high − low)` | 0 to 1 | proportion consumed by lower wick |
| Relative Bar Size | `bar_range / avg_range_lookback` | 0+ | 1.0 = average; >2.0 = expansion |
| Gap Character | categorical | — | full_gap_up, partial_gap_up, no_gap, partial_gap_down, full_gap_down |

### 45.2 Single-Bar Patterns

Doji, Long-Legged Doji, Dragonfly Doji, Gravestone Doji, Hammer, Shooting Star, Hanging Man, Inverted Hammer, Bullish Marubozu, Bearish Marubozu, Spinning Top. Each detection algorithm evaluates conditions against current bar OHLCV and configured parameters. All thresholds (doji body ratio, hammer tail ratio, marubozu threshold) are strategy configuration values.

### 45.3 Two-Bar Patterns

Bullish Engulfing, Bearish Engulfing, Bullish Piercing Line, Dark Cloud Cover, Bullish Tweezer Bottom, Bearish Tweezer Top, Inside Bar (mother bar compression), Outside Bar (engulfing range).

### 45.4 Three-Bar Patterns

Morning Star, Evening Star, Three White Soldiers, Three Black Crows, Three Inside Up / Down.

### 45.5 Pattern Record Schema

```
pattern_record:
  bar_time:              string    — UTC ISO-8601
  bar_character:         object    — {clv, body_ratio, upper_tail, lower_tail, rel_size, gap_type}
  patterns_detected:     list of:
    pattern_type:        string
    direction:           string    — "bullish" | "bearish" | "neutral"
    strength:            float     — 0–1; combination of key condition margins
    context:             string    — "confirmed_in_trend" | "counter_trend" | "no_context"
    bars_involved:       int
  combined_signal:       string    — highest-priority pattern if multiple detected
  combined_strength:     float
```

**Language rule:** NarrativeAgent is prohibited from using anthropomorphic language for patterns ("the market is telling us," "bulls are fighting back"). Patterns are described by their structural characteristics and measured strength score.

---

## SECTION 46: ADVANCED TREND & MOMENTUM INDICATORS

All indicators are available for declaration in any strategy plugin's `required_indicators()`. All parameters are strategy configuration values — none are hardcoded.

**ADX/DMI System:** Three outputs: +DI, −DI, ADX. ADX quantifies trend strength independent of direction. +DI/−DI crossover provides directional bias. ADX threshold separating trending from ranging is a strategy parameter.

**Parabolic SAR:** Dynamic stop-and-reverse per bar. Acceleration factor start, maximum, and initial EP lookback are strategy parameters. Flip events are recorded as a separate boolean event series.

**Ichimoku Cloud:** Five named output series: Tenkan-Sen, Kijun-Sen, Senkou Span A, Senkou Span B, Chikou Span. All period parameters are strategy configuration values. Cloud color (bullish: Span A > Span B; bearish: Span A < Span B) is encoded as a categorical series.

**Supertrend:** ATR-based volatility-adjusted trend. Output: per-bar level and direction series. Direction change bars recorded as a separate event series.

**Multi-MA Ribbon System:** Any number of MAs at any configured combination of periods and types (SMA, EMA, DEMA, TEMA, WMA, VWMA). Ribbon compression score (std dev of MA values), ribbon expansion events, and MA alignment fraction are computed.

**Chande Momentum Oscillator (CMO):** Bounded −100 to +100. Overbought/oversold thresholds are strategy parameters.

**Commodity Channel Index (CCI):** Deviation constant is a strategy parameter. Significance zones are configurable.

**Rate of Change (ROC):** Optional signal line (EMA of ROC). Zero-line and signal-line crossover event series.

**Full Stochastic:** %K (raw), %D (smoothed %K), full slow stochastic (smoothed %D). All periods are strategy parameters.

**Williams %R:** Range −100 to 0. Thresholds are strategy parameters.

### 46.1 Algorithmic Trendline Detection

Swing points identified as local extremes where price is higher or lower than configured bars on each side. Ascending trendlines connect ascending swing lows; descending trendlines connect descending swing highs. Minimum touch count per trendline is a strategy parameter. Each trendline record includes: anchor points, slope, current intercept, touch count, validity status, and strength score.

### 46.2 Multi-Timeframe (MTF) Alignment Engine

**`fetch_multi_timeframe` tool:** Fetches both anchor (higher) and execution (lower) interval datasets. Produces an alignment map linking each execution-interval bar to the most recently completed anchor-interval bar — with zero look-ahead.

**MTF indicator computation:** Indicators computed for both intervals, stored under namespaced keys `{interval}.{indicator_name}`. Strategy plugins access anchor-interval indicator values at any execution-interval bar without look-ahead.

**MTF filter contract:** Strategies declare `mtf_filter()` in addition to `generate_signals()`. Returns `confirm | suppress | downgrade` based on anchor-interval context. MTF filter result is recorded in the signal and surfaced in Why Engine Layer 3.

---

## SECTION 47: SUPPORT, RESISTANCE & KEY LEVELS

All level records contain: level price, level type, origin computation, historical touch count, most recent touch timestamp, active status, and strength score.

**Pivot Points:** Classic, Fibonacci-weighted, Camarilla, Woodie, DeMark — formula type is a strategy parameter. Computed at configured session boundary; weekly and monthly pivots at configured week/month boundary.

**Fibonacci Retracements and Extensions:** Given swing high and low (auto-detected via swing detection), levels computed at configured Fibonacci ratios (all ratios are strategy parameters). Swing selection method is a strategy parameter.

**Algorithmic Swing High/Low Levels:** Significance threshold, minimum level separation, and maximum level age are strategy parameters. Clustered levels within the configured proximity band merge into zone levels with zone width.

**Volume Profile Nodes:** HVN levels from volume profile act as support/resistance. LVN levels act as areas of potential rapid price movement.

**Psychological Levels:** Round-number price increments determined by a configured increment schedule mapping instrument price ranges to relevant increments. Strike clustering from options data refines significance.

**Prior Session Reference Levels:** Prior day/week/month high, low, close, and VWAP stored as active horizontal levels for the current session.

**Level Interaction Scoring:** When a signal bar approaches a key level, a `level_interaction` score is computed: proximity (fraction of ATR), level strength, whether the bar's extreme touched the level, whether the close confirmed or rejected the level.

---

## SECTION 48: VOLUME PROFILE & MARKET PROFILE

### 48.1 Tool: `compute_volume_profile`

**Inputs:** `data_id` (OHLCV), `tick_data_id` (optional; enables true price-level volume), profile_type (from config: fixed_range, session, visible_range, composite), profile_window, price_bucket_size, provider

**Outputs:** `volume_profile_id`, profile_records (per-bucket), poc_price, vah_price, val_price, tpo_records, timestamp_range, source

**Profile record per price bucket:**
```
price_level | volume | buy_volume | sell_volume | delta | tpo_count
is_poc | is_vah | is_val | is_hvn | is_lvn
```

**Logic:** POC = highest volume level. Value Area = configured % of total volume centered on POC. HVN = volume above configured multiple of mean; LVN = volume below configured threshold. When tick data unavailable, bar volume distributed across range using configured method (uniform, triangular, or custom weighted).

### 48.2 Canvas Render Type: `volume_profile_chart`

Horizontal histogram attached to right or left of candlestick chart. POC and value area boundaries as horizontal lines across full chart width. HVN/LVN levels as distinct visual indicators. VWAP with configurable standard deviation bands (1σ, 2σ, 3σ). Delta coloring when tick data available.

---

## SECTION 49: CLASSICAL CHART PATTERN RECOGNITION

### 49.1 Detection Architecture

Classical patterns are arrangements of swing points. All parameters (minimum/maximum formation width, symmetry tolerance, breakout confirmation, measured move method, false breakout threshold) are strategy configuration values.

### 49.2 Pattern Families

**Head and Shoulders / Inverse:** Three swing extremes; middle is most extreme. Neckline connects reaction points between peaks. Confirmation: close through neckline by configured margin. Measured move: neckline ± head-to-neckline distance.

**Double Top / Bottom:** Two swing extremes within configured price tolerance; separated by reaction of minimum configured depth. Measured move: neckline ± peak-to-neckline distance.

**Triangles (Ascending, Descending, Symmetric):** Minimum configured touch count per trendline. Breakout must occur before configured apex proximity. Measured move: maximum triangle width projected from breakout.

**Flags and Pennants:** Prior impulse ≥ configured ATR multiple. Consolidation ≤ configured retracement depth and duration. Measured move: impulse length projected from breakout.

**Wedges (Rising and Falling):** Both trendlines same direction, converging. Rising = bearish; Falling = bullish. Breakout opposite to wedge slope direction.

**Rectangles and Channels:** Flat support and resistance (rectangle) or parallel sloping lines (channel). Measured move: channel height from breakout.

**Cup and Handle:** Rounded bottom (cup) of configured depth/width; shallow handle of configured max depth/duration; breakout above cup rim. Measured move: cup depth from breakout.

### 49.3 Pattern Record Schema

```
pattern_record:
  pattern_type | direction | status: "forming"|"confirmed"|"failed"|"target_reached"
  start_bar | confirmation_bar | invalidation_price | target_price | neckline
  formation_bars | symmetry_score | touch_counts | volume_confirmation
  measured_move_pct | historical_base_rate | strength_score
```

**Canvas integration:** Confirmed and forming patterns included in `candlestick_chart` canvas payload with trendline overlays, neckline/target/invalidation horizontal lines, breakout annotations, and measured-move projection zones.

---

## SECTION 50: OPTIONS FLOW & DERIVATIVES MICROSTRUCTURE

Options data is HARD when from official exchange/regulatory feeds; SOFT when from aggregated third-party services. The distinction is recorded in DataProvenance.

### 50.1 Tool: `fetch_options_data`

**Inputs:** ticker, expiry scope (from config), strike scope (from config), provider, data_type

**Outputs:** `options_data_id`, expiry_dates, strike_count, timestamp, source, unavailability_flags

All Greeks (Delta, Gamma, Theta, Vega, Rho) are provided by source when available; otherwise computed from underlying price, strike, time to expiry, and IV using the configured pricing model (Black-Scholes or configured alternative). OI (stock of contracts) is distinguished from volume (session flow). Both stored per strike and expiry.

### 50.2 Computed Options Indicators

**Gamma Exposure (GEX):** Net market-maker gamma weighted by OI and underlying price. Positive GEX → MM net long gamma → pinning, volatility dampening. Negative GEX → MM net short gamma → trend amplification. Computed aggregate and per-strike (gamma walls). All computation parameters are strategy configuration values.

**Put/Call Ratio (PCR):** Volume-based and OI-based PCR for configured expiry scope. Rolling PCR over configured lookback. Configured thresholds for significant readings are strategy parameters.

**Put/Call Skew:** IV difference between OTM puts and OTM calls at configured delta level. Positive skew = market pays more for downside protection. Skew series over configured lookback shows tail-risk pricing trend.

**IV Term Structure:** ATM IV per expiry date. Contango (normal) vs backwardation (near-term stress). Slope and kinks (at event-adjacent expiries) are computed.

**Max Pain:** Underlying price at expiration minimizing total ITM options dollar value. Gravitational level approaching expiration.

**Unusual Options Activity (UOA):** Volume-to-OI ratio per strike/expiry. Ratio above configured threshold on significant size = UOA flag. Direction implied by strike position relative to current price and expiry.

**IV Rank and IV Percentile:** Rank: current ATM IV position within its historical range (0–100). Percentile: fraction of historical days where IV was below current. Both computed for near-term expiry over configured lookback.

### 50.3 Canvas Render Type: `options_surface`

Surface type: `iv_surface | skew | gex_profile | term_structure`. Data includes IV matrix (2D by strike and expiry), GEX by strike, term structure, or skew series. Max pain level and highest-OI strike are annotated. Color scale is configurable.

---

## SECTION 51: STATISTICAL FEATURES

**Augmented Dickey-Fuller (ADF) Test:** Stationarity test on price series or computed spread. Output: test statistic, p-value, and stationarity classification at configured significance level. Lag structure (fixed, AIC-optimal, BIC-optimal) is a strategy parameter.

**Johansen Cointegration Test:** Tests multiple price series for shared long-run equilibrium. Output: trace statistic, eigenvalue statistic, cointegrating vector (defines hedge ratio), number of cointegrating relationships at configured significance level.

**Hurst Exponent:** H < 0.5 = mean-reverting; H ≈ 0.5 = random walk; H > 0.5 = trending. Estimation method (R/S analysis, DFA, Periodogram) is a strategy parameter. Rolling Hurst produces regime character time-series.

**ACF/PACF:** Autocorrelation and partial autocorrelation for configured number of lags. Significant lags flagged using configured significance threshold (2/√N is configurable default).

**Variance Ratio Test:** Tests random walk hypothesis. Ratio > 1 = momentum; < 1 = mean reversion. Configured test lags and significance level are strategy parameters.

**Spread Z-Score and Half-Life:** Cointegration residual z-score over configured rolling window is the primary pairs entry signal. Mean-reversion half-life estimated from AR(1): `half_life = -log(AR1_coefficient) / log(2)`.

**Approximate Entropy / Sample Entropy:** Higher entropy = more chaotic (high-vol regimes). Lower = more regular (trending/cycle-driven). Rolling entropy produces regime complexity time-series.

---

## SECTION 52: SEASONALITY & CALENDAR EFFECTS ENGINE

### 52.1 Tool: `compute_seasonality`

**Inputs:** `data_id` (requires minimum configured years of history), seasonality_type, instrument_type, lookback_years, min_sample_years

**Outputs:** `seasonality_id`, seasonal_patterns (list), confidence_intervals (bootstrap), data_quality_flags

All base rates are accompanied by bootstrap confidence intervals (configured number of samples). Patterns are reported as average returns and win rates conditioned on regime at period start when regime data is available.

### 52.2 Seasonality Types

- **Day-of-Week:** Average return, win rate, std dev per weekday. Statistical significance tested against equal-returns null hypothesis.
- **Month-of-Year:** Per calendar month. January effect, September weakness, pre-holiday patterns detected when data supports them.
- **Options Expiration Cycle:** Weekly and monthly expiration behavior. Max pain gravity, gamma squeeze/unwind dynamics. 0DTE, quarterly triple witching.
- **FOMC Cycle:** Based on FOMC meeting calendar. Expected return distributions for week before, meeting day, week after. Blackout period tracked.
- **Earnings Season Clustering:** Sector ETF behavior during peak earnings weeks.
- **Pre/Post-Holiday:** Average returns on the trading day before and after configured market holidays.

### 52.3 Seasonality Strategy Plugin Contract

**Entry conditions:** Active seasonal pattern with base rate above configured minimum, p-value below configured threshold, lower confidence interval bound above configured minimum (prevents entry on patterns spanning zero), regime alignment, no overriding event within configured proximity window.

**Regime fitness:** Moderate across most regimes. Low fitness in extreme volatility regimes (seasonal patterns overwhelmed by macro noise).

---

## SECTION 53: INTERMARKET & CROSS-ASSET ANALYSIS

### 53.1 Tool: `fetch_intermarket_data`

**Inputs:** data_type, tickers, period, interval, provider

**Configured data types:**

| Type | Description |
|------|-------------|
| `currency_indices` | DXY, EUR, JPY, GBP indices |
| `yield_curve` | 2Y, 5Y, 10Y, 30Y yields; 2s10s spread; 10s30s spread |
| `credit_spreads` | HY-OAS, IG spread, CDS indices |
| `commodity_prices` | Crude oil, gold, silver, copper, agricultural |
| `sector_etfs` | All configured sector ETFs |
| `volatility_indices` | VIX, VVIX, sector vol indices |
| `breadth_indicators` | A-D line, new highs/lows, % above MA |
| `global_indices` | Configured major international equity indices |

### 53.2 Computed Intermarket Indicators

**Cross-Asset Correlation Matrix:** Rolling pairwise correlations between primary instrument and each intermarket input, computed on returns series. Correlation instability (direction change within configured window) is flagged as correlation regime warning.

**Dollar Impact Score:** For instruments with historically significant dollar correlation, DXY trend direction and strength produce a dollar impact score (headwind/tailwind given historical dollar sensitivity).

**Yield Curve Regime:** 2s10s spread classified as steepening, flattening, inverted, or normalized. Slope direction and velocity (rate of change of spread) as separate series.

**Credit Spread Regime:** HY-OAS level relative to configured historical percentile classified as compressed (risk-on), elevated (risk-off), or spiking (stress). Credit spread velocity is an early warning indicator for equity regime shifts.

**Sector Relative Strength Matrix:** Per-sector ETF relative strength vs broad market over configured lookback. Rotation direction (which sectors improving in RS) as velocity series.

**Market Breadth:** A-D line cumulative value and slope, new 52-week highs/lows as % of universe, % of universe above configured MAs.

### 53.3 Canvas Render Type: `intermarket_dashboard`

Multi-panel layout (grid, side-by-side, or stacked) with each panel showing a different intermarket data type. Correlation matrix shown as heatmap. Primary instrument labeled throughout.

---

## SECTION 54: EXTENDED INDICATOR LIBRARY REGISTRY

The Indicator Library Registry is the authoritative catalog stored in the strategy configuration store. New indicator types are registered without modifying `compute_indicators` core logic.

### 54.1 Complete Indicator Family Catalog

**Trend Family:** `trend.sma | trend.ema | trend.dema | trend.tema | trend.wma | trend.vwma | trend.hull_ma | trend.adx_dmi | trend.parabolic_sar | trend.ichimoku | trend.supertrend | trend.trendlines | trend.ma_ribbon | trend.multi_timeframe`

**Momentum Family:** `momentum.rsi | momentum.macd | momentum.stochastic_full | momentum.stochastic_rsi | momentum.cci | momentum.cmo | momentum.williams_r | momentum.roc | momentum.tsi | momentum.dpo`

**Volatility Family:** `volatility.atr | volatility.bollinger_bands | volatility.keltner_channel | volatility.donchian_channel | volatility.historical_vol | volatility.normalized_atr | volatility.chaikin_vol | volatility.vix_proxy`

**Volume Family:** `volume.obv | volume.vwap | volume.vwap_bands | volume.volume_ma | volume.rvol | volume.cmf | volume.mfi | volume.ad_line | volume.ease_of_movement | volume.force_index | volume.volume_profile`

**Structure Family:** `structure.pivot_points | structure.fibonacci | structure.swing_levels | structure.psychological | structure.prior_session | structure.candlestick_patterns | structure.bar_character | structure.classical_patterns`

**Microstructure Family:** `microstructure.volume_delta | microstructure.obi | microstructure.spread_dynamics | microstructure.absorption | microstructure.rvol | microstructure.footprint | microstructure.iceberg`

**Statistical Family:** `statistical.hurst | statistical.adf | statistical.johansen | statistical.half_life | statistical.spread_zscore | statistical.acf_pacf | statistical.variance_ratio | statistical.approximate_entropy`

**Intermarket Family:** `intermarket.cross_correlation | intermarket.dollar_impact | intermarket.yield_curve | intermarket.credit_spread | intermarket.sector_rs | intermarket.breadth | intermarket.gex`

**Seasonal Family:** `seasonal.day_of_week | seasonal.month_of_year | seasonal.opex_cycle | seasonal.fomc_cycle | seasonal.pre_holiday`

**Options Family:** `options.gex | options.pcr | options.skew | options.term_structure | options.max_pain | options.iv_rank | options.uoa`

### 54.2 Indicator Type Registration Schema

```
indicator_type_id:     string    — namespaced; e.g., "momentum.adx", "structure.trendlines"
display_name:          string
family:                string
required_data_types:   list      — which data types must be present
parameter_schema:      object    — JSON Schema for all parameters
output_keys:           list      — named output series this indicator produces
computation_class:     string    — reference to the computation implementation
warm_up_bars:          string    — expression for required warm-up bars as function of parameters
intraday_only:         bool
requires_external:     bool
```

---

## SECTION 55: ALL STRATEGY PLUGIN CONTRACTS

### 55.1 Trend Following Plugin

**Thesis:** Markets exhibit directional persistence. Enter in the direction of a confirmed trend when momentum supports the move and regime fitness is high.

**Entry conditions:**
- ADX above the configured trend strength threshold (regime confirming trend)
- Price above the configured fast MA (bullish) or below (bearish)
- Multiple MA alignment: configured fraction of ribbon MAs aligned in the signal direction
- RSI above configured momentum floor (bullish) or below (bearish) — not at extreme; momentum is supporting, not reverting
- Volume expanding above the configured threshold relative to the average
- MTF filter: anchor-interval trend aligned with execution-interval signal direction

**Exit logic:**
- Parabolic SAR flip in the opposite direction
- Price closes below (long) or above (short) the configured slow MA
- ADX falls below the configured weak trend threshold (trend ending)
- Strategy's own configured maximum bars held

**Regime fitness curve:** Peak in strong trend regimes; moderate in mild trend; low in ranging; very low in high-volatility choppy regimes.

**Sizing declaration:** ATR-normalized; base risk per trade from config; reduced by regime multiplier.

**Proactive trigger:** Continuously monitors the universe for MA ribbon alignment + ADX expansion developing. When `conditions_met / conditions_total` exceeds the configured threshold, emits `OPPORTUNITY_BRIEF`.

---

### 55.2 Mean Reversion Plugin

**Thesis:** Price deviates from equilibrium and returns. Enter when deviation is statistically significant and regime permits mean reversion.

**Entry conditions:**
- Price at or beyond the configured Bollinger Band multiple (outside the band)
- RSI at or below the configured oversold threshold (bullish) or at/above configured overbought threshold (bearish)
- VWAP deviation filter (optional, from Learning Abstraction): price below VWAP by configured σ with volume increasing (bullish)
- ADF test on the rolling window passes stationarity at the configured significance level (optional)
- No SSR active (for short signals)
- Not within configured bars of a major earnings announcement

**Exit logic:**
- Price returns to the configured band midpoint (Bollinger Band middle)
- Price returns to VWAP when VWAP filter was active
- RSI reaches configured exit zone (neutral)
- Stop: configured ATR multiple beyond the entry bar's extreme

**Regime fitness curve:** Peak in ranging/low-volatility regimes; moderate in mild trend (counter-trend); very low in strong trend; near-zero in extreme volatility (statistical relationships break down).

**Failure pattern awareness:** When `REGIME_OPPOSITION` failure pattern for mean reversion is active, this plugin's Reflection Layer grade is capped at the configured failure ceiling.

---

### 55.3 Breakout Plugin

**Thesis:** When price breaks out of a consolidation range with expanding volume, the move has momentum and followthrough.

**Entry conditions:**
- Price closes beyond the configured consolidation range (Donchian channel breakout, key level breakout, or classical pattern breakout)
- Volume on the breakout bar is above the configured minimum multiple of the average
- ATR is expanding above the configured expansion threshold (volatility supporting the move)
- MTF alignment: anchor interval is not in a counter-trend position
- Not an ex-dividend gap (SSR check for short breakdowns)
- Not within the configured proximity of a known resistance cluster that would limit the move

**Exit logic:**
- Price closes back inside the breakout level (false breakout exit — configured tolerance for retest allowed)
- Configured ATR-based trailing stop activates after the configured minimum move
- Configured maximum bars held

**Regime fitness curve:** Peak in transition regimes (ranging → trend forming) and mild trend. Low in strong trend (price extended; breakouts have poor follow-through). Moderate in high-volatility (breakouts occur but fail at elevated rate).

---

### 55.4 Pairs Trading Plugin

**Thesis:** When two cointegrated instruments' spread deviates significantly from its historical mean, it will revert. Enter long the underperformer and short the outperformer.

**Entry conditions:**
- Johansen cointegration test passes at the configured significance level for the pair
- Spread z-score beyond the configured entry threshold (|z-score| > threshold)
- ADF test on the spread passes stationarity at the configured significance level
- Mean-reversion half-life within the configured minimum and maximum bounds (too short = noise; too long = too slow)
- Both legs pass exchange mechanics checks (SSR not active for the short leg)

**Signal output:** Multi-leg `TradePlan` (plan_type: "pair") with one long leg and one short leg. Hedge ratio from the Johansen cointegrating vector.

**Exit logic:**
- Spread z-score reverts to below the configured exit threshold (near zero)
- Maximum bars held (based on the configured multiple of the half-life estimate)
- Hedge ratio drift beyond configured tolerance triggers re-evaluation (not automatic exit)

**Regime fitness curve:** Stable across regimes — the mean-reversion is statistical, not regime-dependent. Reduced fitness during market-wide correlation spikes (all assets move together; pairs relationships break down temporarily). Evolution Engine monitors hedge effectiveness separately.

---

### 55.5 Volatility Expansion Plugin

**Thesis:** When implied volatility is compressed within a Bollinger Band squeeze (Bollinger Band inside the Keltner Channel), a directional expansion is imminent. Enter in the direction indicated by the first momentum bar after the squeeze fires.

**Entry conditions:**
- Bollinger Band squeeze confirmed: upper BB below upper KC AND lower BB above lower KC for the configured minimum bars
- Squeeze fires: BB expands outside the KC
- First directional momentum bar: CMO (or configured momentum indicator) is positive (bullish squeeze fire) or negative (bearish)
- VIX (or vol proxy) below the configured VIX threshold (squeeze setups work better in low-volatility regimes)
- No earnings within the configured proximity window (earnings create unpredictable directional outcomes)

**Exit logic:**
- CMO reverses beyond the configured exit threshold
- Configured ATR-based trailing stop
- Configured maximum bars held

---

### 55.6 Event-Driven Plugin

**Thesis:** Scheduled market events (earnings, Fed meetings, macro releases) create predictable volatility windows and directional biases when combined with pre-event positioning signals.

**Entry conditions:**
- Confirmed upcoming event within the configured entry window (Calendar Intelligence)
- Pre-event positioning signal: elevated IV rank + directional options flow (UOA) indicating smart money expectations
- Consensus estimate alignment: analyst consensus skews in the configured direction
- Regime is not extreme (extreme regimes override event-driven positioning)

**Exit logic:**
- Configured bars after the event (the event window has passed)
- IV crush on options-based signals
- Price gaps beyond the configured maximum expected move

---

### 55.7 Factor-Based Rotation Plugin

**Thesis:** Factor performance cycles through regimes. Rotate into factors with positive momentum in the current regime.

**Signal output:** Multi-leg basket `TradePlan` (plan_type: "basket") with long exposures to leading factors, short or neutral to lagging factors.

**Entry conditions:**
- Factor momentum: configured factor ETFs showing positive relative strength vs. broad market over configured lookback
- Regime alignment: current regime historically favorable to the selected factors
- Factor crowding below configured threshold (excessive crowding degrades factor returns)

**Exit logic:**
- Factor relative strength deteriorates below the configured threshold
- Regime shift to a configuration unfavorable to the current factor

---

### 55.8 Macro Rotation Plugin

**Thesis:** The business cycle drives predictable sector rotation. Enter sector ETFs aligned with the current cycle phase.

**Signal output:** Multi-leg basket `TradePlan` covering multiple sector ETF positions.

**Entry conditions:**
- Business cycle phase classification: early expansion, late expansion, contraction, or recovery — from yield curve regime + credit spread regime + breadth analysis
- Sector relative strength aligned with the expected leaders for the current cycle phase
- Yield curve not in active inversion (signals late-cycle contraction)

---

### 55.9 Order Flow Plugin

**Thesis:** Large, informed participants leave footprints in volume delta and absorption patterns. Enter in the direction of detected institutional activity.

**Entry conditions:**
- CVD divergence from price (absorption): price declining while CVD rising (buyers absorbing sells)
- OBI above the configured threshold in the signal direction
- Iceberg order detected at a key level (confirms institutional positioning)
- Spread z-score within normal range (elevated spread = avoid entry)

**Requires:** Tick data for CVD and footprint computation; depth data for OBI and iceberg detection.

---

### 55.10 Price Action Plugin

**Thesis:** Bar character and pattern context capture supply/demand imbalances directly from price behavior.

**Entry conditions:**
- Confirming bar character: CLV above the configured floor (bullish) or below (bearish)
- Confirming pattern detected: at least one single, two, or three-bar pattern aligned with the signal direction
- Pattern occurring at a key level (level interaction score above the configured threshold)
- Pattern not counter-trend beyond the configured maximum counter-trend tolerance

---

### 55.11 Volume Profile Plugin

**Thesis:** The market spends the most time at fair value (POC). Deviations to extremes revert; breakouts from the value area with volume follow through.

**Entry conditions (mean reversion mode):**
- Price at or beyond the VAH (bearish) or VAL (bullish) — value area extreme
- LVN above (for short entries) or below (for long entries) the current price — thin air below the LVN accelerates the move

**Entry conditions (breakout mode):**
- Price closes above VAH with volume > configured threshold (bullish breakout)
- Or closes below VAL (bearish breakdown)
- HVN was cleared on the breakout (no major resistance above)

---

### 55.12 MTF Confluence Plugin

**Thesis:** Signals with multi-timeframe alignment have higher probability and follow-through.

**Role:** This plugin operates as a post-aggregation filter, not a primary signal generator. It evaluates aggregated signals from all other plugins and applies an alignment score modifier.

**Operates after:** Signal aggregation step in the pipeline DAG (Section 8.1).

**Alignment evaluation:**
- For each active signal: evaluate anchor-interval trend, momentum, and regime against the signal direction
- Score: `confluence_score = Σ(aligned_conditions) / total_conditions`
- `confluence_score ≥ confirm_threshold` → `confirm`; signal proceeds unchanged
- `suppress_threshold ≤ confluence_score < confirm_threshold` → `downgrade`; signal strength reduced by configured multiplier
- `confluence_score < suppress_threshold` → `suppress`; signal discarded; `MTF_SUPPRESSION` event emitted

**Canvas render type: `mtf_alignment_view`:** Two synchronized charts (anchor and execution intervals) with alignment status panel showing each condition result.

---

## SECTION 56: HARD / SOFT SIGNAL ARCHITECTURE & DATA PROVENANCE

### 56.1 Signal Type Classification

Every data point, indicator output, and signal carries a type classification:

**HARD signals:** Sourced from official, regulated, exchange-level feeds with deterministic computation. Price, volume, options OI, depth data from exchange feeds. Backtestable with historical data. Reproducible.

**SOFT signals:** Sourced from aggregated services, models, or human opinion. Sentiment, analyst consensus, social media flow, expert signals, MCP service outputs. Cannot be backtested as raw signals — only their historical impact on price can be evaluated.

**Guardrail rule:** SOFT signals cannot be the sole basis for a Grade A or Grade B signal. At minimum one HARD signal must be present and aligned. SOFT signals can only reinforce or dampen HARD signals, not override them.

### 56.2 DataProvenance Schema

Every data item in the registry and every signal carries a DataProvenance chain:

```python
class DataProvenance:
    data_id: str
    signal_type: str           # "HARD" | "SOFT"
    source_adapter: str
    source_label: str
    fetched_at: datetime       # UTC
    coverage_start: datetime   # UTC
    coverage_end: datetime     # UTC
    quality_score: float       # 0-1
    unavailability_flags: list[str]
    transformation_chain: list[str]  # ordered steps from raw data to this artifact
    tool_version: str
```

DataProvenance accumulates through the pipeline — each tool that transforms data appends to the `transformation_chain`. The full provenance is included in the DecisionContract and in the Why Engine output.

---

## SECTION 57: EXPLAINABILITY LAYER

### 57.1 Decision Trace

Every pipeline execution produces a `DecisionTrace` — a step-by-step record of every component's input, output, and decision:

```python
class DecisionTrace:
    trace_id: str
    created_at: datetime       # UTC
    intent_type: str
    query_summary: str
    steps: list[TraceStep]     # ordered; one per pipeline component
    total_duration_ms: int
    final_decision: str
    confidence: Decimal
    data_provenance: list[DataProvenance]
    failure_patterns_queried: list[str]
    failure_patterns_applied: list[str]
    knowledge_context_id: str
    pil_context_incorporated: bool
    llm_unavailable: bool
```

Each `TraceStep` contains: step name, inputs (by data_id reference), outputs (by data_id reference), duration_ms, confidence impact, and any errors or warnings.

### 57.2 Feature Attribution (SHAP)

When ML models are active and SHAP computation is configured, feature attribution values are computed for each prediction. These are included in the Why Engine output and surfaced in the Thought Process Inspector under the `feature_attribution` key.

### 57.3 Thought Process Inspector (War Room)

The Thought Process Inspector is a collapsible panel in the War Room that renders the full `DecisionTrace` in a readable, step-by-step format. Each step shows:
- Component name and duration
- Key inputs and outputs (human-readable, not raw data_ids)
- Confidence impact (how this step changed confidence)
- A `[Disagree]` button (triggers step-level disagreement, Section 21.1)

The inspector supports deep-linking: clicking an event in the `proactive_timeline` canvas render type restores the trace from that event for retrospective analysis.

---

## SECTION 58: POSITION CONFIRMATION WORKFLOW

### 58.1 Confirmation Sequence

```
Trade plan generated → User views in War Room
    │
    ▼
User clicks "Confirm Entry"
    │
    ▼
① Behavioral Guardian check (Section 23)
   └─ Bias detected? → friction confirmation dialog → user must actively proceed
    │
    ▼
② Fetch current market data (≤ configured staleness tolerance)
   └─ Stale or unavailable? → "Market data unavailable. Confirm anyway?" gate
    │
    ▼
③ Re-evaluate guardrails (G1–G11) with current data
   └─ Any gate fails? → rejection with specific reason; no confirmation
    │
    ▼
④ T+1 settlement check (Section 5.5)
   └─ Insufficient settled cash? → rejection with settlement detail
    │
    ▼
⑤ SSR check (for short entries) (Section 5.4)
   └─ SSR active? → rejection with SSR_ACTIVE reason
    │
    ▼
⑥ Display final confirmation with:
   - Entry price estimate (current ask for buys, current bid for shorts)
   - Exact shares, notional (Decimal), stop level, take-profit level
   - Projected heat (after this position)
   - Estimated commission (from CommissionModel)
   - Total risk in dollars (Decimal)
   - Thesis health at entry (100% = all entry conditions still intact)
    │
    ▼
⑦ User confirms → position record written with:
   - config_snapshot_id (frozen at this moment)
   - entry_thesis (all entry conditions with their values at entry)
   - settlement_date (computed using NYSE calendar)
   - idempotency_key (from client)
    │
    ▼
⑧ AuditTrail record written
⑨ POSITION_OPENED WebSocket event emitted
⑩ Ticker Intelligence File thesis updated
```

### 58.2 Position Management

After confirmation, the position record is managed by:
- **PIL Risk Sentinel:** Monitors stop proximity, circuit breaker, heat, and correlation
- **Position Thesis Monitor:** Re-evaluates entry thesis health on each PIL cycle
- **Signal Disposition Tracking:** Tracks whether the confirmed signal is classified as acted_on

---

## SECTION 59: SIGNAL DISPOSITION TRACKING

Every signal is dispositioned — its outcome is tracked and classified:

```python
class SignalDisposition:
    signal_id: str
    disposition: str        # "acted_on" | "ignored" | "saved" | "dismissed" | "expired"
    confirmed_at: datetime | None
    ignored_reason: str | None
    outcome: str | None     # "win" | "loss" | "breakeven" | "expired" | "pending"
    realized_r: Decimal | None
```

Dispositions feed into:
- Reflection Layer calibration (what % of Grade A signals acted on were wins?)
- Learning Engine (pattern from ignored signals that would have won)
- Behavioral Guardian (pattern from acted_on vs ignored signals by the user)
- Evolution Engine performance tracking

---

## SECTION 60: STRATEGY PERFORMANCE ATTRIBUTION

### 60.1 Attribution Schema

```python
class StrategyPerformanceAttribution:
    strategy_id: str
    period: str
    
    # Gross metrics
    total_signals: int
    acted_on_signals: int
    win_rate: float
    gross_return: Decimal
    
    # Risk-adjusted
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: Decimal
    calmar_ratio: float
    
    # Factor attribution (where returns came from)
    market_beta_contribution: Decimal
    signal_alpha: Decimal           # returns above beta
    timing_contribution: Decimal    # entry/exit timing vs. holding throughout
    
    # By regime
    regime_breakdown: dict          # per-regime: {win_rate, sharpe, sample_count}
    
    # Calibration
    brier_score: float
    calibration_curve: list[dict]   # {predicted_confidence, actual_win_rate, sample_count}
    
    # Subgroup performance
    by_signal_grade: dict
    by_time_of_day: dict
    by_day_of_week: dict
```

### 60.2 Canvas Render Type: `performance_attribution`

Multi-panel attribution dashboard: equity curve, win rate by regime, calibration curve, factor attribution waterfall, and subgroup performance heatmap.

---

## SECTION 61: MULTI-PROCESS DEPLOYMENT

### 61.1 Architecture

In multi-process mode, multiple server instances share the same database and cache. The shared cache (Redis or equivalent) is used for:
- Portfolio state (StrategicMemory is read from database; updates go through database transactions)
- Circuit breaker states (shared across all instances)
- PIL state snapshot (one PIL process; others are reactive-only)
- Distributed locks (migration lock, PIL cycle lock)

**No in-memory caching of portfolio state in multi-process mode.** All portfolio reads go to the database with `REPEATABLE_READ` isolation. All portfolio mutations use `SERIALIZABLE` isolation with the lock-ordering convention (alphabetical ticker).

### 61.2 PIL Process Assignment

Exactly one process per deployment runs the PIL scheduler. The PIL process acquires a distributed lock on startup. If the lock holder fails, the next healthy process detects the missing heartbeat and acquires the lock. PIL_LEADER_CHANGE event is emitted.

### 61.3 Health Check in Multi-Process

Each process exposes `/health/ready`. The load balancer routes only to ready instances. A process failing its readiness check is removed from rotation within the configured health check interval.

---

## SECTION 62: REPLAY MODE

Bar-by-bar historical replay through the live pipeline with look-ahead prohibition enforced identically to live mode.

### 62.1 Replay Session Schema

```python
class ReplaySession:
    session_id: str
    ticker: str
    interval: str
    strategy_ids: list[str]
    data_start: datetime     # UTC
    data_end: datetime       # UTC
    current_bar: int
    status: str              # "active" | "paused" | "completed"
    look_ahead_prohibited: bool  # always true
    config_snapshot_id: str     # frozen at session start
```

### 62.2 Replay Endpoints

```
POST /replay/sessions                   Create session with dataset, strategy, starting_bar
POST /replay/sessions/{id}/step         Advance one bar; returns pipeline outputs
POST /replay/sessions/{id}/pause        Pause
POST /replay/sessions/{id}/resume       Resume
DELETE /replay/sessions/{id}            End session
```

### 62.3 Look-Ahead Prohibition

The replay engine enforces that no data from bars beyond the current `current_bar` is accessible at any step. Indicator computation uses only bars 0 through `current_bar`. This is verified by the parity test (Section 8.2) which runs both modes against identical datasets and asserts identical outputs.

---

## SECTION 63: NOTIFICATION SYSTEM

### 63.1 Notification Channels

| Channel | Delivery | Use Case |
|---------|----------|----------|
| War Room WebSocket | Real-time | All events; primary channel |
| Push (mobile) | Near-real-time | High-priority alerts when app not in focus |
| Email (digest) | Scheduled | Daily/weekly summary |
| Slack/Teams | Configurable | Team integrations |
| Webhook | Per-event | Custom integrations |

### 63.2 Notification Intelligence

**Aggregation:** "3 of your 5 strategies generated sell signals for AAPL" instead of 3 separate notifications.

**Quiet hours:** User-configurable "do not disturb" with override for critical alerts (circuit breaker, THESIS_INVALIDATED, MEMORY_CEILING_EXCEEDED).

**Fatigue prevention:** If a notification type fires > configured times per day, suggest disabling it. Track notification-to-action ratio.

**Delivery confirmation:** Track whether notifications were delivered, opened, and acted upon.

### 63.3 Webhook Security

Every webhook request includes `X-APEX-Signature: HMAC-SHA256(webhook_secret, request_body)`. Webhook secret is configured per-user in the secrets manager. The receiving endpoint must verify the signature before processing.

---

## SECTION 64: CONFIGURATION DRIFT DETECTION

### 64.1 Drift Computation

A strategy's "reference configuration" is the parameter snapshot from its baseline backtest. After live deployment, any configuration changes create drift from the reference:

```python
class ConfigDriftReport:
    strategy_id: str
    reference_config_id: str
    current_config_id: str
    drifted_parameters: list[dict]  # {param_name, reference_value, current_value, drift_pct}
    material_drift: bool            # any drift exceeds configured materiality threshold
    drift_detected_at: datetime
    impact_estimate: str            # "low" | "medium" | "high"
```

### 64.2 Drift Alerts

When material drift is detected:
- Emit `CONFIG_DRIFT_ALERT` WebSocket event
- Include in the next PIL intelligence brief
- Block Evolution Engine from treating current performance as comparable to the reference (drift means apples-to-oranges comparison)

### 64.3 Drift Reset

`POST /strategies/{id}/drift/reset` establishes the current configuration as the new reference. A new baseline backtest is triggered automatically.

---

## SECTION 65: STRATEGY INTERDEPENDENCY & HEDGE PAIR MANAGEMENT

### 65.1 Hedge Pair Schema

```python
class HedgePair:
    pair_id: str
    primary_strategy_id: str
    hedge_strategy_id: str
    hedge_ratio: Decimal          # from config; not hardcoded
    heat_netting: bool            # whether hedge reduces reported heat
    correlation_monitoring: bool
    hedge_effectiveness_threshold: float  # minimum acceptable effectiveness
```

### 65.2 Hedge Pair Behavior

When heat_netting is true: `net_heat = max(0, primary_heat - hedge_heat * hedge_ratio)`. Portfolio gate (G4) uses net heat for pairs.

Evolution Engine evaluates hedge pairs at the pair level, not individually. `hedge_effectiveness` (rolling correlation between pair P&L streams) is tracked as a separate metric. When effectiveness drops below threshold, `HEDGE_EFFECTIVENESS_DEGRADING` is emitted.

### 65.3 Multi-Strategy Correlation Monitoring

The Strategy Readiness Monitor tracks signal correlation between strategies (not just position correlation). Two strategies that always generate signals in the same direction on the same tickers at the same time provide zero diversification benefit. High signal correlation between active strategies triggers a redundancy advisory.

---

## SECTION 66: TESTING ARCHITECTURE

### 66.1 Test Architecture Requirements

```
Unit Tests:
  - Every indicator computation verified against known mathematical output
  - Numerical type validation: every Decimal-required field tested with float input (must raise G11)
  - Every strategy plugin's determinism test: same inputs twice → byte-identical output
  - Every guardrail gate: tests for rejection AND pass conditions
  - Failure Memory: test that similar failures are retrieved at correct similarity thresholds
  - Learning Engine: test that strategy weights update directionally correctly

Integration Tests:
  - Full reactive pipeline end-to-end with fixture data
  - Database isolation: each test in a transaction rolled back after
  - PIL cycle with mocked adapters
  - Backtest-to-live parity (Section 8.2 — runs on every CI build)
  - Idempotency: submit same request twice; assert same result; assert no duplicate position

Security Tests:
  - Prompt injection attempts through user query field
  - Hallucianted ticker: LLM returns unknown ticker; assert HallucinatedTickerError
  - CSRF: state-changing request without CSRF token; assert rejection
  - HMAC webhook: invalid signature; assert rejection
  - Float monetary value at tool boundary: assert NumericalTypeViolation (G11)

Performance Tests:
  - Single-user profile: 10 concurrent reactive + 1 PIL cycle; p95 < 3000ms
  - Team profile: 50 concurrent reactive + 1 PIL + 20 WebSocket; p95 < 5000ms
  - Stress profile: 200 concurrent + 500-ticker universe scan

Chaos Tests:
  - Kill primary data vendor mid-pipeline; assert graceful failover
  - Kill LLM provider mid-pipeline; assert deterministic-only degradation
  - Inject clock drift above max_drift_ms; assert startup rejection
  - Inject a corporate action mid-session; assert cascade invalidation
  - Dead letter queue fill; assert DLQ_GROWING alert
```

### 66.2 Mutation Testing

The test suite must be validated by mutation testing. Mutations are injected into core logic (indicator computation, guardrail gates, Decimal arithmetic); the suite must detect all mutations. Any mutation not detected signals a coverage gap.

### 66.3 Property-Based Testing

Invariants that must hold under random inputs:
- Position size never exceeds configured max notional (for all valid input combinations)
- Portfolio heat never exceeds 100% (for all valid portfolio states)
- All monetary outputs are Decimal, never float (for all tool calls)
- `generate_signals()` is deterministic (for all valid input pairs)

---

## SECTION 67: MONITORING, ALERTING & RUNBOOKS

### 67.1 Alert Catalog

| Alert | Severity | Condition | Auto-Recovery |
|-------|----------|-----------|--------------|
| `CLOCK_DRIFT_CRITICAL` | Critical | Drift > max_drift_ms | None — human action required |
| `MEMORY_CEILING_EXCEEDED` | Critical | RSS > max_rss_mb | Graceful restart initiated |
| `DLQ_GROWING` | High | DLQ above configured threshold | None — investigate root cause |
| `HEAT_CRITICAL` | High | Portfolio heat > configured critical level | Circuit breaker evaluation |
| `CIRCUIT_BREAKER_TRIGGERED` | High | Circuit breaker activates | All signals suspended |
| `DATA_VENDOR_DOWN` | High | Primary vendor circuit open | Failover to secondary |
| `LLM_UNAVAILABLE` | High | All LLM providers down | Degraded mode |
| `THESIS_INVALIDATED` | High | Open position thesis health critical | Advisory to user |
| `BUDGET_WARNING` | Medium | Daily spend > 80% of budget | PIL/Evolution paused at 95% |
| `AGENT_DRIFT_DETECTED` | Medium | Behavioral drift above threshold | Investigation queued |
| `ABSTRACTION_DEPRECATED` | Medium | Learning abstraction decaying | User notified |
| `CONFIG_DRIFT_ALERT` | Medium | Material parameter drift | Advisory |
| `DATA_RESTATEMENT_ALERT` | Medium | Vendor corrected historical data | Cascade invalidation |
| `MEMORY_LEAK_SUSPECTED` | Medium | Memory growth rate above threshold | Alert only |
| `PIL_COLD_START` | Low | PIL snapshot too old | PIL rebuilds on first cycle |

### 67.2 Runbooks

Each alert has a documented runbook:

**CIRCUIT_BREAKER_TRIGGERED:**
1. Check the triggering condition (heat level? correlation spike? drawdown?)
2. Review the current portfolio: heat, correlation matrix, open positions
3. Assess whether the trigger reflects a real risk increase or a data anomaly
4. If data anomaly: clear the circuit breaker via admin API; note in AuditTrail
5. If real risk: review positions; consider position reduction before clearing

**DLQ_GROWING:**
1. Inspect the DLQ for the most common failure reason
2. If transient failure (vendor outage during the failure period): replay after vendor restored
3. If permanent failure (bug): fix the bug; replay affected events; verify no duplicates

---

## SECTION 68: LOCALIZATION & MULTI-TIMEZONE SUPPORT

All internal timestamps are UTC. Timezone conversion happens only at the display layer using the user's configured IANA timezone. All API responses return UTC ISO-8601. The client converts to local time for display.

**Market hours display:** All session boundaries are displayed in the user's configured timezone. The PIL schedule is stored in UTC and resolved to the user's timezone for display only.

**Number formatting:** Price and P&L formatting uses the user's configured locale for thousand separators and decimal marks. The underlying value is always Decimal with full precision; formatting is display-only.

---

## SECTION 69: STRATEGY PARAMETER VERSIONING & FORK MANAGEMENT

### 69.1 Parameter Versioning

Every active configuration snapshot is stored with a version identifier. When a parameter changes:
1. The new parameter set is stored as a new version
2. The prior version is retained
3. Backtest results are tagged with the parameter version they used
4. The Evolution Engine does not compare performance across parameter versions without a re-baseline

### 69.2 Fork Management

Users can fork a strategy into a named variant with adjusted parameters:
- Fork inherits all backtest history from the source but starts fresh performance tracking
- Fork and source can run in parallel (if configured heat allows)
- Fork has its own Evolution Engine monitoring
- Fork can be merged back to source (requires admin approval; runs comparison analysis first)

---

## SECTION 70: API VERSIONING CONTRACT

### 70.1 Versioning Scheme

All endpoints are prefixed with `/api/v{N}/`. Current major version: v1. Breaking changes bump the major version. Non-breaking additions (new response fields, new optional parameters) are backward-compatible within a major version.

### 70.2 Deprecation Policy

- Deprecated endpoints continue to work for the configured deprecation window (default: 12 months)
- Deprecated endpoints return `Deprecation` and `Sunset` response headers
- Clients are expected to migrate before the sunset date

### 70.3 Version Discovery

`GET /api/versions` returns all active and deprecated versions with their sunset dates and change summaries.

---

## SECTION 71: PROMPT TEMPLATE A/B TESTING

### 71.1 Shadow Prompt Deployment

New prompt templates are deployed in shadow mode — both the current template and the new template run on the same input, and their outputs are evaluated:
- Structured output compliance (does the new template produce valid schema-conforming output?)
- Reasoning quality (LLM-as-judge evaluation using a configured judge prompt)
- Latency (does the new template complete within the configured budget?)

### 71.2 Evaluation Rubric

```python
class PromptEvaluationResult:
    schema_compliance_rate: float   # % of outputs conforming to expected schema
    reasoning_quality_score: float  # 0-1; judge evaluation
    mean_latency_ms: float
    token_cost: Decimal
    promotion_eligible: bool        # true when all criteria exceed configured thresholds
```

Promotion requires human approval when the template change affects the Reflection Layer or Why Engine (these are safety-relevant). Canvas and narrative templates can be auto-promoted when evaluation criteria are met.

---

## SECTION 72: DATA EXPORT & FORMAL REPORTING

### 72.1 Report Types

| Report Type | Contents | Formats |
|------------|----------|---------|
| `daily_brief` | Market regime, active signals, portfolio state, risk summary | PDF, JSON |
| `weekly_digest` | Performance attribution, strategy health, learning progress | PDF, Excel, JSON |
| `monthly_report` | Full analytics, calibration curves, drawdown analysis, factor exposure | PDF |
| `trade_history` | All signals with outcomes, dispositions, grades | CSV, Excel |
| `audit_export` | AuditTrail for a date range | JSON (tamper-evident with hash chain) |
| `strategy_comparison` | Side-by-side strategy performance | PDF |
| `learning_summary` | All active learning abstractions and their impact | PDF, JSON |

### 72.2 Report API

```
POST /reports                         Create report job
  Body: {type, period, format, filters}
GET  /reports/{id}                    Check status and retrieve
GET  /reports                         List reports
```

Reports are generated asynchronously. The `REPORT_READY` WebSocket event is emitted when the report is ready for download. Reports are stored for the configured retention period.

---

## SECTION 73: FEATURE FLAG MANAGEMENT

### 73.1 Feature Flag Types

- **Strategy category flags:** Enable/disable strategy families (short selling, options, intraday, pairs, crypto)
- **Intelligence feature flags:** Enable/disable PIL subsystems, Evolution Engine, Curiosity Engine, Learning Engine, expert integration, behavioral guardian
- **Experimental flags:** A/B test new pipeline components; enable for a configured percentage of requests

### 73.2 Flag Evaluation

Flags are evaluated at request time, not at startup. Flag state can change without server restart. Changes take effect within the configured cache TTL.

**Flag priority:** User-level flags override global flags. Strategy-level flags override user flags for that strategy only.

---

## APPENDIX F: PROJECT DIRECTORY STRUCTURE

```
apex/
├── agent/
│   ├── core/
│   │   ├── config.py
│   │   ├── numerical_policy.py         ← Decimal enforcement
│   │   ├── clock_authority.py          ← NTP sync, timestamp authority
│   │   ├── error_taxonomy.py           ← Unified error classification
│   │   ├── idempotency.py              ← Idempotency key management + outbox
│   │   ├── registry.py
│   │   ├── data_registry.py            ← Memory-bounded, concurrency-safe
│   │   └── event_bus.py
│   ├── orchestration/
│   │   ├── executive_controller.py     ← DAG execution, SLA enforcement
│   │   ├── intent_router.py            ← 3-tier routing
│   │   ├── task_planner.py
│   │   ├── workflow_catalog.py
│   │   └── context_manager.py
│   ├── intelligence/
│   │   ├── proactive/
│   │   │   ├── pil_scheduler.py
│   │   │   ├── regime_intelligence.py
│   │   │   ├── strategy_readiness.py
│   │   │   ├── opportunity_scout.py
│   │   │   ├── calendar_intelligence.py
│   │   │   ├── narrative_monitor.py
│   │   │   └── risk_sentinel.py
│   │   ├── reactive/
│   │   │   ├── why_engine.py
│   │   │   ├── reflection_layer.py     ← Failure-aware
│   │   │   ├── narrative_agent.py      ← Consistency-enforced
│   │   │   ├── stepwise_disagreement.py
│   │   │   └── second_order_analysis.py
│   │   └── bridge/
│   │       └── pil_ril_bridge.py
│   ├── learning/
│   │   ├── learning_engine.py
│   │   ├── failure_memory.py
│   │   ├── failure_classifier.py
│   │   ├── failure_lesson_extractor.py
│   │   ├── failure_pattern_aggregator.py
│   │   ├── learning_abstraction_store.py
│   │   ├── abstraction_decay_monitor.py
│   │   ├── knowledge_application_engine.py
│   │   ├── hitl_validation_queue.py
│   │   ├── expert_observer.py          ← Autonomous analyst observation
│   │   ├── expert_integration.py       ← Expert signal channel
│   │   ├── human_disagreement.py       ← Step-level disagreement capture
│   │   ├── mcp_learning.py             ← MCP service integration
│   │   ├── content_learning.py         ← Video/paper/article learning
│   │   └── knowledge_forgetting.py
│   ├── continuity/
│   │   ├── ticker_intelligence_file.py
│   │   ├── thesis_monitor.py           ← Position thesis lifecycle
│   │   └── narrative_consistency.py
│   ├── behavioral/
│   │   ├── behavioral_guardian.py
│   │   ├── bias_detectors.py
│   │   └── behavioral_profile.py
│   ├── evolution/
│   │   ├── evolution_engine.py
│   │   ├── performance_monitor.py
│   │   ├── root_cause_analyzer.py
│   │   └── shadow_deployment.py
│   ├── curiosity/
│   │   └── curiosity_engine.py
│   ├── strategies/                      ← Strategy plugin directory
│   │   ├── trend_following.py
│   │   ├── mean_reversion.py
│   │   ├── breakout.py
│   │   ├── pairs_trading.py
│   │   ├── volatility_expansion.py
│   │   ├── event_driven.py
│   │   ├── factor_rotation.py
│   │   ├── macro_rotation.py
│   │   ├── order_flow.py
│   │   ├── price_action.py
│   │   ├── volume_profile_strategy.py
│   │   └── mtf_confluence.py
│   ├── tools/
│   │   ├── fetch_market_data.py        ← Corporate action check integrated
│   │   ├── compute_indicators.py
│   │   ├── generate_signals.py
│   │   ├── aggregate_signals.py
│   │   ├── mtf_confluence_filter.py
│   │   ├── compute_position_size.py
│   │   ├── format_trade_plan.py
│   │   ├── run_backtest.py
│   │   ├── fetch_market_depth.py
│   │   ├── fetch_tick_data.py
│   │   ├── compute_order_flow_indicators.py
│   │   ├── fetch_options_data.py
│   │   ├── compute_options_indicators.py
│   │   ├── compute_volume_profile.py
│   │   ├── compute_key_levels.py
│   │   ├── compute_seasonality.py
│   │   ├── fetch_intermarket_data.py
│   │   ├── compute_intermarket_indicators.py
│   │   ├── fetch_multi_timeframe.py
│   │   ├── fetch_corporate_actions.py  ← NEW
│   │   ├── check_ssr_status.py         ← NEW
│   │   ├── check_halt_status.py        ← NEW
│   │   └── compute_settlement_date.py  ← NEW
│   ├── financial_domain/               ← NEW MODULE
│   │   ├── corporate_actions.py
│   │   ├── exchange_mechanics.py       ← LULD, halts, SSR
│   │   ├── settlement.py               ← T+1
│   │   ├── commission_model.py         ← Full fee model (Decimal throughout)
│   │   ├── business_day_calendar.py    ← NYSE trading days
│   │   └── factor_exposure.py
│   ├── guardrails/
│   │   ├── g11_numerical_type.py       ← G11 (NEW; runs before G1)
│   │   ├── g1_schema.py
│   │   ├── g2_security.py
│   │   ├── g3_position_size.py
│   │   ├── g4_portfolio_heat.py
│   │   ├── g5_concentration.py
│   │   ├── g6_correlation.py
│   │   ├── g7_confidence.py            ← Adaptive thresholds
│   │   ├── g8_regime_fitness.py
│   │   ├── g9_market_hours.py          ← LULD/halt/SSR integrated
│   │   └── g10_ethical.py
│   ├── explainability/
│   │   ├── decision_trace.py
│   │   ├── feature_attribution.py
│   │   └── thought_process_inspector.py
│   ├── adapters/
│   │   ├── base_adapter.py             ← Circuit breaker + retry base
│   │   ├── llm_adapter.py              ← Failover chain integrated
│   │   ├── market_data_adapters/
│   │   ├── options_adapters/
│   │   ├── sentiment_adapters/
│   │   ├── news_adapters/
│   │   └── mcp_adapters/
│   ├── observability/                  ← NEW MODULE
│   │   ├── structured_logging.py       ← JSON logs + redaction
│   │   ├── metrics.py                  ← Prometheus-compatible
│   │   ├── tracing.py                  ← OpenTelemetry
│   │   ├── log_redactor.py
│   │   ├── memory_guard.py
│   │   ├── agent_drift_detector.py
│   │   ├── cost_tracker.py
│   │   └── analytical_debt_dashboard.py
│   ├── security/
│   │   ├── auth.py
│   │   ├── csrf.py
│   │   ├── prompt_injection.py
│   │   └── data_sovereignty.py
│   ├── memory/
│   │   └── strategic_memory.py
│   ├── canvas/
│   │   ├── canvas_engine.py
│   │   ├── render_state_manager.py
│   │   └── handlers/
│   ├── db/
│   │   ├── schema.sql
│   │   ├── migrations/
│   │   ├── migration_runner.py
│   │   └── connection_pool.py
│   ├── api/
│   │   ├── routes/
│   │   ├── websocket.py
│   │   └── middleware/
│   ├── model_registry/
│   │   └── model_registry.py
│   └── main.py
├── ui/
├── strategies/                          ← Registered plugin directory
├── config/
│   ├── settings.yaml
│   ├── guardrails.yaml
│   ├── adapters.yaml
│   ├── workflows.yaml
│   ├── intent_patterns.yaml
│   ├── notifications.yaml
│   └── numerical_policy.yaml          ← NEW
├── tests/
│   ├── unit/
│   │   ├── numerical_integrity/       ← Decimal enforcement tests (NEW)
│   │   ├── failure_memory/
│   │   ├── learning_engine/
│   │   ├── guardrails/
│   │   ├── strategies/
│   │   └── tools/
│   ├── integration/
│   │   ├── parity/                    ← Backtest-to-live parity (runs on every CI build)
│   │   ├── pipeline/
│   │   └── api/
│   ├── e2e/
│   ├── security/
│   ├── performance/
│   └── canonical_data/                ← Reference datasets for parity testing
├── docker-compose.yml
├── Dockerfile
├── requirements.lock                  ← Locked with hashes; verified on install
├── requirements.txt
├── pyproject.toml
└── .env.example
```

---

## APPENDIX G: MASTER CONFIGURATION REFERENCE (COMPLETE)

```yaml
# ─────────────────────────────────────────────────
# APEX v3 — MASTER CONFIGURATION SCHEMA
# All values are examples/documentation; actual values
# come from user configuration, env vars, or secrets.
# ─────────────────────────────────────────────────

# ── NUMERICAL POLICY ──────────────────────────────
numerical_policy:
  monetary_type: Decimal
  monetary_precision: 28
  price_display_precision: 2
  percentage_precision: 6
  rounding_mode: ROUND_HALF_UP

# ── TIME AUTHORITY ────────────────────────────────
time_authority:
  source: ntp
  servers: ["time.google.com", "time.aws.com"]
  max_drift_ms: 50
  sync_interval_seconds: 60
  alert_on_drift: true
  internal_precision: microsecond
  storage_timezone: UTC

# ── DATABASE ──────────────────────────────────────
database:
  pool_min_connections: 2
  pool_max_connections: 20
  connection_max_age_seconds: 3600
  connection_idle_timeout_seconds: 300
  statement_timeout_ms: 5000
  isolation:
    default_reads: read_committed
    portfolio_calculations: repeatable_read
    position_mutations: serializable
    order_operations: serializable
  backup:
    schedule: "0 2 * * *"
    retention_days: 30
    verify_restore: true

# ── DATA REGISTRY ─────────────────────────────────
data_registry:
  max_memory_mb: 2048
  eviction_policy: lru_ttl
  memory_warning_pct: 0.80
  memory_critical_pct: 0.95

# ── MEMORY MANAGEMENT ─────────────────────────────
memory:
  max_rss_mb: 8192
  leak_alert_threshold_mb_per_hour: 50
  check_interval_seconds: 300
  emergency_restart_on_ceiling: true

# ── LLM ───────────────────────────────────────────
llm:
  providers:
    - name: primary
      model: claude-sonnet-4-6
      priority: 1
    - name: fallback
      model: claude-haiku-4-5
      priority: 2
  circuit_breaker:
    failure_threshold: 3
    cooldown_seconds: 60

# ── RISK ──────────────────────────────────────────
risk:
  max_portfolio_heat: "0.20"          # Decimal string
  max_risk_per_trade_pct: "0.02"      # Decimal string
  max_notional_per_trade: "50000.00"  # Decimal string
  max_ticker_concentration_pct: "0.15"
  max_sector_concentration_pct: "0.35"
  max_correlation_threshold: 0.75
  circuit_breaker_drawdown_pct: "0.10"

# ── INTELLIGENCE ──────────────────────────────────
intelligence:
  pil:
    schedule:
      mode: session_aware
      sessions:
        - name: us_core_session
          hours: "09:30-16:00 America/New_York"
          days: weekdays
          cycle_interval_seconds: 900
          subsystems:
            all: true
          max_cycle_duration_seconds: 600
    risk_sentinel_always_on: true
    risk_sentinel_off_hours_interval_seconds: 300
    max_snapshot_age_seconds: 3600

# ── GUARDRAILS ────────────────────────────────────
guardrails:
  g7_confidence_threshold: "0.45"    # Decimal string; adaptive base
  g8_regime_fitness_threshold: 0.35
  adaptive:
    enabled: true
    drift_modifier: -0.05
    vol_modifier: -0.03
    health_modifier: -0.04

# ── STEPWISE DISAGREEMENT ─────────────────────────
stepwise_disagreement:
  enabled: true
  early_termination:
    enabled: true
    min_confidence_to_continue: 0.25
    min_steps_before_termination: 3
    termination_action: downgrade_to_research
  reflection:
    trajectory_ceiling_grade: C
    monotonic_decline_threshold: 3

# ── LEARNING ──────────────────────────────────────
learning:
  enabled: true
  speed_mode: balanced
  failure_memory:
    enabled: true
    lookback_days: 90
    min_similarity_score: 0.75
    grade_ceiling_failure_rate: 0.60
  human_disagreement:
    enabled: true
    outcome_window_days: 30
    min_analyst_weight: 0.40
  mcp:
    enabled: false              # requires configured MCP server connections
    active_learning: false
    active_learning_budget_usd: "10.00"
  content_learning:
    enabled: false              # requires configured content sources
  hitl:
    auto_approval:
      enabled: false            # default off; require human review
      min_confidence: 0.90
      min_backtest_sample: 200
  knowledge_forgetting:
    enabled: true
    decay_check_interval: weekly
    deprecation_threshold: 0.10

# ── BEHAVIORAL GUARDIAN ───────────────────────────
behavioral_guardian:
  enabled: true
  revenge_trading:
    cooldown_minutes: 30
    size_threshold_pct: 0.0
  fixation:
    max_same_ticker_per_session: 5
  fomo:
    large_move_threshold_pct: 3.0
    rush_confirmation_ms: 5000

# ── EPISTEMIC HUMILITY ────────────────────────────
epistemic_humility:
  enabled: true
  abstain_threshold: 0.25
  limited_threshold: 0.50

# ── CROSS-SESSION CONTINUITY ──────────────────────
continuity:
  enabled: true
  thesis_exit_threshold: 0.30
  thesis_warning_threshold: 0.50
  max_ticker_file_age_days: 90

# ── FINANCIAL DOMAIN ──────────────────────────────
financial_domain:
  corporate_actions:
    enabled: true
    check_on_each_fetch: true
  exchange_mechanics:
    luld_monitoring: true
    halt_detection: true
    ssr_monitoring: true
    reopening_auction_delay_bars: 2
  settlement:
    enabled: true
    cycle: T+1
    calendar: NYSE
  risk_free_rate:
    source: FRED
    series: DTB3
    update_frequency: daily
    fallback_value: "0.05"

# ── WEBSOCKET ─────────────────────────────────────
websocket:
  inbound_rate_limit_per_second: 10
  outbound_buffer_max_events: 500
  buffer_warning_threshold: 400
  heartbeat_interval_seconds: 30
  heartbeat_timeout_seconds: 90

# ── OBSERVABILITY ─────────────────────────────────
observability:
  log_format: json
  log_level: INFO
  redact_monetary_values_in_logs: true
  metrics_port: 9090
  tracing_endpoint: ""        # OTLP endpoint; empty = tracing disabled
  trace_sampling_rate: 0.10
  slow_request_threshold_ms: 3000
  cost_tracking:
    enabled: true
    daily_llm_budget_usd: "100.00"
    daily_api_call_budget: 10000
    alert_threshold_pct: 0.80
    hard_stop_threshold_pct: 0.95
    reactive_reserve_pct: 0.20

# ── SHUTDOWN ──────────────────────────────────────
shutdown:
  notification_period_seconds: 5
  reactive_drain_timeout_seconds: 30
  pil_abort_timeout_seconds: 15
  evolution_abort_timeout_seconds: 10
  state_flush_timeout_seconds: 20

# ── SECURITY ──────────────────────────────────────
security:
  jwt_expiry_minutes: 60
  websocket_token_refresh: true
  csrf_protection: samesite_strict
  data_sovereignty:
    llm_data_policy: no_portfolio_data_in_prompts
    encryption_at_rest: true
    encryption_algorithm: AES-256-GCM
    key_rotation_days: 90
  supply_chain:
    lockfile_verification: true
    vulnerability_scanning: true

# ── AUDIT ─────────────────────────────────────────
audit:
  active_retention_days: 90
  archive_retention_years: 6
  tamper_proofing: true
  external_backup: true

# ── AUTONOMY ──────────────────────────────────────
autonomy:
  pil_hypothesis_generation: fully_autonomous
  evolution_shadow_deployment: fully_autonomous
  curiosity_research: supervised_autonomous
  learning_abstraction_creation: supervised_autonomous
  strategy_parameter_tuning: requires_approval
  model_promotion: requires_approval
  constitutional_axiom_change: prohibited
  position_confirmation: always_human
  order_execution: prohibited_by_architecture
```

---

## APPENDIX H: ACCEPTANCE CRITERIA TEMPLATE

Every component has acceptance criteria before implementation is considered complete:

```yaml
component: failure_memory_system
acceptance_criteria:
  - "Every failed signal (realized_r < 0) produces a FailureRecord within configured window"
  - "Root cause classifier assigns a primary_cause from the defined taxonomy for every record"
  - "Reflection Layer queries Failure Memory before evaluating every live signal"
  - "When 3+ similar failures exist, reflection prompt includes failure context"
  - "Grade ceiling applied when configured failure rate threshold exceeded"
  - "FailureLesson extraction runs for all records with sample_size >= minimum"
  - "Failure patterns with p-value < 0.05 are flagged as statistically valid"
  - "AuditTrail records every Failure Memory action"
  - "Performance: Failure Memory query completes within 50ms for any ticker"
  - "NumericalTypeViolation raised if any monetary field in failure record is float"
test_suite: "tests/unit/failure_memory/, tests/integration/reflection_failure_memory/"
status: not_started
owner: ""
```

---

*APEX v3 — Single Unified Architecture Specification*
*Sections 1–73, Appendices A–H*
*Everything in one place. Nothing deferred. Nothing separated into "future work."*
*This document supersedes APEX Instruction Set v2 (89 sections) and all gap analysis sessions.*

*APEX is not a signal generator. It is a self-aware, epistemically honest, continuously learning, behaviorally aware trading intelligence that knows what it doesn't know, remembers what went wrong, and tells users the truth — including when that truth is "I should not be trusted on this."*

---

# PART III: ADVANCED INTELLIGENCE SYSTEMS

---

## SECTION 74: CROSS-SESSION ANALYTICAL CONTINUITY

APEX maintains an evolving analytical view on every ticker it has analyzed. Every new analysis explicitly reconciles against the prior thesis.

### 74.1 Ticker Intelligence File Schema

```python
class TickerIntelligenceFile:
    ticker: str
    current_thesis: dict        # direction, confidence, primary_driver, thesis_age_days, trace_id
    thesis_history: list[dict]  # {date, direction, confidence, driver, trigger, trace_id}
    pending_setups: list[dict]  # developing setups with conditions_met / conditions_total
    open_questions: list[dict]  # unanswered questions affecting the thesis
    related_tickers: list[dict] # {ticker, relationship, correlation, thesis_alignment}
    ticker_failure_patterns: list[str]   # failure_pattern_ids specific to this ticker
    active_expert_views: list[dict]
```

### 74.2 Continuity-Aware Pipeline

Before each reactive analysis, the Knowledge Application Engine loads the TickerIntelligenceFile and presents it to the Reflection Layer:

```
Prior thesis: bearish (3 days ago, confidence 0.71)
Driver: bear regime + negative sentiment
Since then: regime score improved from 0.25 → 0.38
            sentiment improved from -0.74 → -0.31
            Pending squeeze setup: 4 of 5 conditions now met
```

### 74.3 Thesis Change Narration Rules

Direction reversal: "My view on {ticker} has REVERSED from {old} to {new}. The key driver was [specific factor]. [N] days ago I was {old} at {confidence}."

Significant confidence shift (>0.20): "My conviction has [strengthened/weakened] from {old} to {new} because [specific factor]."

No material change: "My view is unchanged since [date] — still [direction] at [confidence]. The conditions that drove this view remain intact."

### 74.4 Position Thesis Lifecycle Monitor

Runs on each PIL cycle for every open position. Re-evaluates each component of the entry thesis against current data.

```python
component_status: "intact" | "weakened" | "invalidated" | "strengthened"
overall_health: float  # 0-1

# When overall_health < config.thesis_exit_threshold:
# Emit THESIS_INVALIDATED:
# "The thesis for your AAPL long has deteriorated:
#  - Regime: ranging at entry → bear trend now (INVALIDATED)
#  - RSI: oversold at entry → neutral now (WEAKENED)
#  Thesis health: 0.18 (critical). Consider proactive exit."
```

---

## SECTION 75: SECOND-ORDER CASCADE REASONING

APEX analyzes the current state and also reasons about cascading effects of a signal's outcome.

```python
class SecondOrderAnalysis:
    signal_id: str
    ticker: str

    success_cascade: list[dict]   # if signal RIGHT: cascade effects
    failure_cascade: list[dict]   # if signal WRONG: cascade risks

    # per cascade item:
    # {affected_entity, expected_effect, probability, impact_magnitude,
    #  actionable, preparation_action}

    portfolio_impact: dict        # projected_heat, correlation_risk, circuit_breaker_proximity
```

**Why Engine Layer 6 — Cascade Analysis:** Identifies all entities affected by this signal's outcome. Aggregates into portfolio-level impact. Identifies preparation actions. Included in every trade plan narrative.

```
"If AAPL breaks above $185:
 → MSFT (correlated 0.72) likely follows within 2-3 bars
 → QQQ pulled higher, improving regime score
 → Portfolio heat reaches 14.2% if all three trigger
 → Correlation cluster risk reaches warning threshold"
```

---

## SECTION 76: SYNTHETIC SCENARIO ENGINE

```python
class ScenarioEngine:
    scenario_types = {
        "rate_shock":       ["rate_change_bp", "surprise_flag"],
        "volatility_spike": ["vix_target", "duration_days"],
        "sector_rotation":  ["from_sector", "to_sector", "magnitude"],
        "earnings_surprise":["ticker", "direction", "magnitude_pct"],
        "flash_crash":      ["index_drop_pct", "duration_minutes"],
        "correlation_spike":["target_correlation", "affected_pairs"],
        "liquidity_crisis": ["spread_multiplier", "volume_reduction_pct"],
    }

    def compute_impact(scenario, portfolio) -> ScenarioImpact:
        # Returns: portfolio_pnl_estimate, per_position_impact,
        # regime_shift_probability, projected_regime,
        # circuit_breaker_proximity, recommendations,
        # confidence_in_estimate, historical_analog_count
```

**User query:** "What would happen to my portfolio if the Fed raises rates 50bp unexpectedly tomorrow?"

APEX computes the expected market response using historical analogs, applies to the current portfolio position by position, and outputs: aggregate impact, most affected positions, regime shift probability, and recommendations for hedging or reduction.

---

## SECTION 77: EPISTEMIC HUMILITY MAPPING

```python
class EpistemicAssessment:
    data_coverage: dict         # ohlcv_history, tick_data, options_data, sentiment_data
    model_fitness: dict         # strategy_fitness_for_regime, sample_size_in_regime
    experience_level: dict      # prior_analyses_on_ticker, outcome_data_available
    known_blind_spots: list[dict]  # {blind_spot, impact, mitigation}
    epistemic_score: float      # 0-1
    epistemic_classification: str
    # "well_equipped" | "adequate" | "limited" | "operating_blind" | "novel_territory"
```

**Narrative rules:**
- `operating_blind` / `novel_territory`: Lead with `⚠️ IMPORTANT: This analysis has significant knowledge limitations.`
- `limited`: `Note: This analysis is constrained by [gaps]. Confidence is adjusted downward.`
- `adequate` / `well_equipped`: No epistemic preamble — proceed normally

**Integration:** Epistemic score feeds into Confidence Decomposition (Section 13) and the Abstain/No-Decision Mode (Section 14).

---

## SECTION 78: ANALYTICAL DEBT DASHBOARD

```python
class AnalyticalDebtDashboard:
    model_staleness: dict          # days since last validation per strategy
    calibration_drift: dict        # stated confidence vs. realized accuracy gap
    failure_lesson_backlog: int    # unprocessed failures without extracted lessons
    learning_abstraction_decay: dict   # active abstractions with declining accuracy
    hitl_queue_age: int            # oldest unreviewed learning (days)
    data_source_health: dict       # degrading adapters
    expert_observation_freshness: dict

    analytical_health_score: float # 0-1 composite
    health_classification: str     # "healthy" | "attention" | "degrading" | "critical"
    health_trend: str              # "improving" | "stable" | "declining"
```

Included in every PIL intelligence brief. High debt triggers specific recommended actions. Example: "Analytical health: 0.72 (attention needed). Mean Reversion calibration gap is 0.18 (overconfident). 3 failure lessons unprocessed > 7 days. HITL queue has 5 items pending > 14 days."

---

## SECTION 79: CROSS-ANALYSIS INTELLIGENCE

When analyzing a ticker, the Knowledge Application Engine automatically incorporates insights from recent analyses of related tickers.

```python
# Before analyzing MSFT:
related_analyses = {
    "AAPL": {
        "analyzed_2_hours_ago": True,
        "thesis": "bullish, confidence 0.71",
        "relevant_finding": "Strong institutional buying via order flow",
        "implication_for_MSFT": "If AAPL sees institutional buying, MSFT as sector peer may see similar flow"
    },
    "QQQ": {
        "relevant_finding": "Breadth improving despite index weakness",
        "implication_for_MSFT": "Broad tech breadth improvement supports individual tech setups"
    }
}
# Injected into Why Engine Layer 3 and NarrativeAgent
```

NarrativeAgent explicitly attributes cross-analysis context: "I analyzed AAPL 2 hours ago and found strong institutional buying. As a sector peer with 0.72 correlation, this supports the bullish thesis on MSFT."

---

## SECTION 80: NARRATIVE CONSISTENCY ENFORCEMENT

### 80.1 Consistency Engine

Before every NarrativeAgent synthesis, load the last 5 narratives for this ticker and compare key claims. Contradiction types:

- `legitimate_change`: Material data change justifies the shift → narrate explicitly
- `emphasis_drift`: Underlying data unchanged but different aspects emphasized → normalize
- `model_inconsistency`: Different runs produce different assessments → cache LLM assessment within configured window
- `temporal_drift`: Same indicator values described differently → standardize vocabulary

### 80.2 Indicator Language Standardization

```yaml
indicator_language_map:
  rsi:
    0-20:  "deeply oversold"     # ALWAYS — never "approaching oversold"
    20-30: "oversold"
    40-60: "neutral"             # ALWAYS — never "mid-range momentum"
    70-80: "overbought"
    80-100: "deeply overbought"
  trend_strength:
    adx_0-15:  "no discernible trend"
    adx_25-40: "moderate trend"  # ALWAYS — never just "trending"
    adx_60+:   "extremely strong trend"
```

These mappings ensure RSI at 42 is always described identically regardless of which LLM call generates the narrative.

---

## SECTION 81: LLM OUTPUT SCHEMA VALIDATION

Every LLM call in APEX (Reflection Layer, NarrativeAgent, Why Engine narrative synthesis, intent classification) must produce output conforming to a declared schema. LLM outputs are not trusted to be well-formed.

```python
class LLMOutputValidator:
    def validate(self, output: str, schema: LLMOutputSchema) -> ValidationResult:
        """
        1. Parse output as JSON
        2. Validate against schema (required fields, types, enum values)
        3. If validation fails: log failure, return degraded structured output
        4. Never pass raw LLM output directly to downstream pipeline steps
        """

    def handle_validation_failure(self, failure: ValidationFailure) -> DegradedOutput:
        """
        Returns a structured output with all required fields populated with
        configured defaults or null values. Marks output as llm_schema_violation: true.
        Does NOT abort the pipeline — degrades gracefully.
        """
```

**Coverage:** Every LLM output schema is declared in `config/llm_schemas/`. The validator is registered as a mandatory post-processing step for all LLM calls. Validation failures are tracked as metrics: `apex_llm_schema_violations_total (labels: component)`.

---

## SECTION 82: STRATEGY PLUGIN RESOURCE LIMITS (ENFORCEMENT)

The `resource_limits()` contract declared in Section 3.1 is enforced by the Plugin Runtime:

```python
class PluginRuntime:
    def execute(self, plugin: StrategyPlugin, context: StrategyContext) -> list[Signal]:
        limits = plugin.resource_limits()
        
        with self.resource_monitor(
            max_cpu_ms=limits.max_cpu_time_ms,
            max_memory_mb=limits.max_memory_mb
        ) as monitor:
            try:
                signals = plugin.generate_signals(context)
                if monitor.cpu_exceeded or monitor.memory_exceeded:
                    raise PluginResourceExceeded(plugin.id(), monitor.stats)
                return signals
            except PluginResourceExceeded as e:
                self.log_violation(plugin.id(), e)
                self.increment_violation_count(plugin.id())
                if self.violation_count(plugin.id()) > self.config.max_violations:
                    self.suspend_plugin(plugin.id())
                return []  # returns plugin_error signal
```

Repeated violations trigger plugin suspension pending review. The `generate_signals()` CPU time budget is declared per plugin and enforced independently of the Executive Controller's pipeline-level latency budget.

---

## SECTION 83: INDICATOR COMPUTATION PARTIAL FAILURE

When one indicator type fails during `compute_indicators`:

```yaml
indicator_partial_failure_policy:
  action: "return_partial_with_flags"   # "abort" | "return_partial_with_flags" | "skip_indicator"
  flag_failed_indicators: true          # mark failed indicators as null with failure reason
  notify_strategy_plugins: true         # strategies receive unavailability_flags map
  min_indicators_for_signal: 0.70       # require 70% of declared indicators to proceed
```

Strategies that declare a failed indicator as **required** are excluded from signal generation for this cycle. Strategies that declare it as **optional** proceed with a `DataQualityWarning`. The Signal Aggregator applies a confidence penalty for each excluded strategy (Section 3.3, `partial_aggregation_policy`).

---

## SECTION 84: TICKER SYMBOL RESOLUTION & VALIDATION

All user-supplied and LLM-generated ticker symbols are validated before entering any pipeline:

```python
class TickerValidator:
    def validate(self, symbol: str) -> ValidationResult:
        normalized = symbol.strip().upper()
        
        # Handle variants
        normalized = self.normalize_variants(normalized)  # BRK.B → BRK-B
        
        # Check against known universe
        if normalized not in self.universe:
            suggestions = self.suggest_corrections(normalized)
            if suggestions:
                raise TickerNotFoundError(normalized, suggestions)
            raise UnknownTickerError(normalized)
        
        return ValidationResult(symbol=normalized, valid=True)

    def validate_llm_output(self, tickers: list[str]) -> list[str]:
        validated = []
        for ticker in tickers:
            try:
                result = self.validate(ticker)
                validated.append(result.symbol)
            except (TickerNotFoundError, UnknownTickerError) as e:
                logger.warning("LLM hallucinated ticker", ticker=ticker)
                self.audit_trail.record("security.llm_hallucination", ticker=ticker)
                # Do not add to validated list; skip silently
        return validated
```

`HallucinatedTickerError` events are always logged to the AuditTrail as `security.llm_hallucination` and tracked as a metric: `apex_llm_hallucinations_total`. Tickers that fail validation never enter the data fetch pipeline.

---

## SECTION 85: DATA VENDOR RECONCILIATION ON RESTATEMENT

When a data vendor corrects historical data after it has already been fetched and cached:

```python
class RestatementHandler:
    def on_cache_refresh(self, ticker: str, key: str, new_data: Any) -> None:
        cached = self.data_registry.get(key)
        if cached and self.differs_materially(cached.value, new_data):
            # 1. Log the restatement
            logger.info("DATA_RESTATEMENT_DETECTED", ticker=ticker,
                       field=key, old=cached.value, new=new_data)
            
            # 2. Cascade invalidation
            derived_keys = self.data_registry.get_dependents(key)
            for derived_key in derived_keys:
                self.data_registry.mark_stale(derived_key)
                self.data_registry.set_flag(derived_key, "requires_recomputation", True)
            
            # 3. Invalidate affected signals
            self.signal_store.flag_signals_derived_from(key)
            
            # 4. Alert if any open position was affected
            if self.any_open_position_uses(ticker):
                self.emit_event("DATA_RESTATEMENT_ALERT", {
                    "ticker": ticker, "field": key,
                    "open_position_affected": True
                })
```

---

## SECTION 86: WEBSOCKET BACKPRESSURE HANDLING

```yaml
websocket:
  inbound_rate_limit_per_second: 10
  outbound_buffer_max_events: 500
  buffer_warning_threshold: 400     # emit CLIENT_SLOW at this level
  buffer_drop_policy:
    retain: ["CIRCUIT_BREAKER", "POSITION_ALERT", "THESIS_INVALIDATED", "SHUTDOWN_IMMINENT"]
    drop: ["CANVAS_UPDATE", "INTELLIGENCE_BRIEF_UPDATE", "HEARTBEAT"]
```

**Backpressure sequence:**
1. At 80% of buffer (`buffer_warning_threshold`): emit `CLIENT_SLOW` to the client; log as metric
2. At 100% of buffer: drop non-critical events per drop policy; retain safety-critical events regardless
3. When buffer drains below 50%: resume normal event delivery; emit `BUFFER_RECOVERED`

This prevents slow clients from blocking the event bus or causing memory growth.

---

## SECTION 87: BACKTEST-TO-LIVE PARITY VERIFICATION

The backtest engine and live reactive pipeline are two code paths. They must produce identical signals for identical data. Parity is verified on every CI build.

```yaml
backtest_parity:
  enabled: true
  canonical_datasets:
    - {name: bull_trend_2023,     ticker: SPY, interval: 1d}
    - {name: bear_trend_2022,     ticker: SPY, interval: 1d}
    - {name: ranging_2024,        ticker: QQQ, interval: 1d}
    - {name: high_volatility_2020,ticker: SPY, interval: 1d}
    - {name: regime_transition_2021, ticker: SPY, interval: 1d}
  strategies_under_test: all_registered
  tolerance: 0          # zero tolerance — signals must be identical
  fail_build_on_deviation: true
```

**Parity report format on failure:**
```
PARITY DEVIATION:
  Strategy: trend_following_v1
  Dataset: bull_trend_2023
  Signal bar: 2023-03-15T00:00:00Z
  Backtest: BUY strength 0.78
  Live:     No signal
  Likely cause: RSI confirmation deferred differently between modes
```

Any deviation fails the CI build. The parity test is listed as a mandatory Stage 3 gate in the CI/CD pipeline (Section 39.1).

---

## SECTION 88: EVOLUTION ENGINE SELF-OBSERVABILITY

```python
class EvolutionEngineDashboard:
    proposals_generated_this_month: int
    proposals_promoted: int
    proposals_rejected: int
    proposals_expired: int
    promotion_accuracy: float        # % of promoted changes that improved performance
    average_shadow_duration_days: float
    budget_consumed_pct: float
    is_improving_apex: bool          # meta-assessment based on promotion_accuracy

class CuriosityROIReport:
    proposals_generated: int
    proposals_validated: int         # led to actionable improvements
    proposals_refuted: int
    budget_consumed_usd: Decimal
    cost_per_validated_improvement: Decimal
    roi_score: float
```

If `promotion_accuracy` drops below the configured floor for a rolling window, the Evolution Engine generates a self-assessment alert: "Evolution Engine proposals are not improving system accuracy at the expected rate. Review root cause analysis methodology."

---

## SECTION 89: MULTI-INSTRUMENT TRADE PLAN SCHEMA

For strategies that produce multi-leg outputs (Pairs Trading, Factor Rotation, Macro Rotation, options strategies), the `format_trade_plan` tool is extended:

```python
class TradePlan:
    plan_type: str           # "single" | "pair" | "basket" | "options_spread"
    legs: list[TradeLeg]     # exactly 1 for single; N for others
    net_exposure: Decimal
    correlation_between_legs: float | None   # for pair strategies
    hedge_ratio: Decimal | None

class TradeLeg:
    ticker: str
    direction: str           # "long" | "short"
    shares: Decimal          # always Decimal
    entry_price: Decimal | None
    stop_price: Decimal
    take_profit: Decimal
    notional: Decimal
    role: str                # "primary" | "hedge" | "basket_member"
```

Single-leg plans use `plan_type: "single"` with exactly one leg — fully backward compatible with existing signal disposition tracking, audit trail, and Canvas render types.

---

## SECTION 90: COST VISIBILITY & BUDGET CONTROLS

Every LLM call and external API call is tagged with the component that generated it.

```python
class CostTracker:
    def record_llm_call(self, component: str, tokens_in: int, tokens_out: int, cost_usd: Decimal):
        ...
    def record_api_call(self, adapter: str, endpoint: str, cost_usd: Decimal):
        ...
    def get_daily_report(self) -> DailyCostReport:
        ...

class DailyCostReport:
    llm_api_calls: dict         # {count, cost: Decimal, budget: Decimal, remaining: Decimal}
    data_vendor_calls: dict
    total_daily_cost: Decimal
    cost_per_signal: Decimal
    cost_per_trade_plan: Decimal
    monthly_budget: Decimal
    monthly_spend_to_date: Decimal
    projected_monthly_spend: Decimal
    budget_alert: str | None    # "OVER_BUDGET_PROJECTED" | "APPROACHING_LIMIT"
```

**Budget guards:**
```yaml
budget:
  daily_llm_budget_usd: "100.00"
  hard_stop_threshold_pct: 0.95    # PIL and Evolution Engine pause at 95%
  reactive_reserve_pct: 0.20       # always reserve 20% for user requests
```

At 95% of daily budget: PIL speculative tasks and Evolution Engine shadow evaluations pause. Reactive user requests continue using the reserved budget. `BUDGET_WARNING` event emitted.

**Cost attribution by component** — accessible at `GET /admin/cost/attribution`. Shows breakdown by: PIL subsystems, Evolution Engine, reactive pipeline components, per-user breakdown, and time-period trend.

---

## SECTION 91: SPEC CONSISTENCY FIXES

The following internal contradictions and ambiguities identified in the gap analysis are resolved here as authoritative definitions:

**Heat computation:** Portfolio heat is always recomputed from the current set of open positions using `REPEATABLE_READ` isolation — never an incrementally maintained counter. The data source for positions may be in-memory (single-process) or database (multi-process); the computation is always from-scratch-on-demand. §6.4's "never cached" statement and §72.1's "no in-memory caching in multi-process" are both correct and non-contradictory.

**Tool vs. sub-routine:** `compute_candlestick_patterns`, `compute_key_levels`, and `compute_order_flow_indicators` are **indicator computation modules** within `compute_indicators`, not separate tools. They are sub-routines. They do not appear in the Tool Registry. They are listed in the Indicator Library Registry (Section 54). The "Tool:" heading in prior documentation was incorrect; these sections describe indicator families.

**Why Engine layer count:** The Why Engine produces a **5-layer causal analysis** (Layers 1–5) with a **strategy context preamble** (Layer 0). All references to "5-layer analysis" mean Layers 1–5. The preamble is always present but is not counted as an analytical layer. Cascade analysis is Layer 6 (optional, when enabled).

**ReAct usage:** ReAct is used only when no compiled workflow matches the resolved intent — not as a fallback after trying multiple workflows. The intent router resolves directly to a specific workflow or to ReAct.

**Signal modifier pipeline execution order:** After signal aggregation and before sizing, the execution order is fixed:
1. Signal Aggregation
2. MTF Confluence Filter (Section 55.12)
3. Any additional signal modifier plugins (declared type: `signal_modifier`, executed in configured priority order)
4. Position Sizing

**PIL atomic brief:** On graceful shutdown, the intelligence brief retains the **prior complete cycle's brief** (stale but complete), not a partial brief from an aborted cycle. The partial snapshot written during abort is for PIL state restoration only, not for user-facing brief content.

**Strategy context vs. Data Registry:** The `StrategyContext` object passed to `generate_signals()` contains all resolved data items (by `data_id` reference) that the strategy declared in `required_indicators()` and `optional_indicators()`. The strategy does not access the Data Registry directly. Context assembly happens in the ExecutiveController before plugin execution; the assembled context size is bounded by the plugin's `resource_limits()` declaration.

---

## APPENDIX I: COMPLETE WEBSOCKET EVENT CATALOG (FINAL)

All events emitted by APEX to connected WebSocket clients:

```
# Intelligence Events
INTELLIGENCE_BRIEF_UPDATE       PIL_CYCLE_COMPLETE
OPPORTUNITY_BRIEF               HYPOTHESIS_GENERATED
HYPOTHESIS_VALIDATED            HYPOTHESIS_REJECTED
STRATEGY_READY                  STRATEGY_DEGRADING
STRATEGY_WARM_UP_COMPLETE

# Signal & Trade Plan Events
SIGNAL_GENERATED                SIGNAL_SUPPRESSED
MTF_SUPPRESSION                 SIGNAL_EXPIRED
TRADE_PLAN_READY                TRADE_PLAN_UPDATED
NO_ACTION_ISSUED                ANALYSIS_TRAJECTORY_UPDATE
CANVAS_UPDATE                   CANVAS_PAYLOAD_ERROR

# Portfolio Events
POSITION_OPENED                 POSITION_CLOSED
POSITION_UPDATED                HEAT_WARNING
HEAT_CRITICAL                   CIRCUIT_BREAKER_TRIGGERED
CIRCUIT_BREAKER_CLEARED

# Thesis Events
THESIS_INVALIDATED              THESIS_WEAKENING
THESIS_UPDATED                  THESIS_RESTORED

# Regime & Market Events
REGIME_CHANGE                   REGIME_TRANSITION_ALERT
CORPORATE_ACTION_APPLIED        TICKER_HALT_DETECTED
SSR_ACTIVATED                   SSR_CLEARED
MARKET_CIRCUIT_BREAKER_L1       MARKET_CIRCUIT_BREAKER_L2
MARKET_CIRCUIT_BREAKER_L3

# Data Events
DATA_RESTATEMENT_ALERT          DATA_REGISTRY_MEMORY_WARNING
DATA_VENDOR_FAILOVER            PROVIDER_SCHEMA_DRIFT

# Learning Events
DISAGREEMENT_SUBMITTED          DISAGREEMENT_RESOLVED
EXPERT_SIGNAL_RECEIVED          LEARNING_SESSION_COMPLETE
KNOWLEDGE_VALIDATED             KNOWLEDGE_INTEGRATED
LEARNING_ABSTRACTION_CREATED    ABSTRACTION_DEPRECATED
FAILURE_PATTERN_CONFIRMED       FAILURE_LESSON_ACTIVATED
ACTIVE_LEARNING_QUERY           HITL_ITEM_QUEUED

# System Health Events
AGENT_DRIFT_DETECTED            LLM_UNAVAILABLE
LLM_PROVIDER_FAILOVER           BUDGET_WARNING
BUDGET_HARD_STOP                MEMORY_LEAK_SUSPECTED
MEMORY_CEILING_EXCEEDED         DLQ_GROWING
COMPONENT_RESTORED              ANALYTICAL_DEBT_ALERT

# Behavioral Events
BEHAVIORAL_BIAS_DETECTED        BEHAVIORAL_FRICTION_TRIGGERED

# Session Events
HEARTBEAT                       SESSION_STARTED
SESSION_RESUMED                 SHUTDOWN_IMMINENT
RATE_LIMITED                    CLIENT_SLOW
BUFFER_RECOVERED                PIL_COLD_START
PIL_LEADER_CHANGE
```

---

## APPENDIX J: ARCHITECTURE DECISION RECORD — SINGLE CONSOLIDATED DOCUMENT

**ADR-013: Why This Is One Document, Not Many**

**Status:** Decided. This document is the single source of truth for APEX v3.

**Context:** Prior APEX specifications existed as multiple disconnected documents — the v2 89-section spec, 11 gap analysis sessions, and approximately 30 additional intelligence system specifications. Components referenced each other across documents with no canonical resolution when they conflicted.

**Decision:** All specifications are consolidated into this single document. Every component, every interface, every contract, every configuration key is defined here. Where prior sessions identified conflicts (layer count, heat computation, tool vs. sub-routine), this document provides the authoritative resolution. No other document supersedes this one.

**Consequences:** This document is large. The tradeoff is intentional. A developer implementing any component should be able to find the complete specification here without hunting across multiple files. Cross-references within the document are used extensively; external references are not required for understanding any section.

---

## APPENDIX K: KNOWN DEFERRED ITEMS

The following items were identified in the gap analysis but are deliberately deferred to a future version. They are not gaps — they are conscious scope decisions:

**Deferred to v3.1:**
- Multi-asset class support (Options, Futures, Forex, Crypto) — the architecture is designed to support these via the instrument abstraction layer, but the specific mechanics are not specified here
- Tax intelligence engine — requires jurisdiction-specific configuration; deferred pending geo-targeting decisions
- Causal graph layer — conceptually sound but implementation requires a graph database; dependency conflicts with current stack
- Cross-agent debate system (bull/bear adversarial agents) — architecture supports this via the signal aggregation system; formal spec deferred
- Policy DSL for guardrails — guardrails are currently code-configurable; DSL layer adds complexity without near-term benefit

**Out of scope permanently:**
- Order execution (OMS/EMS) — APEX never executes orders; this is a Constitutional Axiom
- Broker integration for live trading — same constraint
- Multi-exchange routing — deferred until execution is reconsidered (it won't be)

---

*APEX v3 — Complete Unified Architecture Specification*
*Sections 1–91, Appendices A–K*
*Version 3.0 | May 2026*

*This document is self-contained and authoritative. It supersedes APEX Instruction Set v2 (89 sections), all gap analysis sessions (Sessions 1–11), and all intermediate specification documents.*

*APEX is not a signal generator. It is a self-aware, epistemically honest, continuously learning, behaviorally aware trading intelligence that knows what it doesn't know, remembers what went wrong, maintains an evolving view on every ticker across sessions, and tells users the truth — including when that truth is "I should not be trusted on this right now."*
