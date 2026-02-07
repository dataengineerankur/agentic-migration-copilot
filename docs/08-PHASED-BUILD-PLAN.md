# 8. PHASED BUILD PLAN — Actionable Implementation

Each phase has explicit success criteria and done definitions. No phase is complete until all artifacts are produced.

---

## Phase 0: Foundation (Weeks 1-3)

### Objective
Establish core infrastructure, schemas, and base services that all subsequent phases depend on.

### Deliverables

| # | Deliverable | Owner | Artifact |
|---|-------------|-------|----------|
| 0.1 | Git repository structure | Platform | `repo_structure.md` |
| 0.2 | JSON Schema definitions | Platform | `schemas/*.schema.json` |
| 0.3 | Policy rulebook v1.0 | Governance | `policy/policy.json` |
| 0.4 | Type coercion rulebook v1.0 | Data Eng | `policy/type_coercion_rulebook.json` |
| 0.5 | Hashing specification v1.0 | Data Eng | `specs/hashing_spec.json` |
| 0.6 | Secrets manager integration | Security | `infra/secrets_integration.tf` |
| 0.7 | Artifact storage (S3/GCS) | Platform | `infra/artifact_storage.tf` |
| 0.8 | Audit log service | Platform | `services/audit_log/` |
| 0.9 | Base CI/CD pipeline | Platform | `.github/workflows/` |
| 0.10 | Development environment | Platform | `docker-compose.yml` |

### Implementation Tasks

```yaml
phase_0_tasks:
  - id: P0-001
    name: Initialize repository structure
    description: |
      Create mono-repo with:
        - /services (CP + EP services)
        - /schemas (JSON schemas)
        - /policy (rulebooks)
        - /specs (hashing, serialization)
        - /infra (terraform)
        - /docs (documentation)
    done_when:
      - README.md exists with setup instructions
      - .gitignore configured
      - Pre-commit hooks installed

  - id: P0-002
    name: Define all JSON schemas
    description: |
      Implement schemas from Section 2:
        - signed_plan.schema.json
        - policy.schema.json
        - agent_output.schema.json
        - evidence_pack.schema.json
        - state_machine.json
        - type_coercion_rulebook.schema.json
    done_when:
      - All schemas pass validation
      - Example instances provided
      - Schema tests written

  - id: P0-003
    name: Implement AuditLogService
    description: |
      Append-only, hash-chained audit log:
        - PostgreSQL or DynamoDB backend
        - Append-only constraint enforced
        - Hash chaining verified on read
        - Retention policy applied
    done_when:
      - Service deployed
      - API documented
      - Integration tests pass
      - Chain verification works

  - id: P0-004
    name: Implement ArtifactService
    description: |
      Immutable artifact storage:
        - S3/GCS backend
        - SHA256 on upload
        - Immutable (no overwrites)
        - Signed URLs for access
    done_when:
      - Upload/download working
      - SHA256 verification working
      - Immutability enforced
      - Retention policies applied

  - id: P0-005
    name: Secrets manager integration
    description: |
      Integration with HashiCorp Vault:
        - vault:// URI scheme
        - Read-only credentials for connectors
        - No plaintext in logs/configs
    done_when:
      - Vault integration working
      - Secret rotation supported
      - Audit trail for secret access

  - id: P0-006
    name: Base CI/CD pipeline
    description: |
      GitHub Actions workflows:
        - Lint (Python, YAML, JSON)
        - Unit tests
        - Schema validation
        - Security scan (secrets, deps)
    done_when:
      - All checks green on main
      - Branch protection configured
      - Required checks defined
```

### Success Criteria

- [ ] All 6 JSON schemas validated with examples
- [ ] AuditLogService deployed and tested
- [ ] ArtifactService deployed and tested
- [ ] Secrets manager integrated
- [ ] CI pipeline running on every PR
- [ ] Development environment reproducible

### Done Definition

