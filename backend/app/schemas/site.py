import uuid
from datetime import datetime
from pydantic import BaseModel


class SiteCreate(BaseModel):
    name: str
    domain: str


class SiteUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None


class SiteOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    domain: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}