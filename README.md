# Apex

APEX runtime + cognitive layer foundation aligned to the APEX v3 instruction set.

## Implemented now

- Runtime lifecycle with phase progression, preflight clock drift check, degraded startup paths, snapshot staleness handling, and shutdown auditing.
- Idempotent processing with bounded LRU cache behavior.
- Transactional-style outbox queue and DLQ routing primitive with DLQ growth audit signal.
- Typed error taxonomy and validation helpers.
- Monetary Decimal gate enforcement for G11 numerical correctness.
- Cognitive layer with strategic memory, failure memory, confidence adjustment, and TTL-based memory eviction.

## Run tests

```bash
python -m unittest discover -s tests -v
```
