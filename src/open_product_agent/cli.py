from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer
import yaml
from pydantic import ValidationError

from open_product_agent import __version__
from open_product_agent.database.store import Store
from open_product_agent.domain_packs.loader import load_domain_pack
from open_product_agent.importers.csv_importer import load_csv
from open_product_agent.importers.json_importer import load_json
from open_product_agent.models.domain_pack import DomainPack
from open_product_agent.models.item import ImportRun
from open_product_agent.models.profile import ProductProfile, ProductProfileEnvelope
from open_product_agent.reports.markdown import render_report
from open_product_agent.scoring.basic import calculate_scores, profile_id_from_name

app = typer.Typer(help="Open Product Agent CLI.")
profile_app = typer.Typer(help="Validate and manage product profiles.")
domain_app = typer.Typer(help="Validate and inspect domain packs.")
import_app = typer.Typer(help="Import local product data.")

app.add_typer(profile_app, name="profile")
app.add_typer(domain_app, name="domain")
app.add_typer(import_app, name="import")

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
    scores = calculate_scores(
        profile,
        items,
        profile_id=profile_id,
        domain_pack=domain_pack,
    )
    store.save_scores(scores)
    typer.echo(f"Scored {len(scores)} item(s) for profile: {profile.name}")


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
    scored_items = [
        (item, score)
        for score in scores
        if (item := store.get_item(score.item_id)) is not None
    ]
    report_markdown = render_report(profile=profile, scored_items=scored_items, top=top)
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


if __name__ == "__main__":
    app()
