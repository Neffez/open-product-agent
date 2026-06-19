from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attribute: str
    value: Any
    source_text: str
    confidence: float = Field(ge=0, le=1)


class ItemAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detected_attributes: dict[str, Any]
    risk_flags: list[str]
    positive_signals: list[str]
    missing_information: list[str]
    evidence: list[Evidence]
    seller_questions: list[str]
    short_explanation: str
    recommendation: Literal[
        "contact_seller",
        "shortlist",
        "watch",
        "skip",
        "needs_more_information",
    ]
    recommendation_reason: str
    next_steps: list[str]


class AIAnalysisRun(BaseModel):
    id: str
    item_id: str
    snapshot_id: str
    profile_id: str
    domain_pack_id: str
    provider: str
    model: str
    prompt_version: str
    input_hash: str | None = None
    output: dict[str, Any] | None = None
    validation_status: str
    token_usage: dict[str, Any] = Field(default_factory=dict)
    estimated_cost: float | None = None
    created_at: datetime
