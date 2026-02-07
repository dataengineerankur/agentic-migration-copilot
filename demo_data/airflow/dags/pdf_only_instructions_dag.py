from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


def extract_pdf_only(**_kwargs):
    print("Refer to PDF instructions for source extraction details.")


def transform_pdf_only(**_kwargs):
    print("Refer to PDF instructions for transformation rules.")


def publish_pdf_only(**_kwargs):
    print("Refer to PDF instructions for target publish details.")


default_args = {
    "owner": "pdf_only",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="pdf_only_instructions",
    default_args=default_args,
    schedule_interval="0 6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    extract = PythonOperator(
        task_id="extract_pdf_only",
        python_callable=extract_pdf_only,
    )

    transform = PythonOperator(
        task_id="transform_pdf_only",
        python_callable=transform_pdf_only,
    )

    publish = PythonOperator(
        task_id="publish_pdf_only",
        python_callable=publish_pdf_only,
    )

    extract >> transform >> publish
