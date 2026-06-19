from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from open_product_agent.models.analysis import ItemAnalysis


class AnalysisValidationError(ValueError):
    pass


def parse_and_validate_item_analysis(payload: str | dict[str, Any]) -> ItemAnalysis:
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise AnalysisValidationError(f"Invalid JSON: {exc}") from exc
    else:
        data = payload

    try:
        return ItemAnalysis.model_validate(data)
    except ValidationError as exc:
        raise AnalysisValidationError(str(exc)) from exc
