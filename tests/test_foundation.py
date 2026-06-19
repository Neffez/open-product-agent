from pathlib import Path

import yaml
from typer.testing import CliRunner

from open_product_agent import __version__
from open_product_agent.cli import app
from open_product_agent.models.domain_pack import DomainPack
from open_product_agent.models.profile import ProductProfileEnvelope

ROOT = Path(__file__).resolve().parents[1]


def test_version_command() -> None:
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_example_profile_is_valid() -> None:
    data = yaml.safe_load((ROOT / "examples/profiles/family_car.yml").read_text())

    profile = ProductProfileEnvelope.model_validate(data)

    assert profile.profile.domain == "cars"
    assert profile.profile.budget is not None
    assert profile.profile.budget.max == 25000


def test_cars_domain_pack_is_valid() -> None:
    data = yaml.safe_load((ROOT / "domains/cars/domain.yml").read_text())

    domain_pack = DomainPack.model_validate(data)

    assert domain_pack.domain == "cars"
    assert "accident_unclear" in domain_pack.risk_flags
