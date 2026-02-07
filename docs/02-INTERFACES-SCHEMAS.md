# 2. INTERFACES & SCHEMAS — Machine Contracts

All schemas are JSON Schema draft-07 compliant. Every schema includes versioning and audit fields.

---

## 2.1 SignedPlan Schema

**File**: `schemas/signed_plan.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://migration-copilot/schemas/signed_plan.schema.json",
  "title": "SignedPlan",
  "description": "Immutable, cryptographically signed migration execution plan",
  "type": "object",
  "required": [
    "plan_id",
    "version",
    "project_id",
    "archetype_id",
    "status",
    "created_at",
    "created_by",
    "policy_version",
    "rulebook_version",
    "source_config",
    "target_config",
    "steps",
    "recon_config",
    "tolerances",
    "approvals",
    "signature"
  ],
  "properties": {
    "plan_id": {
      "type": "string",
      "pattern": "^plan_[a-f0-9]{32}$",
      "description": "Unique plan identifier"
    },
    "version": {
      "type": "integer",
      "minimum": 1,
      "description": "Monotonically increasing version number"
    },
    "project_id": {
      "type": "string",
      "pattern": "^proj_[a-f0-9]{32}$"
    },
    "archetype_id": {
      "type": "string",
      "enum": ["postgres_to_s3", "hdfs_to_s3", "snowflake_to_redshift", "lake_to_delta_iceberg"]
    },
    "status": {
      "type": "string",
      "enum": ["DRAFTED", "VALIDATED", "APPROVED", "EXECUTING", "EXECUTED", "RECONCILED", "FAILED"]
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "created_by": {
      "type": "string",
      "description": "Service account or user ID that created this plan"
    },
    "policy_version": {
      "type": "string",
      "pattern": "^v[0-9]+\\.[0-9]+\\.[0-9]+$",
      "description": "Version of policy.json used for validation"
    },
    "rulebook_version": {
      "type": "string",
      "pattern": "^v[0-9]+\\.[0-9]+\\.[0-9]+$",
      "description": "Version of type_coercion_rulebook.json used"
    },
    "source_config": {
      "$ref": "#/definitions/connection_config"
    },
    "target_config": {
      "$ref": "#/definitions/connection_config"
    },
    "steps": {
      "type": "array",
      "minItems": 1,
      "items": {
        "$ref": "#/definitions/execution_step"
      }
    },
    "recon_config": {
      "$ref": "#/definitions/recon_config"
    },
    "tolerances": {
      "$ref": "#/definitions/tolerances"
    },
    "approvals": {
      "type": "array",
      "items": {
        "$ref": "#/definitions/approval"
      }
    },
    "signature": {
      "type": "object",
      "required": ["algorithm", "value", "signed_at", "signed_by"],
      "properties": {
        "algorithm": {
          "type": "string",
          "enum": ["RSA-SHA256", "ECDSA-P256-SHA256"]
        },
        "value": {
          "type": "string",
          "description": "Base64-encoded signature"
        },
        "signed_at": {
          "type": "string",
          "format": "date-time"
        },
        "signed_by": {
          "type": "string",
          "description": "Signing service identity"
        }
      }
    },
    "previous_plan_id": {
      "type": ["string", "null"],
      "description": "Link to previous version if this is a revision"
    },
    "metadata": {
      "type": "object",
      "additionalProperties": true
    }
  },
  "definitions": {
    "connection_config": {
      "type": "object",
      "required": ["type", "secret_ref", "scope"],
      "properties": {
        "type": {
          "type": "string",
          "enum": ["postgres", "hdfs", "hive", "snowflake", "redshift", "s3", "delta", "iceberg"]
        },
        "secret_ref": {
          "type": "string",
          "pattern": "^vault://.*$",
          "description": "Reference to secrets manager, never plaintext"
        },
        "scope": {
          "type": "object",
          "required": ["databases", "schemas", "tables"],
          "properties": {
            "databases": { "type": "array", "items": { "type": "string" } },
            "schemas": { "type": "array", "items": { "type": "string" } },
            "tables": { "type": "array", "items": { "type": "string" } },
            "exclude_patterns": { "type": "array", "items": { "type": "string" } }
          }
        }
      }
    },
    "execution_step": {
      "type": "object",
      "required": ["step_id", "step_type", "order", "params", "checkpoint_enabled"],
      "properties": {
        "step_id": {
          "type": "string",
          "pattern": "^step_[a-f0-9]{16}$"
        },
        "step_type": {
          "type": "string",
          "enum": ["extract", "transform", "load", "validate", "checkpoint"]
        },
        "order": {
          "type": "integer",
          "minimum": 1
        },
        "params": {
          "type": "object",
          "description": "Step-specific parameters"
        },
        "checkpoint_enabled": {
          "type": "boolean"
        },
        "retry_config": {
          "type": "object",
          "properties": {
            "max_retries": { "type": "integer", "default": 3 },
            "backoff_seconds": { "type": "integer", "default": 60 }
          }
        },
        "timeout_seconds": {
          "type": "integer",
          "default": 3600
        }
      }
    },
    "recon_config": {
      "type": "object",
      "required": ["strategy", "hashing", "sampling", "parallel_runs"],
      "properties": {
        "strategy": {
          "type": "string",
          "enum": ["row_hash_only", "row_hash_plus_aggregates", "row_hash_plus_aggregates_plus_keydiff"]
        },
        "hashing": {
          "type": "object",
          "required": ["algorithm", "serialization_spec_version"],
          "properties": {
            "algorithm": { "type": "string", "enum": ["xxhash64", "sha256"] },
            "serialization_spec_version": { "type": "string" }
          }
        },
        "sampling": {
          "type": "object",
          "required": ["method", "params"],
          "properties": {
            "method": { "type": "string", "enum": ["deterministic_modulo", "stratified"] },
            "params": {
              "type": "object",
              "properties": {
                "modulo_divisor": { "type": "integer" },
                "modulo_threshold": { "type": "integer" },
                "seed_column": { "type": "string" }
              }
            }
          }
        },
        "parallel_runs": {
          "type": "object",
          "required": ["required_count", "interval_hours"],
          "properties": {
            "required_count": { "type": "integer", "default": 14 },
            "interval_hours": { "type": "integer", "default": 24 }
          }
        }
      }
    },
    "tolerances": {
      "type": "object",
      "required": ["row_count", "hash_mismatch", "null_rate_delta", "numeric_precision"],
      "properties": {
        "row_count": {
          "type": "object",
          "required": ["critical_threshold_pct", "major_threshold_pct"],
          "properties": {
            "critical_threshold_pct": { "type": "number", "default": 0.0 },
            "major_threshold_pct": { "type": "number", "default": 0.01 }
          }
        },
        "hash_mismatch": {
          "type": "object",
          "required": ["critical_threshold_pct", "major_threshold_pct"],
          "properties": {
            "critical_threshold_pct": { "type": "number", "default": 0.0 },
            "major_threshold_pct": { "type": "number", "default": 0.001 }
          }
        },
        "null_rate_delta": {
          "type": "object",
          "properties": {
            "major_threshold_pct": { "type": "number", "default": 0.1 }
          }
        },
        "numeric_precision": {
          "type": "object",
          "properties": {
            "allowed_scale_loss": { "type": "integer", "default": 0 }
          }
        }
      }
    },
    "approval": {
      "type": "object",
      "required": ["approver_id", "role", "approved_at", "scope", "sha256_reviewed"],
      "properties": {
        "approver_id": { "type": "string" },
        "role": { "type": "string", "enum": ["tech_lead", "data_owner", "security", "qa_lead", "business_owner", "release_manager"] },
        "approved_at": { "type": "string", "format": "date-time" },
        "scope": { "type": "string", "enum": ["plan", "execution", "reconciliation", "cutover"] },
        "sha256_reviewed": { "type": "string", "pattern": "^[a-f0-9]{64}$" }
      }
    }
  }
}
```

