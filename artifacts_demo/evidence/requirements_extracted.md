# Extracted Requirements

## Sources
- None detected

## Sinks
- delta
- snowflake

## Schedules
- "0 */6 * * *",
- "0 2 * * *",
- "15 4 * * *",
- "30 1 * * *",

## Notes
- None

## Raw Requirements
- from datetime import datetime, timedelta
- from airflow import DAG
- from airflow.operators.python import PythonOperator
- from datetime import datetime, timedelta
- from airflow import DAG
- from airflow.operators.python import PythonOperator
- from datetime import datetime, timedelta
- from airflow import DAG
- from airflow.operators.bash import BashOperator
- from airflow.operators.python import PythonOperator
- from datetime import datetime, timedelta
- from airflow import DAG
- from airflow.operators.bash import BashOperator
- from airflow.operators.python import PythonOperator
