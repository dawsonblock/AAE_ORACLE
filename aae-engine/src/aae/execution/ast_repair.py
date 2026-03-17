import ast
from .mutation_library import MUTATION_REGISTRY

class ASTRepairEngine:
    def generate_candidates(self, file_path, code, context=None):
        tree = ast.parse(code)
        candidates = []

        for mutation in MUTATION_REGISTRY:
            variants = mutation.generate(tree, context=context)
            for idx, variant in enumerate(variants):
                try:
                    new_code = ast.unparse(variant)
                except Exception:
                    continue

                candidates.append({
                    "id": f"{mutation.mutation_type}-{idx}",
                    "mutation_type": mutation.mutation_type,
                    "file": file_path,
                    "content": new_code,
                    "content_length": len(new_code),
                    "files_modified": 1,
                })

        return candidates
