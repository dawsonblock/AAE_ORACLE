from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from aae.analysis.coverage_runner import CoverageRunner
from aae.code_analysis import CodeAnalyzer
from aae.contracts.planner import PlanBranch
from aae.observability.event_logger import EventLogger
from aae.planning.beam_search import BeamSearch
from aae.planning.branch_memory import BranchMemory
from aae.planning.mutator import Mutator
from aae.planning.plan_evaluator import PlanEvaluator
from aae.planning.ranker import CandidateRanker
from aae.planning.rollout_simulator import RolloutSimulator
from aae.planning.templates import PatchTemplates
from aae.planning.tree_search import TreeSearch
from aae.planning.validator import validate
from aae.storage.ranking_store import RankingStore


class Planner:
    def __init__(
        self,
        evaluator: PlanEvaluator | None = None,
        beam_search: BeamSearch | None = None,
        tree_search: TreeSearch | None = None,
        rollout_simulator: RolloutSimulator | None = None,
        branch_memory: BranchMemory | None = None,
    ) -> None:
        self.analyzer = CodeAnalyzer()
        self.templates = PatchTemplates()
        self.mutator = Mutator()
        self.coverage = CoverageRunner()
        self.ranking_store = RankingStore()
        self.ranker = CandidateRanker(self.ranking_store)
        self.event_logger = EventLogger()
        self.evaluator = evaluator or PlanEvaluator()
        self.beam_search = beam_search or BeamSearch()
        self.tree_search = tree_search or TreeSearch()
        self.rollout_simulator = rollout_simulator or RolloutSimulator()
        self.branch_memory = branch_memory or BranchMemory()

    def _candidate_id(self, code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]

    def _synthesize_templates(self, analysis: Dict[str, Any]) -> List[str]:
        patches: List[str] = []

        defs = analysis["flow"].get("defs", {})
        uses = analysis["flow"].get("uses", {})

        for var in uses.keys():
            patches.append(self.templates.fix_none_check(var))
            break

        for var in defs.keys():
            if var not in uses:
                patches.append(self.templates.initialize_default(var, "None"))
                break

        return [p for p in patches if p]

    def generate(
        self,
        source_code: str,
        target_files: Optional[List[str]] = None,
        trace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        analysis = self.analyzer.analyze(source_code)
        template_patches = self._synthesize_templates(analysis)

        base_cov = self.coverage.run(source_code)
        candidates: List[Dict[str, Any]] = []

        for patch in template_patches:
            mutated_variants = self.mutator.mutate_patch(patch)

            for variant in mutated_variants:
                cov = self.coverage.run(variant)
                coverage_gain = len(
                    set(cov["executed_lines"]) - set(base_cov["executed_lines"])
                )

                candidate = {
                    "id": self._candidate_id(variant),
                    "type": "patch",
                    "confidence": min(0.5 + coverage_gain * 0.05, 0.95),
                    "risk": "low" if len(variant) < 500 else "medium",
                    "target_files": target_files or [],
                    "diff": variant,
                    "trace_id": trace_id,
                }

                verdict = validate(candidate)
                if verdict["valid"]:
                    self.event_logger.log(
                        {
                            "event": "candidate_generated",
                            "stage": "planner",
                            "trace_id": trace_id,
                            "candidate_id": candidate["id"],
                            "target_files": candidate["target_files"],
                        }
                    )
                    candidates.append(candidate)

        return self.ranker.rank(candidates)[:3]

    def build_plan(self, candidates: list[dict]) -> list[PlanBranch]:
        branches = self.tree_search.expand(candidates)
        for branch in branches:
            branch.score = self.evaluator.score(branch) + self.rollout_simulator.score(branch)
            if branch.score <= 0:
                self.branch_memory.remember(
                    branch,
                    status="rejected",
                    rejection_reason="non-positive rollout score",
                )
            else:
                self.branch_memory.remember(branch, status="explored")
        shortlisted = self.beam_search.prune([branch for branch in branches if branch.score > 0])
        for branch in shortlisted:
            branch.metadata["search_score"] = branch.score
        return shortlisted
