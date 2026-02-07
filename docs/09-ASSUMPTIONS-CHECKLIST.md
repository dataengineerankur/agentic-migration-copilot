# 9. ASSUMPTIONS + PRE-CODE CHECKLIST

---

## 9.1 Assumptions

### Infrastructure Assumptions

1. **Cloud Provider**: AWS, GCP, or Azure available with appropriate permissions
2. **Artifact Storage**: S3/GCS/Azure Blob available for immutable artifact storage
3. **Secrets Manager**: HashiCorp Vault, AWS Secrets Manager, or Azure Key Vault available
4. **Git Provider**: GitHub, GitLab, or Bitbucket with API access for PR automation
5. **CI/CD**: GitHub Actions, GitLab CI, or equivalent available
6. **Compute**: Container orchestration (K8s/ECS/Cloud Run) for services
7. **Database**: PostgreSQL available for metadata storage (AuditLogService, StateService)

### Source System Assumptions

1. **Postgres**: Version 11+ with read-only credentials available
2. **HDFS/Hive**: Hadoop 3.x, Hive 3.x with Kerberos or equivalent auth
3. **Snowflake**: Enterprise tier with UNLOAD to S3 capability
4. **Redshift**: Serverless or provisioned with COPY from S3

### Target System Assumptions

1. **S3**: Bucket exists with write permissions, lifecycle policies configurable
2. **Redshift**: Cluster sized appropriately, staging S3 bucket available
3. **Delta Lake**: Databricks or OSS Delta available, Unity Catalog or Hive metastore
4. **Iceberg**: AWS Glue, Nessie, or Hive metastore for catalog

### Organizational Assumptions

1. **Approval Roles**: tech_lead, data_owner, security, qa_lead, business_owner, release_manager roles defined
2. **Compliance**: SOX, GDPR, HIPAA requirements known if applicable
3. **Change Management**: Maintenance windows schedulable
4. **Communication**: Notification channels (Slack, email, PagerDuty) available

### Technical Assumptions

1. **Network**: Source and target systems reachable from execution environment
2. **Credentials**: All credentials managed via secrets manager, no plaintext
3. **Encryption**: TLS 1.2+ for transit, AES-256 for rest
4. **Idempotency**: All operations designed for safe retry

---

## 9.2 Pre-Code Checklist

**Before writing ANY code, the following artifacts MUST exist and be reviewed:**

### Schema Definitions (REQUIRED)

- [ ] **`schemas/signed_plan.schema.json`**
  - All fields from Section 2.1 defined
  - Validated with ajv or equivalent
  - Example instance provided: `schemas/examples/signed_plan.example.json`

- [ ] **`schemas/policy.schema.json`**
  - Tolerance definitions for classes A/B/C/D
  - Approval transition matrix
  - Encryption and PII requirements
  - Example: `schemas/examples/policy.example.json`

- [ ] **`schemas/agent_output.schema.json`**
  - proposal.json structure
  - reasoning.json structure
  - artifacts_manifest structure
  - manual_decisions_required structure

- [ ] **`schemas/evidence_pack.schema.json`**
  - metadata.json structure
  - sha256_manifest structure
  - audit_chain structure

- [ ] **`schemas/state_machine.json`**
  - All states defined
  - All transitions with required approvals
  - Blocker conditions per transition

### Policy Rulebook (REQUIRED)

- [ ] **`policy/policy.json`**
  - Version: v1.0.0
  - Dataset classes A/B/C/D with tolerances
  - Approval requirements per transition
  - PII detection patterns
  - Encryption requirements
  - Retention policies

### Type Coercion Rulebook (REQUIRED)

- [ ] **`policy/type_coercion_rulebook.json`**
  - Version: v1.0.0
  - All Postgres → Parquet mappings
  - All Hive → Parquet mappings
  - All Snowflake → Redshift mappings
  - Lossy flag for each rule
  - requires_approval flag for lossy rules

