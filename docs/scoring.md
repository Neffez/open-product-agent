# Scoring

Final scores must be deterministic and reproducible.

AI output may provide structured evidence, risk flags, missing information, and
explanations. The scoring engine decides from validated fields, profile
constraints, risk flags, and configured weights.

The initial score model should stay small:

- hard constraints
- must-have penalties
- risk flag penalties
- nice-to-have bonuses
- capped 0 to 100 overall score

The current MVP scoring implementation is deterministic and intentionally
conservative. It uses item fields, normalized attributes, source text, and
Domain Pack synonyms where available. Valid AI-generated evidence can enrich the
input data, but final score calculation remains rule-based.

When valid AI analysis output exists, scoring may use:

- `detected_attributes` as additional evidence for profile features
- `risk_flags` as deterministic risk penalties
- `missing_information` as deterministic uncertainty penalties

Invalid or failed AI analysis runs are stored for auditability but ignored by
scoring.
