<!-- markdownlint-disable MD040 MD060 -->

# Oracle OS Architecture

This document describes the current runtime layers and how they satisfy the governance contract in [docs/GOVERNANCE.md](docs/GOVERNANCE.md).

## Core Spine

Oracle OS has one execution spine:

`surface -> RuntimeOrchestrator -> Policy -> VerifiedActionExecutor -> Critic -> Trace -> runtime-managed graph/memory/recovery update`

Surfaces:

- Controller
- MCP
- CLI
- Recipes

## Dominant Subsystems

The system reduces to five dominant layers:

| Layer | Role |
|-------|------|
| **Execution kernel** | Verified interaction with the environment |
| **Perception** | Reliable, compressed environment state via PerceptionEngine |
| **Planner** | Goal decomposition and action selection |
| **Evaluator (Critic)** | Detect failure and drive recovery |
| **Memory / Graph** | Persistent learning |

Everything else is supporting infrastructure.

## Layer Map

### RuntimeOrchestrator

Primary files:

- `Sources/OracleOS/Runtime/RuntimeOrchestrator.swift`
- `Sources/OracleOS/Runtime/RuntimeContext.swift`
- `Sources/OracleOS/Runtime/TaskContext.swift`

Responsibilities:

- route task/surface context
- evaluate policy
- call verified execution
- own post-execution graph/memory/recovery updates
- fail closed on policy ambiguity

### Observation and Planning State

Primary files:

- `Sources/OracleOS/Core/Observation/*`
- `Sources/OracleOS/Core/PlanningState/*`
- `Sources/OracleOS/Core/World/*`

Responsibilities:

- build canonical observations
- fuse AX and browser signals conservatively
- abstract raw state into reusable planning state
- maintain world state model, state diffs, and state updates

### Observation Change Detector

Primary files:

- `Sources/OracleOS/Core/Observation/ObservationChangeDetector.swift`
- `Sources/OracleOS/Core/Observation/ObservationDelta.swift`

Responsibilities:

- detect fine-grained element-level changes between consecutive observations
- produce ``ObservationDelta`` describing added, removed, and mutated elements
- enable delta-driven world model updates instead of full rebuilds
- reduce observation processing cost during long autonomous sessions

Pipeline:

```
previous observation
↓
ObservationChangeDetector.detect(previous:incoming:)
↓
ObservationDelta
↓
StateDiffEngine (includes delta when previous observation available)
↓
WorldStateModel.apply(diff:)
```

By capturing only what changed at the element level, downstream consumers
skip re-processing thousands of unchanged elements each loop iteration.
During long runs with mostly stable UI this can reduce observation cost by
an order of magnitude.

### State Abstraction Engine

Primary files:

- `Sources/OracleOS/StateAbstraction/StateAbstractionEngine.swift`

Responsibilities:

- map raw AX / DOM elements to semantic types (`SemanticElement`)
- deduplicate similar elements
- attach intent labels
- produce minimal `CompressedUIState` for the planner

The planner should never read raw AX trees directly. Instead it receives
compressed state objects such as `Button("Send")`, `Input("Search")`, or
`List("Messages")`. This dramatically reduces reasoning token consumption
and improves planner stability.

### Action Schema System

Primary files:

- `Sources/OracleOS/ActionSchema/ActionSchema.swift`

Responsibilities:

- define typed action schemas with explicit preconditions and postconditions
- provide canonical schema library (`ActionSchemaLibrary`)
- verify preconditions against compressed UI state
- enable planners to operate on stable primitives

The planner should never emit raw instructions like `move mouse to 840, 410`.
It should always emit schemas such as `Click(Button("Send"))`. The executor
resolves the actual coordinates.

### Planning

Primary files:

- `Sources/OracleOS/Agent/Planning/*`

Responsibilities:

- interpret goals
- choose OS, code, or mixed planning path
- prefer graph-backed steps when available
- stay out of execution internals

### Skills

