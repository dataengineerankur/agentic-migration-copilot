# 5. RECONCILIATION & PROOF — Deterministic and Auditable

All reconciliation must be deterministic and reproducible. Same inputs → same outputs.

---

## 5.1 Dataset Classification

### Class Definitions

| Class | Description | Examples | Tolerance | Parallel Runs |
|-------|-------------|----------|-----------|---------------|
| **A** | Financial/Regulatory | Transactions, balances, compliance data | Zero tolerance | 14 days |
| **B** | Business Critical | Customer master, orders, inventory | Near-zero (0.001%) | 14 days |
| **C** | Operational | Logs, metrics, session data | Low (0.1%) | 7 days |
| **D** | Archival/Low Priority | Historical backups, deprecated tables | Medium (1%) | 3 days |

### Classification Rules

```yaml
classification_rules:
  # Rule 1: Explicit policy override (highest priority)
  - condition: "table in policy.dataset_class_overrides"
    action: "use policy.dataset_class_overrides[table]"
    
  # Rule 2: Schema/database naming patterns
  - condition: "schema matches 'finance_*' OR schema matches 'compliance_*'"
    class: A
    
  - condition: "schema matches 'core_*' OR schema matches 'master_*'"
    class: B
    
  - condition: "schema matches 'logs_*' OR schema matches 'metrics_*'"
    class: C
    
  - condition: "schema matches 'archive_*' OR table matches '*_backup'"
    class: D
    
  # Rule 3: PII presence
  - condition: "pii_detection_report.pii_columns.length > 0"
    class: "max(current_class, B)"  # At least B if PII present
    
  # Rule 4: Row count thresholds
  - condition: "row_count > 100000000"  # >100M rows
    class: "max(current_class, B)"  # Large tables need more scrutiny
    
  # Rule 5: Default
  - condition: "no other rule matches"
    class: C
    emit: "manual_decisions_required.json"
```

### Classification Decision Artifact

```json
{
  "table": "public.orders",
  "assigned_class": "B",
  "classification_reasoning": [
    {
      "rule": "schema_pattern",
      "matched_pattern": "core_*",
      "result": "B"
    },
    {
      "rule": "pii_check",
      "pii_columns_found": ["customer_email"],
      "result": "upgrade_to_B_minimum"
    },
    {
      "rule": "row_count",
      "row_count": 15234567,
      "threshold": 100000000,
      "result": "no_upgrade"
    }
  ],
  "final_class": "B",
  "tolerances_applied": {
    "row_count_critical_pct": 0.0,
    "row_count_major_pct": 0.001,
    "hash_mismatch_critical_pct": 0.0,
    "hash_mismatch_major_pct": 0.001
  },
  "parallel_runs_required": 14
}
```

---

## 5.2 Canonical Row Serialization Specification

### Purpose

Ensure identical hashing results across different systems. The serialization must be:
- Deterministic (same row → same bytes)
- Platform-independent
- Documented and versioned

### Specification: `hashing_spec.json`

```json
{
  "spec_version": "v1.0.0",
  "created_at": "2026-01-01T00:00:00Z",
  "serialization": {
    "format": "canonical_json",
    "encoding": "utf-8",
    "column_order": "alphabetical_by_name",
    "null_representation": "null",
    "boolean_representation": {
      "true": "true",
      "false": "false"
    },
    "numeric_representation": {
      "integers": "no_leading_zeros",
      "decimals": "fixed_scale_no_trailing_zeros",
      "floats": "ieee754_hex_or_decimal_17_digits",
      "special_values": {
        "nan": "\"NaN\"",
        "inf": "\"Infinity\"",
        "neg_inf": "\"-Infinity\""
      }
    },
    "string_representation": {
      "escaping": "json_standard",
      "unicode": "utf8_nfc_normalized"
    },
    "timestamp_representation": {
      "format": "iso8601",
      "timezone": "convert_to_utc",
      "precision": "milliseconds",
      "example": "2026-01-05T10:30:00.123Z"
    },
    "date_representation": {
      "format": "iso8601",
      "example": "2026-01-05"
    },
    "time_representation": {
      "format": "iso8601",
      "precision": "milliseconds",
      "example": "10:30:00.123"
    },
    "binary_representation": {
      "encoding": "base64_standard"
    },
    "array_representation": {
      "format": "json_array",
      "element_order": "preserve"
    },
    "object_representation": {
      "format": "json_object",
      "key_order": "alphabetical"
    }
  }
}
```

### Serialization Examples

