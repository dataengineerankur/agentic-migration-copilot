# 7. EVIDENCE PACK — Immutable Audit Bundle

Every migration run MUST produce an evidence pack. The pack is immutable and versioned.

---

## 7.1 Evidence Pack Structure

```
evidence_pack/
├── metadata.json                    # Pack metadata and manifest
├── scope/
│   ├── source_scope_definition.json # What was included in migration
│   ├── target_scope_definition.json # Target configuration
│   ├── exclusions.json              # What was excluded and why
│   └── dataset_classification.json  # Classification decisions
│
├── schemas/
│   ├── source_schema_snapshot.json  # Source schema at migration time
│   ├── target_schema_snapshot.json  # Target schema after migration
│   ├── schema_mapping.yml           # Final approved mapping
│   └── type_coercion_log.json       # All type conversions applied
│
├── profiling/
│   ├── source_profiling_report.json # Source data profiling
│   ├── target_profiling_report.json # Target data profiling
│   ├── pii_detection_report.json    # PII detection results
│   └── data_quality_baseline.json   # Quality metrics baseline
│
├── execution/
│   ├── signed_plan_v{N}.json        # Final signed plan
│   ├── execution_log.json           # Execution timeline
│   ├── checkpoints/                 # Checkpoint files
│   │   ├── checkpoint_001.json
│   │   └── ...
│   └── error_recovery_log.json      # Any errors and recovery actions
│
├── reconciliation/
│   ├── recon_plan.json              # Reconciliation configuration
│   ├── parallel_runs/               # All parallel run results
│   │   ├── run_001.json
│   │   ├── run_002.json
│   │   └── ...
│   ├── parallel_run_summary.json    # Summary across all runs
│   ├── diff_explanations/           # Explanations for any diffs
│   │   └── explanation_001.json
│   └── final_recon_report.json      # Final reconciliation report
│
├── approvals/
│   ├── approval_chain.json          # All approvals in sequence
│   ├── approval_001.json            # Individual approval records
│   ├── approval_002.json
│   └── ...
│
├── cutover/
│   ├── cutover_plan.json            # Cutover execution plan
│   ├── rollback_plan.json           # Rollback procedure
│   ├── cutover_execution_log.json   # Cutover execution record
│   └── post_cutover_validation.json # Post-cutover checks
│
├── signoff/
│   ├── final_signoff.json           # Final signoff record
│   ├── stakeholder_acknowledgments/ # Stakeholder signoffs
│   │   ├── data_owner.json
│   │   ├── security.json
│   │   └── business_owner.json
│   └── compliance_attestation.json  # Compliance attestation
│
└── integrity/
    ├── sha256_manifest.json         # SHA256 of every file
    ├── audit_chain.json             # Hash-chained audit log
    └── pack_signature.json          # Cryptographic signature of pack
```

---

## 7.2 Metadata File Specification

`metadata.json`:

```json
{
  "$schema": "https://migration-copilot/schemas/evidence_pack_metadata.schema.json",
  "pack_id": "evpack_abc123def456789",
  "pack_version": 1,
  "created_at": "2026-01-05T23:00:00Z",
  "created_by": "migration-copilot-service",
  "project_id": "proj_xyz789",
  "plan_id": "plan_def456",
  "plan_version": 3,
  "archetype_id": "postgres_to_s3",
  "policy_version": "v2.1.0",
  "rulebook_version": "v1.5.0",
  "source_system": {
    "type": "postgres",
    "identifier": "prod-postgres-east",
    "version": "14.5"
  },
  "target_system": {
    "type": "s3",
    "identifier": "data-lake-bronze",
    "region": "us-east-1"
  },
  "migration_scope": {
    "databases": ["sales_db"],
    "schemas": ["public"],
    "tables": ["orders", "customers", "products"],
    "total_rows_migrated": 45678901,
    "total_bytes_migrated": 12345678901
  },
  "timeline": {
    "project_created": "2025-12-15T10:00:00Z",
    "profiling_completed": "2025-12-16T14:00:00Z",
    "plan_approved": "2025-12-17T09:00:00Z",
    "execution_started": "2025-12-18T02:00:00Z",
    "execution_completed": "2025-12-18T06:00:00Z",
    "parallel_validation_started": "2025-12-18T08:00:00Z",
    "parallel_validation_completed": "2026-01-01T08:00:00Z",
    "cutover_executed": "2026-01-05T02:00:00Z",
    "evidence_pack_created": "2026-01-05T23:00:00Z"
  },
  "final_status": "SUCCESS",
  "approvals_collected": 6,
  "parallel_runs_completed": 14,
  "reconciliation_status": "PASS",
  "retention": {
    "policy": "7_years",
    "expires_at": "2033-01-05T23:00:00Z",
    "compliance_tags": ["SOX", "GDPR"]
  },
  "storage": {
    "location": "s3://migration-evidence/packs/evpack_abc123def456789/",
    "total_files": 47,
    "total_size_bytes": 2345678
  }
}
```

