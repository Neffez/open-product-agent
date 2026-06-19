from __future__ import annotations

import json
from typing import Any

PROMPT_VERSION = "item-analysis-v1"


def build_item_analysis_messages(
    *,
    profile: dict[str, Any],
    item_snapshot: dict[str, Any],
    domain_pack: dict[str, Any],
) -> list[dict[str, str]]:
    system = (
        "You analyze product listings for a self-hosted personal research tool. "
        "Extract only facts supported by the provided item snapshot. Prefer unknown "
        "or missing_information over guessing. Keep source evidence in the original "
        "language. Return only structured JSON matching the schema. Always include a "
        "decision-oriented recommendation, a concise recommendation_reason, and "
        "practical next_steps the user can take before contacting or rejecting the item."
    )
    user_payload = {
        "profile": profile,
        "domain_pack": domain_pack,
        "item_snapshot": item_snapshot,
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, sort_keys=True)},
    ]


def build_repair_messages(
    *,
    invalid_payload: str,
    validation_error: str,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Repair the JSON so it matches the required item analysis schema. "
                "Return only valid JSON and do not add unsupported facts."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "invalid_payload": invalid_payload,
                    "validation_error": validation_error,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        },
    ]
