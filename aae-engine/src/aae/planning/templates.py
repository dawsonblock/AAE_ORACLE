class PatchTemplates:
    def fix_none_check(self, var: str) -> str:
        return f"if {var} is None:\n    return\n"

    def add_guard(self, condition: str) -> str:
        return f"if not ({condition}):\n    raise ValueError('guard failed')\n"

    def safe_division(self, a: str, b: str) -> str:
        return f"{a} / {b} if {b} != 0 else 0"

    def early_return_if_invalid(self, condition: str) -> str:
        return f"if {condition}:\n    return\n"

    def initialize_default(self, var: str, value: str) -> str:
        return f"{var} = {value}\n"