---

## 7.3 SHA256 Manifest

`integrity/sha256_manifest.json`:

```json
{
  "manifest_version": "v1.0.0",
  "created_at": "2026-01-05T23:00:00Z",
  "algorithm": "sha256",
  "files": {
    "metadata.json": "a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890",
    "scope/source_scope_definition.json": "b2c3d4e5f67890123456789012345678901234567890123456789012345678901",
    "scope/target_scope_definition.json": "c3d4e5f678901234567890123456789012345678901234567890123456789012",
    "scope/exclusions.json": "d4e5f6789012345678901234567890123456789012345678901234567890123",
    "scope/dataset_classification.json": "e5f67890123456789012345678901234567890123456789012345678901234",
    "schemas/source_schema_snapshot.json": "f678901234567890123456789012345678901234567890123456789012345",
    "schemas/target_schema_snapshot.json": "7890123456789012345678901234567890123456789012345678901234567",
    "schemas/schema_mapping.yml": "8901234567890123456789012345678901234567890123456789012345678",
    "schemas/type_coercion_log.json": "9012345678901234567890123456789012345678901234567890123456789"
  },
  "total_files": 47,
  "manifest_sha256": "0123456789012345678901234567890123456789012345678901234567890123"
}
```

### Manifest Generation

```python
import hashlib
import json
from pathlib import Path

def generate_sha256_manifest(pack_dir: Path) -> dict:
    """Generate SHA256 manifest for all files in evidence pack."""
    
    manifest = {
        "manifest_version": "v1.0.0",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "algorithm": "sha256",
        "files": {}
    }
    
    for file_path in pack_dir.rglob("*"):
        if file_path.is_file() and file_path.name != "sha256_manifest.json":
            relative_path = str(file_path.relative_to(pack_dir))
            
            with open(file_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            
            manifest["files"][relative_path] = file_hash
    
    manifest["total_files"] = len(manifest["files"])
    
    # Hash the manifest itself (excluding this field)
    manifest_json = json.dumps(manifest, sort_keys=True)
    manifest["manifest_sha256"] = hashlib.sha256(manifest_json.encode()).hexdigest()
    
    return manifest


def verify_sha256_manifest(pack_dir: Path, manifest: dict) -> tuple[bool, list[str]]:
    """Verify all files match their recorded hashes."""
    
    errors = []
    
    for relative_path, expected_hash in manifest["files"].items():
        file_path = pack_dir / relative_path
        
        if not file_path.exists():
            errors.append(f"Missing file: {relative_path}")
            continue
        
        with open(file_path, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()
        
        if actual_hash != expected_hash:
            errors.append(f"Hash mismatch: {relative_path}")
    
    return len(errors) == 0, errors
```

---

## 7.4 Audit Chain

`integrity/audit_chain.json`:

```json
{
  "chain_version": "v1.0.0",
  "pack_id": "evpack_abc123def456789",
  "entries": [
    {
      "sequence": 1,
      "timestamp": "2025-12-15T10:00:00Z",
      "action": "PROJECT_CREATED",
      "actor": "user_jsmith",
      "actor_type": "human",
      "artifact_ref": "scope/source_scope_definition.json",
      "artifact_sha256": "abc123...",
      "previous_hash": null,
      "current_hash": "def456..."
    },
    {
      "sequence": 2,
      "timestamp": "2025-12-16T14:00:00Z",
      "action": "PROFILING_COMPLETED",
      "actor": "profiling_agent",
      "actor_type": "agent",
      "artifact_ref": "profiling/source_profiling_report.json",
      "artifact_sha256": "ghi789...",
      "previous_hash": "def456...",
      "current_hash": "jkl012..."
    },
    {
      "sequence": 3,
      "timestamp": "2025-12-17T09:00:00Z",
      "action": "PLAN_APPROVED",
      "actor": "user_mjones",
      "actor_type": "human",
      "role": "tech_lead",
      "artifact_ref": "approvals/approval_001.json",
      "artifact_sha256": "mno345...",
      "previous_hash": "jkl012...",
      "current_hash": "pqr678..."
    },
    {
      "sequence": 4,
      "timestamp": "2025-12-17T10:00:00Z",
      "action": "PLAN_APPROVED",
      "actor": "user_klee",
      "actor_type": "human",
      "role": "data_owner",
      "artifact_ref": "approvals/approval_002.json",
      "artifact_sha256": "stu901...",
      "previous_hash": "pqr678...",
      "current_hash": "vwx234..."
    },
    {
      "sequence": 5,
      "timestamp": "2025-12-18T06:00:00Z",
      "action": "EXECUTION_COMPLETED",
      "actor": "job_runner",
      "actor_type": "service",
      "artifact_ref": "execution/execution_log.json",
      "artifact_sha256": "yza567...",
      "previous_hash": "vwx234...",
      "current_hash": "bcd890..."
    },
    {
      "sequence": 6,
      "timestamp": "2026-01-01T08:00:00Z",
      "action": "PARALLEL_VALIDATION_COMPLETED",
      "actor": "reconciliation_runner",
      "actor_type": "service",
      "artifact_ref": "reconciliation/parallel_run_summary.json",
      "artifact_sha256": "efg123...",
      "previous_hash": "bcd890...",
      "current_hash": "hij456..."
    },
    {
      "sequence": 7,
      "timestamp": "2026-01-05T02:30:00Z",
      "action": "CUTOVER_COMPLETED",
      "actor": "user_jsmith",
      "actor_type": "human",
      "artifact_ref": "cutover/cutover_execution_log.json",
      "artifact_sha256": "klm789...",
      "previous_hash": "hij456...",
      "current_hash": "nop012..."
    },
    {
      "sequence": 8,
      "timestamp": "2026-01-05T23:00:00Z",
      "action": "EVIDENCE_PACK_SEALED",
      "actor": "artifact_service",
      "actor_type": "service",
      "artifact_ref": "integrity/sha256_manifest.json",
      "artifact_sha256": "qrs345...",
      "previous_hash": "nop012...",
      "current_hash": "tuv678..."
    }
  ],
  "chain_head_hash": "tuv678...",
  "chain_integrity_verified": true
}
```

