# Oracle ↔ AAE integration contract

## Endpoint

`POST /api/oracle/plan`

## Example request

```json
{
  "goal_id": "repair-123",
  "objective": "Repair the failing login flow and validate the patch",
  "repo_path": "/repos/app",
  "state_summary": "2 failing tests in auth/login",
  "constraints": {
    "approval_mode": "strict",
    "max_patch_files": 3
  },
  "max_candidates": 5
}
```

## Example response

```json
{
  "goal_id": "repair-123",
  "engine": "aae.oracle_bridge.v1",
  "summary": {
    "repo_profile": {
      "dominant_language": "python",
      "file_count": 114
    },
    "recommended_test_command": "pytest -q"
  },
  "warnings": [],
  "candidates": [
    {
      "candidate_id": "repair-123-inspect",
      "kind": "aae.inspect_repository",
      "tool": "repository_analyzer",
      "payload": {
        "repo_path": "/repos/app"
      },
      "rationale": "Build a grounded repository and language profile before mutating code.",
      "confidence": 0.94,
      "predicted_score": 0.68,
      "safety_class": "read_only"
    }
  ]
}
```
