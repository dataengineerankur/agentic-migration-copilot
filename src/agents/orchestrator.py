from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..llm.client import LLMClient
from ..llm.settings import LLMSettings
from ..services.activity import ActivityLogger
from .agents import CodegenAgent, MappingAgent, RequirementsAgent
from .indexing_agent import IndexingAgent, IndexingResult
from .mock import MockAgentRunner
from .validation_agent import ValidationResult


@dataclass
class AgenticOutput:
    requirements_summary: str
    assumptions: List[str]
    index_results: List[IndexingResult]
    mapping_results: List[Dict[str, Any]]
    codegen: Dict[str, Any]
    validation: Optional[ValidationResult]


class AgentOrchestrator:
    def __init__(
        self,
        *,
        settings: LLMSettings,
        activity: ActivityLogger,
    ) -> None:
        self.settings = settings
        self.activity = activity

    def run(
        self,
        *,
        dag_sources: Dict[str, str],
        requirements_texts: Dict[str, str],
        project_name: str,
    ) -> AgenticOutput:
        try:
            if self.settings.agent_mode.lower() == "mock":
                return MockAgentRunner(self.activity).run(
                    dag_sources=dag_sources,
                    requirements_texts=requirements_texts,
                    project_name=project_name,
                )

            llm = LLMClient(self.settings)
            self.activity.log("Analyze", "Summarizing external instructions (if any).")
            requirements = RequirementsAgent(llm).run(requirement_texts=requirements_texts)

            index_agent = IndexingAgent()
            index_results: List[IndexingResult] = []
            for path, content in dag_sources.items():
                self.activity.log("Index", f"Indexing DAG {path}.")
                index_results.append(index_agent.run(file_path=path, content=content))

            mapping_agent = MappingAgent(llm)
            mapping_results: List[Dict[str, Any]] = []
            for index_result in index_results:
                self.activity.log("Analyze", f"Analyzing DAG {index_result.dag_id}.", dag_id=index_result.dag_id)
                self.activity.log("Plan", f"Planning migration for {index_result.dag_id}.", dag_id=index_result.dag_id)
                mapping = mapping_agent.run(
                    dag_id=index_result.dag_id,
                    index_payload=index_result.raw,
                    requirements_summary=requirements.summary,
                )
                mapping_results.append(
                    {"dag_id": mapping.dag_id, "mappings": mapping.mappings, "assumptions": mapping.assumptions}
                )

            self.activity.log("Generate", "Generating notebooks, utils, and databricks.yml.")
            codegen_agent = CodegenAgent(llm)
            codegen = codegen_agent.run(
                project_name=project_name,
                index_payloads=[result.raw for result in index_results],
                mapping_payloads=mapping_results,
                requirements_summary=requirements.summary,
            )

            assumptions = requirements.assumptions[:]
            for mapping in mapping_results:
                assumptions.extend(mapping.get("assumptions", []))
            assumptions.extend(codegen.assumptions)

            self.activity.log("Done", "Agentic migration complete.")
            return AgenticOutput(
                requirements_summary=requirements.summary,
                assumptions=assumptions,
                index_results=index_results,
                mapping_results=mapping_results,
                codegen={
                    "utils": codegen.utils,
                    "notebooks": codegen.notebooks,
                    "databricks_yml": codegen.databricks_yml,
                },
                validation=None,
            )
        except Exception as exc:  # noqa: BLE001
            self.activity.log("Failed", f"Agentic migration failed: {exc}")
            raise
