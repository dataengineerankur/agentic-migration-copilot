# 6. PR & CI WORKFLOW — Strict Governance

All changes must flow through PRs. No direct commits. No auto-merge. Human approval required.

---

## 6.1 PR Structure Requirements

### Required Directory Structure

Every migration PR MUST include these directories and files:

```
migration-pr-{project_id}/
├── plans/
│   ├── signed_plan_{plan_id}.json        # REQUIRED: Immutable signed plan
│   └── plan_summary.md                    # REQUIRED: Human-readable summary
│
├── contracts/
│   ├── schema_mapping.yml                 # REQUIRED: Source→target mappings
│   ├── type_coercion_log.json            # REQUIRED: All type conversions applied
│   └── manual_decisions.json             # IF ANY: Resolved manual decisions
│
├── configs/
│   ├── migration_config.yml              # REQUIRED: Migration parameters
│   ├── recon_config.yml                  # REQUIRED: Reconciliation config
│   └── secrets_refs.yml                  # REQUIRED: Secret references (no values)
│
├── reconciliation/
│   ├── recon_plan.json                   # REQUIRED: Reconciliation plan
│   ├── recon_summary.md                  # REQUIRED: Human-readable summary
│   └── parallel_runs/                    # IF VALIDATED: Parallel run results
│       ├── run_001.json
│       ├── run_002.json
│       └── ...
│
├── runbooks/
│   ├── {dataset}_runbook.md              # REQUIRED: Operational runbook
│   ├── cutover_plan.md                   # IF CUTOVER: Cutover instructions
│   └── rollback_plan.md                  # IF CUTOVER: Rollback instructions
│
├── evidence/
│   ├── evidence_links.json               # REQUIRED: Links to evidence artifacts
│   ├── approval_records.json             # REQUIRED: Approval chain
│   └── audit_log_excerpt.json            # REQUIRED: Relevant audit entries
│
├── code/
│   ├── dbt/                              # IF APPLICABLE
│   │   └── models/
│   ├── spark/                            # IF APPLICABLE
│   │   └── jobs/
│   ├── sql/                              # IF APPLICABLE
│   │   └── transforms/
│   └── airflow/                          # IF APPLICABLE
│       └── dags/
│
└── .migration_metadata.json              # REQUIRED: PR metadata
```

### PR Metadata File

`.migration_metadata.json`:

```json
{
  "schema_version": "v1.0.0",
  "project_id": "proj_abc123def456",
  "plan_id": "plan_789xyz",
  "plan_version": 3,
  "archetype_id": "postgres_to_s3",
  "created_at": "2026-01-05T10:00:00Z",
  "created_by": "migration-copilot-agent",
  "state": "PLANNED",
  "target_state": "EXECUTED",
  "policy_version": "v2.1.0",
  "rulebook_version": "v1.5.0",
  "required_approvals": [
    {"role": "data_owner", "status": "pending"},
    {"role": "security", "status": "pending"}
  ],
  "ci_checks_required": [
    "lint_yaml",
    "validate_schema_mapping",
    "policy_compliance",
    "dry_run_extract",
    "security_scan"
  ],
  "blockers": []
}
```

---

## 6.2 PR Blockers

### Automatic Blockers (CI Enforced)

The PR CANNOT be approved if any of these conditions are true:

| Blocker ID | Condition | Resolution |
|------------|-----------|------------|
| `MISSING_METADATA` | `.migration_metadata.json` missing or invalid | Add required metadata |
| `UNSIGNED_PLAN` | `signed_plan.json` missing signature | Re-generate signed plan |
| `POLICY_VERSION_MISMATCH` | Plan policy_version != current PolicyService version | Re-validate with current policy |
| `UNRESOLVED_MANUAL_DECISIONS` | `manual_decisions_required.json` has unresolved items | Resolve all decisions |
| `LOSSY_MAPPING_NO_APPROVAL` | Lossy type mapping without approval request | Add approval request or fix mapping |
| `PROFILING_INCOMPLETE` | Profiling report missing or incomplete | Complete profiling |
| `POLICY_VIOLATION` | PolicyService reports violations | Fix violations |
| `PII_NOT_ADDRESSED` | PII detected but not addressed in plan | Add PII handling |
| `ENCRYPTION_UNMET` | Encryption requirements not met | Configure encryption |
| `CI_FAILURE` | Any CI check failed | Fix CI failures |
| `RECON_CRITICAL` | Reconciliation has CRITICAL severity | Investigate and fix |
| `RECON_MAJOR_UNACK` | Reconciliation has unacknowledged MAJOR | Acknowledge or fix |
| `EVIDENCE_INCOMPLETE` | Evidence pack missing required artifacts | Complete evidence |
| `SCHEMA_VALIDATION_FAILED` | YAML/JSON schema validation failed | Fix schema errors |
| `SECRETS_EXPOSED` | Secrets or credentials in PR content | Remove secrets |

