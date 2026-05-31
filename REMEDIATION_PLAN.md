# APEX v3 Gap Analysis and Improvement Plan

**Updated:** June 1, 2026
**Repository:** `olatunjih/Apex`
**Specification:** APEX v3 Unified Architecture Specification (91 sections, Appendices A-K)

---

## Executive Summary

The APEX v3 repository contains substantial alpha-stage engineering work, but it is materially earlier than the unified specification requires. Several quick wins from the prior remediation plan are now complete or partially complete: tracked `__pycache__` files are absent, dependency manifests exist, and the current test suite passes. The remaining risk is architectural: duplicate subsystems, partial invariants, thin persistence, and many intelligence layers that are schemas rather than production flows.

| Dimension | Current Assessment |
|---|---:|
| Python files under `src/` and `tests/` | 44 |
| Python LOC under `src/` and `tests/` | ~15,766 |
| Tests | 68 passing |
| Spec sections touched | ~45-50 / 91 |
| Production-ready coherent system | ~15-20% |

The highest-leverage next step remains consolidation and invariant enforcement before adding new APEX intelligence features.

---

## Part 1: Structural Issues to Fix Now

### 1.1 Duplicate Subsystems

#### Health checks

Two modules expose overlapping health concepts:

- `src/apex_runtime/health.py` exposes `HealthChecker`.
- `src/apex_runtime/health_signals.py` exposes `HealthCheckSystem` and health server helpers.

**Risk:** endpoint behavior and readiness semantics can diverge depending on import path.

**Plan:** keep the richer health-check implementation, provide backward-compatible exports, and retire the duplicate module after tests move to the canonical API.

#### Signal handling

Two signal handler classes remain:

- `src/apex_runtime/signal_handler.py`
- embedded `SignalHandler` in `src/apex_runtime/health_signals.py`

**Risk:** multiple registration paths for process signals can produce surprising behavior in long-running runtime processes.

**Plan:** keep `signal_handler.py` as the single registration path and make health code consume it instead of defining a second handler.

#### Tool layer

Two tool stacks remain:

- `src/apex_runtime/tools.py`
- `src/apex_runtime/tools/core.py` plus package exports in `src/apex_runtime/tools/__init__.py`

**Risk:** duplicate `BaseTool`, registry, and result-schema concepts can drift and break runtime dispatch.

**Plan:** define one canonical tool schema and registry surface, migrate concrete tools to it, and delete any forward-declaration or global-patching initialization patterns.

---

### 1.2 Dependency and Packaging Hygiene

Dependency manifests exist, but they must track the runtime imports and developer workflow.

**Immediate updates in this remediation pass:**

- Add `psutil>=5.9.0,<6.0` to runtime dependencies because health and memory modules import it.
- Add `ruff` and `mypy` to the development extras so lint/type checks are installable through `pip install -e .[dev]`.
- Clean `.gitignore` formatting so ignore rules are plain gitignore patterns.

**Follow-up:** periodically audit imports against `pyproject.toml` and `requirements.txt` as FastAPI, WebSocket, OpenTelemetry, and persistence layers are expanded.

---

### 1.3 Fragile Dual-Mode Imports

Several modules still support direct script execution with patterns like `try: from .errors ... except ImportError: from errors ...`.

**Risk:** this weakens package cohesion and can hide import errors during tests.

**Plan:** remove fallback imports after CLI entry points are declared in `pyproject.toml` for any supported direct commands.

---

### 1.4 Testing and Coverage

The current suite is green, but coverage remains concentrated.

**Current baseline:** `pytest -q` reports 68 passing tests.

**Priority targets:**

1. `strategy.py`
2. `tools.py` and `tools/core.py`
3. numerical policy and G11 behavior
4. guardrail rejection/audit paths
5. cognitive/executive routing

**Goal:** reach at least 60% coverage on the highest-risk runtime modules before marking P0 features complete.

---

## Part 2: Architectural Gaps vs. Spec

### P0 — System Cannot Function as APEX Without These

1. **G11 Numerical Type Gate:** every monetary tool/API boundary must reject non-`Decimal` values before G1 runs.
2. **Durable Idempotent Event Processor:** replace in-memory dedupe with `processed_events`, transactional outbox, retry metadata, and DLQ alerting.
3. **Startup Sequence Gating:** implement the full 26-step, five-phase startup with clock drift, schema version, config, migration lock, and degraded-startup semantics.
4. **Data Registry v2:** extend the tested in-memory registry with spec keys, provenance, quality scoring, memory pressure thresholds, and durable integration where needed.
5. **Full Guardrail Pipeline G1-G11:** run the mandatory sequence for every evaluation and write an audit trail for every rejection.

