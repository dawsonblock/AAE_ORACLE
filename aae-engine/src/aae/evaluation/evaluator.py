class Evaluator:
    def evaluate(self, before, after, patch_size=0):
        success = after["fail"] == 0
        return {
            "success": success,
            "fail_before": before["fail"],
            "fail_after": after["fail"],
            "patch_size": patch_size,
        }
