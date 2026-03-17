# Deployment Topology

This document describes the deployment topology for the Oracle-AAE fused system, covering the recommended localhost deployment for initial setup and future deployment options for production environments.

## Topology Overview

The Oracle-AAE system consists of two primary components that communicate over HTTP:

| Component | Platform | Role |
|-----------|----------|------|
| **Oracle** | macOS 14+ | Sole execution authority; handles accessibility automation, app interaction, and host-side runtime |
| **AAE** | Python service | Handles candidate search, localization, scoring, and experiment logic |

### Communication Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                         macOS Host                              │
│                                                                 │
│  ┌──────────────┐                    ┌──────────────────────┐   │
│  │    Oracle    │◄──────HTTP───────►│   AAE (Python)       │   │
│  │  (App/Runtime)                   │   Dashboard API      │   │
│  └──────────────┘   localhost:8787  └──────────────────────┘   │
│         │                                    │                  │
│         │                                    ├─ PostgreSQL      │
│         │                                    └─ Redis           │
└─────────────────────────────────────────────────────────────────┘
```

## Preferred First Deployment

The recommended initial deployment runs both components on the same macOS machine using localhost HTTP communication.

### Architecture

```
Oracle (macOS app / runtime)
         │
         │ localhost HTTP
         ▼
    127.0.0.1:8787
         │
         ▼
AAE (Python service - same host)
```

### Default Configuration

The bridge configuration is defined in [`configs/oracle_aae_bridge.json`](configs/oracle_aae_bridge.json):

| Setting | Value |
|---------|-------|
| Base URL | `http://127.0.0.1:8787` |
| Plan Endpoint | `/api/oracle/plan` |
| Result Endpoint | `/api/oracle/experiment_result` |
| Timeout | 30 seconds |
| Max Candidates | 5 per goal |
| Max Execution Attempts | 3 |
| Max Patch Files | 3 per candidate |
| Max Total Runtime | 300 seconds |

### Environment Requirements

| Dependency | Version | Purpose |
|------------|---------|---------|
| macOS | 14+ | Oracle runtime and accessibility framework |
| Python | 3.11+ | AAE service runtime |
| PostgreSQL | 14+ | AAE persistence |
| Redis | 7+ | AAE event bus |

### Startup Sequence

1. **Start AAE Service**

   ```bash
   cd aae-engine
   python -m aae.dashboard_api.server --host 127.0.0.1 --port 8787
   ```

2. **Verify Bridge Connectivity**

   ```bash
   curl http://127.0.0.1:8787/api/oracle/health
   ```

   Or check health:

   ```bash
   curl http://127.0.0.1:8787/api/oracle/health
   ```

3. **Start Oracle**

   Launch Oracle on macOS. The Oracle component will automatically connect to the AAE service at the configured endpoint.

### Network Verification

Ensure the following endpoints are accessible:

- `http://127.0.0.1:8787/api/oracle/health` — Health check
- `http://127.0.0.1:8787/api/oracle/plan` — Planning endpoint
- `http://127.0.0.1:8787/api/oracle/experiment_result` — Result submission

## Later Deployment Options

After the contract stabilizes, consider these deployment topologies:

### Option 1: Separate Service Process

Move AAE to its own dedicated service process on the same network:

```
┌─────────────────────────────────────────────────────────────────┐
│                         macOS Host                              │
│  ┌──────────────┐                                               │
│  │    Oracle    │────────────────────────────────┐            │
│  └──────────────┘                                │            │
│         │                                    HTTP│            │
│         │                                        ▼            │
│         │                            ┌──────────────────────┐ │
│         │                            │   AAE Service        │ │
│         │                            │   (Dedicated Process)│ │
│         │                            └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
   PostgreSQL + Redis
```

**Use case**: When AAE requires independent scaling or monitoring.

### Option 2: Internal Cluster Node

Deploy AAE as a specialized node for repository search and candidate evaluation only:

