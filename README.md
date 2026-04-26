# Pulse Analytics

A self-hosted, multi-tenant web analytics backend — built as a portfolio project to demonstrate production-grade backend engineering with Python, FastAPI, TimescaleDB, Redis, and Docker.

Think of it as a stripped-down, self-hosted alternative to Mixpanel or Amplitude. Instead of paying for third-party analytics and handing your users' data to someone else's servers, you run Pulse Analytics yourself and own everything.

---

## What problem does it solve?

Every website owner wants to answer the same questions:

- How many people visited my site today?
- Which pages are most popular?
- Where do users drop off in my checkout funnel?
- What events are users triggering most?

Existing tools like Google Analytics, Mixpanel, and Amplitude answer these questions — but they're expensive at scale, they send your users' data to third-party servers you don't control, and they lock you into their pricing. Pulse Analytics gives you the same core capabilities, self-hosted, with full data ownership.

---

## Who is it for?

**Developers** building web apps who want analytics without paying for Mixpanel or Amplitude — embed one JS snippet and you're tracking.

**Agencies** managing multiple client websites — each client is an isolated tenant with their own data, users, and dashboards.

**Business owners** who need simple pageview and event tracking without the cost or privacy concerns of third-party tools.

---

## How it works — the full workflow

There are three actors in the system:

**1. The tenant** — a company or individual using Pulse Analytics to track their website. Acme Corp is one tenant, Beta Startup is another. Their data is completely isolated. This is multi-tenancy.

**2. The website visitor** — the end user whose behaviour gets tracked. They never interact with Pulse Analytics directly.

**3. The dashboard user** — someone at Acme Corp who logs in to view their analytics.

```
┌─────────────────────────────────────────────────────────────────┐
│                        acme.com website                         │
│  JS snippet fires POST /api/v1/events on every page load/click  │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                          Nginx                                  │
│         Rate limiting · Load balancing across 2 workers         │
└──────────────────┬──────────────────┬───────────────────────────┘
                   │                  │
              ┌────▼────┐        ┌────▼────┐
              │ API     │        │ API     │
              │ Worker1 │        │ Worker2 │
              └────┬────┘        └────┬────┘
                   └────────┬─────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
        ┌─────▼──────┐ ┌───▼───┐ ┌───────▼──────┐
        │ TimescaleDB│ │ Redis │ │  TimescaleDB  │
        │  (primary) │ │ Cache │ │   (replica)   │
        │  Writes    │ │ Rate  │ │   Reads       │
        └────────────┘ └───────┘ └──────────────┘
```

**Event ingestion flow:**

1. Visitor lands on `acme.com`
2. JS snippet fires `POST /api/v1/events` with the page URL, referrer, and user agent
3. API validates the tenant JWT, writes to the `events` and `pageviews` tables in TimescaleDB
4. Redis cache for that tenant is invalidated, then pre-warmed with fresh aggregations in the background
5. API returns `202 Accepted` in under 50ms — visitor never notices

**Dashboard query flow:**

1. Dashboard user logs in → receives a JWT access token (15 min TTL) and a refresh token (7 days TTL)
2. Calls `GET /api/v1/analytics/pageviews`
3. API checks Redis cache first — cache hit returns instantly
4. On cache miss, queries TimescaleDB using `time_bucket()` to aggregate events by hour
5. Result is cached in Redis for 5 minutes and returned

---

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| API framework | FastAPI + Uvicorn | Async-native, fast, automatic OpenAPI docs |
| Database | TimescaleDB (Postgres extension) | Time-series partitioning for high-volume event tables |
| Cache + rate limiting | Redis 7 | Sub-millisecond reads, sliding window rate limiter, token blacklist |
| Reverse proxy | Nginx | Rate limiting, load balancing across two API workers |
| Containers | Docker + docker-compose | Full multi-service orchestration in one command |
| Migrations | Plain SQL files | No ORM magic — full control over schema |
| Auth | JWT (access + refresh tokens) | Stateless auth, refresh token rotation, logout blacklisting |
| DB driver | asyncpg | Pure async PostgreSQL driver — no SQLAlchemy ORM |
| Testing | pytest + pytest-asyncio + httpx + fakeredis | Full unit and integration test suite |

---

## Architecture decisions worth knowing

**No ORM.** Every database query is raw SQL written explicitly using asyncpg. This gives full control over query performance and makes every query readable without knowing SQLAlchemy's abstraction layer.

