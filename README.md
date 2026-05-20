# Apex

APEX runtime + intelligence substrate foundation aligned to the APEX v3 instruction set.

## Implemented now

- Runtime lifecycle with phased startup, preflight clock drift check, degraded startup paths, snapshot staleness handling, and shutdown auditing.
- Exactly-once style idempotent processing primitives with bounded LRU cache and outbox/DLQ queues.
- Typed error taxonomy and validation helpers.
- Monetary Decimal gate enforcement for G11 numerical correctness.
- Cognitive layer with:
  - thesis memory persistence per ticker
  - evidence/source-aware confidence calibration
  - failure memory with loss-aware confidence penalties
  - TTL-based stale memory eviction
- Reactive layer with:
  - intent routing (portfolio / ticker / education)
  - on-demand analysis that applies cognitive calibration
  - structured “why engine” fields for explainability
  - position confirmation risk-cap check

## Run tests

```bash
python -m unittest discover -s tests -v
```
