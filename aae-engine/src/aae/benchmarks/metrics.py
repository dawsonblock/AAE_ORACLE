class BenchmarkMetrics:
    def summarize(self, results):
        """Aggregates batch results into key performance indicators (KPIs)."""
        valid_results = [r for r in results if r and not r.get("skipped")]
        total = len(valid_results)
        
        successes = [r for r in valid_results if r.get("evaluation", {}).get("success")]
        success_count = len(successes)
        
        avg_patch_size = 0
        if success_count > 0:
            avg_patch_size = sum(
                s.get("evaluation", {}).get("patch_size", 0) for s in successes
            ) / success_count

        return {
            "total_cases": total,
            "success_count": success_count,
            "success_rate": success_count / total if total > 0 else 0.0,
            "avg_patch_size": avg_patch_size
        }
