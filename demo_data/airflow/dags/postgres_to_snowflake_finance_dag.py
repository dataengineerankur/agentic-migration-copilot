from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


def extract_finance(**_kwargs):
    print("Extract finance data from Postgres: finance.transactions")


def transform_finance(**_kwargs):
    print("Transform finance data with business rules")


def publish_finance(**_kwargs):
    print("Publish finance into Snowflake: CURATED.FINANCE_TRANSACTIONS")


default_args = {
    "owner": "finance",
    "retries": 2,
    "retry_delay": timedelta(minutes=7),
}

with DAG(
    dag_id="postgres_to_snowflake_finance",
    default_args=default_args,
    schedule_interval="15 4 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    extract = PythonOperator(
        task_id="extract_finance",
        python_callable=extract_finance,
    )

    transform = PythonOperator(
        task_id="transform_finance",
        python_callable=transform_finance,
    )

    publish = PythonOperator(
        task_id="publish_finance",
        python_callable=publish_finance,
    )

    extract >> transform >> publish
