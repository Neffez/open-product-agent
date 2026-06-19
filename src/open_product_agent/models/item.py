from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class Item(BaseModel):
    id: str
    domain: str
    source_name: str | None = None
    source_url: HttpUrl | None = None
    title: str | None = None
    price: int | None = Field(default=None, ge=0)
    currency: str | None = None
    location: str | None = None
    seller_type: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    first_seen_at: datetime
    last_seen_at: datetime
    status: str = "active"


class ItemSnapshot(BaseModel):
    id: str
    item_id: str
    import_run_id: str | None = None
    observed_at: datetime
    title: str | None = None
    price: int | None = Field(default=None, ge=0)
    currency: str | None = None
    description: str | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)
    content_hash: str | None = None
