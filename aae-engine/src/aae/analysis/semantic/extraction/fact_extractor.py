"""research_engine/extraction/fact_extractor — extract structured facts."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class Fact:
    """A structured fact extracted from text."""

    subject: str
    predicate: str
    obj: str
    source_url: str = ""
    confidence: float = 0.5


class FactExtractor:
    """Extract simple subject-predicate-object triples from text.

    Uses regex patterns rather than NLP to keep dependencies minimal.
    """

    _TRIPLE_PATTERNS = [
        # "X is Y" / "X are Y"
        re.compile(
            r"\b(?P<subj>[A-Z][a-zA-Z\s]{2,30})\s+(?P<pred>is|are)\s+"
            r"(?P<obj>[a-zA-Z\s]{2,40}?)(?:[.,;]|$)",
            re.MULTILINE,
        ),
        # "X uses Y"
        re.compile(
            r"\b(?P<subj>[A-Z][a-zA-Z\s]{1,20})\s+"
            r"(?P<pred>uses?|supports?|provides?|requires?)\s+"
            r"(?P<obj>[a-zA-Z0-9\s._-]{2,40}?)(?:[.,;]|$)",
            re.MULTILINE,
        ),
    ]

    # Named entity patterns (simple heuristics)
    _VERSION_RE = re.compile(r"v?\d+\.\d+(?:\.\d+)?")
    _API_RE = re.compile(r"\b([A-Z][a-zA-Z]+API|[A-Z][a-zA-Z]+SDK)\b")

    def extract(self, text: str, source_url: str = "") -> List[Fact]:
        facts: List[Fact] = []
        for pat in self._TRIPLE_PATTERNS:
            for m in pat.finditer(text):
                facts.append(
                    Fact(
                        subject=m.group("subj").strip(),
                        predicate=m.group("pred").strip(),
                        obj=m.group("obj").strip(),
                        source_url=source_url,
                        confidence=0.55,
                    )
                )
        return facts

    def extract_versions(self, text: str) -> List[str]:
        """Return all version strings found in *text*."""
        return list({m.group() for m in self._VERSION_RE.finditer(text)})

    def extract_apis(self, text: str) -> List[str]:
        """Return all API/SDK identifiers found in *text*."""
        return list({m.group() for m in self._API_RE.finditer(text)})
