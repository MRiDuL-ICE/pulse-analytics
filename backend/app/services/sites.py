import uuid
from fastapi import HTTPException, status
import app.core.db as db


async def create_site(tenant_id: str, name: str, domain: str) -> dict:
    # Normalise domain — strip protocol and trailing slash
    domain = domain.lower().replace("https://", "").replace("http://", "").rstrip("/")

    # Check uniqueness within tenant
    existing = await db.fetchrow(
        "SELECT id FROM sites WHERE tenant_id = $1 AND domain = $2",
        uuid.UUID(tenant_id), domain,
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Site with domain '{domain}' already exists in your workspace",
        )

    row = await db.fetchrow(
        """
        INSERT INTO sites (tenant_id, name, domain)
        VALUES ($1, $2, $3)
        RETURNING id, tenant_id, name, domain, is_active, created_at
        """,
        uuid.UUID(tenant_id), name, domain,
    )
    return dict(row)


async def list_sites(tenant_id: str) -> list[dict]:
    rows = await db.fetch(
        """
        SELECT s.id, s.tenant_id, s.name, s.domain, s.is_active, s.created_at,
               COUNT(ak.id) FILTER (WHERE ak.is_active) AS active_keys
        FROM sites s
        LEFT JOIN api_keys ak ON ak.site_id = s.id
        WHERE s.tenant_id = $1
        GROUP BY s.id
        ORDER BY s.created_at DESC
        """,
        uuid.UUID(tenant_id),
    )
    return [dict(row) for row in rows]


async def get_site(site_id: str, tenant_id: str) -> dict:
    row = await db.fetchrow(
        """
        SELECT id, tenant_id, name, domain, is_active, created_at
        FROM sites WHERE id = $1 AND tenant_id = $2
        """,
        uuid.UUID(site_id), uuid.UUID(tenant_id),
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return dict(row)


async def update_site(site_id: str, tenant_id: str, updates: dict) -> dict:
    if "domain" in updates:
        updates["domain"] = updates["domain"].lower().replace("https://", "").replace("http://", "").rstrip("/")
        existing = await db.fetchrow(
            "SELECT id FROM sites WHERE tenant_id = $1 AND domain = $2 AND id != $3",
            uuid.UUID(tenant_id), updates["domain"], uuid.UUID(site_id),
        )
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Domain already in use")

    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
    row = await db.fetchrow(
        f"""
        UPDATE sites SET {set_clause}
        WHERE id = $1 AND tenant_id = ${len(updates)+2}
        RETURNING id, tenant_id, name, domain, is_active, created_at
        """,
        uuid.UUID(site_id), *updates.values(), uuid.UUID(tenant_id),
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return dict(row)


async def deactivate_site(site_id: str, tenant_id: str) -> None:
    result = await db.execute(
        "UPDATE sites SET is_active = FALSE WHERE id = $1 AND tenant_id = $2",
        uuid.UUID(site_id), uuid.UUID(tenant_id),
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")