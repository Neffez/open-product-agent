# AI Integration

Phase 3 adds structured item analysis through an AI provider.

Current scope:

- `AIProvider` interface
- OpenAI provider
- Ollama provider
- item-analysis prompt versioning
- JSON schema for item analysis
- parse and validation step before storage
- one repair attempt for invalid provider output
- storage in `ai_analysis_runs`
- token usage storage
- optional cost estimate from user-provided token prices

AI output is not accepted as truth automatically. The system stores it as
evidence and keeps final scoring deterministic.

Example:

```bash
opa analyze \
  --profile examples/profiles/family_car.yml \
  --db open_product_agent.sqlite3 \
  --provider openai \
  --model gpt-4.1-mini
```

Set `OPENAI_API_KEY` in the environment before using the OpenAI provider.

For Ollama:

```bash
ollama pull llama3.1
opa analyze \
  --profile examples/profiles/family_car.yml \
  --db open_product_agent.sqlite3 \
  --provider ollama \
  --model llama3.1 \
  --limit 1
```

The Ollama provider reads `OLLAMA_BASE_URL` from the environment and defaults to
`http://localhost:11434`.