| Type | Source Value | Canonical Representation |
|------|-------------|-------------------------|
| INTEGER | `42` | `42` |
| INTEGER | `-0` | `0` |
| DECIMAL(10,2) | `123.40` | `123.4` |
| DECIMAL(10,4) | `123.4000` | `123.4` |
| FLOAT | `3.141592653589793` | `3.141592653589793` |
| FLOAT | `NaN` | `"NaN"` |
| STRING | `Hello` | `"Hello"` |
| STRING | `Line1\nLine2` | `"Line1\nLine2"` |
| BOOLEAN | `true` | `true` |
| NULL | `NULL` | `null` |
| TIMESTAMP | `2026-01-05 10:30:00.123456 -05:00` | `"2026-01-05T15:30:00.123Z"` |
| DATE | `2026-01-05` | `"2026-01-05"` |
| BINARY | `0xDEADBEEF` | `"3q2+7w=="` |
| ARRAY | `[1, 2, 3]` | `[1,2,3]` |

### Row Serialization Algorithm

```python
def serialize_row(row: dict, column_order: list[str], spec: dict) -> bytes:
    """
    Serialize a row to canonical bytes for hashing.
    
    Args:
        row: Dictionary of column_name -> value
        column_order: Alphabetically sorted column names
        spec: Serialization specification
    
    Returns:
        UTF-8 encoded bytes
    """
    canonical = {}
    
    for col in column_order:
        value = row.get(col)
        canonical[col] = serialize_value(value, spec)
    
    # JSON with sorted keys, no whitespace
    json_str = json.dumps(canonical, sort_keys=True, separators=(',', ':'))
    return json_str.encode('utf-8')


def serialize_value(value, spec: dict):
    """Serialize a single value according to spec."""
    
    if value is None:
        return None
    
    if isinstance(value, bool):
        return value  # JSON handles correctly
    
    if isinstance(value, int):
        return value
    
    if isinstance(value, Decimal):
        # Remove trailing zeros, preserve scale
        return str(value.normalize())
    
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    
    if isinstance(value, str):
        # NFC normalize Unicode
        return unicodedata.normalize('NFC', value)
    
    if isinstance(value, datetime):
        # Convert to UTC, format as ISO8601 with milliseconds
        utc_dt = value.astimezone(timezone.utc)
        return utc_dt.strftime('%Y-%m-%dT%H:%M:%S.') + f'{utc_dt.microsecond // 1000:03d}Z'
    
    if isinstance(value, date):
        return value.isoformat()
    
    if isinstance(value, time):
        return value.strftime('%H:%M:%S.') + f'{value.microsecond // 1000:03d}'
    
    if isinstance(value, bytes):
        return base64.standard_b64encode(value).decode('ascii')
    
    if isinstance(value, list):
        return [serialize_value(v, spec) for v in value]
    
    if isinstance(value, dict):
        return {k: serialize_value(v, spec) for k, v in sorted(value.items())}
    
    raise ValueError(f"Unsupported type: {type(value)}")
```

---

## 5.3 Hashing Algorithm

### Algorithm Selection

| Algorithm | Use Case | Speed | Collision Resistance |
|-----------|----------|-------|---------------------|
| **xxHash64** | Row hashing for comparison | Fast | Sufficient for validation |
| **SHA-256** | File integrity, evidence packs | Slower | Cryptographic |

### Row Hashing Configuration

```json
{
  "row_hashing": {
    "algorithm": "xxhash64",
    "seed": 0,
    "output_format": "hex_lowercase"
  },
  "file_integrity": {
    "algorithm": "sha256",
    "output_format": "hex_lowercase"
  },
  "chunking": {
    "enabled": true,
    "chunk_size_rows": 100000,
    "parallel_chunks": 8
  }
}
```

### Hash Computation

```python
import xxhash

def compute_row_hash(serialized_row: bytes, seed: int = 0) -> str:
    """Compute xxHash64 of serialized row."""
    h = xxhash.xxh64(serialized_row, seed=seed)
    return h.hexdigest()


def compute_table_hash(rows: Iterator[bytes], chunk_size: int = 100000) -> dict:
    """
    Compute aggregate hash statistics for a table.
    
    Returns hash counts for reconciliation.
    """
    hash_counts = {}
    
    for row_bytes in rows:
        h = compute_row_hash(row_bytes)
        hash_counts[h] = hash_counts.get(h, 0) + 1
    
    return hash_counts
```

---

## 5.4 Deterministic Sampling Method

### Method: SHA256 Modulo Sampling

Deterministic sampling ensures the same rows are selected every time, enabling reproducible reconciliation.

