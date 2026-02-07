# DAG Report: unknown_dag

- Schedule: Not detected
- Tasks: 3

## Task Conversions
- extract_inventory (PythonOperator) -> python_notebook_task (transform)
- transform_inventory (BashOperator) -> python_notebook_task (transform)
- load_inventory (PythonOperator) -> python_notebook_task (transform)
