from __future__ import annotations

from typing import Any


def estimate_cost_usd(
    token_usage: dict[str, Any],
    *,
    input_cost_per_1m: float | None,
    output_cost_per_1m: float | None,
) -> float | None:
    if input_cost_per_1m is None or output_cost_per_1m is None:
        return None

    input_tokens = _token_count(token_usage, "input_tokens", "prompt_tokens")
    output_tokens = _token_count(token_usage, "output_tokens", "completion_tokens")
    return round(
        (input_tokens / 1_000_000 * input_cost_per_1m)
        + (output_tokens / 1_000_000 * output_cost_per_1m),
        8,
    )


def _token_count(token_usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = token_usage.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
    return 0
