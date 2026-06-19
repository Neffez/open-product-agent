import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer
import yaml
from pydantic import ValidationError

from open_product_agent import __version__
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
from open_product_agent.models.domain_pack import DomainPack
from open_product_agent.models.feedback import FeedbackEvent, FeedbackType
from open_product_agent.models.item import ImportRun
from open_product_agent.models.profile import ProductProfile, ProductProfileEnvelope
from open_product_agent.reports.markdown import render_report
from open_product_agent.scoring.basic import calculate_scores, profile_id_from_name

app = typer.Typer(help="Open Product Agent CLI.")
profile_app = typer.Typer(help="Validate and manage product profiles.")
domain_app = typer.Typer(help="Validate and inspect domain packs.")
import_app = typer.Typer(help="Import local product data.")
feedback_app = typer.Typer(help="Record and inspect preference feedback.")

app.add_typer(profile_app, name="profile")
app.add_typer(domain_app, name="domain")
app.add_typer(import_app, name="import")
app.add_typer(feedback_app, name="feedback")

DatabaseOption = Annotated[
    Path,
    typer.Option("--db", help="SQLite database path."),
]
DomainPackOption = Annotated[
    Path | None,
    typer.Option("--domain-pack", help="Optional domain pack YAML path."),
]


@app.command()
def version() -> None:
    """Print the installed Open Product Agent version."""
    typer.echo(__version__)


@app.command("init-db")
def init_db(db: DatabaseOption = Path("open_product_agent.sqlite3")) -> None:
    """Create or update the local SQLite database schema."""
    Store(db).init()
    typer.echo(f"Database initialized: {db}")


@profile_app.command("validate")
def validate_profile(path: Path) -> None:
    """Validate a YAML product profile."""
    data = _load_yaml(path)
    ProductProfileEnvelope.model_validate(data)
    typer.echo(f"Profile is valid: {path}")


@domain_app.command("validate")
def validate_domain(path: Path) -> None:
    """Validate a YAML domain pack."""
    data = _load_yaml(path)
    DomainPack.model_validate(data)
    typer.echo(f"Domain pack is valid: {path}")


@import_app.command("csv")
def import_csv(
    path: Path,
    profile_path: Annotated[Path, typer.Option("--profile", help="YAML profile path.")],
    db: DatabaseOption = Path("open_product_agent.sqlite3"),
) -> None:
    """Import local CSV product data."""
    _import_records(path, profile_path=profile_path, db=db, loader=load_csv)


@import_app.command("json")
def import_json(
    path: Path,
    profile_path: Annotated[Path, typer.Option("--profile", help="YAML profile path.")],
    db: DatabaseOption = Path("open_product_agent.sqlite3"),
) -> None:
    """Import local JSON product data."""
    _import_records(path, profile_path=profile_path, db=db, loader=load_json)


@import_app.command("html")
def import_html(
    path: Path,
    profile_path: Annotated[Path, typer.Option("--profile", help="YAML profile path.")],
    db: DatabaseOption = Path("open_product_agent.sqlite3"),
) -> None:
    """Import one local HTML file as user-provided offline product data."""
    _import_records(path, profile_path=profile_path, db=db, loader=load_html)


@app.command()
def score(
    profile_path: Annotated[Path, typer.Option("--profile", help="YAML profile path.")],
    domain_pack_path: DomainPackOption = None,
    db: DatabaseOption = Path("open_product_agent.sqlite3"),
) -> None:
    """Calculate deterministic scores for imported items."""
    profile = _load_profile(profile_path)
    domain_pack = load_domain_pack(profile.domain, domain_pack_path)
    profile_id = profile_id_from_name(profile.name)
    store = Store(db)
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
    typer.echo(f"Scored {len(scores)} item(s) for profile: {profile.name}")


