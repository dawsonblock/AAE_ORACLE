from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from fastapi import FastAPI, HTTPException

from aae.oracle_bridge.contracts import Candidate, ContractVersion, PlanRequest
from aae.oracle_bridge.oracle_adapters import (
    CANDIDATE_SCHEMA_VERSION,
    OracleCandidateCommand,
    OraclePlanRequest,
    OraclePlanResponse,
    validate_response,
)
from aae.observability.event_logger import EventLogger
from aae.planning.planner import Planner

app = FastAPI()
planner = Planner()
_event_logger = EventLogger()

_metrics = {
    "accepted": 0,
    "rejected": 0,
    "rejection_reasons": defaultdict(int),
}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats")
def stats():
    return {
        "accepted": _metrics["accepted"],
        "rejected": _metrics["rejected"],
        "rejection_reasons": dict(_metrics["rejection_reasons"]),
    }


@app.post("/plan")
def plan(request: PlanRequest):
    if request.version != ContractVersion.V1:
        _metrics["rejected"] += 1
        _metrics["rejection_reasons"]["unsupported_version"] += 1
        raise HTTPException(status_code=400, detail="Unsupported version")

    trace_id = request.trace_id or str(uuid.uuid4())

    try:
        raw_candidates = planner.generate(
            source_code=request.source_code,
            target_files=request.target_files,
            trace_id=trace_id,
        )
        candidates = [Candidate.model_validate(candidate) for candidate in raw_candidates]
        _event_logger.log(
            {
                "stage": "plan",
                "trace_id": trace_id,
                "goal": request.goal,
                "candidate_count": len(candidates),
            }
        )
        _metrics["accepted"] += 1
        return {
            "trace_id": trace_id,
            "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
        }
    except Exception as exc:
        _event_logger.log(
            {
                "stage": "plan_error",
                "trace_id": trace_id,
                "goal": request.goal,
                "error": str(exc),
            }
        )
        _metrics["rejected"] += 1
        _metrics["rejection_reasons"]["planner_error"] += 1
        raise HTTPException(status_code=500, detail="Planner error")


