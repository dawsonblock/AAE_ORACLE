from __future__ import annotations

import hashlib
import logging
import time
from collections import Counter
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Tuple

from fastapi import FastAPI

from .contracts import OracleCandidateCommand, OraclePlanRequest, OraclePlanResponse, validate_response

app = FastAPI()

# Configure observability logger
observability_logger = logging.getLogger("aae.oracle_bridge.observability")
observability_logger.setLevel(logging.INFO)
if not observability_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    ))
    observability_logger.addHandler(handler)


def _compute_payload_hash(request: OraclePlanRequest) -> str:
    """Compute hash of request payload for correlation."""
    payload = f"{request.goal_id}:{request.objective}:{request.state_summary}:{request.repo_path}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _log_timing_metric(operation: str, duration_ms: float, metadata: Dict[str, Any] = None):
    """Log timing metrics for observability."""
    observability_logger.info(
        f"TIMING | operation={operation} | duration_ms={duration_ms:.2f} | "
        f"metadata={metadata or {}}"
    )


class OraclePlanningBridge:
    """Generate ranked candidate commands for Oracle without taking execution authority."""

    REPAIR_WORDS = {'fix', 'repair', 'bug', 'patch', 'failing', 'failure', 'regression', 'broken'}
    TEST_WORDS = {'test', 'tests', 'pytest', 'xctest', 'unit', 'integration', 'regression'}
    REFACTOR_WORDS = {'refactor', 'cleanup', 'restructure', 'harden', 'simplify'}
    STOP_WORDS = {
        'the', 'and', 'for', 'with', 'into', 'from', 'that', 'this', 'those', 'these', 'your', 'their', 'its',
        'repo', 'repository', 'code', 'module', 'system', 'flow', 'service', 'tests', 'test', 'failing', 'failure',
        'broken', 'repair', 'fix', 'patch', 'run', 'validate', 'candidate', 'strict', 'planner', 'objective',
    }
    SOURCE_EXTENSIONS = {
        '.py', '.swift', '.js', '.ts', '.tsx', '.jsx', '.rs', '.go', '.java', '.kt', '.cpp', '.cc', '.c', '.h',
        '.hpp', '.m', '.mm', '.rb', '.php'
    }

    def plan(self, request: OraclePlanRequest) -> OraclePlanResponse:
        """Plan with full observability logging."""
        start_time = time.perf_counter()
        payload_hash = _compute_payload_hash(request)
        
        observability_logger.info(
            f"REQUEST_RECEIVED | goal_id={request.goal_id} | "
            f"payload_hash={payload_hash} | objective_len={len(request.objective)} | "
            f"max_candidates={request.max_candidates}"
        )
        
        try:
            summary, warnings = self._build_summary(request.repo_path, request.objective, request.state_summary)
            
            # Log repo profile captured
            repo_profile = summary.get('repo_profile', {})
            observability_logger.info(
                f"REPO_PROFILE_CAPTURED | goal_id={request.goal_id} | "
                f"payload_hash={payload_hash} | exists={repo_profile.get('exists', False)} | "
                f"file_count={repo_profile.get('file_count', 0)} | "
                f"dominant_language={repo_profile.get('dominant_language', 'unknown')} | "
                f"candidate_paths_count={len(repo_profile.get('candidate_paths', []))}"
            )
            
            test_command = self._recommended_test_command(summary)
            summary['recommended_test_command'] = test_command
            candidates = self._build_candidates(request, summary, test_command)
            
            # Log candidates returned with rankings
            candidate_rankings = [
                {
                    'candidate_id': c.candidate_id,
                    'kind': c.kind,
                    'confidence': c.confidence,
                    'predicted_score': c.predicted_score,
                }
                for c in candidates
            ]
            observability_logger.info(
                f"CANDIDATES_RETURNED | goal_id={request.goal_id} | "
                f"payload_hash={payload_hash} | count={len(candidates)} | "
                f"rankings={candidate_rankings}"
            )
            
            final_candidates = candidates[: request.max_candidates]
            low_conf = [c for c in final_candidates if c.confidence < 0.9]
            if low_conf:
                min_conf = min(c.confidence for c in low_conf)
                warnings.append(
                    f"Low confidence candidates in plan: {len(low_conf)} "
                    f"candidate(s) below 0.9 threshold (min: {min_conf:.2f})"
                )

            response = OraclePlanResponse(
                goal_id=request.goal_id,
                summary=summary,
                warnings=warnings,
                candidates=final_candidates,
            )
            # Validate at API boundary before returning
            validated_response = validate_response(response)
            
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000
            _log_timing_metric("oracle_bridge.plan", duration_ms, {
                'goal_id': request.goal_id,
                'payload_hash': payload_hash,
                'candidate_count': len(candidates),
            })
            
            observability_logger.info(
                f"REQUEST_COMPLETED | goal_id={request.goal_id} | "
                f"payload_hash={payload_hash} | status=success | "
                f"duration_ms={duration_ms:.2f}"
            )
            
            return validated_response
            
        except Exception as e:
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000
            failure_class = type(e).__name__
            
            observability_logger.error(
                f"REQUEST_FAILED | goal_id={request.goal_id} | "
                f"payload_hash={payload_hash} | status=failure | "
                f"failure_class={failure_class} | error={str(e)} | "
                f"duration_ms={duration_ms:.2f}"
            )
            raise

    def _build_summary(self, repo_path: str | None, objective: str, state_summary: str) -> Tuple[Dict[str, Any], List[str]]:
        warnings: List[str] = []
        profile: Dict[str, Any] = {
            'repo_profile': {
                'exists': False,
                'file_count': 0,
                'dominant_language': 'unknown',
                'top_extensions': [],
                'candidate_paths': [],
            }
        }
        if not repo_path:
            warnings.append('repo_path was not provided; using objective-only planning heuristics.')
            return profile, warnings

        path = Path(repo_path)
        if not path.exists():
            warnings.append(f'repo_path does not exist: {repo_path}')
            return profile, warnings

        counts: Counter[str] = Counter()
        file_count = 0
        for file_path in self._iter_files(path):
            file_count += 1
            counts[file_path.suffix.lower() or '<none>'] += 1

        dominant_ext = counts.most_common(1)[0][0] if counts else '<none>'
        candidate_paths = self._rank_candidate_paths(
            path,
            ' '.join(part for part in [objective, state_summary] if part),
            limit=3,
        )
        profile['repo_profile'] = {
            'exists': True,
            'file_count': file_count,
            'dominant_language': self._language_for_extension(dominant_ext),
            'top_extensions': counts.most_common(8),
            'candidate_paths': candidate_paths,
        }
        return profile, warnings

    def _iter_files(self, root: Path) -> Iterable[Path]:
        ignored = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', '.pytest_cache', '.build', 'dist', 'build'}
        seen = 0
        for path in root.rglob('*'):
            if any(part in ignored for part in path.parts):
                continue
            if path.is_file():
                yield path
                seen += 1
                if seen >= 2000:
                    break

    def _rank_candidate_paths(self, root: Path, objective: str, limit: int = 3) -> List[str]:
        tokens = [
            token for token in re.findall(r'[a-zA-Z0-9_./-]+', objective.lower())
            if len(token) >= 3 and token not in self.STOP_WORDS
        ]
        scored: List[Tuple[float, str]] = []
        fallback_source_files: List[str] = []

        for file_path in self._iter_files(root):
            relative = file_path.relative_to(root).as_posix()
            rel_lower = relative.lower()
            suffix = file_path.suffix.lower()
            if suffix in self.SOURCE_EXTENSIONS:
                fallback_source_files.append(relative)

            score = 0.0
            for token in tokens:
                token_score = 0.0
                if token in rel_lower:
                    token_score += 1.0
                    if rel_lower.endswith(token):
                        token_score += 0.25
                    if f'/{token}' in rel_lower or rel_lower.startswith(token):
                        token_score += 0.25
                if token == 'swift' and suffix == '.swift':
                    token_score += 0.3
                elif token == 'python' and suffix == '.py':
                    token_score += 0.3
                elif token in {'test', 'tests', 'pytest', 'xctest'} and 'test' in rel_lower:
                    token_score += 0.35
                score += token_score

            if suffix in self.SOURCE_EXTENSIONS:
                score += 0.15
            if score > 0:
                scored.append((score, relative))

        ranked = [path for _, path in sorted(scored, key=lambda item: (-item[0], item[1]))]
        if not ranked:
            ranked = sorted(dict.fromkeys(fallback_source_files))
        return list(dict.fromkeys(ranked))[:limit]

    def _language_for_extension(self, ext: str) -> str:
        mapping = {
            '.py': 'python',
            '.swift': 'swift',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.jsx': 'javascript',
            '.rs': 'rust',
            '.go': 'go',
            '.java': 'java',
            '.kt': 'kotlin',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.c': 'c',
        }
        return mapping.get(ext, 'unknown')

    def _recommended_test_command(self, summary: Dict[str, Any]) -> str:
        lang = summary.get('repo_profile', {}).get('dominant_language', 'unknown')
        if lang == 'python':
            return 'pytest -q'
        if lang == 'swift':
            return 'swift test'
        if lang == 'javascript' or lang == 'typescript':
            return 'npm test'
        if lang == 'rust':
            return 'cargo test'
        if lang == 'go':
            return 'go test ./...'
        return 'run repo-native test command'

    def _build_candidates(
        self,
        request: OraclePlanRequest,
        summary: Dict[str, Any],
        test_command: str,
    ) -> List[OracleCandidateCommand]:
        objective = request.objective.lower()
        candidate_paths = summary.get('repo_profile', {}).get('candidate_paths', [])
        preferred_path = candidate_paths[0] if candidate_paths else None
        repo_payload = {
            'repo_path': request.repo_path,
            'constraints': request.constraints,
            'candidate_paths': candidate_paths,
        }
        candidates: List[OracleCandidateCommand] = []

        candidates.append(
            OracleCandidateCommand(
                candidate_id=f'{request.goal_id}-inspect',
                kind='aae.inspect_repository',
                tool='repository_analyzer',
                payload=repo_payload,
                rationale='Build a grounded repository profile before selecting a mutation or execution path.',
                confidence=0.95,
                predicted_score=0.70,
                safety_class='read_only',
            )
        )

        has_test_files = any('test' in p.lower() for p in candidate_paths)
        if self._contains_any(objective, self.TEST_WORDS) or self._contains_any(request.state_summary.lower(), self.TEST_WORDS) or has_test_files:
            candidates.append(
                OracleCandidateCommand(
                    candidate_id=f'{request.goal_id}-tests',
                    kind='aae.run_targeted_tests',
                    tool='sandbox',
                    payload={
                        'repo_path': request.repo_path,
                        'command': test_command,
                        'candidate_paths': candidate_paths,
                    },
                    rationale='Reproduce the current failure surface and capture a precise test baseline.',
                    confidence=0.92,
                    predicted_score=0.76,
                    safety_class='sandboxed_write',
                )
            )

        if self._contains_any(objective, self.REPAIR_WORDS) or self._contains_any(request.state_summary.lower(), self.REPAIR_WORDS):
            candidates.extend([
                OracleCandidateCommand(
                    candidate_id=f'{request.goal_id}-localize',
                    kind='aae.localize_failure',
                    tool='localization_service',
                    payload={
                        'repo_path': request.repo_path,
                        'state_summary': request.state_summary,
                        'workspace_relative_path': preferred_path,
                        'candidate_paths': candidate_paths,
                    },
                    rationale='Fuse failure symptoms, repository structure, and test evidence into a smaller edit region.',
                    confidence=0.90,
                    predicted_score=0.82,
                    safety_class='read_only',
                ),
                OracleCandidateCommand(
                    candidate_id=f'{request.goal_id}-patch',
                    kind='aae.generate_patch',
                    tool='patch_engine',
                    payload={
                        'repo_path': request.repo_path,
                        'objective': request.objective,
                        'constraints': request.constraints,
                        'workspace_relative_path': preferred_path,
                        'candidate_paths': candidate_paths,
                    },
                    rationale='Generate a bounded candidate patch after localization narrows the edit surface.',
                    confidence=0.90,
                    predicted_score=0.79,
                    safety_class='sandboxed_write',
                    target_file=preferred_path,
                ),
                OracleCandidateCommand(
                    candidate_id=f'{request.goal_id}-verify',
                    kind='aae.validate_candidate',
                    tool='verifier',
                    payload={
                        'repo_path': request.repo_path,
                        'command': test_command,
                        'candidate_paths': candidate_paths,
                    },
                    rationale='Run the candidate through the repository test command before Oracle accepts execution.',
                    confidence=0.84,
                    predicted_score=0.77,
                    safety_class='sandboxed_write',
                ),
            ])

        if self._contains_any(objective, self.REFACTOR_WORDS):
            candidates.append(
                OracleCandidateCommand(
                    candidate_id=f'{request.goal_id}-impact',
                    kind='aae.estimate_change_impact',
                    tool='graph_service',
                    payload={
                        'repo_path': request.repo_path,
                        'workspace_relative_path': preferred_path,
                        'candidate_paths': candidate_paths,
                    },
                    rationale='Estimate dependency blast radius before a broad structural edit.',
                    confidence=0.83,
                    predicted_score=0.74,
                    safety_class='read_only',
                )
            )

        if len(candidates) == 1:
            candidates.append(
                OracleCandidateCommand(
                    candidate_id=f'{request.goal_id}-analyze',
                    kind='aae.analyze_objective',
                    tool='planner_service',
                    payload={
                        'objective': request.objective,
                        'state_summary': request.state_summary,
                        'candidate_paths': candidate_paths,
                    },
                    rationale='Produce a ranked next-step analysis when no stronger repo-specific signal is available.',
                    confidence=0.80,
                    predicted_score=0.65,
                    safety_class='read_only',
                )
            )

        return candidates

    def _contains_any(self, text: str, words: Iterable[str]) -> bool:
        return any(word in text for word in words)
