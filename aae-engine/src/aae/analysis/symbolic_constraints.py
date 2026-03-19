from z3 import Int, Solver, sat


class ConstraintEngine:
    def check_integer_bounds(self, lower: int, upper: int) -> bool:
        x = Int("x")
        s = Solver()
        s.add(x >= lower)
        s.add(x <= upper)
        return s.check() == sat

    def check_no_div_zero(self) -> bool:
        x = Int("x")
        s = Solver()
        s.add(x != 0)
        return s.check() == sat

    def validate_patch_safety(self, candidate) -> bool:
        diff = candidate.get("diff", "")

        if not diff.strip():
            return False
        if len(diff) > 10000:
            return False
        if " / 0" in diff:
            return False
        if "import os" in diff or "import subprocess" in diff:
            return False

        return True