```yaml
phase_0_done:
  - artifact: "schemas/signed_plan.schema.json"
    validation: "ajv validate passes"
  - artifact: "schemas/policy.schema.json"
    validation: "ajv validate passes"
  - artifact: "policy/policy.json"
    validation: "validates against policy.schema.json"
  - artifact: "specs/hashing_spec.json"
    validation: "spec document complete"
  - service: "AuditLogService"
    validation: "health check passes, chain verification works"
  - service: "ArtifactService"
    validation: "upload/download works, immutability enforced"
  - infra: "Secrets Manager"
    validation: "vault:// URIs resolve correctly"
  - ci: "Base Pipeline"
    validation: "all checks pass on main branch"
```

---

## Phase 1: Archetypes (Weeks 4-10)

### Objective
Implement all four archetype templates in priority order with full agent support.

### Sub-phases

#### Phase 1.1: Postgres → S3 (Weeks 4-5)

| # | Deliverable | Owner | Artifact |
|---|-------------|-------|----------|
| 1.1.1 | Postgres connector (read-only) | Data Eng | `connectors/postgres/` |
| 1.1.2 | S3 writer (Parquet) | Data Eng | `connectors/s3_parquet/` |
| 1.1.3 | Discovery Agent (Postgres) | Agent Team | `agents/discovery/postgres.py` |
| 1.1.4 | Profiling Agent (Postgres) | Agent Team | `agents/profiling/postgres.py` |
| 1.1.5 | Mapping Agent (PG→S3) | Agent Team | `agents/mapping/postgres_s3.py` |
| 1.1.6 | Rewrite Agent (dbt/Spark) | Agent Team | `agents/rewrite/postgres_s3.py` |
| 1.1.7 | Archetype template | Data Eng | `archetypes/postgres_to_s3.json` |
| 1.1.8 | Type coercion rules (PG→Parquet) | Data Eng | `policy/type_rules/postgres_parquet.json` |
| 1.1.9 | End-to-end test | QA | `tests/e2e/postgres_to_s3/` |

**Done Definition:**
- [ ] Extract 1M rows from Postgres to S3/Parquet
- [ ] Schema mapping generated automatically
- [ ] Type coercions applied correctly
- [ ] dbt model generated and valid
- [ ] Reconciliation runs successfully

#### Phase 1.2: HDFS/Hive → S3 (Weeks 6-7)

| # | Deliverable | Owner | Artifact |
|---|-------------|-------|----------|
| 1.2.1 | HDFS connector | Data Eng | `connectors/hdfs/` |
| 1.2.2 | Hive metastore connector | Data Eng | `connectors/hive_metastore/` |
| 1.2.3 | Discovery Agent (Hive) | Agent Team | `agents/discovery/hive.py` |
| 1.2.4 | Profiling Agent (Hive) | Agent Team | `agents/profiling/hive.py` |
| 1.2.5 | Mapping Agent (Hive→S3) | Agent Team | `agents/mapping/hive_s3.py` |
| 1.2.6 | Partition mapping logic | Data Eng | `connectors/partition_mapper.py` |
| 1.2.7 | Archetype template | Data Eng | `archetypes/hdfs_to_s3.json` |
| 1.2.8 | End-to-end test | QA | `tests/e2e/hdfs_to_s3/` |

**Done Definition:**
- [ ] Read partitioned Hive table
- [ ] Partition mapping preserved or optimized
- [ ] All file formats supported (Parquet, ORC, Avro)
- [ ] Glue/Athena catalog registration working

#### Phase 1.3: Snowflake → Redshift (Weeks 8-9)

