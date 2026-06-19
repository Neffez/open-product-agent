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
Domain Pack synonyms where available. AI-generated evidence will be added later,
but final score calculation should remain rule-based.
