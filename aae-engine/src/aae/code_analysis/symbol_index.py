from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from aae.contracts.graph import GraphSnapshot, SymbolDefinition, SymbolReference


class SymbolIndex:
    """Lightweight symbol index for graph queries.

    Provides the same interface as ReferenceIndex but is importable without
    triggering circular import chains through aae.graph or aae.analysis.graph.
    """

    def __init__(
        self,
        definitions: "List[SymbolDefinition]",
        references: "List[SymbolReference] | None" = None,
    ) -> None:
        self._definitions = definitions
        self._references = references or []
        self._by_key: dict = defaultdict(list)
        self._refs_by_symbol: dict = defaultdict(list)
        self._refs_by_name: dict = defaultdict(list)
        for d in definitions:
            for key in {d.name, d.qualname, d.file_path, getattr(d, "class_scope", ""), getattr(d, "signature", "")}:
                if key:
                    self._by_key[key].append(d)
        for r in self._references:
            if getattr(r, "resolved_symbol_id", None):
                self._refs_by_symbol[r.resolved_symbol_id].append(r)
            self._refs_by_name[r.referenced_name].append(r)

    @classmethod
    def from_snapshot(cls, snapshot: "GraphSnapshot") -> "SymbolIndex":
        return cls(list(snapshot.symbols), list(getattr(snapshot, "references", [])))

    def lookup(self, value: str) -> "List[SymbolDefinition]":
        candidates = list(self._by_key.get(value, []))
        if candidates:
            return _dedupe(candidates)
        lowered = value.lower()
        fuzzy: list = []
        for key, defs in self._by_key.items():
            if lowered in key.lower():
                fuzzy.extend(defs)
        return _dedupe(fuzzy)

    def find_references(self, symbol: str) -> "List[SymbolReference]":
        definitions = self.lookup(symbol)
        refs: list = []
        for d in definitions:
            refs.extend(self._refs_by_symbol.get(d.symbol_id, []))
        refs.extend(self._refs_by_name.get(symbol, []))
        return _dedupe_refs(refs)

    def rank_related_symbols(self, symbol: str) -> list:
        from collections import Counter
        hits: Counter = Counter()
        for ref in self.find_references(symbol):
            key = getattr(ref, "resolved_symbol_id", None) or getattr(ref, "referenced_name", "")
            if key and key != symbol:
                hits[key] += 1
        ranked = []
        for key, count in hits.most_common():
            d = next((item for item in self._definitions if item.symbol_id == key), None)
            ranked.append({
                "symbol_id": getattr(d, "symbol_id", key),
                "name": getattr(d, "name", key),
                "qualname": getattr(d, "qualname", key),
                "file_path": getattr(d, "file_path", ""),
                "reference_count": count,
                "coverage_count": 0,
            })
        return ranked

    def symbols_for_file(self, file_path: str) -> "List[SymbolDefinition]":
        return [d for d in self._definitions if d.file_path == file_path]

    def related_files(self, symbols) -> list:
        paths = []
        seen: set = set()
        for symbol in symbols:
            for d in self.lookup(symbol):
                if d.file_path and d.file_path not in seen:
                    seen.add(d.file_path)
                    paths.append(d.file_path)
        return paths


def _dedupe(definitions: "List[SymbolDefinition]") -> "List[SymbolDefinition]":
    seen: set = set()
    out: list = []
    for d in definitions:
        if d.symbol_id in seen:
            continue
        seen.add(d.symbol_id)
        out.append(d)
    return out


def _dedupe_refs(refs: "List[SymbolReference]") -> "List[SymbolReference]":
    seen: set = set()
    out: list = []
    for r in refs:
        key = (
            getattr(r, "source_symbol_id", None),
            getattr(r, "referenced_name", ""),
            getattr(r, "resolved_symbol_id", None),
            getattr(r, "file_path", ""),
            getattr(r, "line", None),
            getattr(r, "reference_type", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


__all__ = ["SymbolIndex"]