@app.command()
def analyze(
    profile_path: Annotated[Path, typer.Option("--profile", help="YAML profile path.")],
    provider_name: Annotated[str, typer.Option("--provider", help="AI provider name.")] = "openai",
    model: Annotated[str, typer.Option("--model", help="Provider model name.")] = "gpt-4.1-mini",
    input_cost_per_1m: Annotated[
        float | None,
        typer.Option("--input-cost-per-1m", help="Input token cost in USD per 1M tokens."),
    ] = None,
    output_cost_per_1m: Annotated[
        float | None,
        typer.Option("--output-cost-per-1m", help="Output token cost in USD per 1M tokens."),
    ] = None,
    domain_pack_path: DomainPackOption = None,
    limit: Annotated[int | None, typer.Option("--limit", min=1, help="Max items to analyze.")] = None,
    db: DatabaseOption = Path("open_product_agent.sqlite3"),
) -> None:
    """Analyze imported items with an AI provider and store validated output."""
    profile = _load_profile(profile_path)
    domain_pack = load_domain_pack(profile.domain, domain_pack_path)
    if domain_pack is None:
        raise typer.BadParameter(f"No domain pack found for domain: {profile.domain}")

    profile_id = profile_id_from_name(profile.name)
    store = Store(db)
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
        input_hash = _hash_payload(input_payload)
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
        analysis_run = AIAnalysisRun(
            id=f"analysis_{uuid4().hex}",
            item_id=item.id,
            snapshot_id=snapshot.id,
            profile_id=profile_id,
            domain_pack_id=f"{domain_pack.domain}@{domain_pack.version}",
            provider=provider_name,
            model=model,
            prompt_version=PROMPT_VERSION,
            input_hash=input_hash,
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
        store.save_analysis_run(analysis_run)

    typer.echo(f"Analyzed {analyzed} item(s), {failed} failed")


@feedback_app.command("add")
def add_feedback(
    item_id: str,
    feedback_type: FeedbackType,
    profile_path: Annotated[Path, typer.Option("--profile", help="YAML profile path.")],
    reason: Annotated[str | None, typer.Option("--reason", help="Optional feedback reason.")] = None,
    db: DatabaseOption = Path("open_product_agent.sqlite3"),
) -> None:
    """Record explicit preference feedback for an item."""
    profile = _load_profile(profile_path)
    profile_id = profile_id_from_name(profile.name)
    store = Store(db)
    store.init()
    store.save_profile(profile_id, profile)
    if store.get_item(item_id) is None:
        raise typer.BadParameter(f"Unknown item id: {item_id}")
    event = FeedbackEvent(
        id=f"feedback_{uuid4().hex}",
        item_id=item_id,
        profile_id=profile_id,
        feedback_type=feedback_type,
        reason=reason,
        created_at=datetime.now(UTC),
    )
    store.save_feedback_event(event)
    typer.echo(f"Feedback recorded: {item_id} -> {feedback_type}")


@feedback_app.command("list")
def list_feedback(
    profile_path: Annotated[Path, typer.Option("--profile", help="YAML profile path.")],
    item_id: Annotated[str | None, typer.Option("--item", help="Optional item id.")] = None,
    db: DatabaseOption = Path("open_product_agent.sqlite3"),
) -> None:
    """List stored feedback events for a profile."""
    profile = _load_profile(profile_path)
    profile_id = profile_id_from_name(profile.name)
    store = Store(db)
    store.init()
    events = store.list_feedback_events(profile_id, item_id=item_id)
    for event in events:
        suffix = f" - {event.reason}" if event.reason else ""
        typer.echo(f"{event.created_at.isoformat()} {event.item_id} {event.feedback_type}{suffix}")
    if not events:
        typer.echo("No feedback events found.")


@app.command()
def report(
    profile_path: Annotated[Path, typer.Option("--profile", help="YAML profile path.")],
    output: Annotated[Path, typer.Option("--output", help="Markdown report path.")],
    top: Annotated[int, typer.Option("--top", min=1, help="Number of items to include.")] = 10,
    db: DatabaseOption = Path("open_product_agent.sqlite3"),
) -> None:
    """Generate a Markdown report from the latest deterministic scores."""
    profile = _load_profile(profile_path)
    profile_id = profile_id_from_name(profile.name)
    store = Store(db)
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
    report_markdown = render_report(
        profile=profile,
        scored_items=scored_items,
        top=top,
        analyses_by_item=analyses_by_item,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report_markdown, encoding="utf-8")
    typer.echo(f"Report written: {output}")


def _load_yaml(path: Path) -> object:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"File not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise typer.BadParameter(f"Invalid YAML in {path}: {exc}") from exc
    except ValidationError:
        raise


def _load_profile(path: Path) -> ProductProfile:
    data = _load_yaml(path)
    return ProductProfileEnvelope.model_validate(data).profile


def _import_records(path: Path, *, profile_path: Path, db: Path, loader: object) -> None:
    profile = _load_profile(profile_path)
    profile_id = profile_id_from_name(profile.name)
    store = Store(db)
    store.init()
    store.save_profile(profile_id, profile)

    started_at = datetime.now(UTC)
    import_run = ImportRun(
        id=f"run_{uuid4().hex}",
        source_id=path.stem,
        started_at=started_at,
        status="running",
    )
    records = loader(path, domain=profile.domain, import_run_id=import_run.id)

    items_created = 0
    items_updated = 0
    for item, snapshot in records:
        if store.upsert_item_with_snapshot(item, snapshot):
            items_created += 1
        else:
            items_updated += 1

    import_run.status = "completed"
    import_run.finished_at = datetime.now(UTC)
    import_run.items_seen = len(records)
    import_run.items_created = items_created
    import_run.items_updated = items_updated
    store.save_import_run(import_run)
    typer.echo(
        f"Imported {len(records)} item(s): {items_created} created, {items_updated} updated"
    )


def _hash_payload(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _group_feedback(events: list[FeedbackEvent]) -> dict[str, list[FeedbackEvent]]:
    grouped: dict[str, list[FeedbackEvent]] = {}
    for event in events:
        grouped.setdefault(event.item_id, []).append(event)
    return grouped


if __name__ == "__main__":
    app()
