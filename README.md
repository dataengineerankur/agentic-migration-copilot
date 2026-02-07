# Agentic Migration Copilot

This project provides an agent‑driven system to migrate Airflow pipelines (including on‑prem HDFS/Oracle/Sqoop flows) into Databricks Workflows + Notebooks.

## What it does
- Ingests pipeline specs from **Confluence** or **text files**
- Indexes and understands existing Airflow codebases
- Generates Databricks notebooks (`.py` source format)
- Generates Databricks workflow definitions (jobs JSON or DAB)
- Produces evidence + migration plan for review

## Backend Flow (high level)
```
Input (Confluence/Text) → Indexer → Agents → Plan → Notebooks + Workflows → Evidence Pack
```

### Core backend steps
1) **Ingest**  
   - Confluence pages or text files are parsed into a normalized requirements model.
2) **Index & Parse**  
   - Airflow DAGs and operators are indexed.
   - Build a task graph with dependencies, retries, schedules.
3) **Map & Plan**  
   - Operators are mapped to Databricks patterns.
   - A migration plan is assembled with task mappings.
4) **Generate Code**  
   - Notebooks are created in `.py` format.
   - Workflow JSON is generated with task dependencies.
5) **Validate & Evidence**  
   - Output artifacts + assumptions + validation notes are compiled.

## Key outputs
```
databricks.yml
notebooks/<dag_id>/*.py
utils/
reports/<dag_id>/*
reports/index.html
```

## Agent Methodology
See `AGENT_INSTRUCTIONS.md` for the full agent contract, collaboration pattern, and safety rules.

## Notes for migration use‑cases
Typical mappings:
- Sqoop jobs → Databricks JDBC read/write + Delta
- HDFS → ADLS → Databricks Auto Loader
- Bash/Python ops → Databricks notebooks
- Hive/SQL → Spark SQL in notebooks

## Backend behavior (important)
- Agents run in **proposal mode** only (no production execution).
- Outputs are meant for review and approval before deployment.
- Secrets are referenced via placeholder names, never embedded.

## Quickstart
```
python -m src.cli \
  --input /path/to/airflow/dags /path/to/other/repos \
  --output /path/to/artifacts \
  --project-name my-airflow-migration \
  --notebook-format both
```

Outputs are written to `artifacts/`:
- `databricks.yml`
- `notebooks/<dag_name>/` (`.py` and optional `.ipynb`)
- `utils/` (shared modules)
- `reports/<dag_name>/` (plan, mappings, validation, code index)
- `reports/index.html` (UI dashboard)

## Prompt methodology
All agent prompts live under `src/prompts/templates/` and are loaded by the agents at runtime.
This includes:
- Meta + engineered instructions
- Negative prompts (what not to infer or generate)
- Strict no-inference guardrails (optional; see below)

### View the UI
```
cd /path/to/repo
python -m http.server 8000
```
Then open `http://localhost:8000/artifacts/reports/index.html`.

### UI Server (start migration from browser)
```
cd /path/to/repo
python -m src.ui_server --host 127.0.0.1 --port 8001
```
Open `http://127.0.0.1:8001/` to configure settings and start a migration.

In the UI:
- **Source paths** accepts multiple directories or files (one per line).
- Use this for DAG folders, external repos, or shared library code you want indexed.

## LLM Agent Settings
The CLI uses LLM-backed agents by default. Configure one of the providers below:

OpenRouter:
```
export AMC_AGENT_MODE=openrouter
export AMC_OPENROUTER_API_KEY=...
export AMC_OPENROUTER_MODEL=openai/gpt-5.2
```

Groq:
```
export AMC_AGENT_MODE=groq
export AMC_GROQ_API_KEY=...
export AMC_GROQ_MODEL=openai/gpt-oss-120b
```

Cursor Cloud Agents:
```
export AMC_AGENT_MODE=cursor
export AMC_CURSOR_API_KEY=...
export AMC_CURSOR_REPOSITORY=https://github.com/org/repo
export AMC_CURSOR_REF=main
```

In-house OpenAI-compatible service:
```
export AMC_AGENT_MODE=inhouse
export AMC_INHOUSE_AGENT_URL=https://llm.example.com/v1
export AMC_INHOUSE_API_KEY=...
export AMC_INHOUSE_MODEL=custom-model
export AMC_INHOUSE_HEADERS_JSON='{"X-Org":"my-org"}'
```

The in-house client supports:
- `/chat/completions` (OpenAI chat-style)
- `/completions` (OpenAI completions-style)
- Custom in-house endpoints with JSON headers

## Strict no-inference mode
If you want the agents to avoid any extrapolation and use only DAG code + external requirements:
```
export AMC_NO_INFERENCE=true
```
In the UI, enable **Strict no-inference mode** under Settings → Guardrails.

## Git repository setup (clean push)
Before creating a remote repo, remove local artifacts and secrets:
```
rm -rf var/ migration_output_demo/ artifacts/
```
Then initialize and push:
```
git init
git add .
git commit -m "Initial Agentic Migration Copilot"
git remote add origin <your-repo-url>
git push -u origin main
```

For offline testing only:
```
export AMC_AGENT_MODE=mock
export AMC_ALLOW_MOCK=true
```