---

## 2.2 Policy Schema

**File**: `schemas/policy.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://migration-copilot/schemas/policy.schema.json",
  "title": "Policy",
  "description": "Policy rulebook for migration governance",
  "type": "object",
  "required": [
    "version",
    "created_at",
    "created_by",
    "tolerances",
    "sampling",
    "approvals",
    "encryption",
    "pii_handling",
    "retention"
  ],
  "properties": {
    "version": {
      "type": "string",
      "pattern": "^v[0-9]+\\.[0-9]+\\.[0-9]+$"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "created_by": {
      "type": "string"
    },
    "tolerances": {
      "type": "object",
      "required": ["dataset_classes"],
      "properties": {
        "dataset_classes": {
          "type": "object",
          "patternProperties": {
            "^(A|B|C|D)$": {
              "$ref": "#/definitions/tolerance_class"
            }
          }
        }
      }
    },
    "sampling": {
      "type": "object",
      "required": ["min_sample_size", "max_sample_size", "default_method"],
      "properties": {
        "min_sample_size": { "type": "integer", "default": 10000 },
        "max_sample_size": { "type": "integer", "default": 10000000 },
        "default_method": { "type": "string", "enum": ["deterministic_modulo", "stratified"] }
      }
    },
    "approvals": {
      "type": "object",
      "required": ["transitions"],
      "properties": {
        "transitions": {
          "type": "object",
          "properties": {
            "PROPOSED_to_PLANNED": {
              "type": "array",
              "items": { "type": "string" }
            },
            "PLANNED_to_EXECUTED": {
              "type": "array",
              "items": { "type": "string" }
            },
            "EXECUTED_to_PARALLEL_VALIDATED": {
              "type": "array",
              "items": { "type": "string" }
            },
            "PARALLEL_VALIDATED_to_CUTOVER_READY": {
              "type": "array",
              "items": { "type": "string" }
            },
            "CUTOVER_READY_to_CUTOVER_DONE": {
              "type": "array",
              "items": { "type": "string" }
            }
          }
        }
      }
    },
    "encryption": {
      "type": "object",
      "required": ["at_rest", "in_transit", "key_management"],
      "properties": {
        "at_rest": { "type": "string", "enum": ["AES-256", "AES-128"] },
        "in_transit": { "type": "string", "enum": ["TLS-1.3", "TLS-1.2"] },
        "key_management": { "type": "string", "enum": ["customer_managed", "platform_managed"] }
      }
    },
    "pii_handling": {
      "type": "object",
      "required": ["detection_required", "masking_required", "audit_required"],
      "properties": {
        "detection_required": { "type": "boolean", "default": true },
        "masking_required": { "type": "boolean", "default": true },
        "audit_required": { "type": "boolean", "default": true },
        "pii_column_patterns": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "retention": {
      "type": "object",
      "required": ["evidence_days", "audit_log_days"],
      "properties": {
        "evidence_days": { "type": "integer", "default": 2555 },
        "audit_log_days": { "type": "integer", "default": 2555 }
      }
    }
  },
  "definitions": {
    "tolerance_class": {
      "type": "object",
      "required": ["description", "row_count_tolerance", "hash_mismatch_tolerance", "parallel_run_days"],
      "properties": {
        "description": { "type": "string" },
        "row_count_tolerance": {
          "type": "object",
          "properties": {
            "critical_pct": { "type": "number" },
            "major_pct": { "type": "number" }
          }
        },
        "hash_mismatch_tolerance": {
          "type": "object",
          "properties": {
            "critical_pct": { "type": "number" },
            "major_pct": { "type": "number" }
          }
        },
        "parallel_run_days": { "type": "integer" },
        "requires_full_recon": { "type": "boolean" }
      }
    }
  }
}
```

