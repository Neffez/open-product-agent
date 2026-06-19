# Architecture

Open Product Agent separates the generic product evaluation core from
domain-specific knowledge.

```text
Product Profile
  -> Domain Pack
  -> Imports
  -> Items and Snapshots
  -> AI Analysis
  -> Deterministic Scoring
  -> Markdown Reports
```

The core should not contain marketplace-specific behavior or car-specific
business rules. Domain packs provide fields, synonyms, risks, seller questions,
validation hints, and scoring hints.

The current CLI MVP supports local CSV/JSON imports, SQLite persistence, item
snapshots, deterministic scoring, and Markdown reports. AI analysis tables are
present in the schema for auditability, but provider implementations are a later
phase.
