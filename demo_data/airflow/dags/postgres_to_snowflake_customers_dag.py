from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


def extract_customers(**_kwargs):
    print("Extract customers from Postgres: public.customers")


def quality_check(**_kwargs):
    print("Check customers row count and nulls")


def load_customers(**_kwargs):
    print("Load customers into Snowflake: RAW.CUSTOMERS")


default_args = {
    "owner": "analytics",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="postgres_to_snowflake_customers",
    default_args=default_args,
    schedule_interval="30 1 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    extract = PythonOperator(
        task_id="extract_customers",
        python_callable=extract_customers,
    )

    quality = PythonOperator(
        task_id="quality_customers",
        python_callable=quality_check,
    )

    load = PythonOperator(
        task_id="load_customers",
        python_callable=load_customers,
    )

    extract >> quality >> load