Primary files:

- `Sources/OracleOS/Agent/Skills/OS/*`
- `Sources/OracleOS/Agent/Skills/Code/*`

Responsibilities:

- compile bounded intents
- resolve semantic targets through ranking for OS actions
- resolve structured workspace actions for code tasks

They do not execute directly.

### Verified Execution

Primary files:

- `Sources/OracleOS/Core/Execution/VerifiedActionExecutor.swift`
- `Sources/OracleOS/Core/ExecutionSemantics/*`

Responsibilities:

- pre/post observation
- postcondition verification
- failure classification
- transition semantics emission
- trace event creation
- stamps `executedThroughExecutor` on every `ActionResult`
- feeds critic verdict into state memory index
- feeds critic verdict into planning graph engine

This is the execution truth boundary, not the planner and not the architecture engine.
Every action must pass through this executor; the runtime asserts
`executedThroughExecutor == true` on every result to enforce the trust boundary.

### Critic (Self-Evaluation Loop)

Primary files:

- `Sources/OracleOS/Critic/CriticLoop.swift`

Responsibilities:

- evaluate every executed action by comparing pre- and post-state
- classify outcome as SUCCESS, PARTIAL_SUCCESS, FAILURE, or UNKNOWN
- check expected postconditions from action schemas
- signal the planner when recovery is needed
- drive graph edge promotion/demotion via verdict outcome
- trigger state memory updates based on action outcome
- trigger planning graph updates to refine candidate ranking

The critic loop is what allows the agent to correct itself. Every action
step is followed by a critic pass that provides the planner with recovery
signals when expected state changes do not occur. The critic verdict
directly influences:

1. **Task graph**: only critic-confirmed successes promote an edge; failures
   and unknowns record failed executions, reducing the edge's success
   probability and potentially demoting it.
2. **State memory**: the critic outcome is recorded so the planner can
   consult historical success rates for the current UI state.
3. **Planning graph**: successful transitions strengthen candidate edges;
   failures weaken them or create new edges from execution experience.

### Planning Graph Engine

Primary files:

- `Sources/OracleOS/PlanningGraph/PlanningGraphEngine.swift`

Responsibilities:

- store allowed state transitions as a finite action graph
- rank candidate edges by score (success_rate − cost − latency)
- constrain the planner to emit only edges that appear in the graph
- prune weak edges that fall below a success threshold
- record traversal outcomes to update edge statistics

The planner should operate over a finite action graph instead of
generating arbitrary step sequences. Each edge connects two abstract
task states via a concrete `ActionSchema`.

### Trace Replay Engine

Primary files:

- `Sources/OracleOS/TraceReplay/TraceReplayEngine.swift`

Responsibilities:

- record execution steps as `ReplayStep` values from critic verdicts
- collect steps into `ReplayTrace` for an entire session
- compare expected traces against replayed traces
- surface divergences for debugging and regression analysis

Deterministic replay makes debugging autonomous behaviour tractable.
Every step records the pre/post state hash, action name, critic outcome,
and latency.

### State Memory Index

Primary files:

- `Sources/OracleOS/StateMemory/StateMemoryIndex.swift`

Responsibilities:

- index compressed UI states by signature (app + elements)
- track action statistics (attempts, successes) per state
- provide the planner with previously successful strategies
- evict oldest entries when capacity is exceeded

The state memory index allows the planner to reuse known-good strategies
when it encounters a familiar compressed state, reducing exploration
overhead.

### Graph

Primary files:

- `Sources/OracleOS/Graph/*`

Responsibilities:

- persist candidate/stable control knowledge
- enforce trust tiers
- promote, demote, and prune through policy

### Task Graph

Primary files:

- `Sources/OracleOS/TaskGraph/*`

Responsibilities:

