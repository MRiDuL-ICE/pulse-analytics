-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ── Tenants ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(100) NOT NULL UNIQUE,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Users ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL REFERENCES tenants(id),
    email            VARCHAR(255) NOT NULL UNIQUE,
    hashed_password  VARCHAR(255) NOT NULL,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_tenant ON users(tenant_id);

-- ── Events (TimescaleDB hypertable) ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id           UUID NOT NULL DEFAULT gen_random_uuid(),
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tenant_id    UUID NOT NULL REFERENCES tenants(id),
    event_type   VARCHAR(100) NOT NULL,
    session_id   VARCHAR(255),
    user_agent   TEXT,
    ip_address   VARCHAR(45),
    url          TEXT,
    referrer     TEXT,
    properties   JSONB,
    PRIMARY KEY (id, occurred_at)
);

SELECT create_hypertable(
    'events',
    'occurred_at',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS ix_events_tenant_time ON events(tenant_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_events_tenant_type ON events(tenant_id, event_type);

-- ── Pageviews ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pageviews (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID NOT NULL REFERENCES tenants(id),
    url          TEXT NOT NULL,
    title        VARCHAR(512),
    duration_ms  INTEGER,
    session_id   VARCHAR(255),
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_pageviews_tenant_time ON pageviews(tenant_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_pageviews_tenant_url  ON pageviews(tenant_id, url);

-- ── Funnels ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS funnels (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID NOT NULL REFERENCES tenants(id),
    name         VARCHAR(255) NOT NULL,
    description  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_funnels_tenant ON funnels(tenant_id);

-- ── Funnel steps ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS funnel_steps (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    funnel_id        UUID NOT NULL REFERENCES funnels(id) ON DELETE CASCADE,
    tenant_id        UUID NOT NULL,
    name             VARCHAR(255) NOT NULL,
    url_pattern      VARCHAR(512) NOT NULL,
    position         INTEGER NOT NULL,
    conversion_rate  FLOAT
);

CREATE INDEX IF NOT EXISTS ix_funnel_steps_funnel ON funnel_steps(funnel_id, position);

-- ── Migration tracking ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS migrations (
    id          SERIAL PRIMARY KEY,
    filename    VARCHAR(255) NOT NULL UNIQUE,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO migrations (filename) VALUES ('001_initial_schema.sql')
    ON CONFLICT (filename) DO NOTHING;