# Test Baseline

This document describes how to reproduce the project’s test baseline without committing
environment-specific logs or local paths.

## How to run the tests

From the project root:

```bash
pytest
```

## Expected outcome

- All tests should collect and run successfully.
- The test run should complete without unexpected errors.
- Any known, acceptable warnings (for example, about deprecated options) should be
  documented here rather than by pasting full warning stacks.

Example of a stable baseline description:

- Python version: a supported version listed in this project’s documentation
- Test command: `pytest`
- Summary: `N passed, 0 failed` (exact counts may vary as tests are added or removed)

## Environment notes

- Avoid committing full `pytest` logs, `pip list` output, or absolute local paths
  (such as those under a home directory) into version control.
- If detailed logs are needed for debugging or CI, store them as build artifacts
  or add them to `.gitignore` instead of documenting them verbatim here.

This file is intended to provide a concise, reproducible description of how to run
the tests and what success looks like, independent of any one developer’s machine.
click                   8.3.1
coverage                7.13.3
cyclonedx-python-lib    11.6.0
datasets                4.5.0
defusedxml              0.7.1
dill                    0.4.0
distlib                 0.4.0
distro                  1.9.0
docker                  7.1.0
fastcore                1.12.11
filelock                3.20.3
frozenlist              1.8.0
fsspec                  2025.10.0
ghapi                   1.0.10
gitdb                   4.0.12
GitPython               3.1.46
grpclib                 0.4.9
h11                     0.16.0
h2                      4.3.0
hf-xet                  1.2.0
hpack                   4.1.0
httpcore                1.0.9
httpx                   0.28.1
huggingface_hub         1.4.0
hyperframe              6.1.0
identify                2.6.16
idna                    3.11
iniconfig               2.3.0
jiter                   0.13.0
license-expression      30.4.4
markdown-it-py          4.0.0
mdurl                   0.1.2
modal                   1.3.2
msgpack                 1.1.2
multidict               6.7.1
multiprocess            0.70.18
nodeenv                 1.10.0
numpy                   2.4.2
openai                  2.17.0
packageurl-python       0.17.6
packaging               26.0
pandas                  3.0.0
pip                     26.0.1
pip-api                 0.0.34
pip_audit               2.10.0
pip-requirements-parser 32.0.1
platformdirs            4.5.1
pluggy                  1.6.0
pre_commit              4.5.1
propcache               0.4.1
protobuf                6.33.5
py-serializable         2.1.0
pyarrow                 23.0.0
pydantic                2.12.5
pydantic_core           2.41.5
Pygments                2.19.2
pyparsing               3.3.2
pytest                  9.0.2
pytest-cov              7.0.0
python-dateutil         2.9.0.post0
python-dotenv           1.2.1
PyYAML                  6.0.3
requests                2.32.5
rfsn-learner            0.2.0           /Users/dawsonblock/Downloads/rfsn_kernel_learner_build
rich                    14.3.2
ruff                    0.15.0
shellingham             1.5.4
six                     1.17.0
smmap                   5.0.2
sniffio                 1.3.1
sortedcontainers        2.4.0
soupsieve               2.8.3
swebench                4.1.0
synchronicity           0.11.1
tenacity                9.1.3
toml                    0.10.2
tomli                   2.4.0
tomli_w                 1.2.0
tqdm                    4.67.3
typer                   0.21.1
typer-slim              0.21.1
types-certifi           2021.10.8.3
types-toml              0.10.8.20240310
typing_extensions       4.15.0
typing-inspection       0.4.2
unidiff                 0.7.5
urllib3                 2.6.3
virtualenv              20.36.1
watchfiles              1.1.1
xxhash                  3.6.0
yarl                    1.22.0
# AAE-ENGINE Baseline Checkpoint

## Branch: `runtime-unification`

This document captures the baseline state before architectural restructuring to prevent silent regression.

---

## Test Results

**Command:** `pytest -q`

### Summary
- **Status:** FAILED (Collection Errors)
- **Errors:** 24 collection errors
- **Warnings:** 18 pytest warnings

### Error Details

All test collections failed due to **Python version incompatibility**:

```
TypeError: Unable to evaluate type annotation 'datetime | None'. 
If you are making use of the new typing syntax (unions using `|` since Python 3.10 
or builtins subscripting since Python 3.9), you should either replace the use of 
new syntax with the existing `typing` constructs or install the `eval_type_backport` package.
```

**Root Cause:** The codebase uses Python 3.10+ union syntax (`datetime | None`) but the runtime is Python 3.9.6.

**Affected Test Files (24):**
- `tests/integration/test_graph_runtime_integration.py`
- `tests/integration/test_workflows.py`
- `tests/patching/test_diff_constructor.py`
- `tests/test_deep_integration.py`
- `tests/unit/test_action_graph.py`
- `tests/unit/test_adapters.py`
- `tests/unit/test_agent_roles.py`
- `tests/unit/test_artifact_store.py`
- `tests/unit/test_behavior_localization.py`
- `tests/unit/test_dashboard_api.py`
- `tests/unit/test_events.py`
- `tests/unit/test_experiment_evaluator.py`
- `tests/unit/test_graph_pipeline.py`
- `tests/unit/test_knowledge_graph.py`
- `tests/unit/test_launcher.py`
- `tests/unit/test_learning_memory_sandbox.py`
- `tests/unit/test_patching_evaluation.py`
- `tests/unit/test_planner_modules.py`
- `tests/unit/test_registry_memory.py`
- `tests/unit/test_repo_model.py`
- `tests/unit/test_retry_policy.py`
- `tests/unit/test_swarm_planner.py`
- `tests/unit/test_swe_preparation.py`
- `tests/unit/test_task_graph.py`

---

## Python Version

**Version:** Python 3.9.6

---

## Key Dependencies

From `requirements.txt`:

| Category | Package | Version |
|----------|---------|---------|
| Core | fastapi | >=0.115 |
| Core | uvicorn | >=0.30 |
| Core | httpx | >=0.27 |
| Core | pydantic | >=2.0 |
| Core | PyYAML | >=6.0 |
| Database | psycopg | >=3.1 |
| Database | redis | >=5.0 |
| Graph/Vector | neo4j | >=5.0 |
| Graph/Vector | qdrant-client | >=1.7 |
| Graph/Vector | networkx | >=3.0 |
| ML/Embeddings | numpy | >=1.26 |
| ML/Embeddings | scikit-learn | >=1.4 |
| ML/Embeddings | sentence-transformers | >=2.6 |
| Code Parsing | tree-sitter | >=0.21 |
| Code Parsing | tree-sitter-python | >=0.21 |
| Security | bandit | >=1.7 |
| Security | safety | >=3.0 |
| Monitoring | prometheus-client | >=0.20 |
| Monitoring | opentelemetry-api | >=1.23 |
| Process | docker | >=7.0 |
| Process | psutil | >=5.9 |
| Utilities | tenacity | >=8.2 |
| Utilities | rich | >=13.0 |
| Utilities | typer | >=0.12 |
| Utilities | structlog | >=24.0 |

---

## Pre-Restructuring Notes

### Critical Issue
The test suite is **non-functional** due to Python version mismatch. Before proceeding with architectural changes:

1. **Either:** Upgrade Python to 3.10+ to support modern union syntax
2. **Or:** Backport all type annotations to use `Optional[]` and `Union[]` from `typing` module

### Recommendation
This baseline confirms that the primary regression risk is **not** from the planned structural changes, but from the existing Python version incompatibility. The `runtime-unification` branch should address this dependency issue first.

---

*Generated: 2026-03-17*
*Branch: runtime-unification*