```
Sample selection criteria:
    sha256(primary_key_canonical) mod M < K

Where:
    M = modulo divisor (e.g., 100)
    K = threshold (e.g., 10 for 10% sample)
    primary_key_canonical = serialized primary key value(s)
```

### Sampling Configuration

```json
{
  "sampling": {
    "method": "deterministic_modulo",
    "params": {
      "modulo_divisor": 100,
      "threshold": 10,
      "seed_columns": ["order_id"],
      "hash_algorithm": "sha256"
    },
    "expected_sample_rate": 0.10,
    "minimum_sample_size": 10000,
    "maximum_sample_size": 10000000
  }
}
```

### Sampling Implementation

```python
import hashlib

def should_sample_row(primary_key_values: list, config: dict) -> bool:
    """
    Determine if a row should be included in the sample.
    
    Deterministic: same PK always returns same result.
    """
    # Serialize PK values
    pk_str = '|'.join(str(v) for v in primary_key_values)
    
    # Hash
    h = hashlib.sha256(pk_str.encode('utf-8'))
    hash_int = int(h.hexdigest(), 16)
    
    # Modulo check
    modulo = config['modulo_divisor']
    threshold = config['threshold']
    
    return (hash_int % modulo) < threshold


def sample_table(source_rows: Iterator, config: dict) -> Iterator:
    """Generate deterministic sample of rows."""
    seed_columns = config['seed_columns']
    
    for row in source_rows:
        pk_values = [row[col] for col in seed_columns]
        
        if should_sample_row(pk_values, config):
            yield row
```

### Sampling Validation

```json
{
  "sampling_validation": {
    "source_total_rows": 15234567,
    "sample_size_expected": 1523456,
    "sample_size_actual": 1523401,
    "sample_rate_actual": 0.09997,
    "sample_rate_tolerance": 0.001,
    "validation_passed": true,
    "reproducibility_check": {
      "run_1_sample_size": 1523401,
      "run_2_sample_size": 1523401,
      "same_rows_selected": true
    }
  }
}
```

---

## 5.5 Tolerance Rules

### Tolerance Policy Schema

```json
{
  "tolerances": {
    "dataset_classes": {
      "A": {
        "description": "Financial/Regulatory - Zero tolerance",
        "row_count_tolerance": {
          "critical_pct": 0.0,
          "major_pct": 0.0,
          "minor_pct": 0.0001
        },
        "hash_mismatch_tolerance": {
          "critical_pct": 0.0,
          "major_pct": 0.0,
          "minor_pct": 0.0001
        },
        "null_rate_delta_tolerance": {
          "major_pct": 0.0
        },
        "numeric_aggregate_tolerance": {
          "sum_epsilon": 0.0,
          "avg_epsilon": 0.0
        },
        "requires_full_recon": true
      },
      "B": {
        "description": "Business Critical - Near-zero tolerance",
        "row_count_tolerance": {
          "critical_pct": 0.0,
          "major_pct": 0.001,
          "minor_pct": 0.01
        },
        "hash_mismatch_tolerance": {
          "critical_pct": 0.0,
          "major_pct": 0.001,
          "minor_pct": 0.01
        },
        "null_rate_delta_tolerance": {
          "major_pct": 0.001
        },
        "numeric_aggregate_tolerance": {
          "sum_epsilon": 0.01,
          "avg_epsilon": 0.0001
        },
        "requires_full_recon": false
      },
      "C": {
        "description": "Operational - Low tolerance",
        "row_count_tolerance": {
          "critical_pct": 0.01,
          "major_pct": 0.1,
          "minor_pct": 1.0
        },
        "hash_mismatch_tolerance": {
          "critical_pct": 0.01,
          "major_pct": 0.1,
          "minor_pct": 1.0
        },
        "null_rate_delta_tolerance": {
          "major_pct": 0.1
        },
        "numeric_aggregate_tolerance": {
          "sum_epsilon": 0.1,
          "avg_epsilon": 0.01
        },
        "requires_full_recon": false
      },
      "D": {
        "description": "Archival - Medium tolerance",
        "row_count_tolerance": {
          "critical_pct": 0.1,
          "major_pct": 1.0,
          "minor_pct": 5.0
        },
        "hash_mismatch_tolerance": {
          "critical_pct": 0.1,
          "major_pct": 1.0,
          "minor_pct": 5.0
        },
        "null_rate_delta_tolerance": {
          "major_pct": 1.0
        },
        "numeric_aggregate_tolerance": {
          "sum_epsilon": 1.0,
          "avg_epsilon": 0.1
        },
        "requires_full_recon": false
      }
    }
  }
}
```

