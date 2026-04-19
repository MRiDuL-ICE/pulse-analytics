import uuid
from datetime import datetime

from pydantic import BaseModel


class EventPayload(BaseModel):
    event_type: str
    session_id: str | None = None
    url: str | None = None
    referrer: str | None = None
    properties: dict = {}


class EventOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    event_type: str
    url: str | None
    occurred_at: datetime

    model_config = {"from_attributes": True}