---

## 2.3 AgentOutput Schema

**File**: `schemas/agent_output.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://migration-copilot/schemas/agent_output.schema.json",
  "title": "AgentOutput",
  "description": "Standard output format for all agents",
  "type": "object",
  "required": [
    "agent_id",
    "agent_type",
    "run_id",
    "project_id",
    "version",
    "created_at",
    "created_by",
    "policy_version",
    "rulebook_version",
    "proposal",
    "reasoning",
    "artifacts_manifest"
  ],
  "properties": {
    "agent_id": {
      "type": "string",
      "pattern": "^agent_[a-z_]+_[a-f0-9]{16}$"
    },
    "agent_type": {
      "type": "string",
      "enum": ["discovery", "profiling", "mapping", "rewrite", "reconciliation", "diff_explanation", "cutover_planning"]
    },
    "run_id": {
      "type": "string",
      "pattern": "^run_[a-f0-9]{32}$"
    },
    "project_id": {
      "type": "string"
    },
    "version": {
      "type": "string",
      "pattern": "^v[0-9]+\\.[0-9]+\\.[0-9]+$"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "created_by": {
      "type": "string"
    },
    "policy_version": {
      "type": "string"
    },
    "rulebook_version": {
      "type": "string"
    },
    "proposal": {
      "type": "object",
      "description": "Agent-specific proposal content",
      "additionalProperties": true
    },
    "reasoning": {
      "$ref": "#/definitions/reasoning"
    },
    "artifacts_manifest": {
      "$ref": "#/definitions/artifacts_manifest"
    },
    "manual_decisions_required": {
      "type": ["array", "null"],
      "items": {
        "$ref": "#/definitions/manual_decision"
      }
    },
    "warnings": {
      "type": "array",
      "items": { "type": "string" }
    },
    "errors": {
      "type": "array",
      "items": { "type": "string" }
    }
  },
  "definitions": {
    "reasoning": {
      "type": "object",
      "required": ["methodology", "evidence_refs", "confidence", "limitations"],
      "properties": {
        "methodology": {
          "type": "string",
          "description": "Description of the approach taken"
        },
        "evidence_refs": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "uri": { "type": "string" },
              "sha256": { "type": "string" },
              "description": { "type": "string" }
            }
          }
        },
        "confidence": {
          "type": "string",
          "enum": ["high", "medium", "low"]
        },
        "limitations": {
          "type": "array",
          "items": { "type": "string" }
        },
        "assumptions": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "artifacts_manifest": {
      "type": "object",
      "required": ["files"],
      "properties": {
        "files": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["path", "sha256", "size_bytes", "created_at"],
            "properties": {
              "path": { "type": "string" },
              "sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" },
              "size_bytes": { "type": "integer" },
              "created_at": { "type": "string", "format": "date-time" }
            }
          }
        }
      }
    },
    "manual_decision": {
      "type": "object",
      "required": ["decision_id", "category", "description", "options", "deadline_hours"],
      "properties": {
        "decision_id": { "type": "string" },
        "category": { "type": "string", "enum": ["type_mapping", "data_loss", "pii_handling", "partition_strategy", "performance"] },
        "description": { "type": "string" },
        "source_context": { "type": "object" },
        "options": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "option_id": { "type": "string" },
              "description": { "type": "string" },
              "risk_level": { "type": "string" },
              "recommended": { "type": "boolean" }
            }
          }
        },
        "deadline_hours": { "type": "integer" }
      }
    }
  }
}
```

