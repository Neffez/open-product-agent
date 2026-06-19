from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Budget(BaseModel):
    max: int | None = Field(default=None, ge=0)
    currency: str = "EUR"


class LocationPreference(BaseModel):
    country: str | None = None
    max_distance_km: int | None = Field(default=None, ge=0)


class ProductProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    domain: str
    budget: Budget | None = None
    hard_constraints: dict[str, Any] = Field(default_factory=dict)
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    usage_description: str | None = None
    risk_tolerance: Literal["low", "medium", "high"] = "medium"
    location: LocationPreference | None = None


class ProductProfileEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: ProductProfile
