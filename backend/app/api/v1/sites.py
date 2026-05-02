from fastapi import APIRouter, Depends
from app.api.deps import get_current_tenant
from app.schemas.site import SiteCreate, SiteOut, SiteUpdate
from app.services.sites import create_site, deactivate_site, get_site, list_sites, update_site

router = APIRouter(prefix="/sites", tags=["sites"])


@router.post("", response_model=SiteOut, status_code=201)
async def create(data: SiteCreate, tenant_id: str = Depends(get_current_tenant)):
    return await create_site(tenant_id, data.name, data.domain)


@router.get("", response_model=list[SiteOut])
async def list_all(tenant_id: str = Depends(get_current_tenant)):
    return await list_sites(tenant_id)


@router.get("/{site_id}", response_model=SiteOut)
async def get_one(site_id: str, tenant_id: str = Depends(get_current_tenant)):
    return await get_site(site_id, tenant_id)


@router.patch("/{site_id}", response_model=SiteOut)
async def update(site_id: str, data: SiteUpdate, tenant_id: str = Depends(get_current_tenant)):
    updates = data.model_dump(exclude_none=True)
    return await update_site(site_id, tenant_id, updates)


@router.delete("/{site_id}", status_code=204)
async def deactivate(site_id: str, tenant_id: str = Depends(get_current_tenant)):
    await deactivate_site(site_id, tenant_id)