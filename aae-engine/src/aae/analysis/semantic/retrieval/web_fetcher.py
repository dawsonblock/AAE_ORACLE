"""research_engine/retrieval/web_fetcher — fetch and clean web page content."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class FetchedPage:
    url: str
    title: str = ""
    text: str = ""
    markdown: str = ""
    status_code: int = 0
    error: Optional[str] = None


class WebFetcher:
    """Fetch web pages and extract clean text/markdown via Jina Reader.

    Falls back to direct HTML fetch + basic stripping when Jina is unavailable.

    Parameters
    ----------
    use_jina:
        Route through ``https://r.jina.ai/`` for markdown extraction.
    timeout:
        HTTP timeout in seconds.
    """

    _JINA_PREFIX = "https://r.jina.ai/"

    def __init__(self, use_jina: bool = True, timeout: float = 15.0) -> None:
        self._use_jina = use_jina
        self._timeout = timeout

    async def fetch(self, url: str) -> FetchedPage:
        try:
            import httpx
            target = f"{self._JINA_PREFIX}{url}" if self._use_jina else url
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    target,
                    headers={"Accept": "text/markdown, text/plain, text/html"},
                    follow_redirects=True,
                )
                body = resp.text
                if self._use_jina:
                    return FetchedPage(
                        url=url,
                        markdown=body,
                        text=self._strip_markdown(body),
                        status_code=resp.status_code,
                    )
                title, text = self._parse_html(body)
                return FetchedPage(
                    url=url,
                    title=title,
                    text=text,
                    status_code=resp.status_code,
                )
        except Exception as exc:
            log.debug("fetch failed for %s: %s", url, exc)
            return FetchedPage(url=url, error=str(exc))

    async def fetch_many(self, urls: list) -> list:
        import asyncio
        return list(await asyncio.gather(*[self.fetch(u) for u in urls]))

    @staticmethod
    def _strip_markdown(md: str) -> str:
        text = re.sub(r"#+\s*", "", md)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
        text = re.sub(r"`{1,3}[^`]*`{1,3}", "", text)
        return text.strip()

    @staticmethod
    def _parse_html(html: str) -> tuple:
        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        title = title_m.group(1).strip() if title_m else ""
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s{2,}", " ", text).strip()
        return title, text
