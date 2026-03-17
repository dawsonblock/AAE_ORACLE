# Oracle-AAE Candidate Schema

## Overview

This document defines the strict boundary contract between the AAE Engine (Python) and Oracle OS (Swift). AAE returns **structured candidates only** — never executable host-side effects. Oracle validates all incoming candidates before they enter the planning pipeline.

## Schema Version

```
aae.candidate.v1
```

---

## Required Fields

Every candidate MUST contain these fields:

| Field | Type | Description |
|-------|------|-------------|
| `candidate_id` | string | Unique identifier for this candidate |
| `kind` | enum | The candidate type (see allowed values below) |
| `tool_name` | enum | The tool that would execute this candidate (see allowed values below) |
| `rationale` | string | Human-readable explanation of why this candidate was chosen |
| `confidence` | float | Score from 0.0 to 1.0 indicating certainty |
| `safety_class` | enum | Safety classification (see values below) |

---

## Allowed Enums

### candidate_kind

The `kind` field must be one of these exact values:

| Kind | Description |
|------|-------------|
| `aae.inspect_repository` | Build repository profile before mutation |
| `aae.analyze_objective` | Rank next-step analysis without strong repo signal |
| `aae.run_targeted_tests` | Reproduce failure surface, capture test baseline |
| `aae.localize_failure` | Fuse failure symptoms into smaller edit region |
| `aae.generate_patch` | Generate bounded candidate patch |
| `aae.validate_candidate` | Run candidate through test command |
| `aae.estimate_change_impact` | Estimate dependency blast radius |

### tool_name

The `tool_name` field must be one of these exact values:

| Tool | Description |
|------|-------------|
| `repository_analyzer` | Index and profile repository structure |
| `planner_service` | General planning and ranking |
| `sandbox` | Execute commands in isolated environment |
| `localization_service` | Fuse failure symptoms to edit regions |
| `patch_engine` | Generate code patches |
| `verifier` | Validate patches against tests |
| `graph_service` | Analyze dependency graphs |

### safety_class

The `safety_class` field must be one of these exact values:

| Class | Description | Requires Approval |
|-------|-------------|------------------|
| `read_only` | No filesystem or state modifications | No |
| `bounded_mutation` | Limited, reversible changes | No |
| `requires_approval` | Must be explicitly approved by operator | **Yes** |
| `sandboxed_write` | Write operations contained in sandbox | No |

---

## Validation Rules

### 1. Unknown `kind` Values → REJECT

Any candidate with a `kind` value not in the allowed enum list MUST be rejected.

```
ERROR: Unknown candidate_kind: "aae.execute_shell"
VALID: aae.inspect_repository, aae.analyze_objective, etc.
```

### 2. Unknown `tool_name` Values → REJECT

Any candidate with a `tool_name` value not in the allowed enum list MUST be rejected.

```
ERROR: Unknown tool_name: "shell_command"
VALID: repository_analyzer, planner_service, sandbox, etc.
```

### 3. Missing Required Fields → REJECT

The following fields are MANDATORY:
- `rationale` (non-empty string)
- `confidence` (0.0 to 1.0 inclusive)
- `safety_class` (must be valid enum value)

```
ERROR: Missing required field: rationale
ERROR: Missing required field: confidence
ERROR: Missing required field: safety_class
```

### 4. Confidence Bounds → REJECT

`confidence` must be a valid float in range [0.0, 1.0].

```
ERROR: confidence out of bounds: 1.5 (must be 0.0-1.0)
```

### 5. Candidates with `requires_approval` Safety → FLAG

Any candidate with `safety_class: "requires_approval"` MUST be flagged for operator review before execution. Oracle must log these candidates separately and not auto-execute them.

```
WARNING: Candidate {id} requires_approval - awaiting operator authorization
```

---

## Validation Flow

```
AAE Engine                          Oracle OS
    │                                   │
    │  ┌─────────────────────────────┐  │
    │  │  OraclePlanResponse        │  │
    │  │  (candidates: [...])       │  │
    │  └──────────────┬──────────────┘  │
    │                 │                   │
    │                 ▼                   │
    │  ┌─────────────────────────────┐  │
    │  │  OracleAAECandidateValidator│  │
    │  │  ├─ validate_kind()         │  │
    │  │  ├─ validate_tool_name()     │  │
    │  │  ├─ validate_required_fields│  │
    │  │  └─ flag_requires_approval()│  │
    │  └──────────────┬──────────────┘  │
    │                 │                   │
    │      ┌─────────┴─────────┐        │
    │      │                     │        │
    │      ▼                     ▼        │
    │  Valid              Invalid         │
    │  Candidates        Candidates      │
    │      │              (rejected)      │
    │      ▼                             │
    │  ┌─────────────────────────────┐  │
    │  │  Map to Oracle Command Types │  │
    │  └─────────────────────────────┘  │
```

---

## Oracle Command Mapping

Validated candidates are mapped to Oracle-local command types:

| AAE Kind | Oracle Skill | Command Category |
|----------|--------------|------------------|
| `aae.inspect_repository` | `read_repository` | indexRepository |
| `aae.analyze_objective` | `read_repository` | indexRepository |
| `aae.run_targeted_tests` | `run_tests` | test |
| `aae.localize_failure` | `search_code` | searchCode |
| `aae.generate_patch` | `generate_patch` | generatePatch |
| `aae.validate_candidate` | `run_tests` | test |
| `aae.estimate_change_impact` | `search_code` | searchCode |

---

## Error Handling

### On Validation Failure

1. Log the rejection with reason
2. Track validation failure metrics
3. Return only the valid candidates to the planning pipeline
4. Include warnings about rejected candidates in the response

### On Requires Approval

1. Flag candidate for review
2. Do NOT auto-execute
3. Wait for explicit operator authorization
4. Log the approval/rejection decision

---

## Example Valid Candidate

```json
{
  "candidate_id": "goal-123-inspect",
  "kind": "aae.inspect_repository",
  "tool_name": "repository_analyzer",
  "payload": {
    "repo_path": "/path/to/repo",
    "candidate_paths": ["src/main.swift", "tests/MainTests.swift"]
  },
  "rationale": "Build a grounded repository profile before selecting a mutation or execution path.",
  "confidence": 0.95,
  "predicted_score": 0.70,
  "safety_class": "read_only"
}
```

## Example Invalid Candidate (Rejection Cases)

```json
{
  "candidate_id": "goal-123-invalid",
  "kind": "aae.execute_arbitrary_command",  // ❌ Unknown kind
  "tool_name": "shell",                      // ❌ Unknown tool
  "payload": {},
  "rationale": "",                           // ❌ Missing rationale
  "confidence": 1.5,                        // ❌ Out of bounds
  "predicted_score": 0.9,
  "safety_class": "unknown"                 // ❌ Invalid safety_class
}
```

---

## Schema Versioning

The schema version is included in the response header:

```
X-Candidate-Schema-Version: aae.candidate.v1
```

Breaking changes will increment the version (v2, v3, etc.). Oracle must reject responses with unsupported schema versions.
