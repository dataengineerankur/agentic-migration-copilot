# 4. ARCHETYPE EXECUTION TEMPLATES — Step Checklists

Each archetype is a reusable template, not a one-off script. Archetypes are implemented in priority order.

---

## 4.1 Archetype 1: Postgres → S3 (Full Load + Incremental)

### Entry Conditions
- [ ] Source system type = `postgres`
- [ ] Target system type = `s3`
- [ ] Source credentials validated (read-only)
- [ ] Target S3 bucket exists and writable
- [ ] Policy.json loaded and validated
- [ ] type_coercion_rulebook.json includes `postgres_to_s3` rules

### Required Metadata
```json
{
  "archetype_id": "postgres_to_s3",
  "source_config": {
    "type": "postgres",
    "version_min": "11.0",
    "secret_ref": "vault://databases/postgres/readonly",
    "scope": {
      "databases": ["*"],
      "schemas": ["public"],
      "tables": ["*"],
      "exclude_patterns": ["*_backup", "*_temp"]
    }
  },
  "target_config": {
    "type": "s3",
    "bucket": "data-lake-bronze",
    "prefix": "postgres/",
    "format": "parquet",
    "compression": "snappy"
  },
  "load_patterns": ["full", "incremental"],
  "incremental_config": {
    "watermark_column": "updated_at",
    "watermark_type": "timestamp",
    "checkpoint_storage": "s3://data-lake-checkpoints/"
  }
}
```

### Profiling Steps (EP Jobs)

| Step | Job | Input | Output | Checkpoint |
|------|-----|-------|--------|------------|
| 1.1 | `postgres_catalog_discovery` | connection_config | discovery_report.json | Yes |
| 1.2 | `postgres_statistics_profiling` | discovery_report | profiling_report.json | Yes |
| 1.3 | `pii_detection` | profiling_report | pii_detection_report.json | No |

### Mapping Rules (Rulebook References)

| Postgres Type | Parquet Type | Rule ID | Lossy | Notes |
|--------------|--------------|---------|-------|-------|
| `smallint` | INT32 | pg_smallint_to_parquet | No | Widening |
| `integer` | INT32 | pg_integer_to_parquet | No | Exact |
| `bigint` | INT64 | pg_bigint_to_parquet | No | Exact |
| `numeric(p,s)` | DECIMAL(p,s) | pg_numeric_to_parquet | No | Exact if p≤38 |
| `numeric(p>38,s)` | STRING | pg_numeric_large_to_string | Yes | **Requires approval** |
| `real` | FLOAT | pg_real_to_parquet | No | Exact |
| `double precision` | DOUBLE | pg_double_to_parquet | No | Exact |
| `boolean` | BOOLEAN | pg_boolean_to_parquet | No | Exact |
| `char(n)` | STRING | pg_char_to_parquet | No | Trailing spaces preserved |
| `varchar(n)` | STRING | pg_varchar_to_parquet | No | Exact |
| `text` | STRING | pg_text_to_parquet | No | Exact |
| `bytea` | BINARY | pg_bytea_to_parquet | No | Exact |
| `date` | DATE | pg_date_to_parquet | No | Exact |
| `time` | TIME_MILLIS | pg_time_to_parquet | Yes | Microseconds lost |
| `time with time zone` | STRING | pg_timetz_to_string | Yes | **Requires approval** |
| `timestamp` | TIMESTAMP_MILLIS | pg_timestamp_to_parquet | Yes | Microseconds lost |
| `timestamp with time zone` | TIMESTAMP_MILLIS | pg_timestamptz_to_parquet | Yes | Converted to UTC |
| `interval` | STRING | pg_interval_to_string | Yes | **Requires approval** |
| `uuid` | STRING | pg_uuid_to_parquet | No | Exact |
| `json` | STRING | pg_json_to_parquet | No | Exact |
| `jsonb` | STRING | pg_jsonb_to_parquet | No | Exact |
| `array` | LIST | pg_array_to_parquet | No | Exact |

**If mapping not found**: Emit `manual_decisions_required.json` with decision request.

### Code Generation Behavior

