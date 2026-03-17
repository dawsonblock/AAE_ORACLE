class BenchmarkReporter:
    def report(self, summary):
        """Generates a human-readable benchmark report."""
        lines = [
            "=" * 60,
            "BENCHMARK RESULTS",
            "=" * 60,
            f"Total Cases:      {summary['total_cases']}",
            f"Successful:       {summary['success_count']}",
            f"Success Rate:     {summary['success_rate']:.1%}",
        ]
        
        if summary.get('avg_patch_size'):
            lines.append(
                f"Avg Patch Size:   {summary['avg_patch_size']:.0f} chars"
            )
        
        lines.append("=" * 60)
        return "\n".join(lines)
