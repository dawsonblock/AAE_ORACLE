class ExecutionGuard:
    @staticmethod
    def assert_sandbox(context: str) -> None:
        if context != "sandbox":
            raise RuntimeError("Unauthorized execution path")
