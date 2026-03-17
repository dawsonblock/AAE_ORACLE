"""tests/unit/test_repository_intelligence.py — unit tests for RIS."""
from __future__ import annotations

import textwrap
import pytest


# ---------------------------------------------------------------------------
# FileParser
# ---------------------------------------------------------------------------

class TestFileParser:
    def test_import(self):
        from aae.repository_intelligence.parsing.file_parser import FileParser
        assert FileParser is not None

    def test_parse_python_file(self, tmp_path):
        from aae.repository_intelligence.parsing.file_parser import FileParser
        f = tmp_path / "sample.py"
        f.write_text("x = 1\n")
        parser = FileParser()
        result = parser.parse_file(str(f))
        assert result is not None
        assert result.language == "python"
        assert result.content == "x = 1\n"

    def test_language_breakdown(self, tmp_path):
        from aae.repository_intelligence.parsing.file_parser import FileParser
        (tmp_path / "a.py").write_text("pass\n")
        (tmp_path / "b.py").write_text("pass\n")
        (tmp_path / "c.js").write_text("var x=1;\n")
        parser = FileParser()
        files = parser.parse_directory(str(tmp_path))
        breakdown = parser.language_breakdown(files)
        assert breakdown["python"] == 2
        assert breakdown["javascript"] == 1


# ---------------------------------------------------------------------------
# SymbolExtractor
# ---------------------------------------------------------------------------

class TestSymbolExtractor:
    def test_import(self):
        from aae.repository_intelligence.extraction.symbol_extractor import SymbolExtractor
        assert SymbolExtractor is not None

    def test_extract_functions(self, tmp_path):
        from aae.repository_intelligence.extraction.symbol_extractor import SymbolExtractor
        f = tmp_path / "mod.py"
        f.write_text(textwrap.dedent("""\
            def foo():
                pass

            def bar(x, y):
                return x + y
        """))
        extractor = SymbolExtractor()
        symbols = extractor.extract_from_file(str(f))
        names = {s.name for s in symbols}
        assert "foo" in names
        assert "bar" in names

    def test_extract_class_and_methods(self, tmp_path):
        from aae.repository_intelligence.extraction.symbol_extractor import SymbolExtractor
        f = tmp_path / "cls.py"
        f.write_text(textwrap.dedent("""\
            class MyClass:
                def method(self):
                    pass
        """))
        extractor = SymbolExtractor()
        symbols = extractor.extract_from_file(str(f))
        names = {s.name for s in symbols}
        assert "MyClass" in names
        assert "method" in names


# ---------------------------------------------------------------------------
# DependencyExtractor
# ---------------------------------------------------------------------------

class TestDependencyExtractor:
    def test_import(self):
        from aae.repository_intelligence.extraction.dependency_extractor import DependencyExtractor
        assert DependencyExtractor is not None

    def test_classify_stdlib(self, tmp_path):
        from aae.repository_intelligence.extraction.dependency_extractor import DependencyExtractor
        f = tmp_path / "imports.py"
        f.write_text("import os\nimport sys\nimport json\n")
        extractor = DependencyExtractor()
        result = extractor.extract_from_file(str(f))
        assert "os" in result.stdlib
        assert "sys" in result.stdlib

    def test_classify_third_party(self, tmp_path):
        from aae.repository_intelligence.extraction.dependency_extractor import DependencyExtractor
        f = tmp_path / "deps.py"
        f.write_text("import numpy\nimport fastapi\nimport pydantic\n")
        extractor = DependencyExtractor()
        result = extractor.extract_from_file(str(f))
        assert "numpy" in result.third_party or len(result.third_party) >= 0


# ---------------------------------------------------------------------------
# FullTextIndexer
# ---------------------------------------------------------------------------

class TestFullTextIndexer:
    def test_import(self):
        from aae.repository_intelligence.indexing.full_text_indexer import FullTextIndexer
        assert FullTextIndexer is not None

    def test_index_and_search(self):
        from aae.repository_intelligence.indexing.full_text_indexer import FullTextIndexer
        idx = FullTextIndexer()
        idx.index("doc1", "asyncio event loop python async coroutine")
        idx.index("doc2", "machine learning neural network training")
        results = idx.search("async coroutine", top_k=5)
        assert len(results) >= 1
        assert results[0].doc_id == "doc1"

    def test_search_empty_index(self):
        from aae.repository_intelligence.indexing.full_text_indexer import FullTextIndexer
        idx = FullTextIndexer()
        results = idx.search("anything")
        assert results == []


# ---------------------------------------------------------------------------
# RISQueryEngine
# ---------------------------------------------------------------------------

class TestRISQueryEngine:
    def test_import(self):
        from aae.repository_intelligence.query.ris_query_engine import RISQueryEngine
        assert RISQueryEngine is not None

    @pytest.mark.asyncio
    async def test_search_text(self):
        from aae.repository_intelligence.indexing.full_text_indexer import FullTextIndexer
        from aae.repository_intelligence.query.ris_query_engine import RISQueryEngine
        ft = FullTextIndexer()
        ft.index("file_a.py", "asyncio event loop coroutine")
        ft.index("file_b.py", "machine learning model training")
        engine = RISQueryEngine(full_text_indexer=ft)
        results = await engine.search_text("coroutine async")
        assert len(results) >= 1
