"""Hybrid streaming: Ollama (local), OpenAI-compatible APIs, and Anthropic Messages API."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from astrophysics.api_errors import format_connection_error, format_provider_http_error
from astrophysics.config import ASTRO_SYSTEM_PROMPT, Settings

logger = logging.getLogger(__name__)


def _merge_consecutive_roles(items: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in items:
        if out and out[-1]["role"] == m["role"]:
            out[-1]["content"] = out[-1]["content"] + "\n\n" + m["content"]
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out


def _anthropic_system_and_messages(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    """Build Anthropic `system` string and user/assistant `messages` (no system role inside)."""
    extra_system: list[str] = []
    conv: list[dict[str, str]] = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "system":
            extra_system.append(content)
        elif role in ("user", "assistant"):
            conv.append({"role": role, "content": content})
    system = ASTRO_SYSTEM_PROMPT
    if extra_system:
        system = system + "\n\n" + "\n\n".join(extra_system)
    conv = _merge_consecutive_roles(conv)
    return system, conv


async def stream_ollama(
    *,
    settings: Settings,
    model: str,
    messages: list[dict[str, str]],
    client: httpx.AsyncClient,
) -> AsyncIterator[str]:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    body = {
        "model": model,
        "messages": [{"role": "system", "content": ASTRO_SYSTEM_PROMPT}, *messages],
        "stream": True,
    }
    try:
        async with client.stream("POST", url, json=body, timeout=httpx.Timeout(120.0)) as resp:
            if resp.status_code != 200:
                err = await resp.aread()
                raise RuntimeError(
                    format_provider_http_error(
                        provider="Ollama",
                        status_code=resp.status_code,
                        body=err,
                        hint="Check OLLAMA_BASE_URL and that `ollama serve` is running.",
                    )
                )
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                chunk = data.get("message") or {}
                t = chunk.get("content") or ""
                if t:
                    yield t
    except httpx.RequestError as e:
        raise RuntimeError(format_connection_error("Ollama", e)) from e


async def stream_openai_compatible(
    *,
    settings: Settings,
    model: str,
    messages: list[dict[str, str]],
    client: httpx.AsyncClient,
) -> AsyncIterator[str]:
    if not settings.openai_api_key.strip():
        raise RuntimeError(
            "OpenAI-compatible API requires OPENAI_API_KEY in `.env` (or unset provider to use another backend)."
        )
    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [{"role": "system", "content": ASTRO_SYSTEM_PROMPT}, *messages],
        "stream": True,
    }
    try:
        async with client.stream("POST", url, json=body, headers=headers, timeout=httpx.Timeout(120.0)) as resp:
            if resp.status_code != 200:
                err = await resp.aread()
                raise RuntimeError(
                    format_provider_http_error(
                        provider="OpenAI-compatible",
                        status_code=resp.status_code,
                        body=err,
                        hint="Verify OPENAI_API_KEY and OPENAI_BASE_URL (e.g. OpenAI, Groq).",
                    )
                )
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:].strip()
                if payload == "[DONE]":
                    break
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = data.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                t = delta.get("content") or ""
                if t:
                    yield t
    except httpx.RequestError as e:
        raise RuntimeError(format_connection_error("OpenAI-compatible API", e)) from e


async def stream_anthropic(
    *,
    settings: Settings,
    model: str,
    messages: list[dict[str, str]],
    client: httpx.AsyncClient,
) -> AsyncIterator[str]:
    if not settings.anthropic_api_key.strip():
        raise RuntimeError(
            "Anthropic requires ANTHROPIC_API_KEY in `.env`. "
            "Get a key at https://console.anthropic.com/ and add it without quotes."
        )
    base = settings.anthropic_base_url.rstrip("/")
    url = f"{base}/v1/messages"
    system, conv = _anthropic_system_and_messages(messages)
    if not conv:
        raise RuntimeError("No user/assistant messages to send to Anthropic.")

    headers = {
        "x-api-key": settings.anthropic_api_key.strip(),
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": 8192,
        "stream": True,
        "system": system,
        "messages": conv,
    }

    try:
        async with client.stream("POST", url, json=body, headers=headers, timeout=httpx.Timeout(120.0)) as resp:
            if resp.status_code != 200:
                err = await resp.aread()
                raise RuntimeError(
                    format_provider_http_error(
                        provider="Anthropic",
                        status_code=resp.status_code,
                        body=err,
                        hint="Verify ANTHROPIC_API_KEY and model id (e.g. claude-sonnet-4-20250514).",
                    )
                )

            current_event = ""
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("event: "):
                    current_event = line[7:].strip()
                    continue
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                typ = data.get("type")
                if typ == "error":
                    err_obj = data.get("error") or data
                    raise RuntimeError(f"Anthropic stream error: {err_obj}")

                if current_event == "error" or typ == "error":
                    err_obj = data.get("error") if isinstance(data.get("error"), dict) else data
                    raise RuntimeError(f"Anthropic stream error: {err_obj}")

                if typ == "content_block_delta":
                    delta = data.get("delta") or {}
                    if delta.get("type") == "text_delta":
                        t = delta.get("text") or ""
                        if t:
                            yield t
                elif current_event == "content_block_delta":
                    delta = data.get("delta") or {}
                    if delta.get("type") == "text_delta":
                        t = delta.get("text") or ""
                        if t:
                            yield t
    except httpx.RequestError as e:
        raise RuntimeError(format_connection_error("Anthropic", e)) from e


async def ollama_available(settings: Settings, client: httpx.AsyncClient) -> bool:
    try:
        r = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=3.0)
        return r.status_code == 200
    except Exception as e:
        logger.debug("Ollama probe failed: %s", e)
        return False


def _pick_model(settings: Settings, provider: str, override: str | None) -> str:
    o = (override or "").strip()
    if o:
        return o
    if provider == "ollama":
        return settings.ollama_model
    if provider == "openai":
        return settings.openai_model
    if provider == "anthropic":
        return settings.anthropic_model
    return settings.ollama_model


async def stream_chat(
    *,
    settings: Settings,
    messages: list[dict[str, str]],
    client: httpx.AsyncClient,
    provider: str,
    model: str | None,
    preference: str,
) -> AsyncIterator[str]:
    """
    provider: auto | ollama | openai | anthropic
    preference (when provider is auto): auto | local | hosted — local tries Ollama first; hosted tries cloud APIs first.
    model: optional override for the active provider's model id.
    """
    pv = provider if provider in ("auto", "ollama", "openai", "anthropic") else "auto"

    if pv == "ollama":
        m = _pick_model(settings, "ollama", model)
        async for t in stream_ollama(settings=settings, model=m, messages=messages, client=client):
            yield t
        return

    if pv == "openai":
        m = _pick_model(settings, "openai", model)
        async for t in stream_openai_compatible(settings=settings, model=m, messages=messages, client=client):
            yield t
        return

    if pv == "anthropic":
        m = _pick_model(settings, "anthropic", model)
        async for t in stream_anthropic(settings=settings, model=m, messages=messages, client=client):
            yield t
        return

    # auto
    pref = preference if preference in ("local", "hosted") else settings.primary
    if pref == "auto":
        pref = settings.primary
    try_local_first = pref == "local"

    if try_local_first:
        if await ollama_available(settings, client):
            try:
                m = _pick_model(settings, "ollama", model)
                async for t in stream_ollama(settings=settings, model=m, messages=messages, client=client):
                    yield t
                return
            except Exception as e:
                logger.warning("Ollama stream failed in auto mode, trying cloud: %s", e)

        if settings.openai_api_key.strip():
            try:
                m = _pick_model(settings, "openai", model)
                async for t in stream_openai_compatible(
                    settings=settings, model=m, messages=messages, client=client
                ):
                    yield t
                return
            except Exception as e:
                logger.warning("OpenAI-compatible failed in auto mode: %s", e)

        if settings.anthropic_api_key.strip():
            m = _pick_model(settings, "anthropic", model)
            async for t in stream_anthropic(settings=settings, model=m, messages=messages, client=client):
                yield t
            return

        raise RuntimeError(
            "Auto mode could not run any backend: Ollama unreachable, and no OPENAI_API_KEY or ANTHROPIC_API_KEY set. "
            "Start Ollama or add at least one cloud API key in `.env`."
        )

    # hosted first
    if settings.openai_api_key.strip():
        try:
            m = _pick_model(settings, "openai", model)
            async for t in stream_openai_compatible(settings=settings, model=m, messages=messages, client=client):
                yield t
            return
        except Exception as e:
            logger.warning("OpenAI-compatible failed (hosted-first): %s", e)

    if settings.anthropic_api_key.strip():
        try:
            m = _pick_model(settings, "anthropic", model)
            async for t in stream_anthropic(settings=settings, model=m, messages=messages, client=client):
                yield t
            return
        except Exception as e:
            logger.warning("Anthropic failed (hosted-first): %s", e)

    if await ollama_available(settings, client):
        m = _pick_model(settings, "ollama", model)
        async for t in stream_ollama(settings=settings, model=m, messages=messages, client=client):
            yield t
        return

    raise RuntimeError(
        "No hosted API key worked (OpenAI/Anthropic), and Ollama is not reachable. "
        "Check keys in `.env` or start Ollama."
    )


