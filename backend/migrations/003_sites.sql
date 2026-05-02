-- ── Sites table ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sites (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    domain      VARCHAR(255) NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_sites_tenant ON sites(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_sites_tenant_domain ON sites(tenant_id, domain);

-- ── Add site_id to api_keys ───────────────────────────────────────────────────
ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES sites(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS ix_api_keys_site ON api_keys(site_id);

-- ── Add site_id to events ─────────────────────────────────────────────────────
ALTER TABLE events
    ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES sites(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_events_site_time ON events(site_id, occurred_at DESC);

-- ── Add site_id to pageviews ──────────────────────────────────────────────────
ALTER TABLE pageviews
    ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES sites(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_pageviews_site_time ON pageviews(site_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_pageviews_site_url  ON pageviews(site_id, url);

INSERT INTO migrations (filename) VALUES ('003_sites.sql')
    ON CONFLICT (filename) DO NOTHING;