### Blocker Check Implementation

```yaml
# .github/workflows/migration-pr-checks.yml
name: Migration PR Checks

on:
  pull_request:
    paths:
      - 'migrations/**'

jobs:
  validate-structure:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Check required files exist
        run: |
          required_files=(
            ".migration_metadata.json"
            "plans/signed_plan_*.json"
            "contracts/schema_mapping.yml"
            "configs/migration_config.yml"
            "reconciliation/recon_plan.json"
            "runbooks/*.md"
            "evidence/evidence_links.json"
          )
          for pattern in "${required_files[@]}"; do
            if ! ls $pattern 1>/dev/null 2>&1; then
              echo "BLOCKER: Missing required file matching: $pattern"
              exit 1
            fi
          done

  validate-schemas:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Validate JSON schemas
        run: |
          npx ajv validate -s schemas/signed_plan.schema.json -d plans/signed_plan_*.json
          npx ajv validate -s schemas/migration_metadata.schema.json -d .migration_metadata.json

  policy-compliance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run policy checks
        run: |
          python scripts/policy_validator.py \
            --plan plans/signed_plan_*.json \
            --policy policy/policy.json \
            --output policy_check_result.json
          
          if jq -e '.violations | length > 0' policy_check_result.json; then
            echo "BLOCKER: Policy violations detected"
            jq '.violations' policy_check_result.json
            exit 1
          fi

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Scan for secrets
        run: |
          # Check for exposed secrets
          if grep -rE "(password|secret|key|token).*=.*['\"][^'\"]+['\"]" --include="*.yml" --include="*.json" .; then
            echo "BLOCKER: Potential secrets exposed in PR"
            exit 1
          fi
          
          # Check secrets_refs.yml only contains references
          if grep -v "vault://" configs/secrets_refs.yml | grep -E "(password|secret|key)" ; then
            echo "BLOCKER: Direct secrets in secrets_refs.yml"
            exit 1
          fi

  dry-run:
    runs-on: ubuntu-latest
    needs: [validate-structure, validate-schemas, policy-compliance]
    steps:
      - uses: actions/checkout@v4
      
      - name: Execute dry run
        run: |
          python scripts/migration_dry_run.py \
            --plan plans/signed_plan_*.json \
            --output dry_run_result.json
          
          if jq -e '.success == false' dry_run_result.json; then
            echo "BLOCKER: Dry run failed"
            exit 1
          fi

  reconciliation-check:
    runs-on: ubuntu-latest
    if: contains(github.event.pull_request.labels.*.name, 'post-execution')
    steps:
      - uses: actions/checkout@v4
      
      - name: Check reconciliation status
        run: |
          # Find latest recon report
          recon_file=$(ls -t reconciliation/parallel_runs/*.json | head -1)
          
          severity=$(jq -r '.overall_severity' "$recon_file")
          
          if [ "$severity" == "CRITICAL" ]; then
            echo "BLOCKER: Reconciliation has CRITICAL severity"
            exit 1
          fi
          
          if [ "$severity" == "MAJOR" ]; then
            # Check if acknowledged
            if ! jq -e '.acknowledged' "$recon_file"; then
              echo "BLOCKER: MAJOR severity not acknowledged"
              exit 1
            fi
          fi
```

---

## 6.3 CI Pipeline Stages

### Stage 1: Structural Validation

```yaml
stage_1_structural:
  checks:
    - name: file_structure
      description: Verify all required files present
      blocking: true
      
    - name: json_yaml_syntax
      description: Validate JSON/YAML syntax
      blocking: true
      
    - name: schema_validation
      description: Validate against JSON schemas
      blocking: true
      
    - name: metadata_consistency
      description: Verify metadata matches plan
      blocking: true
```

