from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..llm.client import LLMClient
from ..llm.settings import LLMSettings
from ..services.activity import ActivityLogger
from .agents import CodegenAgent, MappingAgent, PdfRequirementsAgent, RequirementsAgent
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
        dag_requirements_texts: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> AgenticOutput:
        try:
            if self.settings.agent_mode.lower() == "mock":
                return MockAgentRunner(self.activity).run(
                    dag_sources=dag_sources,
                    requirements_texts=requirements_texts,
                    project_name=project_name,
                    dag_requirements_texts=dag_requirements_texts,
                )

            llm = LLMClient(self.settings)
            self.activity.log("Docs", "Reading external instructions (if any).")
            requirements = RequirementsAgent(llm).run(requirement_texts=requirements_texts)

            index_agent = IndexingAgent()
            index_results: List[IndexingResult] = []
            for path, content in dag_sources.items():
                self.activity.log("Index", f"Indexing DAG {path}.")
                index_results.append(index_agent.run(file_path=path, content=content))

            mapping_agent = MappingAgent(llm)
            mapping_results: List[Dict[str, Any]] = []
            for index_result in index_results:
                per_dag_requirements = None
                if dag_requirements_texts:
                    per_dag_requirements = dag_requirements_texts.get(index_result.dag_id)
                if self.settings.pdf_required and not per_dag_requirements:
                    raise ValueError(
                        f"PDF required but missing for {index_result.dag_id}."
                    )
                if per_dag_requirements:
                    combined_pdf = "\n\n".join(per_dag_requirements.values()).strip()
                    if not combined_pdf:
                        self.activity.log(
                            "Docs",
                            f"PDF instructions empty for {index_result.dag_id}.",
                            dag_id=index_result.dag_id,
                        )
                        raise ValueError(
                            f"PDF instructions empty or unreadable for {index_result.dag_id}."
                        )
                    self.activity.log(
                        "Docs",
                        f"Summarizing PDF instructions for {index_result.dag_id} ({len(combined_pdf)} chars).",
                        dag_id=index_result.dag_id,
                    )
                    dag_requirements = PdfRequirementsAgent(llm).run(
                        dag_id=index_result.dag_id,
                        requirement_texts=per_dag_requirements,
                    )
                    requirements_summary = f"PDF ONLY:\n{dag_requirements.summary}".strip()
                    assumptions = dag_requirements.assumptions[:]
                    pdf_text = combined_pdf
                else:
                    requirements_summary = requirements.summary
                    assumptions = requirements.assumptions[:]
                    pdf_text = ""
                self.activity.log("Analyze", f"Analyzing DAG {index_result.dag_id}.", dag_id=index_result.dag_id)
                self.activity.log("Plan", f"Planning migration for {index_result.dag_id}.", dag_id=index_result.dag_id)
                mapping = mapping_agent.run(
                    dag_id=index_result.dag_id,
                    index_payload=index_result.raw,
                    requirements_summary=requirements_summary,
                )
                mapping_results.append(
                    {
                        "dag_id": mapping.dag_id,
                        "mappings": mapping.mappings,
                        "assumptions": assumptions + mapping.assumptions,
                        "requirements_summary": requirements_summary,
                        "pdf_text": pdf_text,
                    }
                )

            self.activity.log("Generate", "Generating notebooks, utils, and databricks.yml.")
            codegen_agent = CodegenAgent(llm)
            combined_requirements = requirements.summary
            for mapping in mapping_results:
                rs = (mapping.get("requirements_summary") or "").strip()
                if rs and rs not in combined_requirements:
                    combined_requirements = f"{combined_requirements}\n\nDAG {mapping.get('dag_id')}:\n{rs}".strip()
            codegen = codegen_agent.run(
                project_name=project_name,
                index_payloads=[result.raw for result in index_results],
                mapping_payloads=mapping_results,
                requirements_summary=combined_requirements,
            )

            assumptions = []
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
