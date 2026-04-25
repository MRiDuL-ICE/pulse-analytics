from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_tenant
from app.schemas.tenant import TenantOut, TenantUpdate
from app.services.tenants import deactivate_tenant, get_tenant_by_id, update_tenant

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/me", response_model=TenantOut)
async def get_my_tenant(
    tenant_id: str = Depends(get_current_tenant),
):
    return await get_tenant_by_id(tenant_id)


@router.patch("/me", response_model=TenantOut)
async def update_my_tenant(
    data: TenantUpdate,
    tenant_id: str = Depends(get_current_tenant),
):
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields provided to update",
        )
    return await update_tenant(tenant_id, updates)


@router.delete("/me", status_code=204)
async def deactivate_my_tenant(
    tenant_id: str = Depends(get_current_tenant),
):
    await deactivate_tenant(tenant_id)