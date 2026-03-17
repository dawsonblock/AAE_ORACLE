import unittest
from aae.execution.mutation_library import (
    FlipConditionMutation,
    IncrementIndexMutation,
    MUTATION_REGISTRY
)
from aae.execution.ast_repair import ASTRepairEngine
from aae.benchmarks.loader import BenchmarkLoader
from aae.benchmarks.runner import BenchmarkRunner
from aae.benchmarks.metrics import BenchmarkMetrics
from aae.benchmarks.reporter import BenchmarkReporter
import ast


class TestMutationEngine(unittest.TestCase):
    def test_flip_condition_generates_variants(self):
        """Tests that FlipConditionMutation produces valid AST variants."""
        code = "def check(x):\n    return x < 10"
        tree = ast.parse(code)
        mutation = FlipConditionMutation()
        variants = mutation.generate(tree)
        
        self.assertGreater(len(variants), 0)

    def test_ast_repair_engine_creates_candidates(self):
        """Tests that ASTRepairEngine generates repair candidates."""
        engine = ASTRepairEngine()
        code = "def get_item(items):\n    return items[len(items)]"
        candidates = engine.generate_candidates("test.py", code)
        
        self.assertIsInstance(candidates, list)

    def test_mutation_registry_populated(self):
        """Verifies that the mutation registry contains multiple types."""
        self.assertGreaterEqual(len(MUTATION_REGISTRY), 3)


class TestBenchmarkSystem(unittest.TestCase):
    def test_benchmark_loader_finds_cases(self):
        """Tests that BenchmarkLoader can discover test cases."""
        loader = BenchmarkLoader()
        cases = loader.load_all(language="python")
        
        self.assertGreaterEqual(len(cases), 1)
        self.assertIn("case_id", cases[0])

    def test_benchmark_metrics_summary(self):
        """Tests that BenchmarkMetrics can aggregate results."""
        metrics = BenchmarkMetrics()
        results = [
            {"evaluation": {"success": True, "patch_size": 10}},
            {"evaluation": {"success": False, "patch_size": 0}},
        ]
        
        summary = metrics.summarize(results)
        self.assertEqual(summary["total_cases"], 2)
        self.assertEqual(summary["success_count"], 1)
        self.assertEqual(summary["success_rate"], 0.5)

    def test_benchmark_reporter_formats_output(self):
        """Tests that BenchmarkReporter generates readable output."""
        reporter = BenchmarkReporter()
        summary = {
            "total_cases": 10,
            "success_count": 7,
            "success_rate": 0.7,
            "avg_patch_size": 45.2
        }
        
        report = reporter.report(summary)
        self.assertIn("70.0%", report)
        self.assertIn("7", report)


if __name__ == "__main__":
    unittest.main()