### Stage 2: Policy Compliance

```yaml
stage_2_policy:
  checks:
    - name: policy_version_check
      description: Verify policy version alignment
      blocking: true
      
    - name: tolerance_validation
      description: Verify tolerances within policy bounds
      blocking: true
      
    - name: approval_requirements
      description: Verify required approvals defined
      blocking: true
      
    - name: pii_handling
      description: Verify PII properly addressed
      blocking: true
      
    - name: encryption_compliance
      description: Verify encryption requirements met
      blocking: true
```

### Stage 3: Code Quality

```yaml
stage_3_code:
  checks:
    - name: lint_python
      description: Lint Python code (if applicable)
      blocking: true
      
    - name: lint_sql
      description: Lint SQL code (if applicable)
      blocking: true
      
    - name: lint_yaml
      description: Lint YAML files
      blocking: true
      
    - name: unit_tests
      description: Run unit tests for generated code
      blocking: true
      
    - name: type_check
      description: Type checking for Python
      blocking: false
```

### Stage 4: Security

```yaml
stage_4_security:
  checks:
    - name: secrets_scan
      description: Scan for exposed secrets
      blocking: true
      
    - name: dependency_scan
      description: Scan dependencies for vulnerabilities
      blocking: true
      
    - name: credential_validation
      description: Verify only vault references used
      blocking: true
```

### Stage 5: Dry Run

```yaml
stage_5_dry_run:
  checks:
    - name: connection_test
      description: Verify connectivity (read-only)
      blocking: true
      
    - name: schema_compatibility
      description: Verify target schema compatible
      blocking: true
      
    - name: capacity_check
      description: Verify target has capacity
      blocking: false
      
    - name: extract_sample
      description: Extract sample data (100 rows)
      blocking: true
```

### Stage 6: Post-Execution (Conditional)

```yaml
stage_6_post_execution:
  trigger: label == 'post-execution'
  checks:
    - name: recon_severity
      description: Check reconciliation severity
      blocking: true
      
    - name: parallel_run_progress
      description: Verify parallel runs on track
      blocking: false
      
    - name: trend_analysis
      description: Analyze reconciliation trend
      blocking: false
```

---

## 6.4 Approval Gates

### State Transition Approval Matrix

| Transition | Required Approvers | Minimum Count | Additional Conditions |
|------------|-------------------|---------------|----------------------|
| PROPOSED → PLANNED | tech_lead | 1 | All CI checks pass |
| PLANNED → EXECUTED | data_owner, security | 2 | Dry run successful |
| EXECUTED → PARALLEL_VALIDATED | qa_lead | 1 | First recon passes |
| PARALLEL_VALIDATED → CUTOVER_READY | business_owner | 1 | All parallel runs pass |
| CUTOVER_READY → CUTOVER_DONE | release_manager, data_owner | 2 | Maintenance window scheduled |

### Approval Record Format

```json
{
  "approval_id": "appr_abc123",
  "project_id": "proj_xyz789",
  "plan_id": "plan_def456",
  "transition": "PLANNED_to_EXECUTED",
  "approver": {
    "id": "user_jsmith",
    "name": "John Smith",
    "role": "data_owner",
    "email": "jsmith@company.com"
  },
  "approved_at": "2026-01-05T14:30:00Z",
  "scope": {
    "tables": ["public.orders", "public.customers"],
    "wave": "wave_1"
  },
  "sha256_reviewed": "abc123def456789...",
  "artifacts_reviewed": [
    "plans/signed_plan_v3.json",
    "contracts/schema_mapping.yml",
    "reconciliation/recon_summary.md"
  ],
  "comments": "Reviewed schema mappings and reconciliation plan. Approved for execution.",
  "conditions": [],
  "expiry": null
}
```

### Approval Validation

```python
def validate_approval_chain(
    current_state: str,
    target_state: str,
    approvals: list[dict],
    policy: dict
) -> tuple[bool, list[str]]:
    """
    Validate that all required approvals are present.
    
    Returns:
        (is_valid, blocking_issues)
    """
    transition = f"{current_state}_to_{target_state}"
    required = policy['approvals']['transitions'].get(transition, [])
    
    if not required:
        return True, []
    
    # Group approvals by role
    approval_roles = set()
    for appr in approvals:
        if appr['transition'] == transition:
            approval_roles.add(appr['approver']['role'])
    
    missing = set(required) - approval_roles
    
    if missing:
        return False, [f"Missing approval from: {role}" for role in missing]
    
    return True, []
```

