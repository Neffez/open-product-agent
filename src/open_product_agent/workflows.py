from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import yaml

from open_product_agent.ai.cost_tracker import estimate_cost_usd
from open_product_agent.ai.prompts import PROMPT_VERSION
from open_product_agent.ai.providers import create_provider
from open_product_agent.ai.validator import parse_and_validate_item_analysis
from open_product_agent.database.store import Store
from open_product_agent.domain_packs.loader import load_domain_pack
from open_product_agent.importers.csv_importer import load_csv
from open_product_agent.importers.html_importer import load_html
from open_product_agent.importers.json_importer import load_json
from open_product_agent.models.analysis import AIAnalysisRun
from open_product_agent.models.feedback import FeedbackEvent, FeedbackType
from open_product_agent.models.item import ImportRun, Item, ItemSnapshot
from open_product_agent.models.profile import ProductProfile, ProductProfileEnvelope
from open_product_agent.reports.markdown import render_report
from open_product_agent.scoring.basic import calculate_scores, profile_id_from_name

Loader = Callable[[Path], list[tuple[Item, ItemSnapshot]]]


def load_profile(path: Path) -> ProductProfile:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return ProductProfileEnvelope.model_validate(data).profile


def import_paths(
    paths: list[Path],
    *,
    profile_path: Path,
    db_path: Path,
    import_type: str,
) -> ImportRun:
    profile = load_profile(profile_path)
    profile_id = profile_id_from_name(profile.name)
    store = Store(db_path)
    store.init()
    store.save_profile(profile_id, profile)

    started_at = datetime.now(UTC)
    import_run = ImportRun(
        id=f"run_{uuid4().hex}",
        source_id=f"{import_type}_batch",
        started_at=started_at,
        status="running",
    )
    loader = _loader_for(import_type, profile.domain, import_run.id)

    items_created = 0
    items_updated = 0
    errors: list[str] = []
    items_seen = 0
    for path in paths:
        try:
            records = loader(path)
        except Exception as exc:
            errors.append(f"{path}: {exc}")
            continue
        items_seen += len(records)
        for item, snapshot in records:
            if store.upsert_item_with_snapshot(item, snapshot):
                items_created += 1
            else:
                items_updated += 1

    import_run.status = "completed" if not errors else "completed_with_errors"
    import_run.finished_at = datetime.now(UTC)
    import_run.items_seen = items_seen
    import_run.items_created = items_created
    import_run.items_updated = items_updated
    import_run.errors = errors
    store.save_import_run(import_run)
    return import_run


def score_profile(
    *,
    profile_path: Path,
    db_path: Path,
    domain_pack_path: Path | None = None,
) -> int:
    profile = load_profile(profile_path)
    domain_pack = load_domain_pack(profile.domain, domain_pack_path)
    profile_id = profile_id_from_name(profile.name)
    store = Store(db_path)
    store.init()
    store.save_profile(profile_id, profile)
    items = store.list_items(domain=profile.domain)
    analyses_by_item = {
        item_id: analysis.output or {}
        for item_id, analysis in store.list_latest_valid_analyses(profile_id).items()
    }
    feedback_by_item = _group_feedback(store.list_feedback_events(profile_id))
    scores = calculate_scores(
        profile,
        items,
        profile_id=profile_id,
        domain_pack=domain_pack,
        analyses_by_item=analyses_by_item,
        feedback_by_item=feedback_by_item,
    )
    store.save_scores(scores)
    return len(scores)