**TimescaleDB hypertable.** The `events` table is a TimescaleDB hypertable partitioned by `occurred_at` in 7-day chunks. When querying the last 30 days of events, TimescaleDB only scans the relevant 4-5 chunks instead of the entire table — the difference between a 50ms query and a 5 second one at scale.

**Read/write split.** Write operations (event ingestion, auth) go to the primary database pool. Read operations (analytics queries) go to a replica pool. Under load, dashboard queries don't compete with incoming events for database connections.

**Two-layer rate limiting.** Nginx limits at 30 requests/minute at the network level before a request reaches Python. The Redis sliding window limiter inside the app enforces 100 requests/60 seconds per tenant. Two independent layers means even if one is bypassed, the other holds.

**Refresh token rotation.** Every time a refresh token is used to get a new access token, the old refresh token is immediately blacklisted in Redis and a new one is issued. A stolen token can only be used once before it's dead.

**Multi-tenancy via `tenant_id`.** Every table has a `tenant_id` column. Every query filters by it. There are no separate schemas or databases per tenant — row-level isolation with composite indexes on `(tenant_id, occurred_at)` keeps queries fast.

---

## Project structure

```
pulse-analytics/
├── docker-compose.yml          ← orchestrates all 6 services
├── nginx/
│   └── nginx.conf              ← rate limiting + load balancing config
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── migrations/
│   │   ├── 001_initial_schema.sql   ← full schema + TimescaleDB hypertable
│   │   └── run_migrations.py        ← migration runner
│   └── app/
│       ├── main.py             ← FastAPI app + lifespan hooks
│       ├── core/
│       │   ├── config.py       ← Pydantic Settings (reads from .env)
│       │   ├── db.py           ← asyncpg primary + replica pools
│       │   ├── redis.py        ← Redis connection pool
│       │   └── security.py     ← JWT encode/decode, bcrypt hashing
│       ├── api/
│       │   ├── deps.py         ← shared DI (HTTPBearer, get_current_tenant)
│       │   └── v1/
│       │       ├── auth.py     ← register, login, refresh, logout
│       │       ├── events.py   ← POST /events (ingestion)
│       │       ├── analytics.py← pageviews, top pages, event breakdown
│       │       └── tenants.py  ← tenant management
│       ├── schemas/            ← Pydantic request/response models
│       ├── services/           ← business logic + raw SQL queries
│       ├── middleware/
│       │   └── rate_limit.py   ← sliding window rate limiter
│       └── workers/
│           └── cache_warmer.py ← background cache invalidation + warming
└── tests/
    ├── unit/                   ← security, cache, rate limiter tests
    └── integration/            ← full HTTP tests for all endpoints
```

---

## Local setup

### Prerequisites

- Docker Desktop
- Git

That's it. Everything else (Python, Postgres, Redis, Nginx) runs inside Docker.

### 1. Clone the repo

```bash
git clone https://github.com/MRiDuL-ICE/pulse-analytics.git
cd pulse-analytics
```

### 2. Create your environment file

```bash
cp .env.example .env
```

Open `.env` and set your values. The defaults work for local development without changes.

### 3. Start all services

```bash
docker compose up --build
```

This starts 6 services: Postgres (primary), Postgres (replica), Redis, two FastAPI workers, and Nginx. First run takes 2–3 minutes while Docker pulls images and installs Python dependencies.

Wait until you see:

```
api_1  | Worker 1 — all pools ready.
api_2  | Worker 2 — all pools ready.
```

### 4. Run database migrations

In a second terminal:

```bash
docker compose exec api_1 python migrations/run_migrations.py
```

Output:

```
  applying 001_initial_schema.sql ...
  done ✓
All migrations applied.
```

### 5. Verify everything is running

```bash
curl http://localhost/health
# {"status":"ok"}

curl http://localhost/docs
# Open in browser — Swagger UI with all endpoints
```

---

## API reference

All endpoints are available at `http://localhost:8000 or http://localhost`. The Swagger UI at `/docs` lets you test them interactively.

### Authentication

Pulse Analytics uses JWT Bearer tokens. Every protected endpoint requires:

```
Authorization: Bearer <your_access_token>
```

Access tokens expire in 15 minutes. Use the refresh token to get a new pair without logging in again.

---

### `POST /api/v1/auth/register`

Creates a new tenant and user account in one step.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@yourcompany.com",
    "password": "your_password",
    "tenant_name": "Your Company",
    "tenant_slug": "your-company"
  }'
