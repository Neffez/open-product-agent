from pathlib import Path

import yaml
import pytest
from typer.testing import CliRunner

from open_product_agent import __version__
from open_product_agent.ai.ollama_provider import OllamaProvider
from open_product_agent.ai.providers import create_provider
from open_product_agent.cli import app
from open_product_agent.domain_packs.loader import load_domain_pack
from open_product_agent.importers.json_importer import load_json
from open_product_agent.importers.scrapy_importer import ScrapyRecipe, load_scrapy_recipe_config
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


def test_cars_domain_risk_rules_trigger_from_pack() -> None:
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
            "id": "high_mileage_short_text",
            "attributes": {
                "year": 2019,
                "mileage_km": 180000,
                "source_text": "Short text.",
            },
        }
    )

    scores = calculate_scores(
        profile,
        [item],
        profile_id="family_car",
        domain_pack=domain_pack,
    )

    assert "high_mileage" in scores[0].explanation
    assert "short_description" in scores[0].explanation


def test_analyze_score_and_report_with_ai_output(tmp_path: Path, monkeypatch) -> None:
    class FakeProvider:
        last_token_usage = {"input_tokens": 10, "output_tokens": 20}

        def analyze_item(self, profile, item_snapshot, domain_pack):
            return {
                "detected_attributes": {
                    "air_conditioning": True,
                    "isofix": True,
                    "adaptive_cruise_control": True,
                },
                "risk_flags": ["service_history_missing"],
                "positive_signals": ["detailed_description"],
                "missing_information": ["accident_free"],
                "evidence": [
                    {
                        "attribute": "air_conditioning",
                        "value": True,
                        "source_text": "Air conditioning listed.",
                        "confidence": 0.9,
                    }
                ],
                "seller_questions": ["Is the car accident-free?"],
                "short_explanation": "Good match, but history needs confirmation.",
                "recommendation": "contact_seller",
                "recommendation_reason": "The fit is strong if history checks pass.",
                "next_steps": ["Ask for service records."],
            }

    def fake_create_provider(provider, *, model, temperature=0):
        return FakeProvider()

    monkeypatch.setattr("open_product_agent.workflows.create_provider", fake_create_provider)

    db_path = tmp_path / "opa.sqlite3"
    report_path = tmp_path / "report.md"
    profile_path = ROOT / "examples/profiles/family_car.yml"
    import_path = ROOT / "examples/imports/cars.json"
    runner = CliRunner()

    assert runner.invoke(
        app,
        [
            "import",
            "json",
            str(import_path),
            "--profile",
            str(profile_path),
            "--db",
            str(db_path),
        ],
    ).exit_code == 0

    analyze_result = runner.invoke(
        app,
        [
            "analyze",
            "--profile",
            str(profile_path),
            "--db",
            str(db_path),
            "--provider",
            "openai",
            "--model",
            "fake-model",
        ],
    )
    assert analyze_result.exit_code == 0
    assert "Analyzed 1 item(s), 0 failed" in analyze_result.stdout

    score_result = runner.invoke(
        app,
        ["score", "--profile", str(profile_path), "--db", str(db_path)],
    )
    assert score_result.exit_code == 0

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
    assert "### AI Analysis" in report
    assert "Good match, but history needs confirmation." in report
    assert "#### Recommendation" in report
    assert "The fit is strong if history checks pass." in report
    assert "Ask for service records." in report
    assert "Is the car accident-free?" in report


def test_analyze_stores_provider_failures_without_crashing(tmp_path: Path, monkeypatch) -> None:
    class FailingProvider:
        last_token_usage = {}

        def analyze_item(self, profile, item_snapshot, domain_pack):
            raise RuntimeError("provider unavailable")

    def fake_create_provider(provider, *, model, temperature=0):
        return FailingProvider()

    monkeypatch.setattr("open_product_agent.workflows.create_provider", fake_create_provider)

    db_path = tmp_path / "opa.sqlite3"
    profile_path = ROOT / "examples/profiles/family_car.yml"
    import_path = ROOT / "examples/imports/cars.json"
    runner = CliRunner()

    assert runner.invoke(
        app,
        [
            "import",
            "json",
            str(import_path),
            "--profile",
            str(profile_path),
            "--db",
            str(db_path),
        ],
    ).exit_code == 0

    analyze_result = runner.invoke(
        app,
        [
            "analyze",
            "--profile",
            str(profile_path),
            "--db",
            str(db_path),
            "--provider",
            "openai",
            "--model",
            "fake-model",
        ],
    )

    assert analyze_result.exit_code == 0
    assert "Analyzed 0 item(s), 1 failed" in analyze_result.stdout


