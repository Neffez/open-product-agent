from __future__ import annotations

import json
from typing import Any

from open_product_agent.ai.base import AIProvider
from open_product_agent.ai.prompts import build_item_analysis_messages, build_repair_messages
from open_product_agent.ai.schemas import ITEM_ANALYSIS_SCHEMA, ITEM_ANALYSIS_SCHEMA_NAME
from open_product_agent.ai.validator import AnalysisValidationError, parse_and_validate_item_analysis


class OpenAIProvider(AIProvider):
    provider_name = "openai"

    def __init__(self, *, model: str, temperature: float = 0) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The OpenAI provider requires the 'openai' package. "
                "Install project dependencies with `python -m pip install -e .`."
            ) from exc

        self.model = model
        self.temperature = temperature
        self.client = OpenAI()
        self.last_token_usage: dict[str, Any] = {}

    def generate_profile(
        self,
        user_description: str,
        domain_pack: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError("Profile generation is not implemented in Phase 3.")

    def analyze_item(
        self,
        profile: dict[str, Any],
        item_snapshot: dict[str, Any],
        domain_pack: dict[str, Any],
    ) -> dict[str, Any]:
        messages = build_item_analysis_messages(
            profile=profile,
            item_snapshot=item_snapshot,
            domain_pack=domain_pack,
        )
        raw_output = self._complete_json(messages)
        try:
            return parse_and_validate_item_analysis(raw_output).model_dump()
        except AnalysisValidationError as exc:
            repaired = self._complete_json(
                build_repair_messages(
                    invalid_payload=raw_output,
                    validation_error=str(exc),
                )
            )
            return parse_and_validate_item_analysis(repaired).model_dump()

    def compare_items(
        self,
        profile: dict[str, Any],
        analyzed_items: list[dict[str, Any]],
        domain_pack: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError("Item comparison is not implemented in Phase 3.")

    def _complete_json(self, messages: list[dict[str, str]]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": ITEM_ANALYSIS_SCHEMA_NAME,
                    "schema": ITEM_ANALYSIS_SCHEMA,
                    "strict": True,
                },
            },
        )
        usage = getattr(response, "usage", None)
        self.last_token_usage = usage.model_dump() if usage is not None else {}
        content = response.choices[0].message.content
        if content is None:
            return json.dumps({})
        return content
