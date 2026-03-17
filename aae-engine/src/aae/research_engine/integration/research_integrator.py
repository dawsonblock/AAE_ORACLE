"""research_engine/integration/research_integrator — merge research outputs.

Combines results from web fetching, arXiv retrieval, parsing, and extraction
into a unified :class:`ResearchReport` ready for agent consumption.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class ResearchReport:
    """Unified research report for a given query."""

    query: str
    insights: List[Dict] = field(default_factory=list)
    facts: List[Dict] = field(default_factory=list)
    code_snippets: List[Dict] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    arxiv_papers: List[Dict] = field(default_factory=list)
    summary: str = ""

    def as_context(self, max_tokens: int = 4000) -> str:
        """Render the report as a compact text context string."""
        parts = [f"# Research: {self.query}\n"]
        if self.summary:
            parts.append(f"## Summary\n{self.summary}\n")
        if self.arxiv_papers:
            parts.append("## Relevant Papers")
            for p in self.arxiv_papers[:3]:
                parts.append(
                    f"- [{p.get('title', '?')}] {p.get('summary', '')[:200]}"
                )
        if self.insights:
            parts.append("\n## Key Insights")
            for ins in self.insights[:10]:
                parts.append(f"- {ins.get('text', '')[:300]}")
        if self.code_snippets:
            parts.append("\n## Code Examples")
            for snip in self.code_snippets[:3]:
                lang = snip.get("language", "")
                code = snip.get("content", "")[:500]
                parts.append(f"```{lang}\n{code}\n```")
        text = "\n".join(parts)
        # Rough token trim
        words = text.split()
        if len(words) > max_tokens:
            text = " ".join(words[:max_tokens]) + "\n...[truncated]"
        return text


class ResearchIntegrator:
    """Orchestrate sub-components to produce a :class:`ResearchReport`.

    This class is intentionally thin — it delegates to the individual
    subsystem classes and merges their outputs.
    """

    def __init__(
        self,
        use_jina: bool = True,
        max_sources: int = 10,
        max_arxiv: int = 5,
    ) -> None:
        self._use_jina = use_jina
        self._max_sources = max_sources
        self._max_arxiv = max_arxiv

    async def research(self, query: str) -> ResearchReport:
        """Full research pipeline: discover → fetch → parse → extract."""
        report = ResearchReport(query=query)
        try:
            from ..discovery import SourceFinder
            from ..retrieval import ArxivClient, WebFetcher
            from ..parsing import CodeExtractor, DocumentParser
            from ..extraction import FactExtractor, InsightExtractor

            # 1. Discover sources
            finder = SourceFinder(max_sources=self._max_sources)
            sources = await finder.find(query)
            report.sources = [s.url for s in sources]

            # 2. Fetch pages
            fetcher = WebFetcher(use_jina=self._use_jina)
            pages = await fetcher.fetch_many([s.url for s in sources[:5]])

            # 3. Fetch arXiv
            arxiv = ArxivClient(max_results=self._max_arxiv)
            papers = await arxiv.search(query)
            report.arxiv_papers = [
                {
                    "arxiv_id": p.arxiv_id,
                    "title": p.title,
                    "summary": p.summary,
                    "pdf_url": p.pdf_url,
                }
                for p in papers
            ]

            # 4. Parse + extract
            parser = DocumentParser()
            extractor = InsightExtractor()
            fact_extractor = FactExtractor()
            code_extractor = CodeExtractor()

            for page in pages:
                if page.error or not (page.markdown or page.text):
                    continue
                text = page.markdown or page.text
                doc = parser.parse(text, url=page.url)
                insights = extractor.extract_from_segments(
                    doc.segments, source_url=page.url
                )
                report.insights.extend(
                    [{"text": i.text, "type": i.insight_type} for i in insights]
                )
                facts = fact_extractor.extract(page.text, source_url=page.url)
                report.facts.extend(
                    [{"subject": f.subject, "predicate": f.predicate, "object": f.obj}
                     for f in facts]
                )
                snippets = code_extractor.extract(text, source_url=page.url)
                report.code_snippets.extend(
                    [{"language": s.language, "content": s.content} for s in snippets]
                )

            # 5. Build summary from first insight
            if report.insights:
                report.summary = report.insights[0].get("text", "")
            elif papers:
                report.summary = papers[0].summary[:500]

        except Exception as exc:
            log.error("Research pipeline failed for query '%s': %s", query, exc)

        return report
