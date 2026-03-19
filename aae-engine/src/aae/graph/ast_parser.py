import ast
from typing import Any, Dict, List

from aae.analysis.graph.ast_parser import ParsedPythonFile, PythonAstParser


class ASTParser:
    def parse(self, source: str) -> Dict[str, List[Dict[str, Any]]]:
        tree = ast.parse(source)

        functions = []
        classes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(
                    {
                        "name": node.name,
                        "lineno": node.lineno,
                    }
                )
            elif isinstance(node, ast.ClassDef):
                classes.append(
                    {
                        "name": node.name,
                        "lineno": node.lineno,
                    }
                )

        return {
            "functions": functions,
            "classes": classes,
        }


__all__ = ["ASTParser", "ParsedPythonFile", "PythonAstParser"]
