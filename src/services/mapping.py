from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TaskMapping:
    task_id: str
    operator: str
    pattern: str
    stage: str
    notebook_name: str
    source: Optional[str] = None
    sink: Optional[str] = None
    assumptions: List[str] = field(default_factory=list)


def default_mapping_rules() -> Dict[str, Dict[str, str]]:
    return {
        "sqoop": {
            "pattern": "jdbc_ingest_delta",
            "stage": "ingest",
            "description": "Sqoop jobs mapped to JDBC read/write + Delta.",
        },
        "hdfs": {
            "pattern": "hdfs_to_cloud_copy",
            "stage": "ingest",
            "description": "HDFS to cloud storage via copy/Auto Loader.",
        },
        "hive": {
            "pattern": "spark_sql_transform",
            "stage": "transform",
            "description": "Hive/Impala SQL mapped to Spark SQL.",
        },
        "bash": {
            "pattern": "python_notebook_task",
            "stage": "transform",
            "description": "Bash scripts translated into Python notebooks.",
        },
        "python": {
            "pattern": "python_notebook_task",
            "stage": "transform",
            "description": "Python operators mapped to Python notebooks.",
        },
        "kafka": {
            "pattern": "structured_streaming",
            "stage": "ingest",
            "description": "Kafka streams mapped to Structured Streaming + Delta.",
        },
        "quality": {
            "pattern": "data_quality_checks",
            "stage": "quality",
            "description": "Quality checks mapped to validation notebooks.",
        },
        "publish": {
            "pattern": "publish_delta_or_table",
            "stage": "publish",
            "description": "Publish steps mapped to curated Delta tables.",
        },
        "generic": {
            "pattern": "generic_notebook_task",
            "stage": "transform",
            "description": "Unknown operators mapped to generic notebooks.",
        },
    }


def infer_mapping(task_id: str, operator: str, params: Dict[str, str]) -> TaskMapping:
    text_blob = " ".join([operator] + list(params.values())).lower()
    rules = default_mapping_rules()
    assumptions: List[str] = []

    def pick(rule_key: str) -> TaskMapping:
        rule = rules[rule_key]
        stage = rule["stage"]
        notebook_name = f"{_stage_prefix(stage)}_{_slug(task_id)}.py"
        return TaskMapping(
            task_id=task_id,
            operator=operator,
            pattern=rule["pattern"],
            stage=stage,
            notebook_name=notebook_name,
            assumptions=assumptions,
        )

    if "sqoop" in text_blob or "oracle" in text_blob:
        return pick("sqoop")
    if "hdfs" in text_blob or "adls" in text_blob or "s3" in text_blob or "gcs" in text_blob:
        return pick("hdfs")
    if "hive" in text_blob or "impala" in text_blob or "sql" in text_blob:
        return pick("hive")
    if "bash" in text_blob:
        return pick("bash")
    if "python" in text_blob:
        return pick("python")
    if "kafka" in text_blob or "stream" in text_blob:
        return pick("kafka")
    if "quality" in text_blob or "validate" in text_blob or "check" in text_blob:
        return pick("quality")
    if "publish" in text_blob or "load" in text_blob or "sink" in text_blob:
        return pick("publish")

    assumptions.append("Operator mapping inferred as generic notebook; review required.")
    return pick("generic")


def _slug(value: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in value).strip("_")


def _stage_prefix(stage: str) -> str:
    return {
        "ingest": "00_ingest",
        "transform": "10_transform",
        "quality": "20_quality",
        "publish": "30_publish",
    }.get(stage, "10_transform")
