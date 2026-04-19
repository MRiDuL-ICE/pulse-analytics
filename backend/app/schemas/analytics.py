from pydantic import BaseModel


class PageviewBucket(BaseModel):
    bucket: str
    count: int


class TopPage(BaseModel):
    url: str
    count: int


class EventTypeCount(BaseModel):
    event_type: str
    count: int