### Tolerance Evaluation Algorithm

```python
def evaluate_tolerance(
    metric_name: str,
    source_value: float,
    target_value: float,
    tolerance_config: dict
) -> tuple[str, str]:  # (severity, message)
    """
    Evaluate a metric against tolerance thresholds.
    
    Returns severity: "CRITICAL", "MAJOR", "MINOR", or "PASS"
    """
    if source_value == 0:
        delta_pct = 100.0 if target_value != 0 else 0.0
    else:
        delta_pct = abs(target_value - source_value) / source_value * 100
    
    thresholds = tolerance_config.get(f'{metric_name}_tolerance', {})
    
    critical_pct = thresholds.get('critical_pct', 0.0)
    major_pct = thresholds.get('major_pct', 0.0)
    minor_pct = thresholds.get('minor_pct', float('inf'))
    
    if delta_pct > critical_pct and critical_pct == 0.0:
        if source_value != target_value:
            return "CRITICAL", f"{metric_name}: {delta_pct:.4f}% delta exceeds critical threshold (zero tolerance)"
    
    if delta_pct > major_pct:
        return "MAJOR", f"{metric_name}: {delta_pct:.4f}% delta exceeds major threshold ({major_pct}%)"
    
    if delta_pct > minor_pct:
        return "MINOR", f"{metric_name}: {delta_pct:.4f}% delta exceeds minor threshold ({minor_pct}%)"
    
    return "PASS", f"{metric_name}: {delta_pct:.4f}% delta within tolerance"
```

---

## 5.6 Parallel Validation Rules

### Configuration

```json
{
  "parallel_validation": {
    "class_A": {
      "required_consecutive_passes": 14,
      "interval_hours": 24,
      "minimum_elapsed_days": 14
    },
    "class_B": {
      "required_consecutive_passes": 14,
      "interval_hours": 24,
      "minimum_elapsed_days": 14
    },
    "class_C": {
      "required_consecutive_passes": 7,
      "interval_hours": 24,
      "minimum_elapsed_days": 7
    },
    "class_D": {
      "required_consecutive_passes": 3,
      "interval_hours": 24,
      "minimum_elapsed_days": 3
    }
  }
}
```

### Parallel Run Tracking

```json
{
  "parallel_run_summary": {
    "plan_id": "plan_abc123",
    "table": "public.orders",
    "dataset_class": "B",
    "required_passes": 14,
    "completed_runs": 14,
    "passed_runs": 14,
    "failed_runs": 0,
    "trend": "stable",
    "runs": [
      {
        "run_number": 1,
        "executed_at": "2025-12-22T00:00:00Z",
        "row_count_source": 15234567,
        "row_count_target": 15234567,
        "hash_mismatch_pct": 0.0,
        "severity": "PASS",
        "recon_report_uri": "s3://artifacts/recon/run_001.json"
      },
      {
        "run_number": 2,
        "executed_at": "2025-12-23T00:00:00Z",
        "row_count_source": 15245678,
        "row_count_target": 15245678,
        "hash_mismatch_pct": 0.0,
        "severity": "PASS",
        "recon_report_uri": "s3://artifacts/recon/run_002.json"
      }
    ],
    "ready_for_cutover": true,
    "cutover_eligible_at": "2026-01-05T00:00:00Z"
  }
}
```

### Trend Analysis

```python
def analyze_trend(runs: list[dict]) -> str:
    """
    Analyze trend across parallel runs.
    
    Returns: "improving", "stable", "degrading"
    """
    if len(runs) < 3:
        return "insufficient_data"
    
    # Look at last N runs
    recent = runs[-min(7, len(runs)):]
    
    mismatch_rates = [r['hash_mismatch_pct'] for r in recent]
    
    # Calculate trend
    if all(r == 0 for r in mismatch_rates):
        return "stable"
    
    first_half = sum(mismatch_rates[:len(mismatch_rates)//2])
    second_half = sum(mismatch_rates[len(mismatch_rates)//2:])
    
    if second_half < first_half * 0.5:
        return "improving"
    elif second_half > first_half * 1.5:
        return "degrading"
    else:
        return "stable"
```

---

## 5.7 Severity Model

### Severity Definitions

| Severity | Definition | Action Required |
|----------|------------|-----------------|
| **CRITICAL** | Data integrity at risk; potential compliance violation | HALT. Manual review required. Cannot proceed. |
| **MAJOR** | Significant discrepancy requiring investigation | PAUSE. Investigation required before proceeding. |
| **MINOR** | Small discrepancy within acceptable tolerance | LOG. Continue with acknowledgment. |
| **PASS** | All checks within tolerance | Continue normally. |

