# Astrophysics AI Lab

Astrophysics AI Lab is a web app for learning astrophysics with AI assistance. It combines conversational Q&A, optional arXiv context, and lightweight visuals so you can explore concepts and recent topics from one interface.

The app runs under Codehome Hub (The Sciences group) or directly on your machine.

## What Was Built

- A FastAPI backend with streaming chat responses (SSE).
- Hybrid provider routing for:
  - Local Ollama
  - OpenAI-compatible APIs
  - Anthropic Messages API
- Provider/model selection in the UI with optional model override.
- Better provider error messages (invalid/missing key, permission, rate limit, bad request).
- Topic configuration via `data/topics.yaml` (no code edits needed for new topics).
- Optional arXiv context injection + paper retrieval panel.
- Visual tools:
  - Blackbody spectrum (Plotly)
  - Orbit sketch (Three.js)

## Tech Stack

| Layer | Technologies |
| --- | --- |
| Backend | Python 3.12+, FastAPI, Uvicorn, httpx, pydantic-settings, PyYAML, arxiv, plotly |
| Frontend | Vite, TypeScript, markdown-it, Mermaid, Plotly.js, Three.js |
| Config | `.env` (runtime secrets/settings), `data/topics.yaml` (topic catalog) |

## Running With Codehome Hub

- Hub app manifest: `app.json`
- App id: `astro-physics-hub`
- Default port: `5112`
- Start script: `./start.sh`

Hub sets `PORT` automatically when launching from the card.

Quick verify from Hub API:

```bash
curl -s http://localhost:8085/api/cards | jq '.apps[] | select(.id == "astro-physics-hub")'
```

## Local Quick Start

Prerequisites:

- Python 3.12+
- Node.js (only needed when `frontend/dist` is missing and frontend build is required)

Steps:

1. Copy `.env.example` to `.env` and set your keys/config.
2. Run:

   ```bash
   ./start.sh
   ```

   This script will:
   - create `.venv` if needed
   - install Python dependencies
   - build frontend assets if needed
   - start Uvicorn

3. Open `http://localhost:5112` (or the `PORT` provided by Hub).

Optional dev run:

```bash
python -m uvicorn astrophysics.main:app --host 0.0.0.0 --port 5112 --reload
```

## Configuration

Configuration is loaded from `.env` (see `astrophysics/config.py`).

| Variable | Purpose |
| --- | --- |
| `ASTRO_PRIMARY` / `PRIMARY` | Auto routing default (`local` or `hosted`) |
| `OLLAMA_BASE_URL` | Ollama server URL |
| `OLLAMA_MODEL` | Default Ollama model |
| `OPENAI_API_KEY` | API key for OpenAI-compatible providers |
| `OPENAI_BASE_URL` | Base URL for OpenAI-compatible chat completions |
| `OPENAI_MODEL` | Default model for OpenAI-compatible provider |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `ANTHROPIC_BASE_URL` | Anthropic base URL (`https://api.anthropic.com`) |
| `ANTHROPIC_MODEL` | Default Anthropic model |
| `ASTRO_ENABLE_IMAGE_GEN` | Enables image endpoint when set true and key is present |

Security note: `.env` is gitignored. Do not commit real credentials.

## Topics (No Code Changes)

Topic buttons are loaded from `data/topics.yaml`.

To add/edit topics:

1. Update `data/topics.yaml`
2. Restart the app

Schema:

| Field | Required | Purpose |
| --- | --- | --- |
| `id` | yes | Stable slug |
| `title` | yes | Button label |
| `blurb` | yes | Tooltip text |
| `anchors` | no | Prompt hints |
| `arxiv_query` | no | Prefills arXiv search and enables context |

## API Surface (Key Routes)

- `GET /api/meta` — provider defaults and availability info for UI
- `POST /api/chat/stream` — streamed chat
- `GET /api/topics` — topics loaded from YAML
- `GET /api/arxiv/papers` — paper search/list
- `GET /api/viz/blackbody` — Plotly figure JSON
- `GET /api/viz/orbit-spec` — scene spec for orbit sketch
- `POST /api/image/generate` — optional image generation endpoint

## Project Layout

```text
AstroPhysics/
├── app.json
├── start.sh
├── requirements.txt
├── main.py
├── .env.example
├── data/
│   └── topics.yaml
├── astrophysics/
│   ├── main.py
│   ├── llm_router.py
│   ├── api_errors.py
│   ├── retrieval_arxiv.py
│   ├── topics_loader.py
│   └── viz.py
└── frontend/
    ├── src/main.ts
    └── ...
```