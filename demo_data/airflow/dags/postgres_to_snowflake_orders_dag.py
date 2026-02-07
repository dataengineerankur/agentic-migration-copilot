from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator


def extract_orders(**_kwargs):
    print("Extract orders from Postgres: public.orders")


def load_to_snowflake(**_kwargs):
    print("Load orders into Snowflake: RAW.ORDERS")


default_args = {
    "owner": "data-eng",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="postgres_to_snowflake_orders",
    default_args=default_args,
    schedule_interval="0 2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    extract = PythonOperator(
        task_id="extract_orders",
        python_callable=extract_orders,
    )

    transform = BashOperator(
        task_id="transform_orders",
        bash_command="python /opt/airflow/scripts/transform_orders.py",
    )

    load = PythonOperator(
        task_id="load_orders",
        python_callable=load_to_snowflake,
    )

    extract >> transform >> load
