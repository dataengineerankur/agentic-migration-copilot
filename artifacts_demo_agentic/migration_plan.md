# Migration Plan

Generated: 2026-02-05T00:01:32.540823+00:00

## Inputs
- Sources: None detected
- Sinks: delta, snowflake

## Task Mapping
- extract_finance (PythonOperator) -> python_notebook_task (transform)
- transform_finance (PythonOperator) -> python_notebook_task (transform)
- publish_finance (PythonOperator) -> python_notebook_task (transform)
- extract_customers (PythonOperator) -> python_notebook_task (transform)
- quality_customers (PythonOperator) -> python_notebook_task (transform)
- load_customers (PythonOperator) -> python_notebook_task (transform)
- extract_orders (PythonOperator) -> python_notebook_task (transform)
- transform_orders (BashOperator) -> python_notebook_task (transform)
- load_orders (PythonOperator) -> python_notebook_task (transform)
- extract_inventory (PythonOperator) -> python_notebook_task (transform)
- transform_inventory (BashOperator) -> python_notebook_task (transform)
- load_inventory (PythonOperator) -> python_notebook_task (transform)

## Workflow
- Databricks workflow JSON generated in artifacts/workflows/workflow.json
- Notebook drafts generated in artifacts/notebooks/

## Evidence
- requirements_extracted.md, assumptions.md, validation_report.md