```yaml
# PR patch structure for Postgres → S3
pr_structure:
  - path: dbt/models/bronze/{schema}_{table}.sql
    template: postgres_to_s3_dbt_model.sql.j2
    
  - path: spark/jobs/extract_{schema}_{table}.py
    template: postgres_to_s3_spark_extract.py.j2
    
  - path: airflow/dags/migrate_{schema}_{table}.py
    template: postgres_to_s3_dag.py.j2
    
  - path: configs/{schema}_{table}_config.yml
    template: migration_config.yml.j2
```

### Reconciliation Strategy Selection

```
IF dataset_class == "A" (financial/regulatory):
    strategy = "row_hash_plus_aggregates_plus_keydiff"
    parallel_runs = 14
    sampling_rate = 100%  # Full comparison
    
ELIF dataset_class == "B" (business critical):
    strategy = "row_hash_plus_aggregates_plus_keydiff"
    parallel_runs = 14
    sampling_rate = 10%  # sha256(pk) mod 10 < 1
    
ELIF dataset_class == "C" (operational):
    strategy = "row_hash_plus_aggregates"
    parallel_runs = 7
    sampling_rate = 1%
    
ELIF dataset_class == "D" (archival/low priority):
    strategy = "row_hash_only"
    parallel_runs = 3
    sampling_rate = 0.1%
```

### Parallel Validation Workflow

```
FOR run_number IN 1..parallel_runs:
    1. Wait interval_hours (default 24)
    2. Execute incremental extract (if incremental enabled)
    3. Execute reconciliation with same sampling params
    4. Store recon_report_{run_number}.json
    5. IF Critical severity: HALT, require manual review
    6. IF Major severity: CONTINUE but flag for review
    
AFTER all runs:
    1. Generate parallel_run_summary.json
    2. Calculate trend (improving/stable/degrading)
    3. IF all PASS and trend stable: CUTOVER_READY
    4. ELSE: Require DiffExplanationAgent analysis
```

### Cutover Workflow

```
PRE-CUTOVER:
    1. Verify 14 consecutive passing parallel runs
    2. Schedule maintenance window
    3. Notify all stakeholders
    4. Test rollback procedure
    5. Take final source snapshot
    
CUTOVER (requires release_manager + data_owner approval):
    1. Stop writes to Postgres (read-only mode or application stop)
    2. Execute final incremental sync
    3. Run final reconciliation
    4. Verify PASS status
    5. Update application connection strings to read from S3/catalog
    6. Execute smoke tests
    7. Monitor for 24 hours
    
ROLLBACK (if triggered):
    1. Revert application connection strings
    2. Verify Postgres accessible
    3. Document failure reason
    4. Create failure_analysis.json
    5. Return to RECONCILED state
```

---

## 4.2 Archetype 2: HDFS/Hive → S3

### Entry Conditions
- [ ] Source system type = `hdfs` or `hive`
- [ ] Target system type = `s3`
- [ ] Source Hadoop cluster accessible
- [ ] Hive metastore accessible (if Hive tables)
- [ ] Target S3 bucket exists and writable
- [ ] Policy.json loaded and validated

### Required Metadata
```json
{
  "archetype_id": "hdfs_to_s3",
  "source_config": {
    "type": "hive",
    "metastore_uri": "thrift://metastore:9083",
    "hdfs_namenode": "hdfs://namenode:8020",
    "secret_ref": "vault://hadoop/kerberos/readonly",
    "scope": {
      "databases": ["warehouse"],
      "tables": ["*"],
      "exclude_patterns": ["*_staging"]
    }
  },
  "target_config": {
    "type": "s3",
    "bucket": "data-lake-bronze",
    "prefix": "hive/",
    "format": "parquet",
    "compression": "snappy"
  },
  "partition_mapping": "preserve_or_optimize"
}
```

### Profiling Steps (EP Jobs)

| Step | Job | Input | Output | Checkpoint |
|------|-----|-------|--------|------------|
| 2.1 | `hive_metastore_discovery` | connection_config | discovery_report.json | Yes |
| 2.2 | `hdfs_partition_scan` | discovery_report | partition_inventory.json | Yes |
| 2.3 | `hive_statistics_profiling` | discovery_report | profiling_report.json | Yes |
| 2.4 | `file_format_analysis` | partition_inventory | format_analysis.json | No |

