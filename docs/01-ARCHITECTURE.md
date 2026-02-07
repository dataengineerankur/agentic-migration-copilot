# 1. ARCHITECTURE — Agentic Data Migration Copilot

## 1.1 Components (Implementation Specification)

### Control Plane (CP) Services

| Service | Responsibility | Interface |
|---------|---------------|-----------|
| **ProjectService** | Creates/manages migration projects, tracks state machine, owns project metadata | REST API + CLI |
| **PolicyService** | Loads/enforces policy rulebooks, validates plans against tolerances, encryption requirements, PII rules | Internal RPC |
| **AgentOrchestrator** | Runs agents in sandboxed mode (proposal-only), collects outputs, enforces agent contracts | Internal queue-based |
| **ArtifactService** | Manages PR bundles, reports, evidence packs; returns immutable URIs | REST API |
| **AuditLogService** | Append-only, hash-chained audit entries; every action logged with reasoning | Append-only API |
| **PRCIManager** | Creates branches/commits/PRs via Git provider; triggers CI; blocks merges | Git API adapter |

### Execution Plane (EP) Services

| Service | Responsibility | Constraints |
|---------|---------------|-------------|
| **ConnectorRuntime** | Adapters for Postgres, HDFS/Hive, Snowflake, Redshift, S3, Delta/Iceberg | Read-only unless SignedPlan approved |
| **JobRunner** | Containerized execution; retries with exponential backoff; idempotent; resumable from checkpoint | Only accepts SignedPlan |
| **ReconciliationRunner** | Row hashing, sampling, aggregates, key-diff; produces recon_report.json | Deterministic; params from SignedPlan |
| **ReportPublisher** | Uploads outputs to artifact store; returns immutable URIs with sha256 | No modification after publish |

### Shared Infrastructure

| Component | Specification |
|-----------|--------------|
| **Git Provider Integration** | GitHub/GitLab/Bitbucket adapter; create branches/commits/PRs only; **NO MERGE CAPABILITY** |
| **CI Integration** | Lint, unit tests, policy checks, dry runs; webhook-triggered; results stored in ArtifactService |
| **Artifact Storage** | S3/GCS/Azure Blob; immutable objects; versioned; sha256 integrity; retention policy enforced |
| **Secrets Manager** | HashiCorp Vault / AWS Secrets Manager / Azure Key Vault; customer-controlled; no plaintext in logs/configs |

---

## 1.2 Determinism Boundary (Non-Negotiable)

### Agent Constraints

```
AGENTS MAY:
  - Propose plans, mappings, code patches
  - Emit reasoning.json with citations
  - Request human decisions via manual_decisions_required.json

AGENTS MAY NOT:
  - Execute any data operation
  - Modify production systems
  - Approve their own outputs
  - Access secrets directly
```

### Deterministic Validators (Must Implement)

| Validator | Enforcement Rule |
|-----------|-----------------|
| **TypeCoercionValidator** | Validates source→target type mappings against `type_coercion_rulebook.json` |
| **HashingValidator** | Ensures hashing algorithm + serialization matches `hashing_spec.json` |
| **SamplingValidator** | Confirms sampling params are deterministic and reproducible |
| **ToleranceValidator** | Checks all tolerances against `policy.json` thresholds |
| **ApprovalValidator** | Verifies required approvals exist for current state transition |
| **SignedPlanValidator** | Validates SignedPlan structure, signatures, policy_version alignment |

### EP Execution Constraint

```
EP ACCEPTS ONLY:
  - SignedPlan with valid signature from CP validators
  - SignedPlan.status == "APPROVED"
  - SignedPlan.policy_version == current PolicyService version
  - All required approvals present in approvals[] array
```

---