### Hashing Specification (REQUIRED)

- [ ] **`specs/hashing_spec.json`**
  - Version: v1.0.0
  - Canonical serialization rules for all types
  - Column ordering (alphabetical)
  - Null representation
  - Timestamp timezone handling
  - Numeric precision handling
  - Unicode normalization (NFC)

### PR Layout (REQUIRED)

- [ ] **`docs/pr_structure.md`**
  - Required directories documented
  - Required files per directory documented
  - File naming conventions
  - Blocker conditions documented

### Evidence Pack Structure (REQUIRED)

- [ ] **`docs/evidence_pack_structure.md`**
  - Full directory tree documented
  - Required vs optional files
  - SHA256 manifest format
  - Audit chain format
  - Signature format

### Credential Boundaries (REQUIRED)

- [ ] **`docs/credential_boundaries.md`**
  - vault:// URI scheme documented
  - Read-only vs write credentials
  - Secret rotation requirements
  - Audit logging for secret access
  - No plaintext anywhere policy

### Validator Suite (REQUIRED)

- [ ] **Validator specifications documented:**
  - TypeCoercionValidator: inputs, outputs, rules
  - HashingValidator: inputs, outputs, rules
  - SamplingValidator: inputs, outputs, rules
  - ToleranceValidator: inputs, outputs, rules
  - ApprovalValidator: inputs, outputs, rules
  - SignedPlanValidator: inputs, outputs, rules

---

## 9.3 Validation Checklist for Each Artifact

### For Every Schema

```yaml
schema_validation_checklist:
  - [ ] "$schema" field present (draft-07)
  - [ ] "$id" field with canonical URI
  - [ ] "title" and "description" present
  - [ ] All required fields listed
  - [ ] All fields have type definitions
  - [ ] Patterns defined for ID fields
  - [ ] Enums defined for constrained values
  - [ ] Definitions/refs for reusable structures
  - [ ] Example instance validates
  - [ ] Unit tests for validation logic
```

### For Policy Rulebook

```yaml
policy_validation_checklist:
  - [ ] Version follows semver
  - [ ] All dataset classes (A/B/C/D) defined
  - [ ] Tolerances are numeric (not strings)
  - [ ] All state transitions have approval requirements
  - [ ] PII patterns are valid regex
  - [ ] Encryption requirements are specific (AES-256, TLS-1.3)
  - [ ] Retention periods are defined
  - [ ] Policy approved by security team
```

### For Type Coercion Rulebook

```yaml
type_coercion_validation_checklist:
  - [ ] Every source type has a mapping
  - [ ] Every mapping has rule_id
  - [ ] Lossy mappings are flagged
  - [ ] Lossy mappings have requires_approval
  - [ ] Precision changes documented
  - [ ] Timezone handling specified
  - [ ] NULL semantics documented
  - [ ] Rulebook approved by data engineering lead
```

### For Hashing Specification

```yaml
hashing_spec_validation_checklist:
  - [ ] Algorithm specified (xxhash64 or sha256)
  - [ ] Seed value specified
  - [ ] Column ordering rule specified
  - [ ] Every data type has serialization rule
  - [ ] Null representation specified
  - [ ] Boolean representation specified
  - [ ] Timestamp format specified (ISO8601)
  - [ ] Timezone handling specified (UTC)
  - [ ] Numeric precision rules specified
  - [ ] Unicode normalization specified (NFC)
  - [ ] Binary encoding specified (base64)
  - [ ] Reference implementation provided
  - [ ] Test vectors provided
```

---

## 9.4 Design Review Checklist

Before Phase 0 code begins, conduct design review with these questions:

### Architecture Review

- [ ] Is the Control Plane / Execution Plane boundary clear?
- [ ] Are all agent boundaries documented (can do / cannot do)?
- [ ] Is the SignedPlan the ONLY mechanism for EP execution?
- [ ] Are all state transitions gated by approvals?
- [ ] Is the audit log append-only and hash-chained?

