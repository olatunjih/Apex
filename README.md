# Apex

Initial runtime implementation for APEX v3 focused on foundational invariants:

- deterministic startup/shutdown lifecycle with phase tracking
- degraded startup modes for vendor/LLM outages
- typed error taxonomy
- monetary Decimal gate (G11-style enforcement)
- idempotent event processing cache semantics

## Run tests

```bash
python -m unittest discover -s tests -v
```
