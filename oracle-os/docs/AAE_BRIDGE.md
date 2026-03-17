# AAE bridge

The AAE bridge is now wired into Oracle's code-planning path.

## Boundary

Oracle still owns:
- verification
- execution
- event emission
- committed state

AAE supplies:
- repository profiling
- candidate ranking
- localization / patch generation hints
- target-path suggestions
- sandbox-first validation plans

## Runtime behavior

When the agent loop handles a code task, it now:
1. asks the local Oracle planner for a decision
2. asks the AAE bridge for ranked code-task advice
3. preserves stronger workflow or graph-backed Oracle plans
4. allows AAE to override weak exploratory steps
5. carries any AAE-preferred path into Oracle code-skill resolution

## Configuration

Oracle loads bridge configuration in this order:
1. `ORACLE_AAE_CONFIG`
2. `./configs/oracle_aae_bridge.json`
3. environment variables such as `ORACLE_AAE_BASE_URL`

Optional environment variables:
- `ORACLE_AAE_ENABLED`
- `ORACLE_AAE_PLAN_ENDPOINT`
- `ORACLE_AAE_TIMEOUT_SECONDS`
- `ORACLE_AAE_MAX_CANDIDATES`
- `ORACLE_AAE_MIN_OVERRIDE_SCORE`