| # | Deliverable | Owner | Artifact |
|---|-------------|-------|----------|
| 1.3.1 | Snowflake connector | Data Eng | `connectors/snowflake/` |
| 1.3.2 | Redshift connector | Data Eng | `connectors/redshift/` |
| 1.3.3 | Discovery Agent (Snowflake) | Agent Team | `agents/discovery/snowflake.py` |
| 1.3.4 | Profiling Agent (Snowflake) | Agent Team | `agents/profiling/snowflake.py` |
| 1.3.5 | Mapping Agent (SF→RS) | Agent Team | `agents/mapping/snowflake_redshift.py` |
| 1.3.6 | Null semantics handler | Data Eng | `transforms/null_semantics.py` |
| 1.3.7 | Timezone handler | Data Eng | `transforms/timezone_handler.py` |
| 1.3.8 | Numeric precision handler | Data Eng | `transforms/numeric_precision.py` |
| 1.3.9 | Archetype template | Data Eng | `archetypes/snowflake_to_redshift.json` |
| 1.3.10 | End-to-end test | QA | `tests/e2e/snowflake_to_redshift/` |

**Done Definition:**
- [ ] UNLOAD from Snowflake to S3
- [ ] COPY to Redshift
- [ ] Null semantics preserved
- [ ] Numeric precision validated
- [ ] Timezone conversions correct
- [ ] VARIANT/SUPER mapping verified

#### Phase 1.4: Data Lake → Delta/Iceberg (Week 10)

| # | Deliverable | Owner | Artifact |
|---|-------------|-------|----------|
| 1.4.1 | Delta Lake connector | Data Eng | `connectors/delta/` |
| 1.4.2 | Iceberg connector | Data Eng | `connectors/iceberg/` |
| 1.4.3 | Schema evolution handler | Data Eng | `transforms/schema_evolution.py` |
| 1.4.4 | Partition evolution handler | Data Eng | `transforms/partition_evolution.py` |
| 1.4.5 | Performance benchmark runner | QA | `benchmarks/performance_runner.py` |
| 1.4.6 | Archetype template | Data Eng | `archetypes/lake_to_delta_iceberg.json` |
| 1.4.7 | End-to-end test | QA | `tests/e2e/lake_to_delta_iceberg/` |

**Done Definition:**
- [ ] Convert Parquet lake to Delta
- [ ] Convert Parquet lake to Iceberg
- [ ] Schema evolution applied correctly
- [ ] Partition evolution working
- [ ] Performance parity verified (within 20%)
- [ ] Time travel queries working

### Phase 1 Success Criteria

- [ ] All 4 archetypes have working templates
- [ ] All 7 agents implemented and tested
- [ ] All connectors operational
- [ ] E2E tests pass for each archetype
- [ ] Documentation complete for each archetype

---

## Phase 2: Parallel Run + Reconciliation (Weeks 11-14)

### Objective
Implement complete reconciliation pipeline and parallel validation framework.

### Deliverables

| # | Deliverable | Owner | Artifact |
|---|-------------|-------|----------|
| 2.1 | Row serialization library | Data Eng | `libs/row_serializer/` |
| 2.2 | Hashing library (xxHash64) | Data Eng | `libs/hasher/` |
| 2.3 | Deterministic sampler | Data Eng | `libs/sampler/` |
| 2.4 | Reconciliation Runner | Data Eng | `services/recon_runner/` |
| 2.5 | Reconciliation Agent | Agent Team | `agents/reconciliation/` |
| 2.6 | Diff Explanation Agent | Agent Team | `agents/diff_explanation/` |
| 2.7 | Parallel run scheduler | Platform | `services/parallel_scheduler/` |
| 2.8 | Tolerance evaluator | Data Eng | `libs/tolerance_evaluator/` |
| 2.9 | Recon report generator | Data Eng | `services/recon_reporter/` |
| 2.10 | Dataset classifier | Data Eng | `libs/dataset_classifier/` |

### Implementation Tasks

