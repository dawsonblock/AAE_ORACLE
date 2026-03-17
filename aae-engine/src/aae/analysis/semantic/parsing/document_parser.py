"""research_engine/parsing/document_parser — parse documents into segments."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class DocumentSegment:
    """A meaningful chunk of a parsed document."""

    segment_id: str
    content: str
    segment_type: str = "paragraph"   # "heading" | "paragraph" | "code" | "list"
    heading: Optional[str] = None
    tokens: int = 0

    def __post_init__(self) -> None:
        if not self.tokens:
            self.tokens = len(self.content.split())


@dataclass
class ParsedDocument:
    """Full parsed document."""

    source_url: str
    title: str = ""
    segments: List[DocumentSegment] = field(default_factory=list)
    language: str = "en"

    def full_text(self) -> str:
        return "\n\n".join(s.content for s in self.segments)

    def code_blocks(self) -> List[DocumentSegment]:
        return [s for s in self.segments if s.segment_type == "code"]

    def headings(self) -> List[str]:
        return [s.content for s in self.segments if s.segment_type == "heading"]


class DocumentParser:
    """Parse HTML, Markdown, or plain text into :class:`ParsedDocument`."""

    _CODE_FENCE = re.compile(r"```(?:\w+)?\n(.*?)```", re.DOTALL)
    _HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)

    def parse_markdown(self, text: str, url: str = "") -> ParsedDocument:
        segments: List[DocumentSegment] = []
        sid = 0
        # Extract code blocks first
        positions = {}
        for m in self._CODE_FENCE.finditer(text):
            positions[(m.start(), m.end())] = m.group(1)
            segments.append(
                DocumentSegment(
                    segment_id=f"S{sid:04d}",
                    content=m.group(1).strip(),
                    segment_type="code",
                )
            )
            sid += 1
        # Remove code blocks from text and parse remainder
        clean = self._CODE_FENCE.sub("", text)
        current_heading: Optional[str] = None
        para_lines: List[str] = []

        def _flush(lines: List[str]) -> None:
            nonlocal sid
            block = " ".join(lines).strip()
            if block:
                segments.append(
                    DocumentSegment(
                        segment_id=f"S{sid:04d}",
                        content=block,
                        segment_type="paragraph",
                        heading=current_heading,
                    )
                )
                sid += 1

        for line in clean.splitlines():
            h = self._HEADING.match(line)
            if h:
                _flush(para_lines)
                para_lines = []
                current_heading = h.group(1)
                segments.append(
                    DocumentSegment(
                        segment_id=f"S{sid:04d}",
                        content=h.group(1),
                        segment_type="heading",
                    )
                )
                sid += 1
            elif line.strip():
                para_lines.append(line.strip())
            else:
                _flush(para_lines)
                para_lines = []
        _flush(para_lines)

        title = ""
        if segments and segments[0].segment_type == "heading":
            title = segments[0].content
        return ParsedDocument(source_url=url, title=title, segments=segments)

    def parse_plain(self, text: str, url: str = "") -> ParsedDocument:
        segments = []
        for i, para in enumerate(re.split(r"\n{2,}", text)):
            para = para.strip()
            if para:
                segments.append(
                    DocumentSegment(
                        segment_id=f"S{i:04d}",
                        content=para,
                        segment_type="paragraph",
                    )
                )
        return ParsedDocument(source_url=url, segments=segments)

    def parse(
        self,
        text: str,
        url: str = "",
        fmt: str = "auto",
        source_url: str = "",
    ) -> ParsedDocument:
        """Parse *text* into a :class:`ParsedDocument`.

        ``source_url`` is accepted as an alias for ``url``.
        """
        resolved_url = source_url or url
        if fmt == "markdown" or (
            fmt == "auto" and text.strip().startswith("#")
        ):
            return self.parse_markdown(text, resolved_url)
        return self.parse_plain(text, resolved_url)
