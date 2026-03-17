"""research_engine — top-level package."""
from .discovery import RepoCrawler, SourceFinder
from .extraction import FactExtractor, InsightExtractor
from .integration import ResearchIntegrator, ResearchReport
from .parsing import CodeExtractor, DocumentParser
from .retrieval import ArxivClient, WebFetcher

__all__ = [
    "ResearchIntegrator",
    "ResearchReport",
    "SourceFinder",
    "RepoCrawler",
    "WebFetcher",
    "ArxivClient",
    "DocumentParser",
    "CodeExtractor",
    "InsightExtractor",
    "FactExtractor",
]
