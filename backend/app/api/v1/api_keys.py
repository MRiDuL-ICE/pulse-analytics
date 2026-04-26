from fastapi import APIRouter, Depends

from app.api.deps import get_current_tenant
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.services.api_keys import create_api_key, list_api_keys, revoke_api_key

router = APIRouter(prefix="/api-keys", tags=["api keys"])


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def generate_api_key(
    data: ApiKeyCreate,
    tenant_id: str = Depends(get_current_tenant),
):
    """
    Creates a new write-only API key for your tenant.
    The full key is returned ONCE in this response.
    Store it immediately — it cannot be retrieved again.
    """
    return await create_api_key(tenant_id, data.name)


@router.get("", response_model=list[ApiKeyOut])
async def get_api_keys(
    tenant_id: str = Depends(get_current_tenant),
):
    """Lists all API keys for your tenant. Never returns the raw key."""
    return await list_api_keys(tenant_id)


@router.delete("/{key_id}", status_code=200)
async def delete_api_key(
    key_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Revokes an API key. Revocation is permanent and immediate."""
    await revoke_api_key(key_id, tenant_id)