from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..services.indexer import index_airflow_file


@dataclass
class IndexingResult:
    dag_id: str
    schedule_interval: Optional[str]
    task_count: int
    operator_summary: Dict[str, int]
    dependencies: List[Dict[str, str]]
    task_graph: Dict[str, Any]
    code_index: Dict[str, Any]
    raw: Dict[str, Any]


class IndexingAgent:
    def run(self, *, file_path: str, content: str) -> IndexingResult:
        payload = index_airflow_file(file_path, content)
        return IndexingResult(
            dag_id=payload["dag_id"],
            schedule_interval=payload.get("schedule_interval"),
            task_count=len(payload.get("tasks", [])),
            operator_summary=payload.get("operator_summary", {}),
            dependencies=payload.get("dependencies", []),
            task_graph=payload.get("task_graph", {}),
            code_index=payload.get("code_index", {}),
            raw=payload,
        )
