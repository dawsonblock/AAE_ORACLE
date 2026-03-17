"""research_engine/parsing/code_extractor — extract code snippets from docs."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CodeSnippet:
    """A single code snippet extracted from a document."""

    content: str
    language: str = "python"
    source_url: str = ""
    context: str = ""           # surrounding paragraph for context
    line_count: int = 0

    def __post_init__(self) -> None:
        if not self.line_count:
            self.line_count = self.content.count("\n") + 1

    @property
    def code(self) -> str:
        """Alias for :attr:`content` (backward-compat accessor)."""
        return self.content


class CodeExtractor:
    """Extract code snippets from Markdown or plain text documents.

    Supports fenced code blocks (```lang ... ```) and indented code.
    """

    _FENCED = re.compile(
        r"```(?P<lang>\w*)?\n(?P<code>.*?)```",
        re.DOTALL,
    )
    _INDENTED = re.compile(r"(?:^    .+\n?)+", re.MULTILINE)

    def extract_from_markdown(
        self, text: str, source_url: str = ""
    ) -> List[CodeSnippet]:
        snippets: List[CodeSnippet] = []
        for m in self._FENCED.finditer(text):
            lang = m.group("lang") or "text"
            code = m.group("code").strip()
            if not code:
                continue
            # Grab up to 200 chars of context before the block
            before = text[max(0, m.start() - 200): m.start()].strip()
            snippets.append(
                CodeSnippet(
                    content=code,
                    language=lang,
                    source_url=source_url,
                    context=before[-200:],
                )
            )
        return snippets

    def extract_from_plain(
        self, text: str, source_url: str = ""
    ) -> List[CodeSnippet]:
        snippets: List[CodeSnippet] = []
        for m in self._INDENTED.finditer(text):
            code = "\n".join(
                line[4:] for line in m.group().splitlines()
            ).strip()
            if code:
                snippets.append(
                    CodeSnippet(content=code, source_url=source_url)
                )
        return snippets

    def extract(
        self, text: str, source_url: str = "", fmt: str = "auto"
    ) -> List[CodeSnippet]:
        if fmt == "markdown" or (fmt == "auto" and "```" in text):
            return self.extract_from_markdown(text, source_url)
        return self.extract_from_plain(text, source_url)

    def filter_by_language(
        self, snippets: List[CodeSnippet], language: str
    ) -> List[CodeSnippet]:
        return [s for s in snippets if s.language.lower() == language.lower()]
