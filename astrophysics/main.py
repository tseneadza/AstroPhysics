"""FastAPI app: static UI, SSE chat, visualization, optional arXiv + image helpers."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field

from astrophysics.config import get_settings
from astrophysics.llm_router import stream_chat
from astrophysics.retrieval_arxiv import PaperRef, format_for_llm_context, search_astro_ph
from astrophysics.topics_loader import load_topics
from astrophysics.viz import blackbody_spectrum_json, orbit_demo_spec

logger = logging.getLogger(__name__)
DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


class ChatMsg(BaseModel):
    role: str
    content: str


class ChatStreamBody(BaseModel):
    messages: list[ChatMsg] = Field(default_factory=list)
    preference: str = "auto"
    """Used when provider is auto: local | hosted | auto (follows ASTRO_PRIMARY)."""
    provider: Literal["auto", "ollama", "openai", "anthropic"] = "auto"
    model_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("model_id", "model"),
    )
    use_arxiv: bool = False
    arxiv_query: str | None = None


class ImageGenBody(BaseModel):
    prompt: str
    size: str = "1024x1024"


def _sse(data: dict | str) -> str:
    if isinstance(data, str):
        return f"data: {data}\n\n"
    return f"data: {json.dumps(data)}\n\n"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as client:
        app.state.http = client
        yield


app = FastAPI(title="Astrophysics AI Lab", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"ok": True}


@app.get("/api/meta")
async def meta():
    settings = get_settings()
    has_openai = bool(settings.openai_api_key.strip())
    return {
        "enable_image_gen": settings.enable_image_gen and has_openai,
        "primary": settings.primary,
        "models": {
            "ollama": {
                "default": settings.ollama_model,
                "configured": True,
            },
            "openai": {
                "default": settings.openai_model,
                "configured": has_openai,
            },
            "anthropic": {
                "default": settings.anthropic_model,
                "configured": bool(settings.anthropic_api_key.strip()),
            },
        },
    }


@app.get("/api/topics")
async def topics():
    return {"topics": load_topics()}


@app.get("/api/arxiv/papers")
async def arxiv_papers(q: str = "", limit: int = 8):
    lim = max(1, min(20, limit))
    papers = search_astro_ph(q or "cat:astro-ph", max_results=lim)
    return {
        "papers": [
            {
                "arxiv_id": p.arxiv_id,
                "title": p.title,
                "authors": p.authors,
                "summary": p.summary,
                "pdf_url": p.pdf_url,
            }
            for p in papers
        ]
    }


@app.get("/api/viz/blackbody")
async def viz_blackbody(t: float = 5800):
    try:
        return blackbody_spectrum_json(t)
    except Exception as e:
        raise HTTPException(400, detail=str(e)) from e


@app.get("/api/viz/orbit-spec")
async def viz_orbit():
    return orbit_demo_spec()


@app.post("/api/chat/stream")
async def chat_stream(body: ChatStreamBody, request: Request):
    if not body.messages:
        raise HTTPException(400, detail="messages required")

    settings = get_settings()
    msgs = [{"role": m.role, "content": m.content} for m in body.messages if m.role and m.content]
    user_bits = [m["content"] for m in msgs if m["role"] == "user"]
    augmented = msgs

    if body.use_arxiv:
        q = (body.arxiv_query or (user_bits[-1] if user_bits else "")).strip()
        extras: list[PaperRef] = []
        try:
            extras = search_astro_ph(q, max_results=6) if q else search_astro_ph("cat:astro-ph", max_results=6)
        except Exception as e:
            logger.warning("arXiv search failed (continuing without): %s", e)
        ctx = format_for_llm_context(extras)
        if ctx:
            augmented = [
                {"role": "system", "content": ctx},
                *msgs,
            ]

    client: httpx.AsyncClient = request.app.state.http

    async def tokens() -> AsyncIterator[str]:
        async for chunk in stream_chat(
            settings=settings,
            messages=augmented,
            client=client,
            provider=body.provider,
            model=body.model_id,
            preference=body.preference,
        ):
            yield chunk

    async def gen():
        try:
            async for chunk in tokens():
                yield _sse({"token": chunk})
            yield _sse("[DONE]")
        except Exception as e:
            logger.exception("chat stream error")
            yield _sse({"error": str(e)})

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/image/generate")
async def image_generate(body: ImageGenBody, request: Request):
    settings = get_settings()
    if not settings.enable_image_gen or not settings.openai_api_key.strip():
        raise HTTPException(503, detail="Image generation disabled (set ASTRO_ENABLE_IMAGE_GEN and OPENAI_API_KEY).")

    client: httpx.AsyncClient = request.app.state.http
    url = f"{settings.openai_base_url.rstrip('/')}/images/generations"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": "dall-e-3", "prompt": body.prompt[:4000], "n": 1, "size": body.size}

    resp = await client.post(url, json=payload, headers=headers, timeout=120.0)
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, detail=resp.text[:500])

    data = resp.json()
    urls = [(d.get("url") or d.get("b64_json")) for d in data.get("data", [])]
    return {"urls": urls, "revised_prompt": data.get("data", [{}])[0].get("revised_prompt")}


@app.get("/health")
async def docker_health_redirect():
    return {"ok": True}


def _mount_static() -> None:
    if DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=str(DIST / "assets")), name="assets")


_mount_static()


def _no_frontend_response():
    return PlainTextResponse(
        "Frontend not built. Run npm install && npm run build in frontend/, or restart via start.sh.",
        status_code=503,
    )


@app.get("/")
async def index():
    idx = DIST / "index.html"
    if idx.is_file():
        return FileResponse(idx)
    return _no_frontend_response()


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    # API lives under separate routes (/api/**); StaticFiles catches /assets
    idx = DIST / "index.html"
    if idx.is_file():
        return FileResponse(idx)
    return _no_frontend_response()