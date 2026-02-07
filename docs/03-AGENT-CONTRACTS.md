# 3. AGENT CONTRACTS — Explicit Boundaries

**Hard Rule**: Agents NEVER execute changes. EP only executes SignedPlans approved by deterministic validators.

---

## 3.1 Discovery Agent

### Identity
- **Agent Type**: `discovery`
- **Purpose**: Catalog source system objects, schemas, partitions, dependencies

### Can Do
- Read metadata from source system catalog tables
- Enumerate databases, schemas, tables, views
- Identify partitioning schemes and distribution keys
- Detect foreign key relationships and dependencies
- Estimate row counts from statistics
- Generate discovery_report.json

### Cannot Do
- Read actual data rows
- Execute any DML/DDL
- Modify source system in any way
- Access target system
- Make mapping decisions

### Inputs
| File | Required | Description |
|------|----------|-------------|
| `project.json` | Yes | Project definition with scope |
| `source_connection_config.json` | Yes | Connection parameters (secret_ref only) |
| `discovery_scope.json` | No | Optional filters for discovery |

### Outputs
| File | Always | Description |
|------|--------|-------------|
| `proposal.json` | Yes | Discovered objects catalog |
| `reasoning.json` | Yes | Methodology and limitations |
| `artifacts/discovery_report.json` | Yes | Full discovery results |
| `artifacts/dependency_graph.json` | Yes | Object dependencies |
| `artifacts/manifest.json` | Yes | SHA256 hashes of all artifacts |

### Guardrails
- [ ] PolicyService.check("discovery_scope_within_project_scope")
- [ ] Connection uses read-only credentials (enforced by secrets manager role)
- [ ] Timeout: max 4 hours
- [ ] No sampling of actual data permitted
- [ ] Must emit reasoning.json with confidence assessment

