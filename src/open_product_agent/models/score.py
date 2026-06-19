from datetime import datetime

from pydantic import BaseModel, Field


class ItemScore(BaseModel):
    id: str
    item_id: str
    profile_id: str
    analysis_run_id: str | None = None
    fit_score: int = Field(ge=0, le=100)
    value_score: int = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    condition_score: int = Field(ge=0, le=100)
    convenience_score: int = Field(ge=0, le=100)
    overall_score: int = Field(ge=0, le=100)
    explanation: str
    created_at: datetime
