from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from open_product_agent.models.item import Item, ItemSnapshot

from .normalizer import normalize_record


def load_json(path: Path, *, domain: str, import_run_id: str) -> list[tuple[Item, ItemSnapshot]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    records = _records_from_payload(payload)
    return [
        normalize_record(record, domain=domain, import_run_id=import_run_id)
        for record in records
    ]


def _records_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
        records = payload["items"]
    elif isinstance(payload, dict):
        records = [payload]
    else:
        raise ValueError("JSON import must contain an object, an item list, or an object with items.")

    if not all(isinstance(record, dict) for record in records):
        raise ValueError("Every imported JSON item must be an object.")
    return records
