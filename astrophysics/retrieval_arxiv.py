"""Lightweight cached arXiv search (astro-ph)."""

import hashlib
import time
from dataclasses import dataclass

import arxiv

_CACHE: dict[str, tuple[float, list]] = {}
_TTL_SEC = 300.0


@dataclass
class PaperRef:
    title: str
    authors: str
    summary: str
    arxiv_id: str
    pdf_url: str


def _cache_key(query: str, max_results: int) -> str:
    raw = f"{query.strip().lower()}|{max_results}"
    return hashlib.sha256(raw.encode()).hexdigest()


def search_astro_ph(query: str, max_results: int = 8) -> list[PaperRef]:
    """Return recent/search-matched papers; results cached ~5 minutes."""
    if not query.strip():
        query = "cat:astro-ph"
    key = _cache_key(query, max_results)
    now = time.monotonic()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL_SEC:
        return hit[1]

    q = query if query.startswith("cat:") else f"({query}) AND cat:astro-ph"
    search = arxiv.Search(
        query=q,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    out: list[PaperRef] = []
    for r in search.results():
        authors = ", ".join(a.name for a in r.authors[:5])
        if len(r.authors) > 5:
            authors += ", …"
        entry_id = r.entry_id.split("/abs/")[-1] if r.entry_id else ""
        out.append(
            PaperRef(
                title=r.title.replace("\n", " ").strip(),
                authors=authors,
                summary=(r.summary or "").replace("\n", " ").strip()[:800],
                arxiv_id=entry_id,
                pdf_url=r.pdf_url or "",
            )
        )

    _CACHE[key] = (now, out)
    return out


def format_for_llm_context(papers: list[PaperRef]) -> str:
    if not papers:
        return ""
    lines = ["Recent / matching arXiv (astro-ph) — use as citations only, do not invent details:"]
    for p in papers:
        lines.append(f"- [{p.arxiv_id}] {p.title} — {p.authors}. Summary: {p.summary[:400]}…")
    return "\n".join(lines)
