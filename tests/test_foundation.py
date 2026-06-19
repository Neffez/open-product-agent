from pathlib import Path

import yaml
from typer.testing import CliRunner

from open_product_agent import __version__
from open_product_agent.cli import app
from open_product_agent.domain_packs.loader import load_domain_pack
from open_product_agent.importers.json_importer import load_json
from open_product_agent.models.domain_pack import DomainPack
from open_product_agent.models.profile import ProductProfileEnvelope
from open_product_agent.scoring.basic import calculate_scores

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


def test_csv_import_score_and_report_flow(tmp_path: Path) -> None:
    db_path = tmp_path / "opa.sqlite3"
    report_path = tmp_path / "report.md"
    profile_path = ROOT / "examples/profiles/family_car.yml"
    import_path = ROOT / "examples/imports/cars.csv"
    runner = CliRunner()

    import_result = runner.invoke(
        app,
        [
            "import",
            "csv",
            str(import_path),
            "--profile",
            str(profile_path),
            "--db",
            str(db_path),
        ],
    )
    assert import_result.exit_code == 0
    assert "Imported 2 item(s)" in import_result.stdout

    score_result = runner.invoke(
        app,
        ["score", "--profile", str(profile_path), "--db", str(db_path)],
    )
    assert score_result.exit_code == 0
    assert "Scored 2 item(s)" in score_result.stdout

    report_result = runner.invoke(
        app,
        [
            "report",
            "--profile",
            str(profile_path),
            "--db",
            str(db_path),
            "--output",
            str(report_path),
        ],
    )
    assert report_result.exit_code == 0
    report = report_path.read_text(encoding="utf-8")
    assert "# Product Report: Family car" in report
    assert "Overall score:" in report
    assert "- Year: 2020" in report
    assert "- Mileage: 72000 km" in report
    assert "- Source: https://example.com/cars/1" in report


def test_json_importer_normalizes_nested_attributes() -> None:
    records = load_json(
        ROOT / "examples/imports/cars.json",
        domain="cars",
        import_run_id="run_test",
    )

    item, snapshot = records[0]

    assert item.id == "car_001"
    assert item.attributes["year"] == 2020
    assert item.attributes["source_text"].startswith("Estate car with ACC")
    assert snapshot.description is not None
    assert snapshot.content_hash is not None


def test_scoring_uses_domain_pack_synonyms() -> None:
    profile_data = yaml.safe_load((ROOT / "examples/profiles/family_car.yml").read_text())
    profile = ProductProfileEnvelope.model_validate(profile_data).profile
    domain_pack = load_domain_pack("cars", ROOT / "domains/cars/domain.yml")
    records = load_json(
        ROOT / "examples/imports/cars.json",
        domain="cars",
        import_run_id="run_test",
    )

    scores = calculate_scores(
        profile,
        [record[0] for record in records],
        profile_id="family_car",
        domain_pack=domain_pack,
    )

    assert "adaptive_cruise_control" in scores[0].explanation


def test_short_synonyms_do_not_match_inside_unrelated_words() -> None:
    profile_data = yaml.safe_load((ROOT / "examples/profiles/family_car.yml").read_text())
    profile = ProductProfileEnvelope.model_validate(profile_data).profile
    domain_pack = load_domain_pack("cars", ROOT / "domains/cars/domain.yml")
    records = load_json(
        ROOT / "examples/imports/cars.json",
        domain="cars",
        import_run_id="run_test",
    )
    item = records[0][0].model_copy(
        update={
            "id": "car_without_acc",
            "title": "VW Passat Variant",
            "attributes": {
                "source_text": "Accident-free status not explicitly stated.",
                "year": 2019,
                "mileage_km": 98000,
            },
        }
    )

    scores = calculate_scores(
        profile,
        [item],
        profile_id="family_car",
        domain_pack=domain_pack,
    )

    assert "adaptive_cruise_control" not in scores[0].explanation