```
┌──────────────┐        ┌──────────────────────────────────────┐
│    Oracle    │───────►│  Internal Cluster                    │
│   (macOS)    │  HTTP  │  ┌────────────────────────────────┐  │
└──────────────┘        │  │  AAE Node (Search/Evaluation)  │  │
                        │  └────────────────────────────────┘  │
                        │  ┌────────────────────────────────┐  │
                        │  │  AAE Node (Experiment Runner)  │  │
                        │  └────────────────────────────────┘  │
                        └──────────────────────────────────────┘
```

**Use case**: When candidate volume increases and horizontal scaling is needed.

### Option 3: Remote Internal Service

Deploy AAE on a remote server with proper network authentication:

```
┌──────────────┐                                    ┌─────────┐
│    Oracle    │───────────────HTTPS─────────────────│   AAE   │
│   (macOS)    │            (authenticated)         │ Service │
└──────────────┘                                    └─────────┘
                                                            │
                                                     ┌──────┴──────┐
                                                     │ PostgreSQL  │
                                                     │   Redis    │
                                                     └─────────────┘
```

**Use case**: When AAE resources should be shared across multiple Oracle instances.

### Network Topology Considerations

| Factor | Consideration |
|--------|---------------|
| **Latency** | Oracle-AAE communication should remain under 50ms for responsive planning |
| **Authentication** | Remote deployments require token-based or mTLS authentication |
| **Firewall** | Ensure Oracle can reach AAE port; restrict AAE to internal network |
| **Data Privacy** | Goal context and candidate data remain on-host; only metadata traverses network |

## Authority Boundaries

The deployment topology must enforce the authority boundaries defined in the integration contract:

```
┌─────────────────────────────────────────────────────────────────┐
│                         ORACLE (Authority)                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Sole execution authority                                │  │
│  │  • Executes all side effects                             │  │
│  │  • Controls accessibility automation                    │  │
│  │  • Manages runtime execution                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              │ Goal + Context                    │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  AAE (Advisor)                                           │  │
│  │  • Candidate search and discovery                       │  │
│  │  • Path localization                                     │  │
│  │  • Scoring and ranking                                   │  │
│  │  • Experiment logic                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Responsibilities by Component

| Oracle | AAE |
|--------|-----|
| Execution (file operations, commands) | Candidate discovery |
| Accessibility automation | Path localization |
| Runtime state management | Candidate scoring |
| Side effects | Experiment orchestration |
| Final decision authority | Recommendation only |

### Enforcement in Deployment

- **Oracle remains sole execution authority**: All candidate plans returned by AAE are recommendations only. Oracle validates and executes at its discretion.
- **No direct AAE execution**: AAE never directly accesses the filesystem or executes commands. It only provides scored candidates.
- **Observability boundary**: Both components emit events to the unified event bus, but execution traces remain under Oracle's control.

## Testing the Deployment

### Health Check

```bash
curl http://127.0.0.1:8787/api/oracle/health
```

Expected response:
```json
{
  "status": "ok",
  "engine": "aae.oracle_bridge.v1"  // API version identifier
}
```

The `engine` field identifies the Oracle-AAE bridge API version.

### Fusion Stats Endpoint

Monitor fusion metrics:

```bash
curl http://127.0.0.1:8787/api/oracle/fusion-stats
```

### Integration Test

Run the integration test suite:

```bash
cd aae-engine
python -m pytest tests/integration/test_oracle_bridge.py -v
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Connection refused | Verify AAE is running on port 8787 |
| Timeout errors | Increase `timeout_seconds` in bridge config |
| Oracle not connecting | Check `base_url` matches AAE address |
| High latency | Consider local deployment or network optimization |

## Related Documentation

- [Integration Contract](integration_contract.md) — Protocol and API specifications
- [Candidate Schema](candidate_schema.md) — Candidate data structure
- [Oracle-AAE Fusion Plan](../docs/oracle_aae_fusion_plan.md) — System architecture overview

