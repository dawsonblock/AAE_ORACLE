"""repository_intelligence/graph/ris_graph_builder — build repo call graph."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

log = logging.getLogger(__name__)


@dataclass
class GraphNode:
    """A node in the repository dependency graph."""

    node_id: str
    label: str
    kind: str = "file"      # "file" | "symbol" | "module"
    file: str = ""
    lineno: int = 0
    metadata: Dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    """A directed edge between two nodes."""

    src: str
    dst: str
    edge_type: str = "imports"   # "imports" | "calls" | "inherits" | "uses"
    weight: float = 1.0


@dataclass
class RepoGraph:
    """Full repository intelligence graph."""

    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges.append(edge)

    def neighbours(self, node_id: str) -> List[str]:
        return [e.dst for e in self.edges if e.src == node_id]

    def predecessors(self, node_id: str) -> List[str]:
        return [e.src for e in self.edges if e.dst == node_id]

    def stats(self) -> Dict:
        return {"nodes": len(self.nodes), "edges": len(self.edges)}


class RISGraphBuilder:
    """Build a :class:`RepoGraph` from symbol and dependency data.

    Parameters
    ----------
    repo_root:
        Repository root directory.
    """

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self._root = repo_root or Path(".")

    def build(self, dep_map: Dict, symbol_map: Dict) -> RepoGraph:
        """Build graph from DependencyExtractor and SymbolExtractor outputs.

        Parameters
        ----------
        dep_map:
            ``{file_path: FileDependencies}`` from :class:`DependencyExtractor`.
        symbol_map:
            ``{file_path: List[Symbol]}`` from :class:`SymbolExtractor`.
        """
        graph = RepoGraph()

        # Add file nodes
        for file_path in dep_map:
            nid = self._file_node_id(file_path)
            graph.add_node(
                GraphNode(node_id=nid, label=file_path, kind="file", file=file_path)
            )

        # Add symbol nodes and file→symbol edges
        for file_path, symbols in symbol_map.items():
            file_nid = self._file_node_id(file_path)
            for sym in symbols:
                sym_nid = f"SYM:{file_path}:{sym.name}"
                graph.add_node(
                    GraphNode(
                        node_id=sym_nid,
                        label=sym.name,
                        kind=sym.kind,
                        file=file_path,
                        lineno=sym.lineno,
                    )
                )
                graph.add_edge(
                    GraphEdge(src=file_nid, dst=sym_nid, edge_type="defines")
                )

        # Add import edges between file nodes
        for file_path, deps in dep_map.items():
            src_nid = self._file_node_id(file_path)
            for imp in set(deps.imports + deps.from_imports):
                # Try to resolve to a known file node
                for candidate in dep_map:
                    if imp.replace(".", "/") in candidate:
                        dst_nid = self._file_node_id(candidate)
                        if src_nid != dst_nid:
                            graph.add_edge(
                                GraphEdge(
                                    src=src_nid,
                                    dst=dst_nid,
                                    edge_type="imports",
                                )
                            )

        return graph

    def build_from_directory(self) -> RepoGraph:
        """Convenience: run extraction then build graph."""
        from ..extraction import DependencyExtractor, SymbolExtractor
        dep_ext = DependencyExtractor()
        sym_ext = SymbolExtractor()
        dep_map = dep_ext.extract_directory(self._root)
        sym_map = sym_ext.extract_directory(self._root)
        return self.build(dep_map, sym_map)

    @staticmethod
    def _file_node_id(file_path: str) -> str:
        return f"FILE:{file_path}"
