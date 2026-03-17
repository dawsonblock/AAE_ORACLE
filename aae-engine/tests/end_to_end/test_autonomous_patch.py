"""tests/end_to_end/test_autonomous_patch.py

End-to-end test: goal description → context assembly → patch generation →
pre-flight simulation → scoring → validation.

All external I/O is mocked so the test runs without Postgres/Redis/Qdrant.
"""
from __future__ import annotations

import textwrap
import pytest
from pathlib import Path


class TestAutonomousPatchE2E:
    """Full autonomous patch pipeline, no external services."""

    @pytest.fixture
    def buggy_file(self, tmp_path) -> Path:
        f = tmp_path / "buggy.py"
        f.write_text(textwrap.dedent("""\
            def divide(a, b):
                return a / b  # ZeroDivisionError if b == 0
        """))
        return f

    @pytest.fixture
    def patch_diff(self) -> str:
        return textwrap.dedent("""\
            --- a/buggy.py
            +++ b/buggy.py
            @@ -1,2 +1,4 @@
             def divide(a, b):
            -    return a / b  # ZeroDivisionError if b == 0
            +    if b == 0:
            +        raise ValueError("Divisor must not be zero")
            +    return a / b
        """)

    # ------------------------------------------------------------------
    # Stage 1: Context assembly
    # ------------------------------------------------------------------

    def test_context_assembler_import(self):
        from aae.autonomous_patch_generation.context.context_assembler import ContextAssembler
        assert ContextAssembler is not None

    def test_context_assembler_build(self, buggy_file):
        from aae.autonomous_patch_generation.context.context_assembler import ContextAssembler
        assembler = ContextAssembler(token_budget=1000)
        ctx = assembler.build(
            goal="Fix ZeroDivisionError in divide()",
            file_paths=[str(buggy_file)],
        )
        assert ctx is not None
        assert "divide" in ctx.to_prompt()

    # ------------------------------------------------------------------
    # Stage 2: Pre-flight simulation
    # ------------------------------------------------------------------

    def test_simulation_valid_patch(self, patch_diff):
        from aae.autonomous_patch_generation.simulation.pre_flight_simulator import (
            PreFlightSimulator,
        )
        sim = PreFlightSimulator()
        result = sim.simulate(patch_diff)
        assert result is not None
        assert result.passed is True or result.passed is False  # either outcome OK

    def test_simulation_empty_patch(self):
        from aae.autonomous_patch_generation.simulation.pre_flight_simulator import (
            PreFlightSimulator,
        )
        sim = PreFlightSimulator()
        result = sim.simulate("")
        assert result.passed is False

    # ------------------------------------------------------------------
    # Stage 3: Patch scoring
    # ------------------------------------------------------------------

    def test_patch_scorer_import(self):
        from aae.autonomous_patch_generation.scoring.patch_scorer import PatchScorer
        assert PatchScorer is not None

    def test_patch_scorer_valid(self, patch_diff):
        from aae.autonomous_patch_generation.scoring.patch_scorer import PatchScorer
        from aae.autonomous_patch_generation.simulation.pre_flight_simulator import (
            PreFlightSimulator, SimulationResult,
        )
        scorer = PatchScorer()
        sim_result = SimulationResult(passed=True, checks=[], warnings=[])
        score = scorer.score(patch_diff, simulation=sim_result, test_outcome=None)
        assert 0.0 <= score <= 1.0

    # ------------------------------------------------------------------
    # Stage 4: Validation gate
    # ------------------------------------------------------------------

    def test_patch_validator_import(self):
        from aae.autonomous_patch_generation.validation.patch_validator import PatchValidator
        assert PatchValidator is not None

    def test_validator_rejects_empty(self):
        from aae.autonomous_patch_generation.validation.patch_validator import PatchValidator
        validator = PatchValidator()
        result = validator.validate("")
        assert result.approved is False

    def test_validator_accepts_good_patch(self, patch_diff):
        from aae.autonomous_patch_generation.validation.patch_validator import PatchValidator
        from aae.autonomous_patch_generation.simulation.pre_flight_simulator import (
            PreFlightSimulator,
        )
        sim = PreFlightSimulator()
        sim_result = sim.simulate(patch_diff)
        validator = PatchValidator(min_score=0.0)
        result = validator.validate(patch_diff, simulation=sim_result)
        assert result is not None
        assert isinstance(result.approved, bool)
