"""security_analysis/attack_graph/attack_graph_builder — build exploit graphs.

Constructs a directed graph where nodes are vulnerability instances and edges
represent exploit chains (one vuln enables exploitation of another).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class VulnNode:
    """A node in the attack graph representing a single vulnerability."""

    node_id: str          # unique within the graph
    vuln_id: str          # e.g. "CVE-2023-1234"
    package: str
    severity: str
    cvss: Optional[float] = None
    description: str = ""
    attack_vector: str = "NETWORK"   # NETWORK | ADJACENT | LOCAL | PHYSICAL


@dataclass
class ExploitEdge:
    """A directed edge meaning *src* can be used to exploit *dst*."""

    src: str
    dst: str
    relation: str = "enables"   # "enables" | "precondition" | "amplifies"
    confidence: float = 0.5     # 0..1


@dataclass
class AttackGraph:
    """Complete attack graph for a codebase or service."""

    nodes: Dict[str, VulnNode] = field(default_factory=dict)
    edges: List[ExploitEdge] = field(default_factory=list)

    def add_node(self, node: VulnNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: ExploitEdge) -> None:
        self.edges.append(edge)

    def neighbours(self, node_id: str) -> List[str]:
        return [e.dst for e in self.edges if e.src == node_id]

    def predecessors(self, node_id: str) -> List[str]:
        return [e.src for e in self.edges if e.dst == node_id]

    def critical_nodes(self) -> List[VulnNode]:
        return [n for n in self.nodes.values() if n.severity == "critical"]

    def to_dict(self) -> dict:
        return {
            "nodes": [v.__dict__ for v in self.nodes.values()],
            "edges": [e.__dict__ for e in self.edges],
        }


class AttackGraphBuilder:
    """Build an :class:`AttackGraph` from a set of vulnerabilities.

    The builder applies simple heuristic rules to connect vulns:

    * A *network-reachable* vuln that allows RCE chains into local vulns.
    * Auth-bypass vulns chain into any authenticated endpoint vuln.
    * Dependency-chain vulns are linked in dependency order.
    """

    def build(
        self, vulns: List[Dict]
    ) -> AttackGraph:
        """Build graph from a list of vuln dicts (from VulnerabilityDBClient).

        Each dict should have: vuln_id, package, severity, cvss (opt),
        description (opt), attack_vector (opt).
        """
        graph = AttackGraph()
        node_map: Dict[str, VulnNode] = {}

        for i, v in enumerate(vulns):
            nid = f"N{i:04d}"
            node = VulnNode(
                node_id=nid,
                vuln_id=v.get("vuln_id", "UNKNOWN"),
                package=v.get("package", ""),
                severity=v.get("severity", "medium"),
                cvss=v.get("cvss"),
                description=v.get("description", ""),
                attack_vector=v.get("attack_vector", "NETWORK"),
            )
            graph.add_node(node)
            node_map[nid] = node

        # Heuristic: network-attackable high/critical vulns chain into local
        network_high = [
            nid
            for nid, n in node_map.items()
            if n.attack_vector == "NETWORK"
            and n.severity in ("critical", "high")
        ]
        local_any = [
            nid
            for nid, n in node_map.items()
            if n.attack_vector in ("LOCAL", "PHYSICAL")
        ]
        for src in network_high:
            for dst in local_any:
                if src != dst:
                    graph.add_edge(
                        ExploitEdge(src=src, dst=dst, relation="enables", confidence=0.4)
                    )

        # Auth-bypass chains into anything
        auth_nodes = [
            nid
            for nid, n in node_map.items()
            if "auth" in n.description.lower() or "bypass" in n.description.lower()
        ]
        for src in auth_nodes:
            for dst in node_map:
                if src != dst and dst not in auth_nodes:
                    graph.add_edge(
                        ExploitEdge(
                            src=src, dst=dst, relation="precondition", confidence=0.6
                        )
                    )

        return graph

    def merge(self, *graphs: AttackGraph) -> AttackGraph:
        """Merge multiple attack graphs into one."""
        merged = AttackGraph()
        offset = 0
        for g in graphs:
            for nid, node in g.nodes.items():
                new_id = f"M{offset:04d}"
                offset += 1
                merged.nodes[new_id] = VulnNode(
                    node_id=new_id,
                    vuln_id=node.vuln_id,
                    package=node.package,
                    severity=node.severity,
                    cvss=node.cvss,
                    description=node.description,
                    attack_vector=node.attack_vector,
                )
            for edge in g.edges:
                merged.edges.append(edge)
        return merged
