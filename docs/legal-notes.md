# Legal Notes

Open Product Agent is designed as a user-controlled research and ranking tool.
The core project is intentionally limited to user-provided data and
user-controlled imports. Optional recipe-based crawling must remain generic. The
project must not include built-in integrations that target specific third-party
marketplaces or features intended to defeat access controls or usage limits.

Users are responsible for ensuring that their imports and processing comply with
applicable law, website terms, robots.txt, copyright, database rights, and data
protection law.

The default technical posture is conservative:

- prefer user-provided local data
- require explicit recipes for optional crawling
- keep robots.txt enabled by default for crawls
- use conservative crawl limits and delays
- store only what is needed
- do not copy or republish third-party media by default
- preserve source URLs and timestamps for auditability
- prefer local processing