---

## 2.4 EvidencePack Manifest Schema

**File**: `schemas/evidence_pack.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://migration-copilot/schemas/evidence_pack.schema.json",
  "title": "EvidencePack",
  "description": "Immutable evidence bundle for audit and compliance",
  "type": "object",
  "required": [
    "pack_id",
    "version",
    "project_id",
    "plan_id",
    "created_at",
    "created_by",
    "policy_version",
    "rulebook_version",
    "sha256_manifest",
    "audit_chain",
    "contents"
  ],
  "properties": {
    "pack_id": {
      "type": "string",
      "pattern": "^evpack_[a-f0-9]{32}$"
    },
    "version": {
      "type": "integer",
      "minimum": 1
    },
    "project_id": {
      "type": "string"
    },
    "plan_id": {
      "type": "string"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "created_by": {
      "type": "string"
    },
    "policy_version": {
      "type": "string"
    },
    "rulebook_version": {
      "type": "string"
    },
    "sha256_manifest": {
      "type": "object",
      "description": "Map of relative path to sha256 hash",
      "additionalProperties": {
        "type": "string",
        "pattern": "^[a-f0-9]{64}$"
      }
    },
    "audit_chain": {
      "$ref": "#/definitions/audit_chain"
    },
    "contents": {
      "$ref": "#/definitions/contents"
    },
    "integrity_signature": {
      "type": "object",
      "required": ["algorithm", "value", "signed_at"],
      "properties": {
        "algorithm": { "type": "string" },
        "value": { "type": "string" },
        "signed_at": { "type": "string", "format": "date-time" }
      }
    }
  },
  "definitions": {
    "audit_chain": {
      "type": "object",
      "required": ["entries"],
      "properties": {
        "entries": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["sequence", "timestamp", "action", "actor", "artifact_ref", "previous_hash", "current_hash"],
            "properties": {
              "sequence": { "type": "integer" },
              "timestamp": { "type": "string", "format": "date-time" },
              "action": { "type": "string" },
              "actor": { "type": "string" },
              "artifact_ref": { "type": "string" },
              "previous_hash": { "type": ["string", "null"] },
              "current_hash": { "type": "string" }
            }
          }
        }
      }
    },
    "contents": {
      "type": "object",
      "required": ["scope", "schemas", "profiling", "execution", "reconciliation", "approvals"],
      "properties": {
        "scope": {
          "type": "object",
          "properties": {
            "source_scope_definition": { "type": "string" },
            "target_scope_definition": { "type": "string" },
            "exclusions": { "type": "string" }
          }
        },
        "schemas": {
          "type": "object",
          "properties": {
            "source_schema_snapshot": { "type": "string" },
            "target_schema_snapshot": { "type": "string" },
            "schema_mapping": { "type": "string" }
          }
        },
        "profiling": {
          "type": "object",
          "properties": {
            "source_profiling_report": { "type": "string" },
            "target_profiling_report": { "type": "string" }
          }
        },
        "execution": {
          "type": "object",
          "properties": {
            "signed_plan": { "type": "string" },
            "execution_logs": { "type": "array", "items": { "type": "string" } },
            "checkpoints": { "type": "array", "items": { "type": "string" } }
          }
        },
        "reconciliation": {
          "type": "object",
          "properties": {
            "recon_reports": { "type": "array", "items": { "type": "string" } },
            "parallel_run_summary": { "type": "string" },
            "diff_explanations": { "type": "array", "items": { "type": "string" } }
          }
        },
        "approvals": {
          "type": "object",
          "properties": {
            "approval_records": { "type": "array", "items": { "type": "string" } },
            "signoff_records": { "type": "array", "items": { "type": "string" } }
          }
        },
        "cutover": {
          "type": "object",
          "properties": {
            "cutover_plan": { "type": "string" },
            "rollback_plan": { "type": "string" },
            "cutover_execution_log": { "type": "string" }
          }
        }
      }
    }
  }
}
```

