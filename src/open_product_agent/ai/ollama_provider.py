from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from open_product_agent.ai.base import AIProvider
from open_product_agent.ai.prompts import build_item_analysis_messages, build_repair_messages
from open_product_agent.ai.schemas import ITEM_ANALYSIS_SCHEMA
from open_product_agent.ai.validator import AnalysisValidationError, parse_and_validate_item_analysis


class OllamaProvider(AIProvider):
    provider_name = "ollama"

    def __init__(
        self,
        *,
        model: str,
        temperature: float = 0,
        base_url: str | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
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
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": ITEM_ANALYSIS_SCHEMA,
            "options": {
                "temperature": self.temperature,
            },
        }
        response = self._post_json("/api/chat", payload)
        self.last_token_usage = {
            "input_tokens": response.get("prompt_eval_count", 0),
            "output_tokens": response.get("eval_count", 0),
        }
        message = response.get("message")
        if not isinstance(message, dict):
            return json.dumps({})
        content = message.get("content")
        return content if isinstance(content, str) else json.dumps({})

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama request failed with HTTP {exc.code}: {body}") from exc
        except URLError as exc:
            raise RuntimeError(f"Could not connect to Ollama at {self.base_url}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned invalid JSON.") from exc
