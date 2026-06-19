FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV OPA_DATABASE_PATH=/data/open_product_agent.sqlite3
ENV OPA_PROFILE_PATH=/app/examples/profiles/family_car.yml

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY domains ./domains
COPY examples ./examples
COPY docs ./docs

RUN pip install --no-cache-dir -e ".[ui]"

EXPOSE 8501

CMD ["streamlit", "run", "src/open_product_agent/ui/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