### Audit Chain Verification

```python
import hashlib
import json

def verify_audit_chain(chain: dict) -> tuple[bool, list[str]]:
    """Verify the integrity of the audit chain."""
    
    errors = []
    entries = chain["entries"]
    
    for i, entry in enumerate(entries):
        # Verify sequence
        if entry["sequence"] != i + 1:
            errors.append(f"Sequence mismatch at entry {i}")
        
        # Verify chain linkage
        if i == 0:
            if entry["previous_hash"] is not None:
                errors.append("First entry should have null previous_hash")
        else:
            if entry["previous_hash"] != entries[i-1]["current_hash"]:
                errors.append(f"Chain broken at entry {i}")
        
        # Verify current_hash
        entry_data = {k: v for k, v in entry.items() if k != "current_hash"}
        computed_hash = hashlib.sha256(
            json.dumps(entry_data, sort_keys=True).encode()
        ).hexdigest()[:12] + "..."  # Truncated for example
        
        # In production, compare full hashes
    
    # Verify chain head
    if entries and entries[-1]["current_hash"] != chain["chain_head_hash"]:
        errors.append("Chain head hash mismatch")
    
    return len(errors) == 0, errors
```

---

## 7.5 Pack Signature

`integrity/pack_signature.json`:

```json
{
  "signature_version": "v1.0.0",
  "pack_id": "evpack_abc123def456789",
  "signed_at": "2026-01-05T23:00:01Z",
  "signed_by": {
    "service": "artifact_service",
    "key_id": "key_migration_signing_2026",
    "key_type": "RSA-4096"
  },
  "payload_hash": "sha256:0123456789012345678901234567890123456789012345678901234567890123",
  "payload_description": "SHA256 of sha256_manifest.json",
  "algorithm": "RSA-SHA256",
  "signature": "Base64EncodedSignatureHere...",
  "certificate_chain": [
    "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----",
    "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"
  ],
  "verification_instructions": {
    "1": "Verify certificate chain against trusted root",
    "2": "Extract public key from signing certificate",
    "3": "Verify signature against payload_hash",
    "4": "Verify payload_hash matches sha256_manifest.json hash"
  }
}
```

---

## 7.6 Required Contents Checklist

### Mandatory Files (All Migrations)

| File | Description | Required |
|------|-------------|----------|
| `metadata.json` | Pack metadata | ✓ |
| `scope/source_scope_definition.json` | Source scope | ✓ |
| `scope/target_scope_definition.json` | Target scope | ✓ |
| `scope/dataset_classification.json` | Classification | ✓ |
| `schemas/source_schema_snapshot.json` | Source schema | ✓ |
| `schemas/target_schema_snapshot.json` | Target schema | ✓ |
| `schemas/schema_mapping.yml` | Mappings | ✓ |
| `profiling/source_profiling_report.json` | Profiling | ✓ |
| `execution/signed_plan_v*.json` | Signed plan | ✓ |
| `execution/execution_log.json` | Execution log | ✓ |
| `reconciliation/recon_plan.json` | Recon plan | ✓ |
| `reconciliation/parallel_run_summary.json` | Run summary | ✓ |
| `reconciliation/final_recon_report.json` | Final recon | ✓ |
| `approvals/approval_chain.json` | Approval chain | ✓ |
| `integrity/sha256_manifest.json` | File hashes | ✓ |
| `integrity/audit_chain.json` | Audit chain | ✓ |

