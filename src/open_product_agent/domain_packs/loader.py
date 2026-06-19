from __future__ import annotations

from pathlib import Path

import yaml

from open_product_agent.models.domain_pack import DomainPack


def load_domain_pack(domain: str, path: Path | None = None) -> DomainPack | None:
    domain_path = path or Path("domains") / domain / "domain.yml"
    if not domain_path.exists():
        return None
    with domain_path.open("r", encoding="utf-8") as handle:
        return DomainPack.model_validate(yaml.safe_load(handle))