### Mapping Rules (Partition Mapping)

| Source Partition Scheme | Target Partition Strategy | Rule ID | Notes |
|------------------------|---------------------------|---------|-------|
| `year/month/day` | `year=%Y/month=%m/day=%d` | hive_ymd_to_s3 | Hive style |
| `dt=YYYY-MM-DD` | `dt=%Y-%m-%d` | hive_dt_to_s3 | Preserve |
| `region/date` | `region=X/date=%Y-%m-%d` | hive_compound_to_s3 | Compound |
| No partitioning | No partitioning | hive_nopart_to_s3 | Preserve |
| `bucket(N, col)` | **Requires decision** | - | Cannot auto-map |

### Type Mapping (Hive → Parquet/S3)

| Hive Type | Parquet Type | Rule ID | Lossy |
|-----------|--------------|---------|-------|
| `TINYINT` | INT32 | hive_tinyint_to_parquet | No |
| `SMALLINT` | INT32 | hive_smallint_to_parquet | No |
| `INT` | INT32 | hive_int_to_parquet | No |
| `BIGINT` | INT64 | hive_bigint_to_parquet | No |
| `FLOAT` | FLOAT | hive_float_to_parquet | No |
| `DOUBLE` | DOUBLE | hive_double_to_parquet | No |
| `DECIMAL(p,s)` | DECIMAL(p,s) | hive_decimal_to_parquet | No |
| `STRING` | STRING | hive_string_to_parquet | No |
| `VARCHAR(n)` | STRING | hive_varchar_to_parquet | No |
| `CHAR(n)` | STRING | hive_char_to_parquet | No |
| `BOOLEAN` | BOOLEAN | hive_boolean_to_parquet | No |
| `BINARY` | BINARY | hive_binary_to_parquet | No |
| `DATE` | DATE | hive_date_to_parquet | No |
| `TIMESTAMP` | TIMESTAMP_MILLIS | hive_timestamp_to_parquet | Yes |
| `ARRAY<T>` | LIST<T> | hive_array_to_parquet | No |
| `MAP<K,V>` | MAP<K,V> | hive_map_to_parquet | No |
| `STRUCT<...>` | GROUP | hive_struct_to_parquet | No |

### Code Generation Behavior

```yaml
pr_structure:
  - path: spark/jobs/migrate_{database}_{table}.py
    template: hdfs_to_s3_spark_migrate.py.j2
    
  - path: airflow/dags/migrate_{database}_{table}.py
    template: hdfs_to_s3_dag.py.j2
    
  - path: glue/tables/{database}_{table}.json
    template: glue_table_definition.json.j2
    
  - path: configs/{database}_{table}_config.yml
    template: migration_config.yml.j2
```

### Reconciliation Strategy Selection

```
IF source_format == "parquet" AND target_format == "parquet":
    strategy = "file_checksum_plus_row_hash"
    # Can compare file checksums for unchanged partitions
    
ELIF source_format in ["orc", "avro", "text"]:
    strategy = "row_hash_plus_aggregates"
    # Must read and re-serialize
    
partition_validation:
    - Verify all source partitions exist in target
    - Verify partition row counts match
    - Sample rows from each partition
```

### Parallel Validation Workflow

```
FOR each partition:
    1. Compare row counts
    2. Sample rows using deterministic sampling
    3. Hash and compare
    4. Store partition_recon_{partition_id}.json
    
FOR run_number IN 1..parallel_runs:
    1. Wait interval_hours
    2. Re-validate most recent N partitions (where N = 7 days of data)
    3. Aggregate results
```

### Cutover Workflow

```
PRE-CUTOVER:
    1. Verify all partitions migrated
    2. Update external table definitions to point to S3
    3. Test queries against both locations
    4. Prepare Glue/Athena catalog registration
    
CUTOVER:
    1. Register tables in target catalog (Glue/Athena)
    2. Update downstream jobs to use new location
    3. Redirect queries to S3
    4. Verify query results match
    
ROLLBACK:
    1. Re-register original HDFS locations
    2. Revert downstream job configurations
```

---

## 4.3 Archetype 3: Snowflake → Redshift