---

## 2.5 StateMachine Transitions

**File**: `schemas/state_machine.json`

```json
{
  "version": "v1.0.0",
  "states": [
    "CREATED",
    "DISCOVERED",
    "PROFILED",
    "PLAN_DRAFTED",
    "PROPOSED",
    "PLANNED",
    "EXECUTING",
    "EXECUTED",
    "RECONCILED",
    "PARALLEL_VALIDATED",
    "CUTOVER_READY",
    "CUTOVER_DONE",
    "FAILED",
    "CANCELLED"
  ],
  "transitions": {
    "CREATED": {
      "next": ["DISCOVERED", "CANCELLED"],
      "required_approvals": [],
      "required_artifacts": ["project.json"]
    },
    "DISCOVERED": {
      "next": ["PROFILED", "FAILED"],
      "required_approvals": [],
      "required_artifacts": ["discovery_report.json"]
    },
    "PROFILED": {
      "next": ["PLAN_DRAFTED", "FAILED"],
      "required_approvals": [],
      "required_artifacts": ["profiling_report.json"]
    },
    "PLAN_DRAFTED": {
      "next": ["PROPOSED", "FAILED"],
      "required_approvals": [],
      "required_artifacts": ["migration_plan_draft.json", "schema_mapping.yml"]
    },
    "PROPOSED": {
      "next": ["PLANNED", "CANCELLED"],
      "required_approvals": ["tech_lead"],
      "required_artifacts": ["signed_plan.json"],
      "blocker_conditions": [
        "manual_decisions_unresolved",
        "policy_violations_present",
        "profiling_incomplete"
      ]
    },
    "PLANNED": {
      "next": ["EXECUTING", "CANCELLED"],
      "required_approvals": ["data_owner", "security"],
      "required_artifacts": ["signed_plan.json"],
      "blocker_conditions": [
        "pii_not_addressed",
        "encryption_requirements_unmet"
      ]
    },
    "EXECUTING": {
      "next": ["EXECUTED", "FAILED"],
      "required_approvals": [],
      "required_artifacts": []
    },
    "EXECUTED": {
      "next": ["RECONCILED", "FAILED"],
      "required_approvals": [],
      "required_artifacts": ["execution_report.json"]
    },
    "RECONCILED": {
      "next": ["PARALLEL_VALIDATED", "FAILED"],
      "required_approvals": ["qa_lead"],
      "required_artifacts": ["recon_report.json"],
      "blocker_conditions": [
        "critical_severity_present",
        "major_severity_unacknowledged"
      ]
    },
    "PARALLEL_VALIDATED": {
      "next": ["CUTOVER_READY", "FAILED"],
      "required_approvals": ["business_owner"],
      "required_artifacts": ["parallel_run_summary.json"],
      "blocker_conditions": [
        "parallel_runs_incomplete",
        "trending_failures"
      ]
    },
    "CUTOVER_READY": {
      "next": ["CUTOVER_DONE", "CANCELLED"],
      "required_approvals": ["release_manager", "data_owner"],
      "required_artifacts": ["cutover_plan.json", "rollback_plan.json"],
      "blocker_conditions": [
        "rollback_not_tested",
        "maintenance_window_not_scheduled"
      ]
    },
    "CUTOVER_DONE": {
      "next": [],
      "required_approvals": [],
      "required_artifacts": ["evidence_pack/metadata.json"],
      "terminal": true
    },
    "FAILED": {
      "next": ["PLAN_DRAFTED", "CANCELLED"],
      "required_approvals": ["tech_lead"],
      "required_artifacts": ["failure_analysis.json"],
      "terminal": false
    },
    "CANCELLED": {
      "next": [],
      "required_approvals": [],
      "required_artifacts": ["cancellation_reason.json"],
      "terminal": true
    }
  },
  "approval_roles": {
    "tech_lead": {
      "description": "Technical lead responsible for migration approach",
      "can_approve": ["PROPOSED_to_PLANNED", "FAILED_recovery"]
    },
    "data_owner": {
      "description": "Owner of the data being migrated",
      "can_approve": ["PLANNED_to_EXECUTING", "CUTOVER_READY_to_CUTOVER_DONE"]
    },
    "security": {
      "description": "Security team representative",
      "can_approve": ["PLANNED_to_EXECUTING"]
    },
    "qa_lead": {
      "description": "QA lead for reconciliation approval",
      "can_approve": ["RECONCILED_to_PARALLEL_VALIDATED"]
    },
    "business_owner": {
      "description": "Business stakeholder",
      "can_approve": ["PARALLEL_VALIDATED_to_CUTOVER_READY"]
    },
    "release_manager": {
      "description": "Release management",
      "can_approve": ["CUTOVER_READY_to_CUTOVER_DONE"]
    }
  }
}
```

