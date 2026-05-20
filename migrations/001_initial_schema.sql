-- Initial Database Schema for APEX Runtime

-- Idempotency tracking table
CREATE TABLE IF NOT EXISTS idempotency (
    key TEXT PRIMARY KEY,
    response JSONB,
    status TEXT DEFAULT 'completed',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

-- Outbox table for event publishing
CREATE TABLE IF NOT EXISTS outbox (
    id SERIAL PRIMARY KEY,
    aggregate_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    published BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMPTZ
);

-- Regime state storage
CREATE TABLE IF NOT EXISTS regime_state (
    id SERIAL PRIMARY KEY,
    regime_type TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Risk alerts log
CREATE TABLE IF NOT EXISTS risk_alerts (
    id SERIAL PRIMARY KEY,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    details JSONB NOT NULL,
    acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Guardrail violations log
CREATE TABLE IF NOT EXISTS guardrail_violations (
    id SERIAL PRIMARY KEY,
    guardrail_name TEXT NOT NULL,
    violation_details JSONB NOT NULL,
    action_aborted BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_outbox_published ON outbox(published, created_at);
CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON idempotency(expires_at);
CREATE INDEX IF NOT EXISTS idx_regime_created ON regime_state(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_created ON risk_alerts(created_at DESC);