### Entry Conditions
- [ ] Source system type = `snowflake`
- [ ] Target system type = `redshift`
- [ ] Snowflake warehouse has adequate credits/quota
- [ ] Redshift cluster sized appropriately
- [ ] Cross-cloud networking configured (if applicable)
- [ ] Policy.json loaded with Snowflake/Redshift rules

### Required Metadata
```json
{
  "archetype_id": "snowflake_to_redshift",
  "source_config": {
    "type": "snowflake",
    "account": "org-account",
    "warehouse": "MIGRATION_WH",
    "secret_ref": "vault://snowflake/readonly",
    "scope": {
      "databases": ["PROD_DB"],
      "schemas": ["PUBLIC", "ANALYTICS"],
      "tables": ["*"],
      "exclude_patterns": ["*_TEMP", "*_DEV"]
    }
  },
  "target_config": {
    "type": "redshift",
    "cluster": "prod-redshift",
    "database": "prod_db",
    "secret_ref": "vault://redshift/migrate_user",
    "staging_s3": "s3://redshift-staging/"
  },
  "semantic_handling": {
    "null_semantics": "preserve",
    "numeric_precision": "strict",
    "timezone_handling": "convert_to_utc"
  }
}
```

### Profiling Steps (EP Jobs)

| Step | Job | Input | Output | Checkpoint |
|------|-----|-------|--------|------------|
| 3.1 | `snowflake_information_schema_discovery` | connection_config | discovery_report.json | Yes |
| 3.2 | `snowflake_statistics_profiling` | discovery_report | profiling_report.json | Yes |
| 3.3 | `snowflake_null_analysis` | discovery_report | null_analysis.json | No |
| 3.4 | `redshift_capacity_analysis` | target_config | capacity_analysis.json | No |

### Mapping Rules (Semantic Handling)

#### Null Semantics Differences
| Scenario | Snowflake | Redshift | Handling |
|----------|-----------|----------|----------|
| Empty string | '' (empty) | '' (empty) | Preserve |
| NULL | NULL | NULL | Preserve |
| NaN (float) | NaN | NaN | Verify after load |
| Infinity | Inf/-Inf | **Error** | **Requires decision** |

#### Numeric Precision Rules
| Snowflake Type | Redshift Type | Rule ID | Notes |
|----------------|---------------|---------|-------|
| `NUMBER(p,s)` p≤38 | `DECIMAL(p,s)` | sf_number_to_rs | Exact |
| `NUMBER(p,s)` p>38 | **Requires decision** | - | Lossy or STRING |
| `FLOAT` | `FLOAT8` | sf_float_to_rs | Exact |
| `DOUBLE` | `FLOAT8` | sf_double_to_rs | Exact |

#### Timezone Rules
| Snowflake Type | Redshift Type | Rule ID | Handling |
|----------------|---------------|---------|----------|
| `TIMESTAMP_NTZ` | `TIMESTAMP` | sf_ntz_to_rs | No TZ, preserve |
| `TIMESTAMP_LTZ` | `TIMESTAMPTZ` | sf_ltz_to_rs | Convert to UTC |
| `TIMESTAMP_TZ` | `TIMESTAMPTZ` | sf_tz_to_rs | Preserve offset as UTC |

#### Full Type Mapping
| Snowflake | Redshift | Rule ID | Lossy |
|-----------|----------|---------|-------|
| `NUMBER(p,s)` | `DECIMAL(p,s)` | sf_number_to_rs_decimal | No |
| `FLOAT` | `FLOAT8` | sf_float_to_rs | No |
| `VARCHAR(n)` | `VARCHAR(n*4)` | sf_varchar_to_rs | No (UTF-8 expansion) |
| `CHAR(n)` | `CHAR(n*4)` | sf_char_to_rs | No |
| `TEXT` | `VARCHAR(65535)` | sf_text_to_rs | Yes if >65535 |
| `BINARY` | `VARBYTE` | sf_binary_to_rs | No |
| `BOOLEAN` | `BOOLEAN` | sf_boolean_to_rs | No |
| `DATE` | `DATE` | sf_date_to_rs | No |
| `TIME` | `TIME` | sf_time_to_rs | No |
| `TIMESTAMP_NTZ` | `TIMESTAMP` | sf_timestamp_ntz_to_rs | No |
| `TIMESTAMP_LTZ` | `TIMESTAMPTZ` | sf_timestamp_ltz_to_rs | No |
| `TIMESTAMP_TZ` | `TIMESTAMPTZ` | sf_timestamp_tz_to_rs | No |
| `VARIANT` | `SUPER` | sf_variant_to_rs | Verify after load |
| `OBJECT` | `SUPER` | sf_object_to_rs | Verify after load |
| `ARRAY` | `SUPER` | sf_array_to_rs | Verify after load |
| `GEOGRAPHY` | **Requires decision** | - | No native support |

