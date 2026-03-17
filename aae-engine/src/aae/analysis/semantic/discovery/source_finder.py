"""research_engine/discovery/source_finder — locate research sources."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class Source:
    """A discovered research source."""

    url: str
    title: str = ""
    source_type: str = "web"   # "web" | "arxiv" | "github" | "docs"
    relevance: float = 0.5     # 0..1
    tags: List[str] = field(default_factory=list)


class SourceFinder:
    """Discover relevant research sources from a query.

    Combines web search (via Jina/SerpAPI) and known curated domains.
    """

    _CURATED_DOMAINS = [
        "arxiv.org",
        "github.com",
        "docs.python.org",
        "pypi.org",
        "stackoverflow.com",
        "engineering.blogs.google.com",
        "huggingface.co",
    ]

    def __init__(self, max_sources: int = 20) -> None:
        self._max = max_sources

    async def find(self, query: str, context: Optional[str] = None) -> List[Source]:
        """Return a list of relevant sources for *query*."""
        sources: List[Source] = []
        sources.extend(await self._web_search(query))
        sources.extend(self._curated_lookup(query))
        sources = self._deduplicate(sources)
        sources.sort(key=lambda s: s.relevance, reverse=True)
        return sources[: self._max]

    async def _web_search(self, query: str) -> List[Source]:
        try:
            import httpx
            params = {"q": query, "num": 10}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://r.jina.ai/search", params=params
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
                results = []
                for item in data.get("data", []):
                    results.append(
                        Source(
                            url=item.get("url", ""),
                            title=item.get("title", ""),
                            source_type="web",
                            relevance=0.6,
                        )
                    )
                return results
        except Exception as exc:
            log.debug("Web search failed: %s", exc)
            return []

    def _curated_lookup(self, query: str) -> List[Source]:
        tokens = query.lower().split()
        sources = []
        for domain in self._CURATED_DOMAINS:
            relevance = sum(1 for t in tokens if t in domain) / max(len(tokens), 1)
            if relevance > 0:
                sources.append(
                    Source(
                        url=f"https://{domain}/search?q={query.replace(' ', '+')}",
                        title=domain,
                        source_type="docs",
                        relevance=round(relevance * 0.5, 3),
                    )
                )
        return sources

    @staticmethod
    def _deduplicate(sources: List[Source]) -> List[Source]:
        seen: set = set()
        out = []
        for s in sources:
            if s.url not in seen:
                seen.add(s.url)
                out.append(s)
        return out
