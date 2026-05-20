# APEX Runtime

Autonomous Production-Ready EXecutive (APEX) - A hardened runtime for autonomous trading agents.

## Project Structure

```
/workspace
├── src/                    # Main source code
│   └── apex_runtime/       # Core runtime package
│       ├── agents/         # Agent implementations
│       ├── tools/          # Tool definitions and executors
│       ├── ui/             # User interface components
│       ├── tests/          # Unit tests
│       └── *.py            # Core modules
├── configs/                # Configuration files
│   └── config.yaml         # Runtime configuration
├── migrations/             # Database migration scripts
│   └── 001_initial_schema.sql
├── scripts/                # Utility scripts
│   ├── run_server.py       # Start the runtime server
│   └── run_tests.py        # Run test suite
└── docs/                   # Documentation
    ├── APEX_v3_INSTRUCTION_SET.md
    ├── APEX_BUILD_PLAN.md
    ├── BUILD_PROGRESS.md
    └── README.md
```

## Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Redis 6+

### Installation
```bash
pip install -r requirements.txt
```

### Database Setup
```bash
psql -U apex -d apex_runtime -f migrations/001_initial_schema.sql
```

### Run Server
```bash
python scripts/run_server.py
```

### Run Tests
```bash
python scripts/run_tests.py
```

## Key Features

- **Guardrails**: 11 non-bypassable safety constraints (G1-G11)
- **Idempotency**: PostgreSQL-backed action deduplication
- **Observability**: Structured logging, metrics, and tracing
- **Outbox Pattern**: Reliable event publishing
- **Proactive Intelligence**: Regime detection and risk monitoring

## Configuration

Edit `configs/config.yaml` to customize:
- Guardrail thresholds
- Database connection settings
- Redis cache configuration
- Observability options

## License

Proprietary - All rights reserved
