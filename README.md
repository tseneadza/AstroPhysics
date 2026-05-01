# Astrophysics AI Lab

**Astrophysics AI Lab** is a web app for AI-assisted astrophysics learning: conversational explanations, optional retrieval from arXiv (astro-ph), simple interactive visuals, and sidebar topics you can edit without changing code.

It is designed to run under **Codehome Hub** (group **The Sciences**) or standalone on your machine.

## Features

- **Hybrid chat** — Streamed replies over **Server-Sent Events** from **Ollama**, an **OpenAI-compatible** API, or **Anthropic Messages**, with UI-selectable provider and optional **model id** override. Invalid API keys return clear HTTP 401/403-style hints. See `astrophysics/llm_router.py`, `astrophysics/api_errors.py`, and `POST /api/chat/stream` in `astrophysics/main.py`.
- **Topics sidebar** — Buttons and tooltips are loaded from `data/topics.yaml`. Includes general themes (e.g. cosmology, stellar physics) and **arXiv astro-ph** subcategories (CO, EP, GA, HE, IM, SR) with optional `arxiv_query` so the UI can pre-fill arXiv search and enable “Add arXiv context” for that category.
- **arXiv** — Optional context injected into chat when enabled; separate panel to fetch recent/search-matched **astro-ph** papers with caching. See `astrophysics/retrieval_arxiv.py` and `GET /api/arxiv/papers`.
- **Visuals** — Normalized **blackbody spectrum** (Plotly JSON) and a schematic **orbital** scene (JSON consumed by Three.js in the frontend). See `astrophysics/viz.py` and the right-hand panel in the UI.
- **Optional image generation** — When `ASTRO_ENABLE_IMAGE_GEN` is true and an API key is set, `POST /api/image/generate` can request illustrative images (OpenAI-compatible images endpoint). Off by default.

## Tech stack


| Layer    | Technologies                                                                    |
| -------- | ------------------------------------------------------------------------------- |
| Backend  | Python 3.12+, FastAPI, Uvicorn, httpx, pydantic-settings, PyYAML, arxiv, plotly |
| Frontend | Vite, TypeScript, markdown-it, Mermaid, Plotly.js, Three.js                     |
| Config   | `.env` (see `.env.example`), `data/topics.yaml`                                 |


## Codehome Hub

- This app is declared in `**app.json`** at the project root (`id`: `astro-physics-hub`, default web port **5112**).
- **Start command:** `./start.sh` (Hub sets `**PORT`** in the environment when it launches the app).
- Hub discovery includes `**~/Codehome/The Sciences/AstroPhysics**` (alongside other science apps). The API assigns apps under that path to the **The Sciences** group.
- After Hub is running, you can confirm discovery with:
  ```bash
  curl -s http://localhost:8085/api/cards | jq '.apps[] | select(.id == "astro-physics-hub")'
  ```

## Quick start

**Prerequisites:** Python 3.12+ and, if `frontend/dist` is missing, **Node.js** so `start.sh` can run `npm install` / `npm run build` in `frontend/`.

1. Copy `**.env.example`** to `**.env**` and set API keys / URLs (see [Configuration](#configuration)). Never commit `.env`.
2. From this directory, run `**./start.sh**`. It creates a `.venv` if needed, installs `requirements.txt`, builds the frontend when necessary, and starts Uvicorn on `**PORT**` (default `5112` if not set).
3. Open **[http://localhost:PORT/](http://localhost:PORT/)** in your browser (use the port Hub shows, or `5112` when running locally).

**Local development (optional):**

- `python -m uvicorn astrophysics.main:app --host 0.0.0.0 --port 5112 --reload` after activating the venv and installing dependencies.
- Or run `python main.py` for a dev-oriented entry (reload on port 5112).

## Configuration

Settings are read from `**.env`** in the project root (see `astrophysics/config.py`).


| Variable                     | Purpose                                                                                        |
| ---------------------------- | ---------------------------------------------------------------------------------------------- |
| `ASTRO_PRIMARY` or `PRIMARY` | Default bias: `local` (Ollama first) or `hosted` (API first). The UI can override per request. |
| `OLLAMA_BASE_URL`            | Ollama base URL (default `http://127.0.0.1:11434`).                                            |
| `OLLAMA_MODEL`               | Ollama model name.                                                                             |
| `OPENAI_API_KEY`             | Key for any OpenAI-compatible provider.                                                        |
| `OPENAI_BASE_URL`            | Chat completions base (e.g. `https://api.openai.com/v1`).                                      |
| `OPENAI_MODEL`               | Model id for hosted chat.                                                                      |
| `ANTHROPIC_API_KEY`          | [Anthropic](https://console.anthropic.com/) API key for Claude models.                         |
| `ANTHROPIC_BASE_URL`         | Default `https://api.anthropic.com` (change only if using a proxy).                            |
| `ANTHROPIC_MODEL`            | Default Claude model id (e.g. `claude-3-5-sonnet-20241022`).                                   |
| `ASTRO_ENABLE_IMAGE_GEN`     | Set `true` to allow image generation when a key is present.                                    |


**Security:** `.env` is listed in `.gitignore`. Do not commit secrets. Replace any placeholder values in your own `.env`; rotate keys if they were ever exposed.

## Customizing topics (no code changes)

Edit `**data/topics.yaml`** and restart the app (or restart from Hub) so changes load.


| Field         | Required | Purpose                                                                                                                  |
| ------------- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| `id`          | yes      | Stable slug                                                                                                              |
| `title`       | yes      | Button label                                                                                                             |
| `blurb`       | yes      | Tooltip                                                                                                                  |
| `anchors`     | no       | Optional keyword list (appended to the generated prompt)                                                                 |
| `arxiv_query` | no       | e.g. `cat:astro-ph.CO` — pre-fills the arXiv search field and enables “Add arXiv context” when the user clicks the topic |


## Project layout

```
AstroPhysics/
├── app.json              # Hub manifest
├── start.sh              # venv, deps, optional frontend build, uvicorn
├── requirements.txt
├── main.py               # Optional dev entry
├── .env.example
├── data/
│   └── topics.yaml       # Sidebar topics (YAML)
├── astrophysics/         # FastAPI app, LLM routing, arXiv, viz, topics loader
└── frontend/             # Vite + TypeScript UI (build output in frontend/dist)
```

## Project Manager (Codehome)

If **ProjManager** is configured to scan this project’s path in its `APP_PATHS`, the app can appear there for task sync (requires at least one markdown file in the project root—this README counts).