```yaml
phase_2_tasks:
  - id: P2-001
    name: Implement row serialization
    description: |
      Canonical row serialization per hashing_spec.json:
        - Deterministic column ordering
        - Type-specific serialization
        - Unicode normalization
        - Timezone handling
    done_when:
      - Same row always produces same bytes
      - Cross-platform compatibility verified
      - All types handled per spec

  - id: P2-002
    name: Implement hashing library
    description: |
      xxHash64 for row hashing:
        - Consistent seed
        - Hex output format
        - Chunking for large tables
        - Parallel computation
    done_when:
      - Hash function deterministic
      - Performance benchmarked (>1M rows/sec)
      - Memory-efficient

  - id: P2-003
    name: Implement deterministic sampler
    description: |
      SHA256 modulo sampling:
        - sha256(pk) mod M < K
        - Reproducible across runs
        - Configurable sample rate
    done_when:
      - Same rows selected every run
      - Sample rate accurate (±1%)
      - Works with composite PKs

  - id: P2-004
    name: Implement ReconciliationRunner
    description: |
      Execute reconciliation jobs:
        - Row hash comparison
        - Aggregate comparison
        - Key-diff comparison
        - Tolerance evaluation
        - Report generation
    done_when:
      - All comparison strategies working
      - Severity classification correct
      - Reports generated correctly

  - id: P2-005
    name: Implement Diff Explanation Agent
    description: |
      Analyze reconciliation failures:
        - Pattern detection
        - Hypothesis generation
        - Evidence citation
        - Fix proposal
    done_when:
      - Generates 3+ hypotheses
      - All hypotheses cite evidence
      - Proposed fixes are actionable

  - id: P2-006
    name: Implement parallel run scheduler
    description: |
      Schedule N consecutive runs:
        - Configurable interval
        - Trend analysis
        - Aggregate results
        - Cutover readiness gate
    done_when:
      - Runs execute on schedule
      - Results aggregated correctly
      - Trend analysis working
      - Ready/not-ready gate working
```

### Success Criteria

- [ ] Row hashing deterministic across platforms
- [ ] Sampling reproducible (same rows every time)
- [ ] All reconciliation strategies implemented
- [ ] Diff Explanation produces actionable insights
- [ ] Parallel runs complete for 14 consecutive days
- [ ] Cutover readiness gate working

### Done Definition

```yaml
phase_2_done:
  - test: "Row serialization determinism"
    validation: "100 runs produce identical hashes"
  - test: "Sampling reproducibility"
    validation: "3 runs select identical row sets"
  - test: "Reconciliation accuracy"
    validation: "Known differences detected correctly"
  - test: "Parallel run completion"
    validation: "14-day run completes for test dataset"
  - test: "Diff explanation quality"
    validation: "Hypotheses correctly identify root cause in 5 test cases"
```

---

## Phase 3: Cutover Management (Weeks 15-18)

### Objective
Implement complete cutover workflow with rollback capability and evidence pack generation.

### Deliverables

| # | Deliverable | Owner | Artifact |
|---|-------------|-------|----------|
| 3.1 | Cutover Planning Agent | Agent Team | `agents/cutover_planning/` |
| 3.2 | Cutover executor | Platform | `services/cutover_executor/` |
| 3.3 | Rollback executor | Platform | `services/rollback_executor/` |
| 3.4 | Evidence pack generator | Platform | `services/evidence_generator/` |
| 3.5 | PR/CI Manager | Platform | `services/pr_ci_manager/` |
| 3.6 | State machine service | Platform | `services/state_machine/` |
| 3.7 | Approval workflow | Platform | `services/approval_workflow/` |
| 3.8 | Notification service | Platform | `services/notifications/` |
| 3.9 | Runbook generator | Agent Team | `agents/runbook_generator/` |
| 3.10 | Compliance reporter | Governance | `services/compliance_reporter/` |

### Implementation Tasks

