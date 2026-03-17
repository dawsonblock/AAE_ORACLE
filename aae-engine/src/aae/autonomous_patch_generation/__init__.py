"""autonomous_patch_generation — top-level package."""
from .context import ContextAssembler, PatchContext, SymbolResolver
from .generation import GeneratedPatch, PatchGenerator, TemplateEngine
from .scoring import PatchScore, PatchScorer
from .simulation import PreFlightSimulator, SimulationResult
from .testing import PatchTester, TestRun
from .validation import PatchValidator, ValidationResult

__all__ = [
    "ContextAssembler",
    "PatchContext",
    "SymbolResolver",
    "PatchGenerator",
    "GeneratedPatch",
    "TemplateEngine",
    "PreFlightSimulator",
    "SimulationResult",
    "PatchTester",
    "TestRun",
    "PatchScorer",
    "PatchScore",
    "PatchValidator",
    "ValidationResult",
]
