from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator


def extract_inventory(**_kwargs):
    print("Extract inventory from Postgres: public.inventory")


def load_inventory(**_kwargs):
    print("Load inventory into Snowflake: RAW.INVENTORY")


default_args = {
    "owner": "supply-chain",
    "retries": 3,
    "retry_delay": timedelta(minutes=3),
}

with DAG(
    dag_id="postgres_to_snowflake_inventory",
    default_args=default_args,
    schedule_interval="0 */6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    extract = PythonOperator(
        task_id="extract_inventory",
        python_callable=extract_inventory,
    )

    transform = BashOperator(
        task_id="transform_inventory",
        bash_command="python /opt/airflow/scripts/transform_inventory.py",
    )

    load = PythonOperator(
        task_id="load_inventory",
        python_callable=load_inventory,
    )

    extract >> transform >> load
