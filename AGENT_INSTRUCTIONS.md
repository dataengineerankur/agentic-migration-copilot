# Agent Instructions — Airflow → Databricks Workflow Migration

## Purpose
Build an agent-driven tool that migrates Airflow pipelines (including on‑prem HDFS/Oracle/Sqoop flows) to Databricks Workflows + Notebooks. The system must:
- ingest source/target specs (Confluence pages or text files),
- index and understand existing codebases,
- propose a migration plan,
- generate end‑to‑end Databricks notebooks (in `.py` source format) and workflow definitions,
- produce evidence/reports for review.

This document defines agent responsibilities, methodology, and required artifacts.

---

## Inputs (must support all)
### A) Confluence
- Page URL(s) with pipeline descriptions, dependencies, SLA, and data contracts.
- Agent must extract: sources, sinks, schedules, failure handling, data volumes, SLAs.

### B) Text Files
- Directory or file list containing:
  - Airflow DAGs (`*.py`)
  - Operator configs (YAML/JSON)
  - Runbooks (md/txt)
  - Data contracts/schema files

### C) PDF Specs
- One or more PDF documents containing:
  - pipeline overview, architecture, constraints, SLAs, business logic
  - data flow diagrams, data contracts, runbooks

---

## Outputs (must produce)
1) **Databricks Workflows** definition:
   - Jobs JSON (or DAB bundle) with tasks and dependencies.
2) **Databricks notebooks** in **`.py` format** (not `.ipynb`):
   - Grouped by logical stages (ingest, transform, quality, publish).
   - Only create notebooks when there is actual executable logic.
3) **Migration plan** (human‑readable):
   - mapping of Airflow tasks → Databricks tasks.
   - notebook grouping rationale and task clustering.
4) **Migration report** (step‑by‑step):
   - derived from PDF specs + source code analysis.
   - explicit steps, dependencies, and required changes.
5) **Evidence pack**:
   - extracted requirements, assumptions, mappings, and validation notes.

---

## Agent Methodology (must follow)
### 1) Discovery & Indexing (order matters)
- **PDF first**: extract goals, constraints, SLAs, data flow, and business rules.
- Index all provided repo paths (respect `.gitignore`).
- Parse Airflow DAGs and extract:
  - `DAG` definitions, `schedule_interval`, `default_args`, `tasks`, `dependencies`.
  - Operators (e.g., `BashOperator`, `PythonOperator`, `SqoopOperator`, custom ops).
- Build a **Task Graph**:
  - nodes = tasks
  - edges = dependencies
  - include retries, SLA, triggers

### 2) Source System Classification
Determine each task’s source/sink type:
- HDFS → ADLS
- Oracle → HDFS (Sqoop)
- HDFS → Oracle
- On‑prem scripts (Bash/Python)
- External sources (S3, REST, FTP)

### 3) Target Mapping Strategy (Generalized)
The agent must handle **any Airflow operator** and **any on‑prem/cloud data system** by decomposing each task into **I/O + compute + orchestration** and mapping to the best Databricks pattern available.

Minimum supported mappings (not exhaustive):
- **Sqoop (Oracle ↔ HDFS)** → Databricks JDBC read/write + Delta or external table + copy
- **HDFS → ADLS/S3/GCS** → Databricks copy/Auto Loader or cloud storage SDKs
- **RDBMS → lake** → JDBC/CDC ingestion + Delta
- **Bash/Python** → Databricks notebook with Python logic
- **Hive/Impala SQL** → Spark SQL / Databricks SQL
- **Kafka/Streaming** → Structured Streaming + Delta
- **Custom scripts** → Notebook + parameters + libraries

If an operator is unknown:
- derive its behavior from source code + runbook
- request human decision if behavior is ambiguous

Define mapping rules in **migration_rules.json**:
- operator/type → databricks pattern
- required secrets
- data movement, formats, and checkpoints

### 4) Notebook Planning & Generation (source `.py`)
**Notebook planning must be intelligent**:
- Cluster Airflow tasks into **logical stages** based on data flow and cohesion.
- Prefer **fewer notebooks** with clear stage boundaries instead of one‑per‑task.
- Create a notebook only if it contains executable logic; avoid empty placeholders.
- Document the grouping rationale in the migration plan.

Suggested notebook naming:
- `00_ingest_*.py` (ingestion from source)
- `10_transform_*.py`
- `20_quality_*.py` (basic data checks)
- `30_publish_*.py` (write to curated targets)

Notebook structure:
```
# Databricks notebook source
import ...

# COMMAND ----------
# parameters / widgets

# COMMAND ----------
# read

def main():
  # read
  # transform
  # write

# COMMAND ----------
# entrypoint

if __name__ == "__main__":
  main()
```

### 5) Workflow Definition
Create Databricks workflow JSON:
- tasks with `notebook_task`
- explicit dependencies
- cluster config (or existing_cluster_id)
- retry policy from Airflow if present

### 6) Validation & Evidence
Generate:
- `migration_plan.md`
- `migration_report.md`
- `task_mapping.json`
- `assumptions.md`
- `validation_report.md`

---

## Agent Collaboration Pattern
Agents communicate via shared artifacts (no direct system writes):

1) **Discovery Agent**
   - outputs task graph + extracted operator config
2) **Mapping Agent**
   - outputs mapping rules + task mapping
3) **Notebook Agent**
   - outputs notebook drafts + workflow definition
4) **Review Agent**
   - checks for gaps, unsafe assumptions, missing dependencies
5) **Evidence Agent**
   - compiles evidence pack and change summary

---

## Constraints & Safety Rules
- Do not execute production data operations.
- Do not require secrets; only reference named secrets (e.g., `{{secrets/oracle_pwd}}`).
- Avoid destructive operations unless explicitly allowed.
- Default to idempotent writes (overwrite with partitioning or merge).

---

## UI Requirements (Product/UX)
Provide a **visually appealing** UI that mirrors PATCHIT quality:
- **Animated progress timeline** for migration phases (Discovery → Mapping → Notebook → Workflow → Review → Done)
- **Color‑coded cards** per pipeline with status badges
- **Real‑time activity feed** of agent decisions and artifacts produced
- **Diff viewer** for generated notebooks/workflows
- **Toggle** for notebook output format (`.py` source vs `.ipynb`)
- **Export bundle** button (zip with notebooks + workflow + plan)
Animations should be smooth, not distracting; use short transitions for phase changes.

---

## Success Criteria
Migration is considered successful when:
- all Airflow tasks are mapped,
- Databricks workflow compiles,
- notebooks contain runnable logic,
- dependencies and schedule are preserved,
- evidence pack is complete.

