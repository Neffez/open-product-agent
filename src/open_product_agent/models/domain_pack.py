from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DomainField(BaseModel):
    name: str
    type: str = "string"
    required: bool = False
    description: str | None = None


class DomainPack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    version: str
    schema_version: int = Field(ge=1)
    display_name: str
    supported_languages: list[str] = Field(default_factory=list)
    fields: list[DomainField] = Field(default_factory=list)
    synonyms: dict[str, list[str] | dict[str, list[str]]] = Field(default_factory=dict)
    risk_flags: list[str] = Field(default_factory=list)
    positive_signals: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    scoring_hints: dict[str, Any] = Field(default_factory=dict)
