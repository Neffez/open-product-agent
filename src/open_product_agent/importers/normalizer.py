from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from open_product_agent.models.item import Item, ItemSnapshot

CORE_FIELDS = {
    "id",
    "source_name",
    "source_url",
    "title",
    "price",
    "currency",
    "location",
    "seller_type",
    "description",
    "attributes",
}


def normalize_record(
    record: dict[str, Any],
    *,
    domain: str,
    import_run_id: str,
    observed_at: datetime | None = None,
) -> tuple[Item, ItemSnapshot]:
    observed_at = observed_at or datetime.now(UTC)
    attributes = _extract_attributes(record)
    item_id = str(record.get("id") or _stable_hash(record))
    price = _to_int(record.get("price"))

    item = Item(
        id=item_id,
        domain=domain,
        source_name=_to_str(record.get("source_name")),
        source_url=_to_str(record.get("source_url")),
        title=_to_str(record.get("title")),
        price=price,
        currency=_to_str(record.get("currency")),
        location=_to_str(record.get("location")),
        seller_type=_to_str(record.get("seller_type")),
        attributes=attributes,
        first_seen_at=observed_at,
        last_seen_at=observed_at,
    )
    snapshot = ItemSnapshot(
        id=f"snap_{_stable_hash({'run': import_run_id, 'record': record})}",
        item_id=item.id,
        import_run_id=import_run_id,
        observed_at=observed_at,
        title=item.title,
        price=item.price,
        currency=item.currency,
        description=_to_str(record.get("description")),
        raw_data=record,
        content_hash=f"sha256:{_stable_hash(record)}",
    )
    return item, snapshot


def _extract_attributes(record: dict[str, Any]) -> dict[str, Any]:
    explicit = record.get("attributes")
    attributes = explicit if isinstance(explicit, dict) else {}
    if record.get("description"):
        attributes["source_text"] = record["description"]
    for key, value in record.items():
        if key not in CORE_FIELDS and value not in (None, ""):
            attributes[key] = _coerce_scalar(value)
    return attributes


def _coerce_scalar(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped == "":
        return None
    lowered = stripped.lower()
    if lowered in {"true", "yes", "ja"}:
        return True
    if lowered in {"false", "no", "nein"}:
        return False
    integer = _to_int(stripped)
    return integer if integer is not None else stripped


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