## 1.3 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CONTROL PLANE                                   │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   User/UI    │  │     CLI      │  │   Webhook    │  │   API GW     │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │             │
│         └─────────────────┴────────┬────────┴─────────────────┘             │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        ProjectService                                │    │
│  │  • Project CRUD  • State Machine  • Archetype Selection             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Agent Orchestrator                              │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │    │
│  │  │Discovery │ │Profiling │ │ Mapping  │ │ Rewrite  │ │  Recon   │  │    │
│  │  │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │    │
│  │  ┌──────────┐ ┌──────────┐                                         │    │
│  │  │DiffExpl. │ │ Cutover  │  [All agents: PROPOSAL MODE ONLY]       │    │
│  │  │  Agent   │ │  Agent   │                                         │    │
│  │  └──────────┘ └──────────┘                                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐    │
│  │PolicyService│  │ArtifactSvc  │  │ AuditLog    │  │  PR/CI Manager  │    │
│  │ • Rulebooks │  │ • PR Bundles│  │ • Hash-chain│  │ • Branch/Commit │    │
│  │ • Tolerances│  │ • Evidence  │  │ • Immutable │  │ • NO MERGE      │    │
│  │ • Validators│  │ • Reports   │  │ • Reasoning │  │ • CI Triggers   │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘    │
│         │                 │                 │                 │             │
└─────────┼─────────────────┼─────────────────┼─────────────────┼─────────────┘
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                      SIGNED PLAN BARRIER                         │
    │  • Signature verification  • Policy version check                │
    │  • Approval chain validation  • Scope boundary enforcement       │
    └─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXECUTION PLANE                                 │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                          Job Runner                                  │    │
│  │  • Containerized  • Idempotent  • Resumable  • Retry w/ backoff     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Connector Runtimes                              │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │    │
│  │  │ Postgres │ │HDFS/Hive │ │Snowflake │ │ Redshift │ │  S3/GCS  │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │    │
│  │  ┌──────────┐ ┌──────────┐                                         │    │
│  │  │  Delta   │ │ Iceberg  │                                         │    │
│  │  └──────────┘ └──────────┘                                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Reconciliation Runner                             │    │
│  │  • Row hashing  • Deterministic sampling  • Aggregate checks        │    │
│  │  • Key-diff  • Tolerance evaluation  • Report generation            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       Report Publisher                               │    │
│  │  • Immutable upload  • SHA256 integrity  • URI generation           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │   Immutable Artifact Store   │
                    │  (S3/GCS/Azure Blob)         │
                    │  • Versioned  • SHA256       │
                    │  • Retention enforced        │
                    │  • Compliance tagged         │
                    └──────────────────────────────┘
```

---

## 1.4 Control/Data Flow (Implementation Sequence)

### Flow Step 1: Project Creation + Archetype Selection

```
INPUT:  User request (source system, target system, scope)
OUTPUT: project.json with archetype_id, project_id, initial_state="CREATED"

STEPS:
1. User calls ProjectService.create(source_type, target_type, scope_definition)
2. ProjectService validates scope against available archetypes
3. ProjectService assigns archetype_id from archetype registry
4. ProjectService creates project.json with unique project_id
5. AuditLogService.append(project_id, "PROJECT_CREATED", reasoning)
6. State = CREATED
```

### Flow Step 2: Discovery + Profiling (Proposal Mode)

```
INPUT:  project.json, source connection config (from Secrets Manager)
OUTPUT: discovery_report.json, profiling_report.json

STEPS:
1. AgentOrchestrator.run(DiscoveryAgent, project_id)
2. DiscoveryAgent emits proposal.json: { objects_found, schemas, partitions }
3. DiscoveryAgent emits reasoning.json: { methodology, confidence, limitations }
4. AgentOrchestrator.run(ProfilingAgent, discovery_report)
5. ProfilingAgent emits proposal.json: { row_counts, null_rates, cardinality, data_types, samples }
6. ProfilingAgent emits reasoning.json
7. All outputs stored via ArtifactService
8. State = DISCOVERED
```

### Flow Step 3: Compile MigrationPlan

```
INPUT:  discovery_report.json, profiling_report.json, archetype_template
OUTPUT: migration_plan.json (unsigned)

