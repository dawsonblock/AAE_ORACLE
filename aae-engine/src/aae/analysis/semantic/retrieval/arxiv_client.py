"""research_engine/retrieval/arxiv_client — query arXiv for papers."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional
from xml.etree import ElementTree as ET

log = logging.getLogger(__name__)

_NS = {"atom": "http://www.w3.org/2005/Atom"}
_ARXIV_API = "http://export.arxiv.org/api/query"


@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    summary: str
    authors: List[str] = field(default_factory=list)
    published: str = ""
    pdf_url: str = ""
    categories: List[str] = field(default_factory=list)


class ArxivClient:
    """Query the arXiv public API for research papers.

    Parameters
    ----------
    max_results:
        Default number of results to retrieve.
    timeout:
        HTTP timeout in seconds.
    """

    def __init__(self, max_results: int = 10, timeout: float = 15.0) -> None:
        self._max = max_results
        self._timeout = timeout

    async def search(
        self, query: str, max_results: Optional[int] = None
    ) -> List[ArxivPaper]:
        """Full-text search arXiv and return parsed papers."""
        n = max_results or self._max
        try:
            import httpx
            params = {
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": n,
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(_ARXIV_API, params=params)
                resp.raise_for_status()
                return self._parse(resp.text)
        except Exception as exc:
            log.debug("arXiv search failed: %s", exc)
            return []

    async def fetch_by_id(self, arxiv_id: str) -> Optional[ArxivPaper]:
        """Retrieve a single paper by arXiv ID (e.g. ``"2303.08774"``)."""
        papers = await self.search(f"id:{arxiv_id}", max_results=1)
        return papers[0] if papers else None

    @staticmethod
    def _parse(xml_text: str) -> List[ArxivPaper]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            log.warning("arXiv XML parse error: %s", exc)
            return []
        papers = []
        for entry in root.findall("atom:entry", _NS):
            def _text(tag: str) -> str:
                el = entry.find(f"atom:{tag}", _NS)
                return el.text.strip() if el is not None and el.text else ""

            arxiv_id_raw = _text("id")
            arxiv_id = arxiv_id_raw.split("/abs/")[-1] if "/abs/" in arxiv_id_raw else arxiv_id_raw
            authors = [
                (a.find("atom:name", _NS).text or "").strip()
                for a in entry.findall("atom:author", _NS)
                if a.find("atom:name", _NS) is not None
            ]
            pdf_url = ""
            for link in entry.findall("atom:link", _NS):
                if link.attrib.get("title") == "pdf":
                    pdf_url = link.attrib.get("href", "")
            categories = [
                c.attrib.get("term", "")
                for c in entry.findall("atom:category", _NS)
            ]
            papers.append(
                ArxivPaper(
                    arxiv_id=arxiv_id,
                    title=_text("title"),
                    summary=_text("summary"),
                    authors=authors,
                    published=_text("published"),
                    pdf_url=pdf_url,
                    categories=categories,
                )
            )
        return papers
