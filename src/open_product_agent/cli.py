from pathlib import Path

import typer
import yaml
from pydantic import ValidationError

from open_product_agent import __version__
from open_product_agent.models.domain_pack import DomainPack
from open_product_agent.models.profile import ProductProfileEnvelope

app = typer.Typer(help="Open Product Agent CLI.")
profile_app = typer.Typer(help="Validate and manage product profiles.")
domain_app = typer.Typer(help="Validate and inspect domain packs.")

app.add_typer(profile_app, name="profile")
app.add_typer(domain_app, name="domain")


@app.command()
def version() -> None:
    """Print the installed Open Product Agent version."""
    typer.echo(__version__)


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


if __name__ == "__main__":
    app()