STEPS:
1. AgentOrchestrator.run(MappingAgent, profiling_report)
2. MappingAgent loads archetype template + type_coercion_rulebook.json
3. MappingAgent emits schema_mapping.yml (source→target column mappings)
4. MappingAgent emits manual_decisions_required.json IF any mapping is ambiguous/lossy
5. AgentOrchestrator.run(RewriteAgent, schema_mapping)
6. RewriteAgent generates code patches (dbt models, Spark jobs, SQL transforms)
7. Compile all into migration_plan.json with explicit steps/params
8. State = PLAN_DRAFTED
```

### Flow Step 4: Validation + SignedPlan Creation

```
INPUT:  migration_plan.json, policy.json
OUTPUT: signed_plan.json (version N, immutable)

STEPS:
1. PolicyService.validate(migration_plan, policy.json)
2. TypeCoercionValidator.run(migration_plan.mappings)
3. ToleranceValidator.run(migration_plan.tolerances)
4. HashingValidator.run(migration_plan.recon_config)
5. IF all pass: create SignedPlan with cryptographic signature
6. SignedPlan.version = N (incremented)
7. SignedPlan.policy_version = PolicyService.current_version
8. Store SignedPlan via ArtifactService (immutable)
9. State = PLANNED
```

### Flow Step 5: Execution Phase

```
INPUT:  signed_plan.json (approved)
OUTPUT: execution_report.json, data in target

STEPS:
1. EP.JobRunner receives SignedPlan
2. SignedPlanValidator.verify(signature, policy_version, approvals)
3. JobRunner.execute(SignedPlan.steps[]) with checkpointing
4. Each step: extract → transform → load → checkpoint
5. ReportPublisher uploads execution_report.json
6. State = EXECUTED
```

### Flow Step 6: Reconciliation

```
INPUT:  execution_report.json, recon_plan from SignedPlan
OUTPUT: recon_report.json

STEPS:
1. ReconciliationRunner loads recon_plan
2. Execute row hashing on source + target (same serialization)
3. Execute aggregate checks (counts, sums, nulls)
4. Execute key-diff where applicable
5. Evaluate against tolerances from policy.json
6. Generate severity classifications (Critical/Major/Minor)
7. ReportPublisher uploads recon_report.json
8. State = RECONCILED
```

### Flow Step 7: PR Creation + CI Checks

```
INPUT:  all artifacts, schema mappings, configs, runbooks
OUTPUT: Pull Request with CI status

STEPS:
1. PRCIManager.createBranch(project_id)
2. PRCIManager.commit(plans/, contracts/, configs/, reconciliation/, runbooks/, evidence/)
3. PRCIManager.createPR(branch, target_branch, description)
4. CI pipeline triggered: lint, unit tests, policy checks, dry runs
5. CI results stored via ArtifactService
6. PR status updated (blocked if any blocker condition met)
7. State = PR_CREATED
```

### Flow Step 8: Approval + State Transitions

```
INPUT:  PR with passing CI, required approvers
OUTPUT: Approved state transitions

STEPS:
1. Approvers review PR contents
2. Each approval recorded: { approver, timestamp, scope, sha256_of_reviewed }
3. ApprovalValidator checks required approvals per transition:
   - PROPOSED → PLANNED: Tech Lead
   - PLANNED → EXECUTED: Data Owner + Security
   - EXECUTED → PARALLEL_VALIDATED: QA Lead
   - PARALLEL_VALIDATED → CUTOVER_READY: Business Owner
   - CUTOVER_READY → CUTOVER_DONE: Release Manager + Data Owner
4. State machine advances only with valid approvals
```

### Flow Step 9: Evidence Pack Composition

```
INPUT:  All artifacts from steps 1-8
OUTPUT: evidence_pack/ (versioned, immutable)

STEPS:
1. ArtifactService.composeEvidencePack(project_id)
2. Include: plan, code, recon, approvals, audit_chain
3. Generate sha256_manifest.json for every file
4. Generate audit_chain.json linking plan→runs→approvals
5. Upload to immutable artifact store
6. Generate immutable URI
7. State = EVIDENCE_COMPLETE
```