### Severity Aggregation Rules

```python
def aggregate_severity(table_results: list[dict]) -> str:
    """
    Aggregate severity across all checks for a table.
    
    Rules:
    - Any CRITICAL → overall CRITICAL
    - Any MAJOR (and no CRITICAL) → overall MAJOR
    - Any MINOR (and no CRITICAL/MAJOR) → overall MINOR
    - All PASS → overall PASS
    """
    severities = [r['severity'] for r in table_results]
    
    if 'CRITICAL' in severities:
        return 'CRITICAL'
    if 'MAJOR' in severities:
        return 'MAJOR'
    if 'MINOR' in severities:
        return 'MINOR'
    return 'PASS'
```

---

## 5.8 "Safe Enough" Decision Gate

### Criteria for Cutover Readiness

```yaml
cutover_readiness_gate:
  mandatory_conditions:
    - all_parallel_runs_completed: true
    - no_critical_severity_in_final_run: true
    - no_unacknowledged_major_severity: true
    - trend_not_degrading: true
    - all_required_approvals_present: true
    
  class_specific:
    A:
      - all_runs_passed: true
      - full_reconciliation_completed: true
      - zero_hash_mismatches: true
      
    B:
      - final_run_passed: true
      - mismatch_rate_below_threshold: true
      - acknowledged_deviations_documented: true
      
    C:
      - final_run_passed: true
      - no_critical_in_any_run: true
      
    D:
      - final_run_passed: true
```

### Gate Evaluation

```json
{
  "cutover_readiness_evaluation": {
    "evaluated_at": "2026-01-05T10:00:00Z",
    "plan_id": "plan_abc123",
    "dataset_class": "B",
    "mandatory_conditions": {
      "all_parallel_runs_completed": {"status": true, "value": "14/14"},
      "no_critical_severity_in_final_run": {"status": true, "value": "PASS"},
      "no_unacknowledged_major_severity": {"status": true, "value": "0 unacknowledged"},
      "trend_not_degrading": {"status": true, "value": "stable"},
      "all_required_approvals_present": {"status": true, "value": "4/4 approvals"}
    },
    "class_specific_conditions": {
      "final_run_passed": {"status": true},
      "mismatch_rate_below_threshold": {"status": true, "value": "0.0% < 0.001%"},
      "acknowledged_deviations_documented": {"status": true, "value": "0 deviations"}
    },
    "overall_ready": true,
    "blocking_issues": [],
    "warnings": []
  }
}
```

---

## 5.9 Diff Explanation Agent Requirements

### Evidence Citation Requirements

Every hypothesis MUST include:
1. At least one evidence URI (to artifact store)
2. SHA256 of referenced artifact
3. Specific observation from the evidence

### Hypothesis Structure

```json
{
  "hypothesis": {
    "hypothesis_id": "H1",
    "description": "Clear description of suspected root cause",
    "likelihood": "high|medium|low",
    "evidence": [
      {
        "uri": "s3://artifacts/mismatches/sample_001.json",
        "sha256": "abc123...",
        "observation": "Specific finding from this evidence"
      }
    ],
    "root_cause_category": "serialization|type_coercion|timezone|null_handling|encoding|other",
    "proposed_fix": {
      "type": "config_change|code_change|manual_correction|requires_investigation",
      "description": "What to change",
      "patch_file": "path/to/patch if applicable",
      "estimated_effort": "hours"
    },
    "next_actions": [
      "Action 1",
      "Action 2",
      "Action 3"
    ]
  }
}
```

### Top 3 Hypotheses Requirement

Diff Explanation Agent MUST:
1. Generate at least 3 hypotheses for any failure
2. Rank by likelihood
3. Provide next actions for each
4. Never claim certainty without deterministic proof

```json
{
  "diff_explanation": {
    "failure_summary": {
      "table": "orders",
      "mismatch_count": 15,
      "mismatch_pct": 0.001
    },
    "hypotheses": [
      {
        "rank": 1,
        "hypothesis_id": "H1",
        "likelihood": "high",
        "description": "Timezone conversion inconsistency"
      },
      {
        "rank": 2,
        "hypothesis_id": "H2",
        "likelihood": "medium",
        "description": "Floating point precision in aggregates"
      },
      {
        "rank": 3,
        "hypothesis_id": "H3",
        "likelihood": "low",
        "description": "Race condition during extraction"
      }
    ],
    "recommended_action": "Investigate H1 first, verify timezone handling in serialization spec"
  }
}
```