```

**Response `201`:**
```json
{
  "id": "4295bf74-3bc3-411d-88bd-8dba8a4562a2",
  "email": "you@yourcompany.com",
  "tenant_id": "5ab8e3a0-7cc7-4cc8-812b-e210676f6292",
  "is_active": true,
  "created_at": "2026-04-25T12:00:00Z"
}
```

---

### `POST /api/v1/auth/login`

Returns an access token and refresh token.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=you@yourcompany.com&password=your_password"
```

> Note: the field is named `username` because this follows the OAuth2 spec. Pass your email as the value.

**Response `200`:**
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

---

### `POST /api/v1/auth/refresh`

Exchange a refresh token for a new access + refresh token pair. The old refresh token is immediately blacklisted.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "eyJhbGci..."}'
```

---

### `POST /api/v1/auth/logout`

Blacklists the refresh token so it can never be used again. Requires a valid access token.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "eyJhbGci..."}'
```

**Response: `204 No Content`**

---

### `POST /api/v1/events`

Ingests a tracking event. This is the endpoint your JS snippet calls.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "pageview",
    "url": "/pricing",
    "referrer": "https://google.com",
    "session_id": "sess_abc123",
    "properties": {
      "title": "Pricing Page"
    }
  }'
```

**Supported `event_type` values:** any string — `pageview`, `click`, `conversion`, `signup`, `purchase`, or anything you define. Events with `event_type: "pageview"` are also written to the dedicated `pageviews` table for faster aggregation.

**Response `202`:**
```json
{
  "accepted": true,
  "event_id": "7f3a1b2c-..."
}
```

---

### `GET /api/v1/analytics/pageviews`

Returns hourly pageview counts for your tenant over a time range. Uses TimescaleDB's `time_bucket()` for efficient aggregation.

**Request:**
```bash
curl "http://localhost:8000/api/v1/analytics/pageviews" \
  -H "Authorization: Bearer <access_token>"

# With custom date range:
curl "http://localhost:8000/api/v1/analytics/pageviews?start=2026-04-01T00:00:00Z&end=2026-04-30T23:59:59Z" \
  -H "Authorization: Bearer <access_token>"
```

**Default range:** last 7 days.

**Response `200`:**
```json
{
  "tenant_id": "5ab8e3a0-...",
  "data": [
    { "bucket": "2026-04-25T10:00:00+00:00", "count": 142 },
    { "bucket": "2026-04-25T11:00:00+00:00", "count": 89 },
    { "bucket": "2026-04-25T12:00:00+00:00", "count": 201 }
  ]
}
```

---

### `GET /api/v1/analytics/top-pages`

Returns the most visited URLs ranked by pageview count.

**Request:**
```bash
curl "http://localhost:8000/api/v1/analytics/top-pages?limit=10" \
  -H "Authorization: Bearer <access_token>"
```

**Query parameters:**
- `limit` — number of results (1–100, default 10)
- `start` / `end` — ISO 8601 datetime range (default last 7 days)

**Response `200`:**
```json
{
  "tenant_id": "5ab8e3a0-...",
  "data": [
    { "url": "/home", "count": 1432 },
    { "url": "/pricing", "count": 876 },
    { "url": "/about", "count": 341 }
  ]
}
```

---

### `GET /api/v1/analytics/events`

Returns a breakdown of all event types and their counts.

**Request:**
```bash
curl "http://localhost:8000/api/v1/analytics/events" \
  -H "Authorization: Bearer <access_token>"
```

**Response `200`:**
```json
{
  "tenant_id": "5ab8e3a0-...",
  "data": [
    { "event_type": "pageview", "count": 4821 },
    { "event_type": "click", "count": 1203 },
    { "event_type": "conversion", "count": 47 }
  ]
}
```

---

### `GET /api/v1/tenants/me`

Returns your tenant's details.

```bash
curl http://localhost:8000/api/v1/tenants/me \
  -H "Authorization: Bearer <access_token>"
```

### `PATCH /api/v1/tenants/me`

Updates your tenant name or slug.

```bash
curl -X PATCH http://localhost:8000/api/v1/tenants/me \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "New Company Name"}'
```

### `DELETE /api/v1/tenants/me`

Soft-deletes your tenant (sets `is_active = false`).

---

## Multi-tenancy — how data isolation works

Every table in the database has a `tenant_id` column. When you register, a tenant row is created and all your users, events, and funnels are linked to it via foreign key.

Every API request goes through this chain:

```
HTTP request
    → Bearer token extracted from Authorization header
    → JWT decoded → tenant_id claim extracted
    → tenant_id injected into every database query via WHERE tenant_id = $1
