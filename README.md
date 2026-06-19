# Open Product Agent

Open Product Agent is a self-hosted AI assistant for understanding, evaluating,
and ranking products from user-provided sources.

The project starts with a local Python CLI. The first domain pack is `cars`,
because used cars are expensive, risk-prone, and hard to evaluate with rigid
marketplace filters. The core remains generic so other domains such as laptops,
bikes, cameras, tools, and furniture can be added later.

## Status

This repository is in the foundation phase. The current goal is a clean,
installable project skeleton for the CLI MVP.

## Principles

- Generic core, domain-specific packs.
- AI extracts, normalizes, and explains.
- Deterministic rules score and enforce constraints.
- User-defined imports only.
- No web automation in the MVP.
- Store snapshots and analysis metadata for auditability.

## What It Is

- A personal research and decision-support tool.
- A generic product evaluation layer above user-provided data.
- A self-hosted application for private use.
- A framework for structured extraction, risk detection, scoring, and reports.

## What It Is Not

- A marketplace data acquisition tool.
- A tool for defeating access controls or usage limits.
- A centralized database of third-party listings.
- A system for republishing third-party listing content or images.

## Planned MVP

The MVP should allow a user to:

1. Load a product profile from YAML.
2. Load product items from CSV or JSON.
3. Normalize items into a generic schema.
4. Analyze items with an AI provider.
5. Validate structured AI output.
6. Calculate deterministic scores.
7. Generate a Markdown report.


## Local Development

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
opa --help
```

## First CLI Commands

```bash
opa version
opa profile validate examples/profiles/family_car.yml
opa domain validate domains/cars/domain.yml
opa init-db --db open_product_agent.sqlite3
opa import csv examples/imports/cars.csv --profile examples/profiles/family_car.yml --db open_product_agent.sqlite3
opa analyze --profile examples/profiles/family_car.yml --db open_product_agent.sqlite3 --provider openai --model gpt-4.1-mini
opa score --profile examples/profiles/family_car.yml --db open_product_agent.sqlite3
opa report --profile examples/profiles/family_car.yml --db open_product_agent.sqlite3 --output examples/reports/family_car.md
```

The current CLI supports local CSV/JSON imports, deterministic scoring, and
Markdown report generation. AI analysis is available through the OpenAI provider
and stores validated structured output before scoring uses it.

Cost estimates are only calculated when explicit token prices are passed:

```bash
opa analyze \
  --profile examples/profiles/family_car.yml \
  --input-cost-per-1m 0.00 \
  --output-cost-per-1m 0.00
```

## License

Open Product Agent is released under the MIT License.
