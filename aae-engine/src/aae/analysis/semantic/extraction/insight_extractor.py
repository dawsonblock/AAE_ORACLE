"""research_engine/extraction/insight_extractor — extract key insights."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class Insight:
    """A single extracted insight or key finding."""

    text: str
    source_url: str = ""
    confidence: float = 0.5
    tags: List[str] = field(default_factory=list)
    insight_type: str = "general"  # "finding" | "recommendation" | "definition"

    @property
    def kind(self) -> str:
        """Alias for :attr:`insight_type`."""
        return self.insight_type


class InsightExtractor:
    """Extract key insights from document segments using heuristics.

    No external LLM required — uses pattern matching and sentence scoring.
    Integration with an LLM is expected at a higher orchestration layer.
    """

    _FINDING_PATTERNS = [
        re.compile(r"^Finding:\s*", re.I),
        re.compile(r"\bwe (found|show|demonstrate|prove|observe)\b", re.I),
        re.compile(r"\bresults? (show|indicate|suggest|reveal)\b", re.I),
        re.compile(r"\bin (this|our) (paper|work|study)\b", re.I),
    ]
    _RECOMMENDATION_PATTERNS = [
        re.compile(r"^Recommendation:\s*", re.I),
        re.compile(
            r"\b(recommend|suggest|advise|propose|should|must)\b", re.I
        ),
        re.compile(r"\bbest practice\b", re.I),
    ]
    _DEFINITION_PATTERNS = [
        re.compile(r"\bis defined as\b|\bwe define\b|\brefers to\b", re.I),
    ]

    def extract(
        self, text: str, source_url: str = "", min_len: int = 40
    ) -> List[Insight]:
        """Extract insights from a block of plain text."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        insights: List[Insight] = []
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < min_len:
                continue
            insight_type, confidence = self._classify(sent)
            if insight_type != "skip":
                insights.append(
                    Insight(
                        text=sent,
                        source_url=source_url,
                        confidence=confidence,
                        insight_type=insight_type,
                    )
                )
        return insights

    def extract_from_segments(
        self, segments: list, source_url: str = ""
    ) -> List[Insight]:
        """Extract from a list of :class:`DocumentSegment` objects."""
        all_insights: List[Insight] = []
        for seg in segments:
            if getattr(seg, "segment_type", "") == "code":
                continue
            all_insights.extend(
                self.extract(seg.content, source_url=source_url)
            )
        return all_insights

    def _classify(self, sentence: str) -> tuple:
        for pat in self._FINDING_PATTERNS:
            if pat.search(sentence):
                return "finding", 0.75
        for pat in self._RECOMMENDATION_PATTERNS:
            if pat.search(sentence):
                return "recommendation", 0.70
        for pat in self._DEFINITION_PATTERNS:
            if pat.search(sentence):
                return "definition", 0.65
        # Include long informative sentences
        if len(sentence.split()) > 15:
            return "general", 0.4
        return "skip", 0.0