```yaml
phase_3_tasks:
  - id: P3-001
    name: Implement Cutover Planning Agent
    description: |
      Generate cutover and rollback plans:
        - Dependency analysis
        - Step sequencing
        - Time estimation
        - Rollback procedures
    done_when:
      - Cutover plan generated automatically
      - Rollback plan generated
      - Steps are executable
      - Time estimates reasonable

  - id: P3-002
    name: Implement state machine service
    description: |
      Manage migration state transitions:
        - Enforce valid transitions
        - Require approvals
        - Log all changes
        - Prevent invalid states
    done_when:
      - All transitions enforced
      - Invalid transitions rejected
      - Approvals required work
      - Audit log complete

  - id: P3-003
    name: Implement PR/CI Manager
    description: |
      Create and manage migration PRs:
        - Create branches
        - Commit artifacts
        - Create PRs
        - Trigger CI checks
        - Block invalid PRs
    done_when:
      - PRs created automatically
      - All required files included
      - CI checks triggered
      - Blockers enforced

  - id: P3-004
    name: Implement evidence pack generator
    description: |
      Generate immutable evidence packs:
        - Collect all artifacts
        - Generate SHA256 manifest
        - Generate audit chain
        - Sign pack
        - Upload to storage
    done_when:
      - Pack contains all required files
      - SHA256 manifest accurate
      - Audit chain valid
      - Signature verifiable

  - id: P3-005
    name: Implement approval workflow
    description: |
      Manage approval collection:
        - Request approvals
        - Record approvals
        - Verify approvals
        - Enforce requirements
    done_when:
      - Approvals requested correctly
      - Approvals recorded immutably
      - Requirements enforced
      - Audit trail complete

  - id: P3-006
    name: Implement rollback executor
    description: |
      Execute rollback procedures:
        - Revert configuration changes
        - Verify rollback success
        - Log all actions
        - Generate rollback report
    done_when:
      - Rollback executes successfully
      - Verification confirms rollback
      - Report generated
      - System restored to previous state
```

### Success Criteria

- [ ] State machine enforces all transitions
- [ ] PRs created with all required artifacts
- [ ] Approval workflow collects all required approvals
- [ ] Evidence packs generated and verified
- [ ] Rollback tested and working
- [ ] End-to-end migration completes successfully

### Done Definition

```yaml
phase_3_done:
  - test: "Complete migration E2E"
    validation: "Postgres→S3 migration from CREATED to CUTOVER_DONE"
  - test: "Approval enforcement"
    validation: "Cannot advance without required approvals"
  - test: "Evidence pack completeness"
    validation: "Pack passes validation with 47+ files"
  - test: "Rollback execution"
    validation: "Rollback restores system to pre-cutover state"
  - test: "PR structure"
    validation: "PR contains all required directories and files"
  - test: "CI enforcement"
    validation: "PR blocked when checks fail"
```

---

## Build Timeline Summary

```
Week 1-3:   Phase 0 - Foundation
Week 4-5:   Phase 1.1 - Postgres → S3
Week 6-7:   Phase 1.2 - HDFS/Hive → S3
Week 8-9:   Phase 1.3 - Snowflake → Redshift
Week 10:    Phase 1.4 - Lake → Delta/Iceberg
Week 11-14: Phase 2 - Parallel Run + Reconciliation
Week 15-18: Phase 3 - Cutover Management

Total: 18 weeks (4.5 months)
```

---

## Resource Requirements

| Role | Phase 0 | Phase 1 | Phase 2 | Phase 3 |
|------|---------|---------|---------|---------|
| Platform Engineer | 2 | 1 | 2 | 3 |
| Data Engineer | 1 | 3 | 2 | 1 |
| Agent Developer | 0 | 2 | 2 | 1 |
| Security Engineer | 1 | 0.5 | 0.5 | 0.5 |
| QA Engineer | 0.5 | 1 | 1 | 1 |
| **Total FTEs** | **4.5** | **7.5** | **7.5** | **6.5** |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Schema complexity delays | Start with simple schemas, iterate |
| Connector instability | Extensive integration testing |
| Performance issues | Early benchmarking, optimize hot paths |
| Approval bottlenecks | Parallel approval workflows |
| Rollback failures | Test rollback before every cutover |

