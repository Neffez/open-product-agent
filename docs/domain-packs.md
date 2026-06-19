# Domain Packs

Domain packs define category-specific knowledge while the core remains generic.

A domain pack should define:

- domain name
- version
- schema version
- supported languages
- fields
- synonyms
- risk flags
- positive signals
- seller questions
- scoring hints

The first domain pack is `cars` at version `0.1.0`.

The `cars` pack includes multilingual synonyms, seller questions, and simple
risk rules that the deterministic scorer can apply without hardcoding car logic
in the core package.
