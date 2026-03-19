from __future__ import annotations

from typing import Any, Dict, Optional

from aae.analysis.experiment_evaluator import ExperimentEvaluator
from aae.analysis.failure_localizer import FailureLocalizer
from aae.evaluation.test_harness import TestHarness
from aae.observability.event_logger import EventLogger
from aae.execution.patch_applier import PatchApplier
from aae.oracle_bridge.result_service import ResultService
from aae.planning.planner import Planner


class RepairLoop:
    def __init__(self) -> None:
        self.harness = TestHarness()
        self.localizer = FailureLocalizer()
        self.applier = PatchApplier()
        self.evaluator = ExperimentEvaluator()
        self.result_service = ResultService()
        self.planner = Planner()
        self.event_logger = EventLogger()

    def run(
        self,
        project_path: str | Dict[str, Any],
        source_code: str | Dict[str, Any],
        file_path: str,
        trace_id: Optional[str] = None,
        goal_id: str = "repair",
    ) -> Dict[str, Any]:
        if isinstance(project_path, dict):
            sandbox_result = project_path
            patch_candidate = source_code if isinstance(source_code, dict) else {}
            failures = self.localizer.extract(
                str(sandbox_result.get("stdout", "")) + "\n" + str(sandbox_result.get("stderr", ""))
            )
            return {
                "status": "completed",
                "trace_id": trace_id,
                "goal_id": goal_id,
                "failures": failures,
                "best_score": 0.0,
                "best_candidate": patch_candidate,
                "applied": False,
            }

        self.event_logger.log(
            {
                "stage": "repair_start",
                "trace_id": trace_id,
                "goal_id": goal_id,
                "file_path": file_path,
            }
        )
        baseline = self.harness.run(project_path)
        if baseline["status"] == "success":
            return {"status": "no_fix_needed", "trace_id": trace_id, "goal_id": goal_id}

        failures = self.localizer.extract(baseline["output"] + "\n" + baseline["errors"])
        candidates = self.planner.generate(
            source_code=source_code,
            target_files=[file_path],
            trace_id=trace_id,
        )

        best_score = -1.0
        best_candidate = None

        for candidate in candidates:
            patch_meta = self.applier.apply(file_path, candidate["diff"])
            result = self.harness.run(project_path)
            evaluation = self.evaluator.evaluate(goal_id, result)
            score = evaluation["score"]

            self.result_service.ingest(
                {
                    "trace_id": trace_id,
                    "goal": goal_id,
                    "candidate_id": candidate["id"],
                    "candidate_type": candidate["type"],
                    "target_files": candidate["target_files"],
                    "accepted": score > 0.8,
                    "execution_result": result["status"],
                    "metrics": evaluation["metrics"],
                }
            )

            self.applier.rollback(file_path)

            if score > best_score:
                best_score = score
                best_candidate = candidate

        if best_candidate is not None:
            self.applier.apply(file_path, best_candidate["diff"])

        self.event_logger.log(
            {
                "stage": "repair_complete",
                "trace_id": trace_id,
                "goal_id": goal_id,
                "best_score": best_score,
                "applied": best_candidate is not None,
            }
        )
        return {
            "status": "completed",
            "trace_id": trace_id,
            "goal_id": goal_id,
            "failures": failures,
            "best_score": best_score,
            "best_candidate": best_candidate,
            "applied": best_candidate is not None,
        }
