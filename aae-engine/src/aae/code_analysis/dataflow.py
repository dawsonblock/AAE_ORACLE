import ast
from collections import defaultdict
from typing import Dict, List


class DataFlowAnalyzer(ast.NodeVisitor):
    def __init__(self) -> None:
        self.defs: Dict[str, List[int]] = defaultdict(list)
        self.uses: Dict[str, List[int]] = defaultdict(list)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.defs[target.id].append(node.lineno)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        self.uses[node.id].append(node.lineno)
        self.generic_visit(node)

    def analyze(self, source: str) -> Dict[str, Dict[str, List[int]]]:
        self.defs.clear()
        self.uses.clear()

        tree = ast.parse(source)
        self.visit(tree)

        return {
            "defs": dict(self.defs),
            "uses": dict(self.uses),
        }
