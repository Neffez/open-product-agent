from datetime import datetime
from typing import Literal

from pydantic import BaseModel

FeedbackType = Literal[
    "too_expensive",
    "too_far_away",
    "too_risky",
    "wrong_brand",
    "missing_feature",
    "not_my_style",
    "favorite",
    "ignore",
]


class FeedbackEvent(BaseModel):
    id: str
    item_id: str
    profile_id: str
    feedback_type: FeedbackType
    reason: str | None = None
    created_at: datetime
