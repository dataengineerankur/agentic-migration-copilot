# DAG Report: postgres_to_snowflake_orders

- Schedule: 0 2 * * *
- Tasks: 3

## Task Conversions
- extract_orders (PythonOperator) -> python_notebook_task (transform)
- transform_orders (BashOperator) -> python_notebook_task (transform)
- load_orders (PythonOperator) -> python_notebook_task (transform)