---

## 2.6 Type Coercion Rulebook Schema

**File**: `schemas/type_coercion_rulebook.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://migration-copilot/schemas/type_coercion_rulebook.schema.json",
  "title": "TypeCoercionRulebook",
  "type": "object",
  "required": ["version", "created_at", "rules"],
  "properties": {
    "version": { "type": "string" },
    "created_at": { "type": "string", "format": "date-time" },
    "rules": {
      "type": "array",
      "items": {
        "$ref": "#/definitions/coercion_rule"
      }
    }
  },
  "definitions": {
    "coercion_rule": {
      "type": "object",
      "required": ["source_system", "target_system", "source_type", "target_type", "lossy", "precision_change"],
      "properties": {
        "rule_id": { "type": "string" },
        "source_system": { "type": "string" },
        "target_system": { "type": "string" },
        "source_type": { "type": "string" },
        "target_type": { "type": "string" },
        "lossy": { "type": "boolean" },
        "precision_change": {
          "type": "string",
          "enum": ["none", "widening", "narrowing", "truncation"]
        },
        "null_semantics_change": { "type": "boolean", "default": false },
        "timezone_handling": {
          "type": "string",
          "enum": ["preserve", "convert_to_utc", "strip", "requires_decision"]
        },
        "requires_approval": { "type": "boolean", "default": false },
        "notes": { "type": "string" }
      }
    }
  }
}
```