- live planning substrate that the planner navigates directly
- maintain current task node pointer and candidate edge expansion
- abstract world state into task-relevant states (not raw UI noise)
- accumulate edge evidence (success/failure counts, cost, latency)
- support recovery via alternate graph edges
- enforce bounded growth (max nodes, max edges, node merging)
- export diagnostics in DOT and JSON formats

The task graph is the canonical representation of the current task position.
The planner operates on task graph nodes and edges — not on raw ephemeral
state alone. Every verified action creates or updates a graph edge, and
recovery branches through alternate edges rather than side channels.

### Perception Engine and Vision

Primary files:

- `Sources/OracleOS/PerceptionEngine/*`
- `Sources/OracleOS/Vision/*`

Responsibilities:

- fuse AX tree, vision, screen capture, DOM hints into unified observation
- provide screenshot capture (`ScreenCapture`) for visual grounding
- bridge to vision sidecar for OCR, object detection, layout analysis
- bridge to Chrome DevTools Protocol for structured DOM information

The perception pipeline flows:
  environment → PerceptionEngine → StateAbstractionEngine → planner

Planner must only receive compressed semantic state objects such as
`Button("Send")`, `Input("Search")`, never raw AX structures.

### Browser Bridge

Primary files:

- `Sources/OracleOS/BrowserAutomation/BrowserBridge.swift`

Responsibilities:

- provide high-level DOM interaction via CSS selectors
- expose querySelector, getBoundingRect, getText, click, type
- abstract over CDP transport so callers need no protocol knowledge
- complement AX-based perception for web content

### Memory

Primary files:

- `Sources/OracleOS/Learning/Memory/*`
- `Sources/OracleOS/ProjectMemory/*`

Responsibilities:

- lightweight runtime bias
- long-horizon engineering memory
- explicit classification between reusable knowledge and episode residue

### Recovery

Primary files:

- `Sources/OracleOS/Agent/Recovery/*`

Responsibilities:

- bounded repair actions
- recovery tagging
- recovery-specific evidence

### Architecture Governance

Primary files:

- `Sources/OracleOS/Architecture/*`

Responsibilities:

- emit findings, governance violations, and refactor proposals
- detect boundary drift and coverage gaps
- stay advisory-first except where governance tests hard-fail

### Program Knowledge Graph

Primary files:

- `Sources/OracleOS/CodeIntelligence/ProgramKnowledgeGraph.swift`

Responsibilities:

- provide a unified query interface over all code-intelligence graphs
  (``SymbolGraph``, ``CallGraph``, ``TestGraph``, ``BuildGraph``, ``DependencyGraph``)
- enable program-structure-aware reasoning for the planner
- trace test failures through the call graph to locate root-cause source files
- compute change impact (affected tests, dependent files, blast radius)
- expose call-graph neighborhood expansion for fault localisation

Pipeline position:

```
filesystem observation
↓
RepositoryIndexer
↓
ProgramKnowledgeGraph
↓
planner
```

The planner should reason about program structure (symbols, call edges,
test coverage, dependencies) rather than treating a codebase as flat files.
This layer sits between filesystem observation and planning to provide
the structural understanding required for autonomous software engineering.

## Module Layout

```
OracleCore
├── Core                    (execution, policy, trace, observation, world)
├── Runtime                 (agent loop, coordinators)
├── Agent                   (planning, recovery, skills)
├── Search                  (candidate generation, search-centric selection)
├── StateAbstraction        (compressed semantic UI state)
├── ActionSchema            (typed action schemas)
├── Critic                  (self-evaluation loop)
├── PlanningGraph           (deterministic planning graph)
├── TraceReplay             (execution replay and divergence detection)
├── StateMemory             (compressed state caching and reuse)
├── PerceptionEngine        (AX + DOM + vision fusion)
├── Vision                  (screen capture, vision sidecar, CDP bridge)
├── HostAutomation          (macOS app control)
├── BrowserAutomation       (browser control, BrowserBridge)
├── CodeExecution            (safe command execution)
├── CodeIntelligence         (repository indexing, ProgramKnowledgeGraph)
├── Graph                   (long-term knowledge)
├── TaskGraph               (runtime task tracking)
├── Memory                  (session memory)
├── ProjectMemory           (repository knowledge)
├── Experiments             (parallel patch testing)
├── Reasoning               (LLM clients, plan generation)
├── PromptEngine            (prompt construction)
├── Workflows               (reusable action sequences)
├── Recipes                 (user-defined task macros)
├── MCP                     (Model Context Protocol)
├── Diagnostics             (runtime debugging, MetricsRecorder)
├── Tools                   (utility functions)
├── Strategy                (high-level planning strategies)
└── Learning                (success probability updates)
```