### Security Review

- [ ] Are credentials never in plaintext?
- [ ] Is vault:// the only credential reference scheme?
- [ ] Are all connections TLS 1.2+?
- [ ] Is data encrypted at rest?
- [ ] Are PII detection patterns defined?
- [ ] Is secret access audited?

### Compliance Review

- [ ] Are retention policies defined?
- [ ] Are evidence packs immutable?
- [ ] Is the audit chain verifiable?
- [ ] Are approvals recorded with timestamps and SHA256?
- [ ] Can evidence packs be retrieved for audit?

### Operability Review

- [ ] Are all services observable (metrics, logs, traces)?
- [ ] Are health checks defined?
- [ ] Are retry policies defined?
- [ ] Is rollback documented and tested?
- [ ] Are runbooks generated automatically?

---

## 9.5 Go/No-Go Criteria for Each Phase

### Phase 0 Go Criteria

```yaml
phase_0_go:
  mandatory:
    - All schemas defined and validated
    - Policy rulebook v1.0 approved
    - Type coercion rulebook v1.0 approved
    - Hashing spec v1.0 approved
    - AuditLogService design reviewed
    - ArtifactService design reviewed
    - Security review passed
    - CI/CD pipeline design reviewed
  recommended:
    - Development environment documented
    - Runbook templates created
    - Monitoring requirements defined
```

### Phase 1 Go Criteria

```yaml
phase_1_go:
  mandatory:
    - Phase 0 done definition met
    - All Phase 0 artifacts deployed
    - Read-only connectors designed
    - Agent contracts finalized
    - Archetype templates designed
  recommended:
    - Test data available
    - Target environments available
    - Performance baselines established
```

### Phase 2 Go Criteria

```yaml
phase_2_go:
  mandatory:
    - Phase 1 done definition met
    - All archetypes functional
    - All agents operational
    - Reconciliation Runner designed
    - Diff Explanation Agent designed
  recommended:
    - Test datasets classified
    - Tolerance thresholds validated
    - Parallel run infrastructure available
```

### Phase 3 Go Criteria

```yaml
phase_3_go:
  mandatory:
    - Phase 2 done definition met
    - 14-day parallel run successful
    - State machine service designed
    - PR/CI Manager designed
    - Evidence pack generator designed
    - Rollback tested successfully
  recommended:
    - Approval workflow tested
    - Stakeholders trained
    - Runbooks reviewed
```

---

## 9.6 Manual Decisions Required Template

When any agent encounters ambiguity, it MUST emit this artifact instead of guessing:

**`manual_decisions_required.json`**:

```json
{
  "$schema": "https://migration-copilot/schemas/manual_decisions.schema.json",
  "version": "v1.0.0",
  "created_at": "2026-01-05T10:00:00Z",
  "created_by": "mapping_agent",
  "project_id": "proj_abc123",
  "decisions_required": [
    {
      "decision_id": "dec_001",
      "category": "type_mapping",
      "priority": "high",
      "blocking": true,
      "description": "Source column 'interval_col' has type INTERVAL which has no direct Parquet equivalent",
      "context": {
        "source_table": "public.events",
        "source_column": "duration",
        "source_type": "interval",
        "target_system": "parquet/s3"
      },
      "options": [
        {
          "option_id": "opt_a",
          "description": "Convert to STRING representation (ISO 8601 duration)",
          "example": "P1DT2H30M",
          "lossy": false,
          "recommended": true,
          "tradeoffs": "Requires parsing for calculations"
        },
        {
          "option_id": "opt_b",
          "description": "Convert to total seconds as INT64",
          "example": 95400,
          "lossy": true,
          "recommended": false,
          "tradeoffs": "Loses months/years precision (variable days)"
        },
        {
          "option_id": "opt_c",
          "description": "Split into multiple columns (months, days, seconds)",
          "example": {"months": 0, "days": 1, "seconds": 9000},
          "lossy": false,
          "recommended": false,
          "tradeoffs": "Schema complexity, query changes required"
        }
      ],
      "deadline_hours": 48,
      "escalation_contact": "data-engineering@company.com",
      "documentation_refs": [
        "https://docs.company.com/data-types/interval",
        "https://www.postgresql.org/docs/current/datatype-datetime.html"
      ]
    }
  ],
  "summary": {
    "total_decisions": 1,
    "blocking_decisions": 1,
    "categories": {"type_mapping": 1},
    "estimated_resolution_hours": 48
  }
}
```