```

Acme Corp's events are physically in the same `events` table as Beta Startup's — but every query filters by `tenant_id` so neither can ever see the other's data. Composite indexes on `(tenant_id, occurred_at)` make these filtered queries as fast as if the data were in separate tables.

There is no way to query another tenant's data through the API. The `tenant_id` always comes from the verified JWT, never from the request body.

---

## JS tracking snippet

Add this to any website to start sending events to your Pulse Analytics instance. Replace `YOUR_API_URL` with your deployed URL and `YOUR_ACCESS_TOKEN` with a valid JWT from the login endpoint.

```html
<script>
  (function() {
    var PULSE_URL = "https://YOUR_API_URL";
    var PULSE_TOKEN = "YOUR_ACCESS_TOKEN";

    function track(eventType, properties) {
      fetch(PULSE_URL + "/api/v1/events", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer " + PULSE_TOKEN
        },
        body: JSON.stringify({
          event_type: eventType,
          url: window.location.pathname,
          referrer: document.referrer,
          session_id: sessionStorage.getItem("pulse_sid") || generateId(),
          properties: properties || {}
        })
      }).catch(function() {});  // fail silently — never block the page
    }

    function generateId() {
      var id = Math.random().toString(36).slice(2);
      sessionStorage.setItem("pulse_sid", id);
      return id;
    }

    // Auto-track pageview on load
    window.addEventListener("load", function() {
      track("pageview", { title: document.title });
    });

    // Expose for manual event tracking
    window.pulse = { track: track };
  })();
</script>
```

**Manual event tracking usage:**

```javascript
// Track a button click
document.getElementById("signup-btn").addEventListener("click", function() {
  window.pulse.track("click", { element_id: "signup-btn" });
});

// Track a conversion
window.pulse.track("conversion", { plan: "pro", amount: 49 });
```

---

## Running tests

```bash
# Run all tests with coverage report
docker compose exec api_1 pytest tests/ -v --cov=app --cov-report=term-missing

# Unit tests only (no database needed)
docker compose exec api_1 pytest tests/unit/ -v

# Integration tests only
docker compose exec api_1 pytest tests/integration/ -v

# Single file
docker compose exec api_1 pytest tests/integration/test_auth.py -v
```

The test suite covers:
- JWT token creation, signing, expiry, tampering detection
- Password hashing and verification
- Cache key generation and tenant isolation
- Sliding window rate limiter logic
- Full HTTP integration tests for auth, events, analytics, and tenant management

---

## Rate limiting

Two independent layers protect the API:

**Nginx layer (first):** 30 requests/minute per IP address. Blocks abusive traffic before it reaches Python.

**Redis sliding window (second):** 100 requests/60 seconds per tenant. Uses a Redis sorted set to track exact request timestamps. If a request comes in over the limit, the API returns:

```json
HTTP 429 Too Many Requests
Retry-After: 45

{
  "detail": "Rate limit exceeded. Try again later.",
  "retry_after_seconds": 45
}
```

---

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `POSTGRES_USER` | Database username | `pulse_user` |
| `POSTGRES_PASSWORD` | Database password | — |
| `POSTGRES_DB` | Database name | `pulse_db` |
| `POSTGRES_HOST` | DB hostname (inside Docker) | `db` |
| `POSTGRES_PORT` | DB port (inside Docker) | `5432` |
| `POSTGRES_REPLICA_HOST` | Replica hostname | `db_replica` |
| `POSTGRES_REPLICA_PORT` | Replica port | `5432` |
| `REDIS_HOST` | Redis hostname | `redis` |
| `REDIS_PORT` | Redis port | `6379` |
| `SECRET_KEY` | JWT signing secret — change in production | — |
| `DEBUG` | Logs all SQL queries when `true` | `false` |
| `WORKER_ID` | Set per container to identify workers in logs | — |

---

## What's next

The backend API is complete. Planned next steps:

- **Next.js dashboard** — charts for pageviews, top pages, event breakdown using the analytics endpoints
- **Production deployment** — Railway or Oracle Cloud Always Free (4 OCPUs, 24GB RAM)
- **Funnel analysis** — track multi-step user journeys through `funnels` and `funnel_steps` tables (schema already in place)
- **Alerting** — webhook notifications when traffic spikes or drops

---

## Author

Abdul Wahab — Full Stack Software Engineer  
[GitHub](https://github.com/YOUR_USERNAME) · [Upwork](https://upwork.com/YOUR_PROFILE)