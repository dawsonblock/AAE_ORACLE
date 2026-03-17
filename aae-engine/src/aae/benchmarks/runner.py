class BenchmarkRunner:
    def run_case(self, case, repair_engine):
        """Runs a single benchmark case: broken repo + expected metadata."""
        baseline = case.get("baseline", {"passed": False})
        if baseline.get("passed"):
            return {"skipped": True, "reason": "baseline already passing"}

        # Expected format for before_state: {'fail': 1}
        return repair_engine.run(
            case.get("candidates", []), 
            {"fail": 1}
        )

    def run_batch(self, cases, repair_engine):
        """Executes a list of benchmark cases sequentially."""
        results = []
        for case in cases:
            results.append(self.run_case(case, repair_engine))
        return results