class OraclePlanningBridge:
    REPAIR_WORDS = {"fix", "repair", "bug", "patch", "failing", "failure", "regression", "broken"}
    TEST_WORDS = {"test", "tests", "pytest", "xctest", "unit", "integration", "regression"}
    REFACTOR_WORDS = {"refactor", "cleanup", "restructure", "harden", "simplify"}
    SOURCE_EXTENSIONS = {
        ".py",
        ".swift",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".rs",
        ".go",
        ".java",
        ".kt",
        ".cpp",
        ".cc",
        ".c",
    }

    def plan(self, request: OraclePlanRequest) -> OraclePlanResponse:
        summary, warnings = self._build_summary(
            request.repo_path,
            request.objective,
            request.state_summary,
        )
        test_command = self._recommended_test_command(summary)
        summary["recommended_test_command"] = test_command
        candidates = self._build_candidates(request, summary, test_command)
        response = OraclePlanResponse(
            goal_id=request.goal_id,
            engine=CANDIDATE_SCHEMA_VERSION,
            summary=summary,
            warnings=warnings,
            candidates=candidates[: request.max_candidates],
        )
        if any(candidate.confidence < 0.9 for candidate in response.candidates):
            response.warnings.append("Low confidence candidates returned")
        return validate_response(response)

    def _build_summary(
        self,
        repo_path: str | None,
        objective: str,
        state_summary: str,
    ) -> Tuple[Dict[str, Any], List[str]]:
        warnings: List[str] = []
        profile: Dict[str, Any] = {
            "repo_profile": {
                "exists": False,
                "file_count": 0,
                "dominant_language": "unknown",
                "top_extensions": [],
                "candidate_paths": [],
            }
        }
        if not repo_path:
            warnings.append("repo_path was not provided; using objective-only planning heuristics.")
            return profile, warnings

        path = Path(repo_path)
        if not path.exists():
            warnings.append(f"repo_path does not exist: {repo_path}")
            return profile, warnings

        counts: Counter[str] = Counter()
        candidate_paths: List[str] = []
        for file_path in self._iter_files(path):
            counts[file_path.suffix.lower() or "<none>"] += 1
            relative = file_path.relative_to(path).as_posix()
            if file_path.suffix.lower() in self.SOURCE_EXTENSIONS and len(candidate_paths) < 5:
                candidate_paths.append(relative)

        dominant_ext = counts.most_common(1)[0][0] if counts else "<none>"
        profile["repo_profile"] = {
            "exists": True,
            "file_count": sum(counts.values()),
            "dominant_language": self._language_for_extension(dominant_ext),
            "top_extensions": counts.most_common(8),
            "candidate_paths": self._rank_candidate_paths(path, objective + " " + state_summary, candidate_paths),
        }
        return profile, warnings

    def _iter_files(self, root: Path) -> Iterable[Path]:
        ignored = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".build", "dist", "build"}
        for path in root.rglob("*"):
            if any(part in ignored for part in path.parts):
                continue
            if path.is_file():
                yield path

    def _rank_candidate_paths(self, root: Path, objective: str, fallback_paths: List[str]) -> List[str]:
        objective_lower = objective.lower()
        ranked = []
        for file_path in self._iter_files(root):
            relative = file_path.relative_to(root).as_posix()
            score = 0
            if any(word in relative.lower() for word in objective_lower.split()):
                score += 2
            if "test" in objective_lower and "test" in relative.lower():
                score += 2
            if file_path.suffix.lower() in self.SOURCE_EXTENSIONS:
                score += 1
            if score:
                ranked.append((score, relative))
        ordered = [path for _, path in sorted(ranked, key=lambda item: (-item[0], item[1]))]
        if not ordered:
            ordered = fallback_paths
        return list(dict.fromkeys(ordered))[:3]

    def _language_for_extension(self, ext: str) -> str:
        mapping = {
            ".py": "python",
            ".swift": "swift",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".kt": "kotlin",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".c": "c",
        }
        return mapping.get(ext, "unknown")

    def _recommended_test_command(self, summary: Dict[str, Any]) -> str:
        language = summary.get("repo_profile", {}).get("dominant_language", "unknown")
        if language == "python":
            return "pytest -q"
        if language == "swift":
            return "swift test"
        if language in {"javascript", "typescript"}:
            return "npm test"
        if language == "rust":
            return "cargo test"
        if language == "go":
            return "go test ./..."
        return "run repo-native test command"

    def _build_candidates(
        self,
        request: OraclePlanRequest,
        summary: Dict[str, Any],
        test_command: str,
    ) -> List[OracleCandidateCommand]:
        objective = request.objective.lower()
        candidate_paths = summary.get("repo_profile", {}).get("candidate_paths", [])
        preferred_path = candidate_paths[0] if candidate_paths else None
        candidates = [
            OracleCandidateCommand(
                candidate_id=f"{request.goal_id}-inspect",
                kind="aae.inspect_repository",
                tool="repository_analyzer",
                payload={"repo_path": request.repo_path, "candidate_paths": candidate_paths},
                rationale="Build a grounded repository profile before selecting a mutation or execution path.",
                confidence=0.95,
                predicted_score=0.70,
                safety_class="read_only",
            )
        ]

        if self._contains_any(objective, self.TEST_WORDS) or any("test" in path.lower() for path in candidate_paths):
            candidates.append(
                OracleCandidateCommand(
                    candidate_id=f"{request.goal_id}-tests",
                    kind="aae.run_targeted_tests",
                    tool="sandbox",
                    payload={"command": test_command, "candidate_paths": candidate_paths},
                    rationale="Reproduce the current failure surface and capture a precise test baseline.",
                    confidence=0.92,
                    predicted_score=0.76,
                    safety_class="sandboxed_write",
                )
            )

        if self._contains_any(objective, self.REPAIR_WORDS) or self._contains_any(
            request.state_summary.lower(),
            self.REPAIR_WORDS,
        ):
            candidates.extend(
                [
                    OracleCandidateCommand(
                        candidate_id=f"{request.goal_id}-localize",
                        kind="aae.localize_failure",
                        tool="localization_service",
                        payload={"candidate_paths": candidate_paths},
                        rationale="Fuse failure symptoms, repository structure, and test evidence into a smaller edit region.",
                        confidence=0.90,
                        predicted_score=0.82,
                        safety_class="read_only",
                    ),
                    OracleCandidateCommand(
                        candidate_id=f"{request.goal_id}-patch",
                        kind="aae.generate_patch",
                        tool="patch_engine",
                        payload={"candidate_paths": candidate_paths, "workspace_relative_path": preferred_path},
                        rationale="Generate a bounded candidate patch after localization narrows the edit surface.",
                        confidence=0.90,
                        predicted_score=0.79,
                        safety_class="sandboxed_write",
                        target_file=preferred_path,
                    ),
                    OracleCandidateCommand(
                        candidate_id=f"{request.goal_id}-verify",
                        kind="aae.validate_candidate",
                        tool="verifier",
                        payload={"command": test_command, "candidate_paths": candidate_paths},
                        rationale="Run the candidate through the repository test command before Oracle accepts execution.",
                        confidence=0.84,
                        predicted_score=0.77,
                        safety_class="sandboxed_write",
                    ),
                ]
            )

        if self._contains_any(objective, self.REFACTOR_WORDS):
            candidates.append(
                OracleCandidateCommand(
                    candidate_id=f"{request.goal_id}-impact",
                    kind="aae.estimate_change_impact",
                    tool="graph_service",
                    payload={"candidate_paths": candidate_paths},
                    rationale="Estimate dependency blast radius before a broad structural edit.",
                    confidence=0.83,
                    predicted_score=0.74,
                    safety_class="read_only",
                )
            )

        if len(candidates) == 1:
            candidates.append(
                OracleCandidateCommand(
                    candidate_id=f"{request.goal_id}-analyze",
                    kind="aae.analyze_objective",
                    tool="planner_service",
                    payload={"candidate_paths": candidate_paths},
                    rationale="Produce a ranked next-step analysis when no stronger repo-specific signal is available.",
                    confidence=0.80,
                    predicted_score=0.65,
                    safety_class="read_only",
                )
            )
        return candidates

    def _contains_any(self, text: str, words: Iterable[str]) -> bool:
        return any(word in text for word in words)