def test_feedback_adjusts_future_scores(tmp_path: Path) -> None:
    db_path = tmp_path / "opa.sqlite3"
    profile_path = ROOT / "examples/profiles/family_car.yml"
    import_path = ROOT / "examples/imports/cars.json"
    runner = CliRunner()

    assert runner.invoke(
        app,
        [
            "import",
            "json",
            str(import_path),
            "--profile",
            str(profile_path),
            "--db",
            str(db_path),
        ],
    ).exit_code == 0
    assert runner.invoke(
        app,
        ["score", "--profile", str(profile_path), "--db", str(db_path)],
    ).exit_code == 0

    feedback_result = runner.invoke(
        app,
        [
            "feedback",
            "add",
            "car_001",
            "too_risky",
            "--profile",
            str(profile_path),
            "--db",
            str(db_path),
            "--reason",
            "history unclear",
        ],
    )
    assert feedback_result.exit_code == 0

    score_result = runner.invoke(
        app,
        ["score", "--profile", str(profile_path), "--db", str(db_path)],
    )
    assert score_result.exit_code == 0

    list_result = runner.invoke(
        app,
        ["feedback", "list", "--profile", str(profile_path), "--db", str(db_path)],
    )
    assert list_result.exit_code == 0
    assert "too_risky" in list_result.stdout
    assert "history unclear" in list_result.stdout


def test_html_import_flow(tmp_path: Path) -> None:
    db_path = tmp_path / "opa.sqlite3"
    profile_path = ROOT / "examples/profiles/family_car.yml"
    import_path = ROOT / "examples/imports/car_listing.html"
    runner = CliRunner()

    import_result = runner.invoke(
        app,
        [
            "import",
            "html",
            str(import_path),
            "--profile",
            str(profile_path),
            "--db",
            str(db_path),
        ],
    )

    assert import_result.exit_code == 0
    assert "Imported 1 item(s)" in import_result.stdout

    score_result = runner.invoke(
        app,
        ["score", "--profile", str(profile_path), "--db", str(db_path)],
    )
    assert score_result.exit_code == 0


def test_multi_html_import_flow(tmp_path: Path) -> None:
    db_path = tmp_path / "opa.sqlite3"
    profile_path = ROOT / "examples/profiles/family_car.yml"
    import_path = ROOT / "examples/imports/car_listing.html"
    second_import_path = tmp_path / "second_listing.html"
    second_import_path.write_text(import_path.read_text(encoding="utf-8"), encoding="utf-8")
    runner = CliRunner()

    import_result = runner.invoke(
        app,
        [
            "import",
            "html",
            str(import_path),
            str(second_import_path),
            "--profile",
            str(profile_path),
            "--db",
            str(db_path),
        ],
    )

    assert import_result.exit_code == 0
    assert "Imported 2 item(s)" in import_result.stdout


def test_scrapy_recipe_example_is_valid_and_conservative() -> None:
    recipe = load_scrapy_recipe_config(ROOT / "examples/imports/scrapy_recipe.example.yml")

    assert recipe.name == "example_products"
    assert recipe.settings.obey_robots_txt is True
    assert recipe.settings.download_delay >= 1
    assert recipe.settings.concurrent_requests == 1
    assert recipe.settings.max_pages == 10


def test_scrapy_recipe_requires_explicit_allowed_domains_and_fields() -> None:
    with pytest.raises(ValueError):
        ScrapyRecipe.model_validate(
            {
                "name": "unsafe",
                "start_urls": ["https://example.com/products"],
                "allowed_domains": [],
                "fields": {"title": ".title::text"},
            }
        )

    with pytest.raises(ValueError):
        ScrapyRecipe.model_validate(
            {
                "name": "missing_fields",
                "start_urls": ["https://example.com/products"],
                "allowed_domains": ["example.com"],
                "fields": {},
            }
        )


def test_provider_factory_creates_ollama_provider() -> None:
    provider = create_provider("ollama", model="llama3.1")

    assert isinstance(provider, OllamaProvider)
    assert provider.model == "llama3.1"


def test_ollama_provider_validates_json_response(monkeypatch) -> None:
    provider = OllamaProvider(model="llama3.1")

    def fake_post_json(path, payload):
        assert path == "/api/chat"
        assert payload["format"]["type"] == "object"
        return {
            "message": {
                "content": """
                {
                  "detected_attributes": {"isofix": true},
                  "risk_flags": [],
                  "positive_signals": ["isofix"],
                  "missing_information": ["service_history"],
                  "evidence": [
                    {
                      "attribute": "isofix",
                      "value": true,
                      "source_text": "Isofix listed.",
                      "confidence": 0.9
                    }
                  ],
                  "seller_questions": ["Is there a complete service history?"],
                  "short_explanation": "Isofix is mentioned.",
                  "recommendation": "needs_more_information",
                  "recommendation_reason": "Service history must be confirmed first.",
                  "next_steps": ["Ask for service history documents."]
                }
                """
            },
            "prompt_eval_count": 11,
            "eval_count": 22,
        }

    monkeypatch.setattr(provider, "_post_json", fake_post_json)

    result = provider.analyze_item(
        profile={"name": "Family car"},
        item_snapshot={"description": "Isofix listed."},
        domain_pack={"domain": "cars"},
    )

    assert result["detected_attributes"]["isofix"] is True
    assert provider.last_token_usage == {"input_tokens": 11, "output_tokens": 22}
