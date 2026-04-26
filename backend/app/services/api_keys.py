import hashlib
import secrets
import uuid

from fastapi import HTTPException, status
from passlib.context import CryptContext

import app.core.db as db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _generate_raw_key() -> str:
    """
    Generates a cryptographically secure random API key.
    Format: pk_live_<32 random chars>
    Example: pk_live_a8f3k2m9x1q7z4n6
    """
    random_part = secrets.token_urlsafe(24)  # 32 chars URL-safe base64
    return f"pk_live_{random_part}"


def _hash_key(raw_key: str) -> str:
    """bcrypt hash of the full key — stored in DB, never the raw key."""
    return pwd_context.hash(raw_key)


def _verify_key(raw_key: str, hashed: str) -> bool:
    return pwd_context.verify(raw_key, hashed)


def _extract_prefix(raw_key: str) -> str:
    """First 15 chars shown in the dashboard e.g. 'pk_live_a8f3k2'"""
    return raw_key[:15]


async def create_api_key(tenant_id: str, name: str) -> dict:
    """
    Creates a new write-only API key for a tenant.
    Returns the raw key ONCE — it is never stored and cannot be retrieved again.
    """
    raw_key = _generate_raw_key()
    key_hash = _hash_key(raw_key)
    prefix = _extract_prefix(raw_key)

    row = await db.fetchrow(
        """
        INSERT INTO api_keys (tenant_id, name, key_prefix, key_hash)
        VALUES ($1, $2, $3, $4)
        RETURNING id, tenant_id, name, key_prefix, is_active, created_at
        """,
        uuid.UUID(tenant_id),
        name,
        prefix,
        key_hash,
    )

    result = dict(row)
    # Include raw key in response — this is the ONLY time it's returned
    result["key"] = raw_key
    result["warning"] = "Save this key now. It will never be shown again."
    return result


async def list_api_keys(tenant_id: str) -> list[dict]:
    """Lists all API keys for a tenant — never returns the raw key."""
    rows = await db.fetch(
        """
        SELECT id, tenant_id, name, key_prefix, is_active, last_used_at, created_at
        FROM api_keys
        WHERE tenant_id = $1
        ORDER BY created_at DESC
        """,
        uuid.UUID(tenant_id),
    )
    return [dict(row) for row in rows]


async def revoke_api_key(key_id: str, tenant_id: str) -> None:
    """
    Revokes an API key by setting is_active = false.
    Verifies the key belongs to the requesting tenant — tenants cannot
    revoke each other's keys.
    """
    row = await db.fetchrow(
        "SELECT id FROM api_keys WHERE id = $1 AND tenant_id = $2",
        uuid.UUID(key_id),
        uuid.UUID(tenant_id),
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    await db.execute(
        "UPDATE api_keys SET is_active = FALSE WHERE id = $1",
        uuid.UUID(key_id),
    )


async def verify_api_key(raw_key: str) -> str | None:
    """
    Validates an incoming API key from a request header.
    Returns the tenant_id if valid, None if invalid.

    Uses the key_prefix to narrow down candidates before bcrypt comparison
    so we don't bcrypt-check every key in the table on every request.
    """
    prefix = _extract_prefix(raw_key)

    rows = await db.fetch(
        """
        SELECT id, tenant_id, key_hash
        FROM api_keys
        WHERE key_prefix = $1
          AND is_active = TRUE
        """,
        prefix,
    )

    for row in rows:
        if _verify_key(raw_key, row["key_hash"]):
            # Update last_used_at without blocking the response
            await db.execute(
                "UPDATE api_keys SET last_used_at = NOW() WHERE id = $1",
                row["id"],
            )
            return str(row["tenant_id"])

    return None