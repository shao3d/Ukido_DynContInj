# Ukido AI Assistant

Ukido is a FastAPI chatbot for the Ukido soft-skills school. It answers product
questions from a curated knowledge base, keeps short conversation state,
adapts replies to the user's language and intent, and sends trial requests to
HubSpot.

Production: <https://ukido.beyondhorizon.dev>

## What is in the current product

- Russian, Ukrainian and English chat through JSON or SSE.
- Gemini 3.5 Flash Lite (`google/gemini-3.5-flash-lite`) via OpenRouter for
  routing, answer generation, translation and optional humour; every model
  can be overridden with environment variables (`ROUTER_MODEL`,
  `MODEL_ANSWER`, `TRANSLATION_MODEL`, `ZHVANETSKY_MODEL`).
- Deterministic handling for greetings, thanks, farewells, CTA limits and
  completed actions around the LLM pipeline.
- File-backed conversation persistence outside application releases.
- Trial signup integration with HubSpot.
- Automatic deployment to Beyond Horizon after tests pass on `main`.

## Local start

Requirements: Python 3.11+ and an OpenRouter API key.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python src/main.py
```

Set `OPENROUTER_API_KEY` in `.env`. HubSpot variables are optional unless live
trial signup is needed. The application opens at <http://localhost:8000> and
FastAPI schema at <http://localhost:8000/docs>.

Docker uses the same environment contract:

```bash
docker build -t ukido-assistant .
docker run --rm -p 8000:8000 --env-file .env ukido-assistant
```

## Tests

```bash
python3 -m pytest -q
```

The default suite is offline and deterministic. Live scenario scripts under
`tests/scripts/` are manual checks and are not part of normal pytest
collection.

## Documentation

- [Documentation map](docs/README.md)
- [Current architecture](docs/architecture.md)
- [HTTP and SSE API](docs/API.md)
- [Beyond Horizon deployment](docs/deployment-beyondhorizon.md)

Superseded plans, generated reports and diagrams remain available in Git
history instead of the current project tree.

## Deployment

`main` is the production branch. A push runs Python 3.11/3.12 tests and a
Docker build, then deploys the exact commit to Beyond Horizon and verifies both
private and public health endpoints. Railway remains rollback infrastructure,
not the primary production target. See the deployment runbook before changing
host, service or release settings.
