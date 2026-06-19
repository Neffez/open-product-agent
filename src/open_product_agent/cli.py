from pathlib import Path
from typing import Annotated

import typer
import yaml
from pydantic import ValidationError

from open_product_agent import __version__
from open_product_agent.database.store import Store
from open_product_agent.models.domain_pack import DomainPack
from open_product_agent.models.feedback import FeedbackType
from open_product_agent.models.profile import ProductProfileEnvelope
from open_product_agent.workflows import (
    add_feedback_event,
    analyze_profile,
    import_paths,
    list_feedback_for_profile,
    load_profile,
    render_profile_report,
    score_profile,
)

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
    paths: list[Path],
    profile_path: Annotated[Path, typer.Option("--profile", help="YAML profile path.")],
    db: DatabaseOption = Path("open_product_agent.sqlite3"),
) -> None:
    """Import local CSV product data."""
    _import_many(paths, profile_path=profile_path, db=db, import_type="csv")


@import_app.command("json")
def import_json(
    paths: list[Path],
    profile_path: Annotated[Path, typer.Option("--profile", help="YAML profile path.")],
    db: DatabaseOption = Path("open_product_agent.sqlite3"),
) -> None:
    """Import local JSON product data."""
    _import_many(paths, profile_path=profile_path, db=db, import_type="json")


@import_app.command("html")
def import_html(
    paths: list[Path],
    profile_path: Annotated[Path, typer.Option("--profile", help="YAML profile path.")],
    db: DatabaseOption = Path("open_product_agent.sqlite3"),
) -> None:
    """Import local HTML files as user-provided offline product data."""
    _import_many(paths, profile_path=profile_path, db=db, import_type="html")


@import_app.command("scrapy")
def import_scrapy(
    recipes: list[Path],
    profile_path: Annotated[Path, typer.Option("--profile", help="YAML profile path.")],
    db: DatabaseOption = Path("open_product_agent.sqlite3"),
) -> None:
    """Import products from explicit, user-controlled Scrapy recipes."""
    _import_many(recipes, profile_path=profile_path, db=db, import_type="scrapy")


@app.command()
def score(
    profile_path: Annotated[Path, typer.Option("--profile", help="YAML profile path.")],
    domain_pack_path: DomainPackOption = None,
    db: DatabaseOption = Path("open_product_agent.sqlite3"),
) -> None:
    """Calculate deterministic scores for imported items."""
    profile = load_profile(profile_path)
    count = score_profile(profile_path=profile_path, db_path=db, domain_pack_path=domain_pack_path)
    typer.echo(f"Scored {count} item(s) for profile: {profile.name}")


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
    try:
        analyzed, failed = analyze_profile(
            profile_path=profile_path,
            db_path=db,
            provider_name=provider_name,
            model=model,
            domain_pack_path=domain_pack_path,
            limit=limit,
            input_cost_per_1m=input_cost_per_1m,
            output_cost_per_1m=output_cost_per_1m,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
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
    try:
        add_feedback_event(
            profile_path=profile_path,
            db_path=db,
            item_id=item_id,
            feedback_type=feedback_type,
            reason=reason,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Feedback recorded: {item_id} -> {feedback_type}")


@feedback_app.command("list")
def list_feedback(
    profile_path: Annotated[Path, typer.Option("--profile", help="YAML profile path.")],
    item_id: Annotated[str | None, typer.Option("--item", help="Optional item id.")] = None,
    db: DatabaseOption = Path("open_product_agent.sqlite3"),
) -> None:
    """List stored feedback events for a profile."""
    events = list_feedback_for_profile(profile_path=profile_path, db_path=db, item_id=item_id)
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
    report_markdown = render_profile_report(profile_path=profile_path, db_path=db, top=top)
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


def _import_many(paths: list[Path], *, profile_path: Path, db: Path, import_type: str) -> None:
    import_run = import_paths(paths, profile_path=profile_path, db_path=db, import_type=import_type)
    typer.echo(
        f"Imported {import_run.items_seen} item(s): "
        f"{import_run.items_created} created, {import_run.items_updated} updated"
    )
    for error in import_run.errors:
        typer.echo(f"Import error: {error}", err=True)


if __name__ == "__main__":
    app()
