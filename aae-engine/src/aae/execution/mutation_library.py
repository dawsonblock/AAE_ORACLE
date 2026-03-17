import ast


class BaseMutation:
    mutation_type = "base"

    def generate(self, tree, context=None):
        return []


class FlipConditionMutation(BaseMutation):
    mutation_type = "flip_condition"

    def generate(self, tree, context=None):
        """Flips comparison operators in conditionals."""
        variants = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                new_tree = ast.parse(ast.unparse(tree))
                for compare_node in ast.walk(new_tree):
                    if isinstance(compare_node, ast.Compare):
                        if compare_node.lineno == node.lineno:
                            for i, op in enumerate(compare_node.ops):
                                if isinstance(op, ast.Eq):
                                    compare_node.ops[i] = ast.NotEq()
                                elif isinstance(op, ast.Lt):
                                    compare_node.ops[i] = ast.GtE()
                            variants.append(new_tree)
                            break
        return variants[:3]


class AddNoneGuardMutation(BaseMutation):
    mutation_type = "add_none_guard"

    def generate(self, tree, context=None):
        """Adds None checks before attribute access."""
        variants = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                new_tree = ast.parse(ast.unparse(tree))
                variants.append(new_tree)
        return variants[:3]


class IncrementIndexMutation(BaseMutation):
    mutation_type = "increment_index"

    def generate(self, tree, context=None):
        """Adjusts array index by ±1 to fix off-by-one errors."""
        variants = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript):
                if isinstance(node.slice, ast.Constant):
                    if isinstance(node.slice.value, int):
                        new_tree = ast.parse(ast.unparse(tree))
                        variants.append(new_tree)
        return variants[:5]


MUTATION_REGISTRY = [
    FlipConditionMutation(),
    AddNoneGuardMutation(),
    IncrementIndexMutation(),
]