### P1 — System Becomes a Basic Signal Generator Without These

1. **Proactive Intelligence Layer:** scheduler, six subsystems, event emission, and snapshot/warm-start protocol.
2. **Three-Tier Intent Router:** deterministic Tier 1, lightweight classifier Tier 2, and bounded LLM Tier 3 fallback.
3. **Why Engine Layers 2-5:** regime, risk/thesis coherence, external signals, and failure-aware historical analogs.
4. **Failure Memory System:** durable records, fingerprint indexes, root-cause taxonomy, and pattern lifecycle.
5. **Learning Engine:** outcome resolution, Brier/calibration metrics, retraining triggers, shadow deployments, and promotion rules.
6. **Cross-Session Continuity:** durable ticker intelligence files and position thesis lifecycle monitoring.
7. **HTTP/WebSocket API:** full REST surface, WebSocket events, session management, backpressure, auth, CSRF, and rate limiting.

### P2 — Intelligence Differentiators

- Behavioral Guardian
- Agent Drift Detection
- Evolution Engine
- Curiosity Engine
- Knowledge Application Engine
- Expert Observer Engine
- VaR/CVaR and full financial risk architecture
- Complete observability stack
- Epistemic humility output contract
- Confidence decomposition
- Complete Decision Contract persistence

---

## Part 3: Roadmap

### Phase 0 — Structural Integrity

1. Consolidate health checks to one public implementation.
2. Consolidate signal handling to one registration path.
3. Consolidate tool schemas, results, registry, and `BaseTool` definitions.
4. Remove dual-mode import fallbacks after CLI entry points exist.
5. Keep packaging manifests aligned with actual imports.
6. Preserve a green test baseline after every consolidation PR.

**Exit criteria:** no duplicate health/signal/tool public classes remain, `pip install -e .[dev]` succeeds, and all existing tests pass.

### Phase 1 — Foundational Invariants

1. Implement `G11NumericalTypeGate` and tests for every monetary field family.
2. Add durable idempotency and transactional outbox migrations.
3. Implement outbox delivery worker with retries and DLQ alerting.
4. Extend Data Registry with spec key format, provenance, quality scoring, and memory pressure behavior.
5. Implement the audited G11 -> G1 -> ... -> G10 guardrail runner.

### Phase 2 — Core Intelligence

1. Complete startup/shutdown hardening and crash-restart detection.
2. Implement Failure Memory persistence and pattern aggregation.
3. Complete Why Engine layers 2-5.
4. Build the PIL scheduler, Regime Intelligence, Strategy Readiness Monitor, and snapshot restore path.

### Phase 3 — Session Intelligence and Learning

1. Persist ticker intelligence files.
2. Implement thesis change narration and lifecycle monitor.
3. Implement outcome resolution and calibration metrics.
4. Add Knowledge Application pre-pipeline context assembly.
5. Benchmark the three-tier intent router against latency and routing-share targets.

### Phase 4 — Production Hardening

1. Add Prometheus metrics and OpenTelemetry spans for all pipeline stages.
2. Add structured log redaction.
3. Add JWT, CSRF, RBAC, and rate limiting.
4. Implement WebSocket event catalog and backpressure semantics.
5. Add CI gates for lint, type checking, tests, coverage, determinism, and dependency audit.

### Phase 5 — Intelligence Differentiators

Implement the Behavioral Guardian, drift detection, evolution/shadow deployments, curiosity engine, full risk architecture, confidence decomposition, epistemic humility, analytical debt dashboard, and complete Decision Contract storage.

---

## Part 4: Quick Wins

- Keep tracked bytecode out of git; verify with `git ls-files | grep __pycache__`.
- Keep `.gitignore` as plain patterns without markdown fences.
- Keep runtime dependencies pinned when imports are introduced.
- Add lint/type tooling to dev extras before enforcing CI gates.
- Treat `docs/BUILD_PROGRESS.md` as a planning artifact and update it only with tested implementation status.

---

## Appendix: Non-Negotiable Invariants

| Invariant | Enforcement Target |
|---|---|
| Monetary values are `Decimal`, never `float` | G11 at every tool/API boundary plus tests |
| State-mutating events carry an idempotency key | Middleware and durable event processor |
| Timestamps are UTC internally | Validators and code review gate |
| `generate_signals()` is deterministic | CI parity test |
| Raw exceptions never reach LLM/API responses | `APEXError` wrapping and redaction |
| Tools do not call LLMs | Tool contract tests |
| Order execution is never implemented | `NO_EXECUTION` guard at all exits |
| Database monetary columns are `NUMERIC(28,10)` | Migration review gate |
| JSON monetary serialization uses strings | Pydantic validators/serializers |
