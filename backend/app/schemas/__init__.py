import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


# ── Tenant ────────────────────────────────────────────────

class TenantCreate(BaseModel):
    name: str
    slug: str


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── User ──────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    tenant_name: str
    tenant_slug: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    tenant_id: uuid.UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Auth ──────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str