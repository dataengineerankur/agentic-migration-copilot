from typing import Any, Dict, List, Optional

from ..services.activity import ActivityLogger
from ..services.mapping import infer_mapping
from ..services.airflow_parser import parse_airflow_file
from .indexing_agent import IndexingResult


class MockAgentRunner:
    def __init__(self, activity: ActivityLogger) -> None:
        self.activity = activity

    def run(
        self,
        *,
        dag_sources: Dict[str, str],
        requirements_texts: Dict[str, str],
        project_name: str,
        dag_requirements_texts: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> "AgenticOutput":
        from .orchestrator import AgenticOutput

        self.activity.log("Requirements", "Mock summarizing requirements.")
        summary = "Mock mode: no external requirements provided."
        if requirements_texts:
            summary = "Mock mode: summarized external requirements."

        self.activity.log("Index", "Mock indexing DAG code.")
        parsed_dags = [parse_airflow_file(path, content) for path, content in dag_sources.items()]
        index_results: List[IndexingResult] = []
        for dag in parsed_dags:
            index_results.append(
                IndexingResult(
                    dag_id=dag.dag_id or "unknown_dag",
                    schedule_interval=dag.schedule_interval,
                    task_count=len(dag.tasks),
                    operator_summary={},
                    dependencies=[{"upstream": u, "downstream": d} for u, d in dag.dependencies],
                    task_graph={},
                    code_index={},
                    raw={"dag_id": dag.dag_id or "unknown_dag"},
                )
            )

        self.activity.log("Plan", "Mock mapping tasks to patterns.")
        mapping_results: List[Dict[str, Any]] = []
        for dag in parsed_dags:
            mappings: List[Dict[str, Any]] = []
            for task_id, task in dag.tasks.items():
                mapping = infer_mapping(task_id, task.operator, task.params)
                mappings.append(mapping.__dict__)
            mapping_results.append({"dag_id": dag.dag_id or "unknown_dag", "mappings": mappings, "assumptions": []})

        assumptions: List[str] = ["Mock mode used; replace with LLM provider for real mapping."]

        self.activity.log("Generate", "Mock generating notebooks and databricks.yml.")
        notebooks = [
            {"dag_id": mr["dag_id"], "notebook_name": m["notebook_name"], "code": ""}
            for mr in mapping_results
            for m in mr["mappings"]
        ]
        codegen = {"utils": {}, "notebooks": notebooks, "databricks_yml": ""}

        self.activity.log("Done", "Mock agentic migration complete.")

        return AgenticOutput(
            requirements_summary=summary,
            assumptions=assumptions,
            index_results=index_results,
            mapping_results=mapping_results,
            codegen=codegen,
            validation=None,
        )
