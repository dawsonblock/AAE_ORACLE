from __future__ import annotations

import random


class Mutator:
    """Coverage-guided source code mutator.

    Applies simple syntactic mutations to explore new execution paths.
    Mutations are lightweight and reversible — they should be combined with
    coverage scoring to filter useful variants.
    """

    _STRATEGIES = [
        lambda line: line.replace("==", "!=", 1),
        lambda line: line.replace(">", "<", 1),
        lambda line: line.replace("<", ">", 1),
        lambda line: line.replace("True", "False", 1),
        lambda line: line.replace("False", "True", 1),
        lambda line: line + "  # mutated",
    ]

    def mutate(self, source: str) -> str:
        """Apply a single random mutation to source code.

        Picks a random line and applies a random mutation strategy.
        Lines that would produce a no-op (unchanged after mutation) are
        skipped.  Falls back to a comment-append mutation if no effective
        mutation is found within 10 attempts.
        """
        lines = source.split("\n")
        if not lines:
            return source

        for _ in range(10):
            idx = random.randint(0, len(lines) - 1)
            original = lines[idx]
            strategy = random.choice(self._STRATEGIES)
            mutated = strategy(original)
            if mutated != original:
                result = list(lines)
                result[idx] = mutated
                return "\n".join(result)

        # Fallback: append a comment to a random non-empty line
        non_empty = [i for i, l in enumerate(lines) if l.strip()]
        if non_empty:
            idx = random.choice(non_empty)
            result = list(lines)
            result[idx] = lines[idx] + "  # mutated"
            return "\n".join(result)

        return source


__all__ = ["Mutator"]