---

## 6.5 PR Labels and Workflow

### Standard Labels

| Label | Description | Triggers |
|-------|-------------|----------|
| `migration/proposed` | Initial PR for review | Stage 1-4 CI |
| `migration/planned` | Tech lead approved | Stage 5 dry run |
| `migration/executing` | Execution in progress | Status updates |
| `migration/post-execution` | Execution complete | Stage 6 recon checks |
| `migration/validated` | Parallel runs complete | Cutover readiness |
| `migration/cutover-ready` | Ready for cutover | Cutover checklist |
| `needs-decision` | Manual decision required | Alerts |
| `blocked` | PR is blocked | Prevents merge |
| `security-review` | Security review required | Security team alert |

### Workflow State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                        PR LIFECYCLE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    CI Pass    ┌──────────┐   Tech Lead   ┌──────┐│
│  │ PROPOSED │──────────────▶│  READY   │──────────────▶│PLANNED││
│  └──────────┘               └──────────┘               └──────┘│
│       │                                                    │    │
│       │ CI Fail                                            │    │
│       ▼                                                    ▼    │
│  ┌──────────┐                                        ┌─────────┐│
│  │ BLOCKED  │◀───────────────────────────────────────│EXECUTING││
│  └──────────┘                                        └─────────┘│
│       │                                                    │    │
│       │ Fix & Re-run                                       │    │
│       └─────────────────────▶ PROPOSED                     ▼    │
│                                                     ┌──────────┐│
│                                                     │ EXECUTED ││
│                                                     └──────────┘│
│                                                          │      │
│                                                          ▼      │
│                                                   ┌────────────┐│
│                                                   │ VALIDATING ││
│                                                   └────────────┘│
│                                                          │      │
│                                                          ▼      │
│                                                   ┌────────────┐│
│                                                   │  CUTOVER   ││
│                                                   │   READY    ││
│                                                   └────────────┘│
│                                                          │      │
│                                                          ▼      │
│                                                   ┌────────────┐│
│                                                   │   MERGED   ││
│                                                   │  (DONE)    ││
│                                                   └────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## 6.6 Branch Naming Convention

```
migration/{archetype}/{project_id}/{version}

Examples:
  migration/postgres-to-s3/proj_abc123/v1
  migration/snowflake-to-redshift/proj_def456/v2
  migration/hdfs-to-s3/proj_ghi789/v1
```

---

## 6.7 Commit Message Format

```
[MIGRATION] {action}: {description}

Action types:
  - PROPOSE: Initial migration proposal
  - UPDATE: Update to existing proposal
  - APPROVE: Record approval
  - EXECUTE: Execution artifacts
  - RECON: Reconciliation results
  - CUTOVER: Cutover artifacts
  - EVIDENCE: Evidence pack update

Examples:
  [MIGRATION] PROPOSE: Initial postgres-to-s3 migration for orders table
  [MIGRATION] UPDATE: Resolve manual decision for timestamp mapping
  [MIGRATION] APPROVE: Tech lead approval for plan v3
  [MIGRATION] RECON: Add parallel run 7 results
  [MIGRATION] EVIDENCE: Complete evidence pack for audit
```

---

## 6.8 No Bypass Policy

### Enforced Restrictions

1. **Branch Protection Rules**
   ```yaml
   branch_protection:
     required_reviews: 2
     require_code_owner_reviews: true
     dismiss_stale_reviews: true
     require_status_checks: true
     required_status_checks:
       - structural-validation
       - policy-compliance
       - security-scan
       - dry-run
     include_administrators: true  # Even admins must follow rules
   ```

2. **No Force Push**
   ```yaml
   force_push: disabled
   delete_branch_on_merge: true
   ```

3. **Audit All Actions**
   ```yaml
   audit_requirements:
     log_all_commits: true
     log_all_reviews: true
     log_all_merges: true
     log_bypass_attempts: true
     alert_on_bypass_attempt: true
   ```

4. **No Direct Merge**
   - Merge button disabled until all approvals present
   - Squash merge only (clean history)
   - Merge commit must include approval references

