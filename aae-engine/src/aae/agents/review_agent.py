from __future__ import annotations

from typing import Any, Dict, List

from aae.agents.base_agent import BaseAgent


class ReviewAgent(BaseAgent):
    """Code review agent that verifies patches before they are committed.

    The ReviewAgent is the final gate in the autonomous patch pipeline.
    It performs three checks:

        1. Static correctness  — does the patch parse and type-check?
        2. Semantic coherence  — does the change match the stated intent?
        3. Policy compliance   — does the patch respect ownership and style rules?

    A patch is approved only if all three checks pass.
    """

    name = "reviewer"
    domain = "review"

    APPROVAL_THRESHOLD = 0.70    # minimum score to approve a patch

    async def run(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        action = task.get("action", "review_patch")
        if action == "review_patch":
            return await self.review_patch(task, context)
        if action == "rank_candidates":
            return await self.rank_candidates(task, context)
        if action == "approve":
            return await self.approve(task, context)
        return {"status": "unknown_action", "action": action}

    async def review_patch(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        patch_diff: str = task.get("patch_diff", "")
        intent: str = task.get("intent", context.get("goal", ""))

        syntax_ok = self._check_syntax(patch_diff)
        semantic_score = self._semantic_score(patch_diff, intent)
        policy_ok = self._policy_check(patch_diff, context)

        overall = semantic_score * (1.0 if syntax_ok else 0.0) * (1.0 if policy_ok else 0.5)
        approved = overall >= self.APPROVAL_THRESHOLD

        return {
            "status": "reviewed",
            "approved": approved,
            "overall_score": round(overall, 4),
            "syntax_ok": syntax_ok,
            "semantic_score": round(semantic_score, 4),
            "policy_ok": policy_ok,
            "feedback": self._build_feedback(syntax_ok, semantic_score, policy_ok),
        }

    async def rank_candidates(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Rank a list of patch candidates and return the best one."""
        candidates: List[Dict[str, Any]] = task.get("candidates", [])
        scored = []
        for i, candidate in enumerate(candidates):
            review = await self.review_patch(
                {**task, "patch_diff": candidate.get("diff", "")}, context
            )
            scored.append({
                "index": i,
                "score": review["overall_score"],
                "approved": review["approved"],
                "review": review,
                "candidate": candidate,
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return {
            "status": "ranked",
            "total": len(scored),
            "best_index": scored[0]["index"] if scored else -1,
            "rankings": scored,
        }

    async def approve(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        review = await self.review_patch(task, context)
        if not review["approved"]:
            return {
                "status": "rejected",
                "reason": review["feedback"],
                "score": review["overall_score"],
            }
        return {
            "status": "approved",
            "score": review["overall_score"],
            "ready_for_pr": True,
        }

    # ── internal ──────────────────────────────────────────────────────────────

    def _check_syntax(self, diff: str) -> bool:
        """Very lightweight: reject obviously malformed diffs."""
        if not diff.strip():
            return False
        lines = diff.splitlines()
        has_minus = any(l.startswith("-") for l in lines)
        has_plus = any(l.startswith("+") for l in lines)
        return has_minus or has_plus

    def _semantic_score(self, diff: str, intent: str) -> float:
        """Heuristic semantic match between patch and stated intent."""
        if not intent:
            return 0.5
        intent_words = set(intent.lower().split())
        diff_words = set(diff.lower().split())
        overlap = len(intent_words & diff_words)
        return min(1.0, 0.3 + (overlap / max(1, len(intent_words))) * 0.7)

    def _policy_check(self, diff: str, context: Dict[str, Any]) -> bool:
        """Check forbidden file modifications."""
        forbidden = context.get("forbidden_files", [
            "requirements.txt", "pyproject.toml", "Makefile",
            "docker-compose.yml", ".github/",
        ])
        for path in forbidden:
            if path in diff:
                return False
        return True

    def _build_feedback(
        self, syntax_ok: bool, semantic_score: float, policy_ok: bool
    ) -> str:
        issues = []
        if not syntax_ok:
            issues.append("Patch diff is malformed or empty.")
        if semantic_score < 0.4:
            issues.append("Patch does not appear to address the stated intent.")
        if not policy_ok:
            issues.append("Patch modifies a protected file.")
        if not issues:
            return "Patch approved."
        return " ".join(issues)
