# Web UI

The first web UI is built with Streamlit because the current application is a
Python CLI and can reuse the same SQLite store, importers, scoring logic, and AI
providers directly.

Run locally:

```bash
python -m pip install -e ".[ui]"
streamlit run src/open_product_agent/ui/streamlit_app.py
```

Current UI scope:

- configure database and profile paths
- upload multiple HTML, CSV, or JSON files
- import all queued files
- run AI analysis through OpenAI or external Ollama
- run deterministic scoring
- view candidate table and item details
- record feedback
- download Markdown report

Ollama is not managed by this application. Set `OLLAMA_BASE_URL` to point to the
external Ollama server.