---

## 9.7 Final Pre-Code Verification

Execute this verification before any code is written:

```bash
#!/bin/bash
# pre_code_verify.sh

echo "=== Pre-Code Verification ==="

# 1. Check schemas exist
SCHEMAS=(
  "schemas/signed_plan.schema.json"
  "schemas/policy.schema.json"
  "schemas/agent_output.schema.json"
  "schemas/evidence_pack.schema.json"
  "schemas/state_machine.json"
)

for schema in "${SCHEMAS[@]}"; do
  if [ ! -f "$schema" ]; then
    echo "FAIL: Missing $schema"
    exit 1
  fi
  echo "OK: $schema exists"
done

# 2. Validate schemas
for schema in "${SCHEMAS[@]}"; do
  if ! npx ajv compile -s "$schema" 2>/dev/null; then
    echo "FAIL: $schema is invalid"
    exit 1
  fi
  echo "OK: $schema is valid"
done

# 3. Check policy exists
if [ ! -f "policy/policy.json" ]; then
  echo "FAIL: Missing policy/policy.json"
  exit 1
fi
echo "OK: policy/policy.json exists"

# 4. Validate policy against schema
if ! npx ajv validate -s schemas/policy.schema.json -d policy/policy.json; then
  echo "FAIL: policy.json does not validate"
  exit 1
fi
echo "OK: policy.json validates"

# 5. Check type coercion rulebook
if [ ! -f "policy/type_coercion_rulebook.json" ]; then
  echo "FAIL: Missing type_coercion_rulebook.json"
  exit 1
fi
echo "OK: type_coercion_rulebook.json exists"

# 6. Check hashing spec
if [ ! -f "specs/hashing_spec.json" ]; then
  echo "FAIL: Missing hashing_spec.json"
  exit 1
fi
echo "OK: hashing_spec.json exists"

# 7. Check documentation
DOCS=(
  "docs/pr_structure.md"
  "docs/evidence_pack_structure.md"
  "docs/credential_boundaries.md"
)

for doc in "${DOCS[@]}"; do
  if [ ! -f "$doc" ]; then
    echo "WARN: Missing $doc (recommended)"
  else
    echo "OK: $doc exists"
  fi
done

echo "=== Pre-Code Verification PASSED ==="
```

---

## 9.8 Signoff Requirements

Before Phase 0 begins, collect signoffs:

| Document | Approver Role | Required |
|----------|--------------|----------|
| `schemas/signed_plan.schema.json` | Tech Lead | ✓ |
| `schemas/policy.schema.json` | Tech Lead + Security | ✓ |
| `policy/policy.json` | Security + Compliance | ✓ |
| `policy/type_coercion_rulebook.json` | Data Engineering Lead | ✓ |
| `specs/hashing_spec.json` | Data Engineering Lead | ✓ |
| Architecture Document | Tech Lead + Security | ✓ |
| Security Boundaries | Security Lead | ✓ |
| Compliance Requirements | Compliance Officer | If applicable |

---

**END OF SPECIFICATION**

This document contains 9 sections with complete implementation-ready specifications. All schemas, workflows, and checklists are concrete and actionable. No guessing—emit `manual_decisions_required.json` for any ambiguity.