### Conditional Files

| File | Condition |
|------|-----------|
| `profiling/pii_detection_report.json` | If PII detection enabled |
| `scope/exclusions.json` | If any exclusions |
| `reconciliation/diff_explanations/*` | If any diffs found |
| `cutover/cutover_plan.json` | If cutover executed |
| `cutover/rollback_plan.json` | If cutover executed |
| `signoff/compliance_attestation.json` | If compliance required |

---

## 7.7 Evidence Pack Validation

```python
def validate_evidence_pack(pack_dir: Path) -> tuple[bool, list[str]]:
    """Validate evidence pack completeness and integrity."""
    
    errors = []
    
    # 1. Check required files exist
    required_files = [
        "metadata.json",
        "scope/source_scope_definition.json",
        "scope/target_scope_definition.json",
        "schemas/source_schema_snapshot.json",
        "schemas/target_schema_snapshot.json",
        "schemas/schema_mapping.yml",
        "profiling/source_profiling_report.json",
        "execution/execution_log.json",
        "reconciliation/recon_plan.json",
        "reconciliation/final_recon_report.json",
        "approvals/approval_chain.json",
        "integrity/sha256_manifest.json",
        "integrity/audit_chain.json"
    ]
    
    for required in required_files:
        if not (pack_dir / required).exists():
            errors.append(f"Missing required file: {required}")
    
    # 2. Validate SHA256 manifest
    manifest_path = pack_dir / "integrity/sha256_manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        valid, manifest_errors = verify_sha256_manifest(pack_dir, manifest)
        errors.extend(manifest_errors)
    
    # 3. Validate audit chain
    chain_path = pack_dir / "integrity/audit_chain.json"
    if chain_path.exists():
        with open(chain_path) as f:
            chain = json.load(f)
        
        valid, chain_errors = verify_audit_chain(chain)
        errors.extend(chain_errors)
    
    # 4. Validate metadata
    metadata_path = pack_dir / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path) as f:
            metadata = json.load(f)
        
        # Validate required fields
        required_metadata = [
            "pack_id", "pack_version", "created_at", "project_id",
            "plan_id", "archetype_id", "policy_version", "final_status"
        ]
        for field in required_metadata:
            if field not in metadata:
                errors.append(f"Missing metadata field: {field}")
    
    # 5. Validate approvals
    approvals_path = pack_dir / "approvals/approval_chain.json"
    if approvals_path.exists():
        with open(approvals_path) as f:
            approvals = json.load(f)
        
        # Verify minimum approvals present
        if len(approvals.get("approvals", [])) < 2:
            errors.append("Insufficient approvals in chain")
    
    return len(errors) == 0, errors
```

---

## 7.8 Retention and Compliance

### Retention Policy

```json
{
  "retention_policies": {
    "default": {
      "duration_years": 7,
      "storage_class": "STANDARD_IA",
      "legal_hold": false
    },
    "financial": {
      "duration_years": 7,
      "storage_class": "GLACIER_DEEP_ARCHIVE",
      "legal_hold": true,
      "compliance_tags": ["SOX", "SEC"]
    },
    "gdpr": {
      "duration_years": 7,
      "storage_class": "STANDARD_IA",
      "legal_hold": false,
      "compliance_tags": ["GDPR"],
      "right_to_erasure": "metadata_only"
    },
    "hipaa": {
      "duration_years": 6,
      "storage_class": "GLACIER",
      "legal_hold": true,
      "compliance_tags": ["HIPAA"],
      "encryption_required": true
    }
  }
}
```

### Compliance Attestation

`signoff/compliance_attestation.json`:

```json
{
  "attestation_id": "attest_abc123",
  "pack_id": "evpack_abc123def456789",
  "created_at": "2026-01-05T23:30:00Z",
  "attestations": [
    {
      "compliance_framework": "SOX",
      "control_id": "IT-GC-4.1",
      "description": "Data migration controls",
      "status": "COMPLIANT",
      "evidence_refs": [
        "approvals/approval_chain.json",
        "reconciliation/final_recon_report.json"
      ],
      "attested_by": "user_compliance_officer",
      "attested_at": "2026-01-05T23:30:00Z"
    },
    {
      "compliance_framework": "GDPR",
      "control_id": "Art-32",
      "description": "Security of processing",
      "status": "COMPLIANT",
      "evidence_refs": [
        "profiling/pii_detection_report.json",
        "schemas/schema_mapping.yml"
      ],
      "attested_by": "user_dpo",
      "attested_at": "2026-01-05T23:30:00Z"
    }
  ]
}
```

