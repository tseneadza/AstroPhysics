"""Load sidebar topics from data/topics.yaml (project root)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOPICS_PATH = PROJECT_ROOT / "data" / "topics.yaml"

_FALLBACK: list[dict[str, Any]] = [
    {
        "id": "cosmo",
        "title": "Cosmology",
        "blurb": "Expansion, microwave background, dark matter and energy.",
    },
]


def load_topics() -> list[dict[str, Any]]:
    if not TOPICS_PATH.is_file():
        logger.warning("Missing %s — using fallback topics", TOPICS_PATH)
        return [dict(t) for t in _FALLBACK]

    try:
        raw = TOPICS_PATH.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
    except Exception as e:
        logger.warning("Failed to read or parse topics YAML: %s — using fallback", e)
        return [dict(t) for t in _FALLBACK]

    if not isinstance(data, dict) or "topics" not in data:
        logger.warning("topics.yaml must contain a top-level 'topics' list — using fallback")
        return [dict(t) for t in _FALLBACK]

    topics = data["topics"]
    if not isinstance(topics, list):
        logger.warning("'topics' must be a list — using fallback")
        return [dict(t) for t in _FALLBACK]

    out: list[dict[str, Any]] = []
    for i, row in enumerate(topics):
        if not isinstance(row, dict):
            logger.warning("Skipping topics[%d]: not an object", i)
            continue
        tid = row.get("id")
        title = row.get("title")
        blurb = row.get("blurb")
        if not tid or not title or not blurb:
            logger.warning("Skipping topics[%d]: missing id, title, or blurb", i)
            continue
        item: dict[str, Any] = {
            "id": str(tid),
            "title": str(title),
            "blurb": str(blurb),
        }
        if row.get("anchors") and isinstance(row["anchors"], list):
            item["anchors"] = [str(a) for a in row["anchors"]]
        aq = row.get("arxiv_query")
        if aq:
            item["arxiv_query"] = str(aq).strip()
        out.append(item)

    if not out:
        logger.warning("No valid topics after parsing — using fallback")
        return [dict(t) for t in _FALLBACK]

    return out
