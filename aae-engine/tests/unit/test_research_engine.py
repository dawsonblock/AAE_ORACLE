"""tests/unit/test_research_engine.py — unit tests for research engine."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# DocumentParser
# ---------------------------------------------------------------------------

class TestDocumentParser:
    def test_import(self):
        from aae.research_engine.parsing.document_parser import DocumentParser
        assert DocumentParser is not None

    def test_parse_markdown(self):
        from aae.research_engine.parsing.document_parser import DocumentParser
        parser = DocumentParser()
        md = "# Title\n\nSome paragraph text.\n\n## Section\n\nMore text."
        doc = parser.parse(md, source_url="http://example.com")
        assert doc is not None
        assert len(doc.segments) >= 1

    def test_parse_empty(self):
        from aae.research_engine.parsing.document_parser import DocumentParser
        parser = DocumentParser()
        doc = parser.parse("", source_url="http://example.com")
        assert doc is not None
        assert doc.segments == []


# ---------------------------------------------------------------------------
# CodeExtractor
# ---------------------------------------------------------------------------

class TestCodeExtractor:
    def test_import(self):
        from aae.research_engine.parsing.code_extractor import CodeExtractor
        assert CodeExtractor is not None

    def test_extract_fenced(self):
        from aae.research_engine.parsing.code_extractor import CodeExtractor
        extractor = CodeExtractor()
        text = "Some text\n```python\nx = 1\n```\nMore text"
        blocks = extractor.extract(text)
        assert len(blocks) == 1
        assert "x = 1" in blocks[0].code

    def test_extract_multiple(self):
        from aae.research_engine.parsing.code_extractor import CodeExtractor
        extractor = CodeExtractor()
        text = "```python\na = 1\n```\n\n```bash\necho hi\n```"
        blocks = extractor.extract(text)
        assert len(blocks) == 2

    def test_extract_empty(self):
        from aae.research_engine.parsing.code_extractor import CodeExtractor
        extractor = CodeExtractor()
        blocks = extractor.extract("No code here.")
        assert blocks == []


# ---------------------------------------------------------------------------
# InsightExtractor
# ---------------------------------------------------------------------------

class TestInsightExtractor:
    def test_import(self):
        from aae.research_engine.extraction.insight_extractor import InsightExtractor
        assert InsightExtractor is not None

    def test_extract_finding(self):
        from aae.research_engine.extraction.insight_extractor import InsightExtractor
        extractor = InsightExtractor()
        text = "Finding: SQL injection was discovered in the login endpoint."
        insights = extractor.extract(text)
        assert len(insights) >= 1
        assert insights[0].kind in {"finding", "recommendation", "definition"}

    def test_extract_recommendation(self):
        from aae.research_engine.extraction.insight_extractor import InsightExtractor
        extractor = InsightExtractor()
        text = "Recommendation: Always sanitize user inputs before processing."
        insights = extractor.extract(text)
        assert len(insights) >= 1

    def test_extract_empty(self):
        from aae.research_engine.extraction.insight_extractor import InsightExtractor
        extractor = InsightExtractor()
        insights = extractor.extract("")
        assert insights == []


# ---------------------------------------------------------------------------
# FactExtractor
# ---------------------------------------------------------------------------

class TestFactExtractor:
    def test_import(self):
        from aae.research_engine.extraction.fact_extractor import FactExtractor
        assert FactExtractor is not None

    def test_extract_version(self):
        from aae.research_engine.extraction.fact_extractor import FactExtractor
        extractor = FactExtractor()
        text = "Django version 4.2.1 was released with security patches."
        facts = extractor.extract(text)
        assert isinstance(facts, list)

    def test_extract_empty(self):
        from aae.research_engine.extraction.fact_extractor import FactExtractor
        extractor = FactExtractor()
        facts = extractor.extract("")
        assert facts == []