Removed or archived modules:

- `MetaReasoning` — removed (added complexity without measurable gains)
- `Simulation` — removed (rarely useful in UI agents)
- `WorldModel` — merged into `Core/World`
- `Screenshot` — merged into `Vision`
- `Perception` — renamed to `PerceptionEngine`

## Core Control Loop

The integrated control loop after the architecture upgrades:

```
observe environment
  → detect observation delta (ObservationChangeDetector)
  → compute state diff with element-level delta (StateDiffEngine)
  → apply incremental world model update (WorldStateModel.apply)
  → compress state (StateAbstractionEngine)
  → query state memory for known strategies (StateMemoryIndex.likelyActions)
  → generate candidates: memory → graph → LLM fallback (CandidateGenerator)
  → execute candidate actions (VerifiedActionExecutor via SearchController)
  → critic evaluates each result (CriticLoop)
  → select best verified result (ResultSelector)
  → critic verdict drives graph promotion/demotion (TaskGraphStore)
  → update state memory with outcome (StateMemoryIndex)
  → record metrics (MetricsRecorder)
  → record step for replay (TraceReplayEngine)
  → repeat
```

When a previous observation is available, the pipeline uses
`ObservationChangeDetector` to produce a fine-grained `ObservationDelta`
that tracks added, removed, and mutated elements.  `StateDiffEngine` now
includes this delta so `WorldStateModel` can patch only the pieces that
changed rather than rebuilding the entire world model from scratch.

### Search-Centric Selection

The `SearchController` replaces single-path action selection with
candidate generation and verified selection:

- `CandidateGenerator` produces candidates in priority order:
  memory suggestions → graph-valid actions → LLM fallback
- `SearchController` orchestrates execution of each candidate
- `ResultSelector` chooses the best verified outcome
- `MetricsRecorder` tracks action success rates, candidate source
  distribution, and runtime performance

## Trust Model

### Knowledge tiers

- `exploration`
- `candidate`
- `stable`
- `experiment`
- `recovery`

### Knowledge classes

- `reusable`
- `parameter`
- `episode`

Only reusable knowledge is eligible for canonical long-term storage.

## Current Enforcement

- runtime owns post-execution updates
- runtime asserts `executedThroughExecutor` on every action result to enforce the trust boundary
- graph promotion blocks experiment and recovery evidence from stable promotion
- target-bearing OS skills resolve through ranking
- project-memory episode residue is kept out of canonical `ProjectMemory/`
- architecture review emits governance reports tied to rule IDs
- CI runs build and test as the minimum repo gate
- critic verdict drives state memory, planning graph, and task graph updates
- `SearchController` selects from multiple verified candidates per state
- `CandidateGenerator` prioritises memory → graph → LLM fallback
- `PlanningGraphEngine.validActions(for:)` constrains the candidate action space
- `StateMemoryIndex.likelyActions(for:)` provides memory-driven action ranking
- `MetricsRecorder` tracks action success, patch rates, and search cycle statistics

## Known Boundaries

- experiments may gather evidence in isolated worktrees, but their results only become promotable knowledge after replay through the main runtime
- recovery remains a first-class tracked mode, but not yet a promotable nominal control path
- architecture review is advisory-first; its hard-fail behavior is enforced through tests and governance checks rather than autonomous blocking