### Output Schema: `discovery_report.json`
```json
{
  "discovered_at": "2026-01-05T10:00:00Z",
  "source_system": "postgres",
  "databases": [
    {
      "name": "sales_db",
      "schemas": [
        {
          "name": "public",
          "tables": [
            {
              "name": "orders",
              "estimated_row_count": 15000000,
              "columns": [
                {"name": "order_id", "type": "bigint", "nullable": false, "primary_key": true},
                {"name": "customer_id", "type": "integer", "nullable": false},
                {"name": "order_date", "type": "timestamp with time zone", "nullable": false},
                {"name": "total", "type": "numeric(12,2)", "nullable": false}
              ],
              "partitioning": null,
              "dependencies": ["customers"]
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 3.2 Profiling Agent

### Identity
- **Agent Type**: `profiling`
- **Purpose**: Statistical profiling of data characteristics for validation planning

### Can Do
- Execute aggregate queries (COUNT, SUM, MIN, MAX, AVG, DISTINCT)
- Calculate null rates per column
- Sample data for cardinality estimation
- Detect data patterns (date formats, numeric ranges)
- Identify potential PII columns via pattern matching
- Generate profiling_report.json

### Cannot Do
- Extract full data sets
- Store raw data samples containing PII
- Modify any data
- Access target system
- Make mapping decisions

### Inputs
| File | Required | Description |
|------|----------|-------------|
| `discovery_report.json` | Yes | Objects to profile |
| `profiling_config.json` | No | Profiling parameters |
| `pii_patterns.json` | Yes | PII detection patterns from policy |

### Outputs
| File | Always | Description |
|------|--------|-------------|
| `proposal.json` | Yes | Profiling summary |
| `reasoning.json` | Yes | Methodology and limitations |
| `artifacts/profiling_report.json` | Yes | Full profiling results |
| `artifacts/pii_detection_report.json` | Yes | Detected PII columns |
| `artifacts/manifest.json` | Yes | SHA256 hashes of all artifacts |
| `manual_decisions_required.json` | If needed | PII handling decisions required |

### Guardrails
- [ ] PolicyService.check("profiling_sample_size_within_limits")
- [ ] PolicyService.check("pii_detection_executed")
- [ ] No raw data samples stored if PII detected
- [ ] Connection uses read-only credentials
- [ ] Timeout: max 8 hours per table

### Output Schema: `profiling_report.json`
```json
{
  "profiled_at": "2026-01-05T12:00:00Z",
  "tables": [
    {
      "table_name": "public.orders",
      "exact_row_count": 15234567,
      "profiled_row_count": 1523456,
      "sampling_method": "deterministic_modulo",
      "sampling_params": {"modulo": 10, "threshold": 1, "seed_column": "order_id"},
      "columns": [
        {
          "name": "order_id",
          "null_rate": 0.0,
          "distinct_count": 15234567,
          "min": 1,
          "max": 15234567,
          "pii_detected": false
        },
        {
          "name": "customer_id",
          "null_rate": 0.0,
          "distinct_count": 2345678,
          "min": 1,
          "max": 3000000,
          "pii_detected": false
        },
        {
          "name": "order_date",
          "null_rate": 0.0,
          "min": "2020-01-01T00:00:00Z",
          "max": "2026-01-01T00:00:00Z",
          "pii_detected": false
        },
        {
          "name": "total",
          "null_rate": 0.0,
          "min": 0.01,
          "max": 99999.99,
          "avg": 156.78,
          "sum": 2389456789.12,
          "precision_observed": 2,
          "scale_observed": 2,
          "pii_detected": false
        }
      ]
    }
  ]
}
```

---

## 3.3 Mapping Agent

### Identity
- **Agent Type**: `mapping`
- **Purpose**: Generate source-to-target schema mappings with type coercions

### Can Do
- Load archetype template for migration type
- Load type_coercion_rulebook.json
- Generate column-to-column mappings
- Identify lossy conversions and flag for decision
- Propose partition strategy for target
- Generate schema_mapping.yml

### Cannot Do
- Execute any data operations
- Override policy-defined type rules
- Auto-approve lossy conversions
- Access actual data

### Inputs
| File | Required | Description |
|------|----------|-------------|
| `discovery_report.json` | Yes | Source schema information |
| `profiling_report.json` | Yes | Data characteristics |
| `type_coercion_rulebook.json` | Yes | Type mapping rules |
| `archetype_template.json` | Yes | Target archetype specification |

### Outputs
| File | Always | Description |
|------|--------|-------------|
| `proposal.json` | Yes | Mapping summary |
| `reasoning.json` | Yes | Mapping rationale |
| `artifacts/schema_mapping.yml` | Yes | Full mapping specification |
| `artifacts/type_coercion_log.json` | Yes | All type conversions applied |
| `artifacts/manifest.json` | Yes | SHA256 hashes of all artifacts |
| `manual_decisions_required.json` | If needed | Lossy/ambiguous mappings requiring decision |

### Guardrails
- [ ] All mappings must reference rule_id from rulebook
- [ ] Lossy mappings must be flagged in manual_decisions_required.json
- [ ] PolicyService.check("all_columns_mapped_or_excluded")
- [ ] No invented type mappings (must exist in rulebook or flag for decision)

### Output Schema: `schema_mapping.yml`
```yaml
version: "1.0.0"
created_at: "2026-01-05T14:00:00Z"
source_system: postgres
target_system: s3
archetype: postgres_to_s3

tables:
  - source_table: public.orders
    target_path: s3://bucket/bronze/orders/
    target_format: parquet
    
    columns:
      - source_column: order_id
        target_column: order_id
        source_type: bigint
        target_type: INT64
        coercion_rule_id: "pg_bigint_to_parquet_int64"
        lossy: false
        
      - source_column: order_date
        target_column: order_date
        source_type: "timestamp with time zone"
        target_type: TIMESTAMP_MILLIS
        coercion_rule_id: "pg_timestamptz_to_parquet_timestamp"
        lossy: false
        timezone_handling: convert_to_utc
        
      - source_column: total
        target_column: total
        source_type: "numeric(12,2)"
        target_type: DECIMAL(12,2)
        coercion_rule_id: "pg_numeric_to_parquet_decimal"
        lossy: false
    
    partitioning:
      strategy: daily
      partition_column: order_date
      partition_format: "year=%Y/month=%m/day=%d"
