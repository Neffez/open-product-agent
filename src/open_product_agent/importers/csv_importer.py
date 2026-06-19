from __future__ import annotations

import csv
from pathlib import Path

from open_product_agent.models.item import Item, ItemSnapshot

from .normalizer import normalize_record


def load_csv(path: Path, *, domain: str, import_run_id: str) -> list[tuple[Item, ItemSnapshot]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        normalize_record(row, domain=domain, import_run_id=import_run_id)
        for row in rows
    ]
