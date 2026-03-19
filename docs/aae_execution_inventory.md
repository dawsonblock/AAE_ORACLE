# AAE Execution Inventory

| File | Function/Class | Decision |
| --- | --- | --- |
| `aae-engine/src/aae/execution/sandbox_adapter.py` | `SandboxAdapter.run` | keep |
| `aae-engine/src/aae/execution/executor.py` | `Executor.run` | keep |
| `aae-engine/src/aae/execution/sandbox.py` | `ExecutionSandbox.execute` | move |
| `aae-engine/src/aae/execution/executor_simple.py` | `Executor.execute` | move |
| `aae-engine/src/aae/execution/patch_engine.py` | `PatchEngine.apply_patch` | move |
| `aae-engine/src/aae/execution/ast_repair.py` | `ASTRepairEngine.generate_candidates` | move |
| `aae-engine/src/aae/sandbox/sandbox_manager.py` | `SandboxManager.run_job` | keep |
| `aae-engine/src/aae/patching/git_ops/git_patch_applier.py` | `GitPatchApplier.apply_patch` | keep |
| `aae-engine/src/aae/patching/git_ops/rollback_manager.py` | `RollbackManager.*` | keep |