```

---

## 3.4 Rewrite Agent

### Identity
- **Agent Type**: `rewrite`
- **Purpose**: Generate migration code/transforms based on approved mappings

### Can Do
- Generate dbt models from schema mappings
- Generate Spark jobs from schema mappings
- Generate SQL transform scripts
- Apply code templates from archetype
- Produce code as PR patches (diff format)

### Cannot Do
- Execute any generated code
- Commit directly to repository
- Modify existing production code
- Change mapping decisions

### Inputs
| File | Required | Description |
|------|----------|-------------|
| `schema_mapping.yml` | Yes | Approved schema mappings |
| `archetype_template.json` | Yes | Code generation templates |
| `migration_config.yml` | Yes | Migration-specific parameters |

### Outputs
| File | Always | Description |
|------|--------|-------------|
| `proposal.json` | Yes | Generated code summary |
| `reasoning.json` | Yes | Code generation rationale |
| `artifacts/generated_code/` | Yes | Directory of generated files |
| `artifacts/code_patches/` | Yes | Diff patches for PR |
| `artifacts/manifest.json` | Yes | SHA256 hashes of all artifacts |

### Guardrails
- [ ] Code must be syntactically valid (linted)
- [ ] No hardcoded credentials
- [ ] No production endpoints in generated code
- [ ] All code must be reviewed via PR
- [ ] Generated code must include idempotency handling

### Output Structure
```
artifacts/
├── generated_code/
│   ├── dbt/
│   │   └── models/
│   │       └── bronze/
│   │           └── orders.sql
│   ├── spark/
│   │   └── jobs/
│   │       └── extract_orders.py
│   └── sql/
│       └── validate_orders.sql
├── code_patches/
│   └── 001_add_orders_model.patch
└── manifest.json
```

---

## 3.5 Reconciliation Agent

### Identity
- **Agent Type**: `reconciliation`
- **Purpose**: Design and execute reconciliation strategy

### Can Do
- Select reconciliation strategy based on dataset class
- Configure hashing parameters
- Configure sampling parameters
- Execute row hash comparison
- Execute aggregate comparisons
- Execute key-diff where applicable
- Generate recon_report.json

### Cannot Do
- Modify source or target data
- Override tolerance thresholds from policy
- Auto-approve reconciliation failures
- Change SignedPlan parameters

### Inputs
| File | Required | Description |
|------|----------|-------------|
| `signed_plan.json` | Yes | Execution plan with recon_config |
| `policy.json` | Yes | Tolerance thresholds |
| `hashing_spec.json` | Yes | Row serialization specification |

### Outputs
| File | Always | Description |
|------|--------|-------------|
| `proposal.json` | Yes | Reconciliation summary |
| `reasoning.json` | Yes | Strategy selection rationale |
| `artifacts/recon_report.json` | Yes | Full reconciliation results |
| `artifacts/mismatches/` | If any | Sample of mismatched records (PII-safe) |
| `artifacts/manifest.json` | Yes | SHA256 hashes of all artifacts |

### Guardrails
- [ ] Hashing algorithm matches hashing_spec.json
- [ ] Sampling is deterministic and reproducible
- [ ] Tolerance thresholds from policy.json (not overridable)
- [ ] PII must be masked in mismatch samples
- [ ] PolicyService.check("recon_strategy_suitable_for_dataset_class")

### Output Schema: `recon_report.json`
```json
{
  "reconciled_at": "2026-01-05T20:00:00Z",
  "plan_id": "plan_abc123",
  "strategy": "row_hash_plus_aggregates_plus_keydiff",
  "tables": [
    {
      "table_name": "orders",
      "source_row_count": 15234567,
      "target_row_count": 15234567,
      "row_count_match": true,
      "row_count_delta_pct": 0.0,
      "hash_comparison": {
        "sample_size": 1523456,
        "sampling_method": "deterministic_modulo",
        "sampling_params": {"modulo": 10, "threshold": 1, "seed_column": "order_id"},
        "matches": 1523456,
        "mismatches": 0,
        "mismatch_pct": 0.0
      },
      "aggregate_comparison": {
        "total_sum_source": 2389456789.12,
        "total_sum_target": 2389456789.12,
        "total_sum_match": true,
        "null_count_comparisons": [
          {"column": "order_id", "source": 0, "target": 0, "match": true}
        ]
      },
      "key_diff": {
        "keys_only_in_source": 0,
        "keys_only_in_target": 0,
        "key_match": true
      },
      "severity": "none",
      "pass": true
    }
  ],
  "overall_severity": "none",
  "overall_pass": true,
  "tolerances_applied": {
    "row_count_critical_pct": 0.0,
    "row_count_major_pct": 0.01,
    "hash_mismatch_critical_pct": 0.0,
    "hash_mismatch_major_pct": 0.001
  }
}
```

---

## 3.6 Diff Explanation Agent

### Identity
- **Agent Type**: `diff_explanation`
- **Purpose**: Analyze reconciliation failures and provide explainable hypotheses

### Can Do
- Analyze recon_report.json for failure patterns
- Sample mismatched records (with PII masking)
- Generate hypotheses for root causes
- Cite evidence URIs for each hypothesis
- Propose fix patches if pattern is deterministic

### Cannot Do
- Modify source or target data
- Execute any fixes
- Override reconciliation results
- Access records beyond approved sample

### Inputs
| File | Required | Description |
|------|----------|-------------|
| `recon_report.json` | Yes | Reconciliation results |
| `schema_mapping.yml` | Yes | Applied mappings |
| `type_coercion_rulebook.json` | Yes | Type rules for reference |
| `execution_report.json` | Yes | Execution details |

### Outputs
| File | Always | Description |
|------|--------|-------------|
| `proposal.json` | Yes | Explanation summary |
| `reasoning.json` | Yes | Analysis methodology |
| `artifacts/diff_explanation.json` | Yes | Full analysis with hypotheses |
| `artifacts/proposed_fixes/` | If applicable | Proposed fix patches |
| `artifacts/manifest.json` | Yes | SHA256 hashes of all artifacts |

### Guardrails
- [ ] All hypotheses must cite evidence_uri
- [ ] Hypotheses must include likelihood assessment
- [ ] PII must be masked in all samples
- [ ] Proposed fixes must be validated syntactically
- [ ] Cannot claim certainty without deterministic proof

### Output Schema: `diff_explanation.json`
```json
{
  "analyzed_at": "2026-01-05T22:00:00Z",
  "recon_report_ref": "s3://artifacts/recon_report_abc123.json",
  "tables_analyzed": [
    {
      "table_name": "orders",
      "failure_type": "hash_mismatch",
      "mismatch_count": 15,
      "sample_analyzed": 15,
      "hypotheses": [
        {
          "hypothesis_id": "H1",
          "description": "Timezone conversion applied inconsistently to order_date column",
          "likelihood": "high",
          "evidence": [
            {
              "uri": "s3://artifacts/mismatches/orders_sample_001.json",
              "sha256": "abc123...",
              "observation": "Source timestamp 2025-12-31T23:00:00-05:00 became 2026-01-01T04:00:00Z in target (expected) but hash used local time"
            }
          ],
          "root_cause_category": "serialization_mismatch",
          "proposed_fix": {
            "type": "config_change",
            "description": "Update hashing_spec.json to normalize timestamps to UTC before hashing",
            "patch_file": "artifacts/proposed_fixes/fix_timestamp_hashing.patch"
          },
          "next_actions": [
            "Review hashing_spec.json timezone handling",
            "Re-run reconciliation with updated spec",
            "Verify 14 consecutive passing runs"
          ]
        },
        {
          "hypothesis_id": "H2",
          "description": "Numeric precision loss during Parquet encoding",
          "likelihood": "low",
          "evidence": [],
          "root_cause_category": "type_coercion",
          "proposed_fix": null,
          "next_actions": [
            "Sample additional records to confirm/deny"
          ]
        }
      ],
      "recommended_action": "Implement H1 fix and re-run reconciliation"
    }
  ]
}
```

---

## 3.7 Cutover Planning Agent

### Identity
- **Agent Type**: `cutover_planning`
- **Purpose**: Generate cutover and rollback plans

### Can Do
- Analyze parallel run results for cutover readiness
- Generate cutover plan with explicit steps
- Generate rollback plan with explicit steps
- Identify dependencies and sequencing
- Calculate maintenance window requirements
- Generate runbook documentation

### Cannot Do
- Execute cutover
- Execute rollback
- Modify production configurations
- Override approval requirements

### Inputs
| File | Required | Description |
|------|----------|-------------|
| `parallel_run_summary.json` | Yes | Results of N parallel runs |
| `signed_plan.json` | Yes | Migration plan |
| `dependency_graph.json` | Yes | Object dependencies |
| `policy.json` | Yes | Cutover requirements |

### Outputs
| File | Always | Description |
|------|--------|-------------|
| `proposal.json` | Yes | Cutover readiness assessment |
| `reasoning.json` | Yes | Readiness rationale |
| `artifacts/cutover_plan.json` | Yes | Step-by-step cutover plan |
| `artifacts/rollback_plan.json` | Yes | Step-by-step rollback plan |
| `artifacts/runbook.md` | Yes | Human-readable runbook |
| `artifacts/manifest.json` | Yes | SHA256 hashes of all artifacts |
| `manual_decisions_required.json` | If needed | Cutover timing decisions |

### Guardrails
- [ ] Rollback plan must be tested before cutover approval
- [ ] All dependencies must be satisfied
- [ ] PolicyService.check("parallel_runs_meet_threshold")
- [ ] Maintenance window must be scheduled
- [ ] Communication plan must be included

### Output Schema: `cutover_plan.json`
```json
{
  "created_at": "2026-01-06T10:00:00Z",
  "plan_id": "plan_abc123",
  "readiness_assessment": {
    "ready": true,
    "parallel_runs_completed": 14,
    "parallel_runs_required": 14,
    "all_runs_passed": true,
    "trending_stable": true
  },
  "maintenance_window": {
    "proposed_start": "2026-01-10T02:00:00Z",
    "proposed_end": "2026-01-10T06:00:00Z",
    "duration_hours": 4,
    "timezone": "UTC"
  },
  "pre_cutover_steps": [
    {
      "step": 1,
      "action": "Notify stakeholders",
      "owner": "release_manager",
      "estimated_duration_minutes": 0
    },
    {
      "step": 2,
      "action": "Verify rollback procedure documented and tested",
      "owner": "tech_lead",
      "estimated_duration_minutes": 30
    },
    {
      "step": 3,
      "action": "Take final source snapshot",
      "owner": "dba",
      "estimated_duration_minutes": 60
    }
  ],
  "cutover_steps": [
    {
      "step": 1,
      "action": "Stop writes to source",
      "owner": "dba",
      "estimated_duration_minutes": 5,
      "verification": "Confirm no active transactions"
    },
    {
      "step": 2,
      "action": "Execute final incremental sync",
      "owner": "data_engineer",
      "estimated_duration_minutes": 30,
      "verification": "Incremental job completes successfully"
    },
    {
      "step": 3,
      "action": "Run final reconciliation",
      "owner": "data_engineer",
      "estimated_duration_minutes": 60,
      "verification": "Recon report shows PASS"
    },
    {
      "step": 4,
      "action": "Switch application connection strings",
      "owner": "devops",
      "estimated_duration_minutes": 15,
      "verification": "Application connects to target"
    },
    {
      "step": 5,
      "action": "Validate application functionality",
      "owner": "qa_lead",
      "estimated_duration_minutes": 30,
      "verification": "Smoke tests pass"
    }
  ],
  "post_cutover_steps": [
    {
      "step": 1,
      "action": "Monitor for 24 hours",
      "owner": "ops",
      "estimated_duration_minutes": 1440
    },
    {
      "step": 2,
      "action": "Archive source system",
      "owner": "dba",
      "estimated_duration_minutes": 0,
      "delay_days": 30
    }
  ],
  "rollback_trigger_conditions": [
    "Reconciliation fails with CRITICAL severity",
    "Application smoke tests fail",
    "Data integrity issues reported within 24 hours"
  ]
}
```

