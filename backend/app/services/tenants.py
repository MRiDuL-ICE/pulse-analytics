from fastapi import HTTPException, status

import app.core.db as db


async def get_tenant_by_id(tenant_id: str) -> dict:
    row = await db.fetchrow(
        """
        SELECT id, name, slug, is_active, created_at
        FROM tenants
        WHERE id = $1
        """,
        tenant_id,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return dict(row)


async def update_tenant(tenant_id: str, updates: dict) -> dict:
    # Check slug uniqueness if slug is being changed
    if "slug" in updates:
        existing = await db.fetchrow(
            "SELECT id FROM tenants WHERE slug = $1 AND id != $2",
            updates["slug"],
            tenant_id,
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Slug already taken",
            )

    set_clause = ", ".join(
        f"{col} = ${i + 2}" for i, col in enumerate(updates.keys())
    )
    values = list(updates.values())

    row = await db.fetchrow(
        f"""
        UPDATE tenants
        SET {set_clause}
        WHERE id = $1
        RETURNING id, name, slug, is_active, created_at
        """,
        tenant_id,
        *values,
    )
    return dict(row)


async def deactivate_tenant(tenant_id: str) -> None:
    await db.execute(
        "UPDATE tenants SET is_active = FALSE WHERE id = $1",
        tenant_id,
    )