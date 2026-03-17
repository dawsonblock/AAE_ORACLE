import ast

class DataFlowAnalyzer:
    def analyze(self, tree):
        defs = {}
        uses = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defs.setdefault(target.id, []).append(node.lineno)

            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                uses.setdefault(node.id, []).append(node.lineno)

        return {"defs": defs, "uses": uses}
