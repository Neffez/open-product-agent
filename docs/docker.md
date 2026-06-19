# Docker

The application can run in a single container with Streamlit. SQLite data should
be mounted as a persistent volume. Ollama runs outside the app container.

Build:

```bash
docker build -t open-product-agent .
```

Run with external Ollama:

```bash
docker run --rm -p 8501:8501 \
  -v opa-data:/data \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  open-product-agent
```

Useful environment variables:

- `OPA_DATABASE_PATH=/data/open_product_agent.sqlite3`
- `OPA_PROFILE_PATH=/app/examples/profiles/family_car.yml`
- `OPENAI_API_KEY=...`
- `OLLAMA_BASE_URL=http://host.docker.internal:11434`