### Code Generation Behavior

```yaml
pr_structure:
  - path: sql/ddl/redshift/{schema}_{table}.sql
    template: snowflake_to_redshift_ddl.sql.j2
    
  - path: sql/transform/{schema}_{table}_transform.sql
    template: snowflake_to_redshift_transform.sql.j2
    
  - path: spark/jobs/unload_load_{schema}_{table}.py
    template: snowflake_to_redshift_spark.py.j2
    
  - path: airflow/dags/migrate_{schema}_{table}.py
    template: snowflake_to_redshift_dag.py.j2
```

### Reconciliation Strategy Selection

```
ALWAYS use:
    strategy = "row_hash_plus_aggregates_plus_keydiff"
    
ADDITIONAL checks for Snowflake→Redshift:
    1. NULL count comparison per column
    2. Numeric SUM comparison with tolerance (for floating point)
    3. Timestamp comparison (verify timezone conversion)
    4. VARIANT/SUPER JSON path sampling
```

### Parallel Validation Workflow

```
FOR run_number IN 1..parallel_runs:
    1. Execute queries on both systems
    2. Compare:
        - Row counts
        - NULL counts per column
        - Numeric aggregates (SUM, AVG with epsilon)
        - Sampled row hashes
        - Key-diff for missing/extra rows
    3. Special validation:
        - VARIANT columns: sample JSON paths
        - Timestamps: verify UTC conversion
```

### Cutover Workflow

```
PRE-CUTOVER:
    1. Verify Redshift cluster performance acceptable
    2. Run query performance comparison
    3. Update BI tool connections (test mode)
    4. Prepare connection string swap
    
CUTOVER:
    1. Final incremental sync
    2. Final reconciliation
    3. Swap BI/application connections to Redshift
    4. Verify dashboards/reports function correctly
    5. Monitor query performance for 24 hours
    
ROLLBACK:
    1. Swap connections back to Snowflake
    2. Verify functionality
    3. Analyze failure cause
```

---

## 4.4 Archetype 4: Data Lake → Delta/Iceberg

### Entry Conditions
- [ ] Source is existing data lake (S3/ADLS/GCS with Parquet/ORC/Avro)
- [ ] Target format is Delta Lake or Apache Iceberg
- [ ] Catalog service available (Unity Catalog, Glue, Hive, Nessie)
- [ ] Compute available (Spark, Databricks, EMR)

### Required Metadata
```json
{
  "archetype_id": "lake_to_delta_iceberg",
  "source_config": {
    "type": "s3_parquet",
    "bucket": "data-lake-raw",
    "prefix": "tables/",
    "catalog": "glue",
    "secret_ref": "vault://aws/readonly"
  },
  "target_config": {
    "type": "delta",
    "catalog": "unity_catalog",
    "database": "bronze",
    "storage_path": "s3://data-lake-delta/",
    "secret_ref": "vault://databricks/migrate"
  },
  "schema_evolution": {
    "allow_column_adds": true,
    "allow_type_widening": true,
    "allow_column_drops": false,
    "allow_renames": false
  },
  "performance_requirements": {
    "query_latency_p99_ms": 5000,
    "concurrent_readers": 100,
    "partition_pruning_required": true
  }
}
```

### Profiling Steps (EP Jobs)

| Step | Job | Input | Output | Checkpoint |
|------|-----|-------|--------|------------|
| 4.1 | `lake_file_inventory` | source_config | file_inventory.json | Yes |
| 4.2 | `lake_schema_inference` | file_inventory | schema_report.json | Yes |
| 4.3 | `lake_partition_analysis` | file_inventory | partition_analysis.json | Yes |
| 4.4 | `lake_file_size_analysis` | file_inventory | file_size_analysis.json | No |
| 4.5 | `lake_query_pattern_analysis` | query_logs | query_patterns.json | No |