def analyze_profile(
    *,
    profile_path: Path,
    db_path: Path,
    provider_name: str,
    model: str,
    domain_pack_path: Path | None = None,
    limit: int | None = None,
    input_cost_per_1m: float | None = None,
    output_cost_per_1m: float | None = None,
) -> tuple[int, int]:
    profile = load_profile(profile_path)
    domain_pack = load_domain_pack(profile.domain, domain_pack_path)
    if domain_pack is None:
        raise ValueError(f"No domain pack found for domain: {profile.domain}")

    profile_id = profile_id_from_name(profile.name)
    store = Store(db_path)
    store.init()
    store.save_profile(profile_id, profile)
    provider = create_provider(provider_name, model=model, temperature=0)
    items = store.list_items(domain=profile.domain)
    if limit is not None:
        items = items[:limit]

    analyzed = 0
    failed = 0
    for item in items:
        snapshot = store.get_latest_snapshot(item.id)
        if snapshot is None:
            continue

        input_payload = {
            "profile": profile.model_dump(mode="json"),
            "domain_pack": domain_pack.model_dump(mode="json"),
            "item_snapshot": snapshot.model_dump(mode="json"),
        }
        validation_status = "valid"
        output: dict[str, object] | None = None
        try:
            raw_output = provider.analyze_item(
                profile=input_payload["profile"],
                item_snapshot=input_payload["item_snapshot"],
                domain_pack=input_payload["domain_pack"],
            )
            output = parse_and_validate_item_analysis(raw_output).model_dump(mode="json")
            analyzed += 1
        except Exception as exc:
            validation_status = "analysis_failed"
            output = {"error": str(exc)}
            failed += 1

        token_usage = getattr(provider, "last_token_usage", {})
        store.save_analysis_run(
            AIAnalysisRun(
                id=f"analysis_{uuid4().hex}",
                item_id=item.id,
                snapshot_id=snapshot.id,
                profile_id=profile_id,
                domain_pack_id=f"{domain_pack.domain}@{domain_pack.version}",
                provider=provider_name,
                model=model,
                prompt_version=PROMPT_VERSION,
                input_hash=_hash_payload(input_payload),
                output=output,
                validation_status=validation_status,
                token_usage=token_usage,
                estimated_cost=estimate_cost_usd(
                    token_usage,
                    input_cost_per_1m=input_cost_per_1m,
                    output_cost_per_1m=output_cost_per_1m,
                ),
                created_at=datetime.now(UTC),
            )
        )
    return analyzed, failed


def render_profile_report(*, profile_path: Path, db_path: Path, top: int) -> str:
    profile = load_profile(profile_path)
    profile_id = profile_id_from_name(profile.name)
    store = Store(db_path)
    store.init()
    scores = store.list_scores(profile_id)
    analyses_by_item = {
        item_id: analysis.output or {}
        for item_id, analysis in store.list_latest_valid_analyses(profile_id).items()
    }
    scored_items = [
        (item, score)
        for score in scores
        if (item := store.get_item(score.item_id)) is not None
    ]
    return render_report(
        profile=profile,
        scored_items=scored_items,
        top=top,
        analyses_by_item=analyses_by_item,
    )


def add_feedback_event(
    *,
    profile_path: Path,
    db_path: Path,
    item_id: str,
    feedback_type: FeedbackType,
    reason: str | None = None,
) -> FeedbackEvent:
    profile = load_profile(profile_path)
    profile_id = profile_id_from_name(profile.name)
    store = Store(db_path)
    store.init()
    store.save_profile(profile_id, profile)
    if store.get_item(item_id) is None:
        raise ValueError(f"Unknown item id: {item_id}")
    event = FeedbackEvent(
        id=f"feedback_{uuid4().hex}",
        item_id=item_id,
        profile_id=profile_id,
        feedback_type=feedback_type,
        reason=reason,
        created_at=datetime.now(UTC),
    )
    store.save_feedback_event(event)
    return event


def list_feedback_for_profile(
    *,
    profile_path: Path,
    db_path: Path,
    item_id: str | None = None,
) -> list[FeedbackEvent]:
    profile = load_profile(profile_path)
    profile_id = profile_id_from_name(profile.name)
    store = Store(db_path)
    store.init()
    return store.list_feedback_events(profile_id, item_id=item_id)


def _loader_for(import_type: str, domain: str, import_run_id: str) -> Loader:
    if import_type == "csv":
        return lambda path: load_csv(path, domain=domain, import_run_id=import_run_id)
    if import_type == "json":
        return lambda path: load_json(path, domain=domain, import_run_id=import_run_id)
    if import_type == "html":
        return lambda path: load_html(path, domain=domain, import_run_id=import_run_id)
    raise ValueError(f"Unsupported import type: {import_type}")


def _hash_payload(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _group_feedback(events: list[FeedbackEvent]) -> dict[str, list[FeedbackEvent]]:
    grouped: dict[str, list[FeedbackEvent]] = {}
    for event in events:
        grouped.setdefault(event.item_id, []).append(event)
    return grouped
