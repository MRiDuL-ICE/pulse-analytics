CREATE TABLE IF NOT EXISTS api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    key_prefix  VARCHAR(16) NOT NULL,   -- first 8 chars e.g. "pk_live_" shown in UI
    key_hash    VARCHAR(255) NOT NULL UNIQUE, -- bcrypt hash of the full key
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_api_keys_tenant ON api_keys(tenant_id);
CREATE INDEX IF NOT EXISTS ix_api_keys_prefix ON api_keys(key_prefix);

INSERT INTO migrations (filename) VALUES ('002_api_keys.sql')
    ON CONFLICT (filename) DO NOTHING;