### Schema Evolution Rules

| Scenario | Delta Support | Iceberg Support | Handling |
|----------|---------------|-----------------|----------|
| Add nullable column | Yes | Yes | Auto-allow |
| Add non-nullable column | With default | With default | **Requires decision** |
| Widen INT→BIGINT | Yes | Yes | Auto-allow |
| Widen FLOAT→DOUBLE | Yes | Yes | Auto-allow |
| Narrow type | No | No | **Block** |
| Rename column | Mapping only | Yes (via metadata) | **Requires decision** |
| Drop column | Soft delete | Yes | **Block without approval** |
| Change partition scheme | Rewrite required | Via partition evolution | See below |

### Partition Strategy Change Rules

| Source Partition | Target Partition | Delta Handling | Iceberg Handling |
|-----------------|------------------|----------------|------------------|
| Unpartitioned | Partitioned | Rewrite all data | Partition evolution |
| Daily | Monthly | Rewrite data | Partition evolution |
| Single column | Compound | Rewrite data | Partition evolution |
| Compound | Single | Rewrite data | Partition evolution |

### Performance Parity Checks

```yaml
performance_validation:
  - check: query_latency
    queries:
      - name: point_lookup
        template: "SELECT * FROM {table} WHERE {pk} = {value}"
        baseline_source_ms: null  # Measured
        target_tolerance_pct: 20
        
      - name: partition_scan
        template: "SELECT COUNT(*) FROM {table} WHERE {partition_col} = {value}"
        baseline_source_ms: null
        target_tolerance_pct: 20
        
      - name: full_scan_aggregate
        template: "SELECT SUM({numeric_col}) FROM {table}"
        baseline_source_ms: null
        target_tolerance_pct: 50  # More tolerance for full scans
        
  - check: concurrent_readers
    test_concurrency: [10, 50, 100]
    max_degradation_pct: 30
    
  - check: file_layout
    expected_avg_file_size_mb: [128, 1024]  # Min/max
    max_small_files_pct: 5
```

### Code Generation Behavior

```yaml
pr_structure:
  # For Delta Lake
  - path: delta/migrations/{table}_initial.py
    template: lake_to_delta_initial.py.j2
    
  - path: delta/maintenance/{table}_optimize.py
    template: delta_optimize.py.j2
    
  # For Iceberg
  - path: iceberg/migrations/{table}_initial.py
    template: lake_to_iceberg_initial.py.j2
    
  - path: iceberg/maintenance/{table}_compact.py
    template: iceberg_compact.py.j2
    
  # Common
  - path: airflow/dags/migrate_{table}.py
    template: lake_to_lakehouse_dag.py.j2
    
  - path: configs/{table}_config.yml
    template: migration_config.yml.j2
```

### Reconciliation Strategy Selection

```
strategy = "row_hash_plus_aggregates"

ADDITIONAL for lakehouse migrations:
    1. File count and size distribution comparison
    2. Partition metadata comparison
    3. Schema version tracking
    4. Time travel verification (can query historical versions)
    5. Performance benchmark comparison
```

### Parallel Validation Workflow

```
FOR run_number IN 1..parallel_runs:
    1. Compare row counts
    2. Compare partition inventories
    3. Sample row hashes
    4. Run performance benchmarks
    5. Verify ACID properties:
        - Concurrent read during write
        - Time travel queries
        - Schema evolution handling
```

### Cutover Workflow

```
PRE-CUTOVER:
    1. Verify all data migrated
    2. Run performance benchmarks
    3. Register tables in target catalog
    4. Update downstream jobs to use new format
    5. Test query compatibility
    
CUTOVER:
    1. Final sync of incremental changes
    2. Update catalog entries to point to Delta/Iceberg
    3. Verify downstream jobs function
    4. Archive source files (do not delete immediately)
    
ROLLBACK:
    1. Revert catalog entries
    2. Revert downstream job configurations
    3. Verify source files accessible
```

