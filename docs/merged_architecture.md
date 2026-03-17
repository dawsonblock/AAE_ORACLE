# Merged architecture

```text
Goal / intent
    ↓
Oracle planner
    ↓
Oracle → AAE bridge request
    ↓
AAE candidate generation / ranking / repo heuristics
    ↓
Ranked candidate commands
    ↓
Oracle verification
    ↓
Oracle execution
    ↓
Oracle domain events
    ↓
Oracle commit coordinator
    ↓
Committed world state + traces
```

## Boundary

Oracle remains the only layer allowed to create side effects in the host runtime.
AAE proposes, ranks, localizes, simulates, and evaluates.

## Why this shape

AAE is strong at search and evaluation.
Oracle is strong at verified execution and durable state.
Mixing those authorities inside one hot path would create duplicate control planes.
