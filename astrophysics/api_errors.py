"""Human-readable errors for LLM HTTP failures (auth, rate limits, bad requests)."""

from __future__ import annotations

import json


def parse_error_body(body: bytes | str) -> str:
    if isinstance(body, bytes):
        try:
            text = body.decode("utf-8", errors="replace")
        except Exception:
            return "(could not decode error body)"
    else:
        text = body
    text = text.strip()
    if not text:
        return "(empty response body)"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text[:800]

    err = data.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err.get("type") or err)[:800]
    if isinstance(err, str):
        return err[:800]
    if "message" in data:
        return str(data["message"])[:800]
    return text[:800]


def format_provider_http_error(
    *,
    provider: str,
    status_code: int,
    body: bytes | str,
    hint: str | None = None,
) -> str:
    """Build a user-facing message for failed chat/completions requests."""
    detail = parse_error_body(body)
    p = provider.strip() or "API"

    if status_code == 401:
        return (
            f"{p}: authentication failed (HTTP 401). The API key may be missing, invalid, or revoked. "
            f"Check the key in your `.env` ({_env_hint(provider)}). Server said: {detail}"
        )
    if status_code == 403:
        return (
            f"{p}: access denied (HTTP 403). The key may be valid but lacks permission for this model or endpoint. "
            f"Details: {detail}"
        )
    if status_code == 429:
        return f"{p}: rate limited (HTTP 429). Retry later or reduce usage. Details: {detail}"
    if status_code == 400:
        return f"{p}: bad request (HTTP 400). Check model name and parameters. Details: {detail}"

    base = f"{p}: request failed (HTTP {status_code}). {detail}"
    if hint:
        return f"{base} Hint: {hint}"
    return base


def _env_hint(provider: str) -> str:
    pl = provider.lower()
    if "anthropic" in pl or pl == "anthropic":
        return "ANTHROPIC_API_KEY"
    if "openai" in pl or "groq" in pl or pl in ("openai", "hosted"):
        return "OPENAI_API_KEY / OPENAI_BASE_URL"
    if "ollama" in pl:
        return "OLLAMA_BASE_URL / OLLAMA_MODEL"
    return "your provider API key settings"


def format_connection_error(provider: str, exc: Exception) -> str:
    msg = str(exc).strip() or type(exc).__name__
    return (
        f"{provider}: could not reach the service ({msg}). "
        f"If using Ollama, ensure it is running and OLLAMA_BASE_URL is correct."
    )
