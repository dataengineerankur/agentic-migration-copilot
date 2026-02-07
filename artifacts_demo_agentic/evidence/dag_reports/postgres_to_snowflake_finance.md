# DAG Report: postgres_to_snowflake_finance

- Schedule: 15 4 * * *
- Tasks: 3

## Task Conversions
- extract_finance (PythonOperator) -> python_notebook_task (transform)
- transform_finance (PythonOperator) -> python_notebook_task (transform)
- publish_finance (PythonOperator) -> python_notebook_task (transform)
