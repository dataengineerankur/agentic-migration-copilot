import json
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from .mapping import TaskMapping, _stage_prefix


def render_notebook(mapping: TaskMapping, params: Dict[str, str]) -> str:
    header = "# Databricks notebook source\n"
    body = "\n".join(
        [
            "import json",
            "from pyspark.sql import functions as F",
            "",
            "def main():",
            f"    task_id = {json.dumps(mapping.task_id)}",
            f"    params = {json.dumps(params, indent=2)}",
            f"    pattern = {json.dumps(mapping.pattern)}",
            "    # TODO: replace placeholders with real connections and logic",
            "",
            _render_stage_snippet(mapping, params),
            "",
            "if __name__ == \"__main__\":",
            "    main()",
            "",
        ]
    )
    return header + body


def render_ipynb(mapping: TaskMapping, params: Dict[str, str]) -> Dict[str, object]:
    return {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": render_notebook(mapping, params).splitlines(keepends=True),
            }
        ],
        "metadata": {"language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def build_workflow(
    project_name: str,
    mappings: Iterable[TaskMapping],
    dependencies: List[Dict[str, List[str]]],
    notebook_root: str,
) -> Dict[str, object]:
    dep_map: Dict[str, List[str]] = {}
    for item in dependencies:
        dep_map.setdefault(item["task_id"], [])
        dep_map[item["task_id"]].extend(item["depends_on"])

    tasks = []
    for mapping in mappings:
        task = {
            "task_key": mapping.task_id,
            "notebook_task": {
                "notebook_path": f"{notebook_root}/{mapping.notebook_name}",
                "base_parameters": {"task_id": mapping.task_id},
            },
            "depends_on": [
                {"task_key": dep} for dep in sorted(set(dep_map.get(mapping.task_id, [])))
            ],
        }
        tasks.append(task)

    return {
        "name": project_name,
        "format": "MULTI_TASK",
        "new_cluster": {
            "spark_version": "13.3.x-scala2.12",
            "node_type_id": "i3.xlarge",
            "num_workers": 2,
        },
        "tasks": tasks,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def build_activity_feed(mappings: Iterable[TaskMapping]) -> List[Dict[str, str]]:
    feed: List[Dict[str, str]] = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "Discovery complete",
            "detail": "Airflow DAGs indexed and task graph assembled.",
        },
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "Mapping complete",
            "detail": "Airflow operators mapped to Databricks patterns.",
        },
    ]
    for mapping in mappings:
        feed.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": f"Notebook drafted for {mapping.task_id}",
                "detail": mapping.pattern,
            }
        )
    return feed


def _render_stage_snippet(mapping: TaskMapping, params: Dict[str, str]) -> str:
    stage = _stage_prefix(mapping.stage)
    if stage == "00_ingest":
        return "\n".join(
            [
                "    # Example ingest pattern",
                "    df = (",
                "        spark.read",
                "        .format(\"jdbc\")",
                "        .option(\"url\", \"{{secrets/jdbc_url}}\")",
                "        .option(\"dbtable\", params.get(\"source_table\", \"<source_table>\"))",
                "        .load()",
                "    )",
                "    df.write.format(\"delta\").mode(\"overwrite\").saveAsTable(\"<target_table>\")",
            ]
        )
    if stage == "10_transform":
        return "\n".join(
            [
                "    # Example transform pattern",
                "    df = spark.table(\"<source_table>\")",
                "    df = df.withColumn(\"processed_at\", F.current_timestamp())",
                "    df.write.format(\"delta\").mode(\"overwrite\").saveAsTable(\"<target_table>\")",
            ]
        )
    if stage == "20_quality":
        return "\n".join(
            [
                "    # Example quality checks",
                "    df = spark.table(\"<target_table>\")",
                "    total_rows = df.count()",
                "    if total_rows == 0:",
                "        raise ValueError(\"Quality check failed: zero rows\")",
            ]
        )
    return "\n".join(
        [
            "    # Example publish pattern",
            "    df = spark.table(\"<curated_table>\")",
            "    df.write.format(\"delta\").mode(\"overwrite\").saveAsTable(\"<published_table>\")",
        ]
    )
