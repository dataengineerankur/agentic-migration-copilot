# DAG Report: postgres_to_snowflake_customers

- Schedule: 30 1 * * *
- Tasks: 3

## Task Conversions
- extract_customers (PythonOperator) -> python_notebook_task (transform)
- quality_customers (PythonOperator) -> python_notebook_task (transform)
- load_customers (PythonOperator) -> python_notebook_task (transform)
