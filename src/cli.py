import argparse
import difflib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .agents.orchestrator import AgentOrchestrator
from .agents.validation_agent import ValidationAgent
from .llm.settings import LLMSettings
from .services.activity import ActivityLogger
from .services.airflow_parser import ParsedDAG, parse_airflow_file
from .services.ingest import ingest_inputs
from .services.mapping import TaskMapping, infer_mapping
from .utils.fs import ensure_dir, read_text, write_json, write_text


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agentic Migration Copilot - Airflow to Databricks"
    )
    parser.add_argument(
        "--input",
        nargs="+",
        required=True,
        help="File or directory paths containing Airflow DAGs and specs.",
    )
    parser.add_argument(
        "--output",
        default="artifacts",
        help="Output directory for generated artifacts.",
    )
    parser.add_argument("--project-name", default="airflow-migration")
    parser.add_argument("--confluence-url", default=None)
    parser.add_argument("--confluence-user", default=None)
    parser.add_argument("--confluence-token", default=None)
    parser.add_argument(
        "--notebook-format",
        choices=["py", "ipynb", "both"],
        default="py",
        help="Notebook output format.",
    )
    parser.add_argument(
        "--pdfs",
        default=None,
        help="Path to PDF instruction folder (PDF name must match dag_id).",
    )
    parser.add_argument(
        "--agent-mode",
        default=None,
        help="Override AMC_AGENT_MODE for LLM provider selection.",
    )
    args = parser.parse_args()

    output_root = os.path.abspath(args.output)
    ensure_dir(output_root)
    artifacts = build_migration_artifacts(
        inputs=args.input,
        output_root=output_root,
        project_name=args.project_name,
        confluence_url=args.confluence_url,
        confluence_user=args.confluence_user,
        confluence_token=args.confluence_token,
        notebook_format=args.notebook_format,
        agent_mode=args.agent_mode,
        pdfs_path=args.pdfs,
    )

    print("Migration artifacts generated:")
    for path in artifacts:
        print(f" - {path}")


def build_migration_artifacts(
    inputs: List[str],
    output_root: str,
    project_name: str,
    confluence_url: str,
    confluence_user: str,
    confluence_token: str,
    notebook_format: str,
    agent_mode: Optional[str],
    selected_dags: Optional[List[str]] = None,
    pdfs_path: Optional[str] = None,
) -> List[str]:
    generated: List[str] = []

    ingest_result, text_blobs = ingest_inputs(
        inputs,
        confluence_url=confluence_url,
        confluence_user=confluence_user,
        confluence_token=confluence_token,
    )

    dags: List[ParsedDAG] = []
    dag_sources: Dict[str, str] = {}
    for path, content in text_blobs.items():
        if path.endswith(".py"):
            parsed = parse_airflow_file(path, content)
            if parsed.has_dag_definition:
                dag_sources[path] = content
                dags.append(parsed)
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    pdfs_dir = pdfs_path or os.path.join(repo_root, "pdfs")
    ensure_dir(pdfs_dir)

    from .services.pdf_reader import load_pdf_instructions

    pdf_instructions, pdf_notes = load_pdf_instructions(
        pdfs_dir, [dag.dag_id or "" for dag in dags]
    )
    ingest_result.notes.extend(pdf_notes)


    if selected_dags:
        selected_set = set(selected_dags)
        dags = [dag for dag in dags if (dag.dag_id or "") in selected_set]
        dag_sources = {
            path: content
            for path, content in dag_sources.items()
            if (parse_airflow_file(path, content).dag_id or "") in selected_set
        }

    migration_root = output_root
    notebooks_root = os.path.join(migration_root, "notebooks")
    utils_root = os.path.join(migration_root, "utils")
    reports_root = os.path.join(migration_root, "reports")
    ensure_dir(notebooks_root)
    ensure_dir(utils_root)
    ensure_dir(reports_root)

    activity_path = os.path.join(reports_root, "activity.json")
    activity_logger = ActivityLogger(activity_path)

    settings = LLMSettings()
    if agent_mode:
        settings.agent_mode = agent_mode
    agent_configured = _is_agent_configured(settings)
    _assert_agent_configured(settings)

    activity_logger.log("Scan", "Scanning Airflow DAGs.")
    orchestrator = AgentOrchestrator(settings=settings, activity=activity_logger)
    agentic_output = orchestrator.run(
        dag_sources=dag_sources,
        requirements_texts={
            key: value
            for key, value in text_blobs.items()
            if key.endswith((".md", ".txt", ".json", ".yml", ".yaml"))
        },
        project_name=project_name,
        dag_requirements_texts={dag_id: {f"{dag_id}.pdf": text} for dag_id, text in pdf_instructions.items()},
    )

    index_results = agentic_output.index_results
    mapping_results = agentic_output.mapping_results
    codegen = agentic_output.codegen

    databricks_yml_path = os.path.join(migration_root, "databricks.yml")
    activity_logger.log("Generate", f"Generating databricks.yml at {databricks_yml_path}")
    write_text(databricks_yml_path, codegen.get("databricks_yml", ""))
    activity_logger.log("Generate", f"Generated databricks.yml at {databricks_yml_path}")
    generated.append(databricks_yml_path)

    utils_paths = write_utils(utils_root, codegen.get("utils", {}), activity_logger)
    generated.extend(utils_paths)

    notebook_paths = write_notebooks_agentic(
        notebooks_root, codegen.get("notebooks", []), notebook_format, activity_logger
    )
    generated.extend(notebook_paths)

    dag_reports = write_reports_per_dag(
        reports_root,
        index_results,
        mapping_results,
        ingest_result,
        agentic_output.assumptions,
    )
    generated.extend(dag_reports)

    session_path = os.path.join(reports_root, "session.json")
    session_payload = build_session_payload(
        migration_root,
        settings.agent_mode,
        agent_configured,
        index_results,
        mapping_results,
        inputs,
    )
    write_json(session_path, session_payload)
    generated.append(session_path)

    report_path = os.path.join(reports_root, "index.html")
    write_text(report_path, render_report_html(project_name))
    generated.append(report_path)
    write_ui_assets(reports_root)

    validation = ValidationAgent().run(
        root_path=migration_root,
        notebook_paths=[p for p in notebook_paths if p.endswith(".py")],
        utils_paths=utils_paths,
        databricks_yml_path=databricks_yml_path,
    )
    activity_logger.log("Validate", "Validation checks completed.")
    write_validation_reports(reports_root, validation, index_results)

    export_path = os.path.join(reports_root, "export_bundle.zip")
    write_export_bundle(export_path, migration_root)
    generated.append(export_path)

    per_dag_exports = write_per_dag_exports(migration_root, reports_root, index_results)
    generated.extend(per_dag_exports)

    generated.append(activity_path)

    return generated


def build_task_mappings(
    dags: List[ParsedDAG],
) -> Tuple[List[TaskMapping], List[Dict[str, List[str]]], List[str]]:
    mappings: List[TaskMapping] = []
    dependency_map: Dict[str, List[str]] = {}
    assumptions: List[str] = []

    for dag in dags:
        for task_id, task in dag.tasks.items():
            mapping = infer_mapping(task_id, task.operator, task.params)
            mappings.append(mapping)

        for upstream, downstream in dag.dependencies:
            dependency_map.setdefault(downstream, []).append(upstream)

        if not dag.schedule_interval:
            assumptions.append(
                f"DAG {dag.dag_id or '<unknown>'} missing schedule_interval."
            )

        assumptions.extend(dag.notes)

    dependencies = [
        {"task_id": task_id, "depends_on": sorted(set(depends_on))}
        for task_id, depends_on in dependency_map.items()
    ]
    return mappings, dependencies, assumptions


def build_dependencies(dags: List[ParsedDAG]) -> Tuple[List[Dict[str, List[str]]], List[str]]:
    dependency_map: Dict[str, List[str]] = {}
    assumptions: List[str] = []
    for dag in dags:
        for upstream, downstream in dag.dependencies:
            dependency_map.setdefault(downstream, []).append(upstream)
        if not dag.schedule_interval:
            assumptions.append(
                f"DAG {dag.dag_id or '<unknown>'} missing schedule_interval."
            )
        assumptions.extend(dag.notes)
    dependencies = [
        {"task_id": task_id, "depends_on": sorted(set(depends_on))}
        for task_id, depends_on in dependency_map.items()
    ]
    return dependencies, assumptions


def write_dag_reports(
    dags: List[ParsedDAG],
    mappings: List[TaskMapping],
    dag_reports_root: str,
) -> List[str]:
    reports: List[str] = []
    mapping_index = {mapping.task_id: mapping for mapping in mappings}
    for dag in dags:
        dag_id = dag.dag_id or "unknown_dag"
        lines = [
            f"# DAG Report: {dag_id}",
            "",
            f"- Schedule: {dag.schedule_interval or 'Not detected'}",
            f"- Tasks: {len(dag.tasks)}",
            "",
            "## Task Conversions",
        ]
        for task_id, task in dag.tasks.items():
            mapping = mapping_index.get(task_id)
            if mapping:
                lines.append(
                    f"- {task_id} ({task.operator}) -> {mapping.pattern} "
                    f"({mapping.stage})"
                )
            else:
                lines.append(f"- {task_id} ({task.operator}) -> No mapping found")
        lines.append("")
        report_path = os.path.join(dag_reports_root, f"{dag_id}.md")
        write_text(report_path, "\n".join(lines))
        reports.append(report_path)
    return reports


def write_dag_reports_llm(
    mappings: List[Dict[str, Any]],
    dags: List[ParsedDAG],
    dag_reports_root: str,
) -> List[str]:
    mapping_index = {mapping["task_id"]: mapping for mapping in mappings}
    reports: List[str] = []
    for dag in dags:
        dag_id = dag.dag_id or "unknown_dag"
        lines = [
            f"# DAG Report: {dag_id}",
            "",
            f"- Schedule: {dag.schedule_interval or 'Not detected'}",
            f"- Tasks: {len(dag.tasks)}",
            "",
            "## Task Conversions",
        ]
        for task_id, task in dag.tasks.items():
            mapping = mapping_index.get(task_id)
            if mapping:
                lines.append(
                    f"- {task_id} ({task.operator}) -> {mapping.get('pattern')} "
                    f"({mapping.get('stage')})"
                )
            else:
                lines.append(f"- {task_id} ({task.operator}) -> No mapping found")
        lines.append("")
        report_path = os.path.join(dag_reports_root, f"{dag_id}.md")
        write_text(report_path, "\n".join(lines))
        reports.append(report_path)
    return reports


def write_notebooks(
    mappings: List[TaskMapping], notebooks_root: str, notebook_format: str
) -> List[str]:
    generated: List[str] = []
    for mapping in mappings:
        if notebook_format in {"py", "both"}:
            path = os.path.join(notebooks_root, mapping.notebook_name)
            content = render_notebook(mapping, params={})
            write_text(path, content)
            generated.append(path)
        if notebook_format in {"ipynb", "both"}:
            ipynb_name = mapping.notebook_name.replace(".py", ".ipynb")
            path = os.path.join(notebooks_root, ipynb_name)
            payload = render_ipynb(mapping, params={})
            write_json(path, payload)
            generated.append(path)
    return generated


def write_notebooks_llm(
    notebooks: List[Dict[str, str]],
    notebooks_root: str,
    notebook_format: str,
) -> List[str]:
    generated: List[str] = []
    for notebook in notebooks:
        name = notebook["notebook_name"]
        code = notebook.get("code", "")
        if notebook_format in {"py", "both"}:
            path = os.path.join(notebooks_root, name)
            write_text(path, code)
            generated.append(path)
        if notebook_format in {"ipynb", "both"}:
            ipynb_name = name.replace(".py", ".ipynb")
            path = os.path.join(notebooks_root, ipynb_name)
            payload = render_ipynb_stub(code)
            write_json(path, payload)
            generated.append(path)
    return generated


def render_ipynb_stub(code: str) -> Dict[str, object]:
    return {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": code.splitlines(keepends=True),
            }
        ],
        "metadata": {"language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write_notebook_diffs(mappings: List[TaskMapping], diffs_root: str) -> None:
    baseline = "\n".join(
        [
            "# Databricks notebook source",
            "def main():",
            "    pass",
            "",
            "if __name__ == \"__main__\":",
            "    main()",
            "",
        ]
    )
    for mapping in mappings:
        diff_path = os.path.join(diffs_root, f"{mapping.notebook_name}.diff")
        notebook = render_notebook(mapping, params={})
        write_diff_file(diff_path, baseline, notebook)


def write_notebook_diffs_llm(notebooks: List[Dict[str, str]], diffs_root: str) -> None:
    baseline = "\n".join(
        [
            "# Databricks notebook source",
            "def main():",
            "    pass",
            "",
            "if __name__ == \"__main__\":",
            "    main()",
            "",
        ]
    )
    for notebook in notebooks:
        diff_path = os.path.join(diffs_root, f"{notebook['notebook_name']}.diff")
        write_diff_file(diff_path, baseline, notebook.get("code", ""))


def write_diff_file(path: str, original: str, updated: str) -> None:
    diff = difflib.unified_diff(
        original.splitlines(),
        updated.splitlines(),
        fromfile="baseline",
        tofile="generated",
        lineterm="",
    )
    write_text(path, "\n".join(diff) + "\n")


def format_requirements(result) -> str:
    lines = ["# Extracted Requirements", ""]
    lines.append("## Sources")
    lines.extend([f"- {source}" for source in result.sources] or ["- None detected"])
    lines.append("")
    lines.append("## Sinks")
    lines.extend([f"- {sink}" for sink in result.sinks] or ["- None detected"])
    lines.append("")
    lines.append("## Schedules")
    lines.extend([f"- {schedule}" for schedule in result.schedules] or ["- None detected"])
    lines.append("")
    lines.append("## Notes")
    lines.extend([f"- {note}" for note in result.notes] or ["- None"])
    lines.append("")
    lines.append("## Raw Requirements")
    lines.extend([f"- {req}" for req in result.requirements] or ["- None extracted"])
    lines.append("")
    return "\n".join(lines)


def format_assumptions(assumptions: List[str]) -> str:
    lines = ["# Assumptions", ""]
    if not assumptions:
        lines.append("- None")
    else:
        lines.extend([f"- {assumption}" for assumption in assumptions])
    lines.append("")
    return "\n".join(lines)


def format_validation_report(
    dags: List[ParsedDAG],
    mappings: List[TaskMapping],
    assumptions: List[str],
    ingest_result,
) -> str:
    unknown_mappings = [m for m in mappings if m.pattern == "generic_notebook_task"]
    lines = [
        "# Validation Report",
        "",
        f"- Total DAGs parsed: {len(dags)}",
        f"- Total tasks mapped: {len(mappings)}",
        f"- Unknown operator mappings: {len(unknown_mappings)}",
        f"- Assumptions recorded: {len(assumptions)}",
        f"- Sources detected: {', '.join(ingest_result.sources) or 'None'}",
        f"- Sinks detected: {', '.join(ingest_result.sinks) or 'None'}",
        "",
        "## Follow-ups",
        "- Review generic mappings and confirm operator behavior.",
        "- Validate schedules, retries, and SLA requirements.",
        "",
    ]
    return "\n".join(lines)


def format_validation_report_llm(
    dags: List[Any],
    mappings: List[Dict[str, Any]],
    assumptions: List[str],
    ingest_result,
) -> str:
    unknown_mappings = [
        m
        for m in mappings
        if str(m.get("pattern", "")).lower() in {"generic_notebook_task", "generic"}
    ]
    lines = [
        "# Validation Report",
        "",
        f"- Total DAGs parsed: {len(dags)}",
        f"- Total tasks mapped: {len(mappings)}",
        f"- Unknown operator mappings: {len(unknown_mappings)}",
        f"- Assumptions recorded: {len(assumptions)}",
        f"- Sources detected: {', '.join(ingest_result.sources) or 'None'}",
        f"- Sinks detected: {', '.join(ingest_result.sinks) or 'None'}",
        "",
        "## Follow-ups",
        "- Review LLM mappings and confirm operator behavior.",
        "- Validate schedules, retries, and SLA requirements.",
        "",
    ]
    return "\n".join(lines)


def format_migration_plan(
    dags: List[ParsedDAG], mappings: List[TaskMapping], ingest_result
) -> str:
    lines = [
        "# Migration Plan",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Inputs",
        f"- Sources: {', '.join(ingest_result.sources) or 'None detected'}",
        f"- Sinks: {', '.join(ingest_result.sinks) or 'None detected'}",
        "",
        "## Task Mapping",
    ]
    for mapping in mappings:
        lines.append(
            f"- {mapping.task_id} ({mapping.operator}) -> {mapping.pattern} "
            f"({mapping.stage})"
        )
    lines.extend(
        [
            "",
            "## Workflow",
            "- Databricks Asset Bundle generated in databricks.yml",
            "- Notebook drafts generated in notebooks/<dag_name>/",
            "",
            "## Evidence",
            "- task_mapping.json, assumptions.md, validation_report.md",
            "",
        ]
    )
    return "\n".join(lines)


def format_migration_plan_llm(
    dags: List[Any], mappings: List[Dict[str, Any]], ingest_result
) -> str:
    lines = [
        "# Migration Plan",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Inputs",
        f"- Sources: {', '.join(ingest_result.sources) or 'None detected'}",
        f"- Sinks: {', '.join(ingest_result.sinks) or 'None detected'}",
        "",
        "## Task Mapping",
    ]
    for mapping in mappings:
        lines.append(
            f"- {mapping.get('task_id')} ({mapping.get('operator')}) -> {mapping.get('pattern')} "
            f"({mapping.get('stage')})"
        )
    lines.extend(
        [
            "",
            "## Workflow",
            "- Databricks workflow JSON generated in artifacts/workflows/workflow.json",
            "- Notebook drafts generated in artifacts/notebooks/",
            "",
            "## Evidence",
            "- requirements_extracted.md, assumptions.md, validation_report.md",
            "",
        ]
    )
    return "\n".join(lines)


def render_report_html(project_name: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{project_name} Migration</title>
    <link rel="stylesheet" href="./ui.css" />
  </head>
  <body>
    <div class="layout">
      <aside class="sidebar">
        <div class="sidebar-header">
          <h1>Airflow DAGs</h1>
          <div class="source-info">
            <span>Source</span>
            <div id="source-paths">—</div>
          </div>
          <div class="source-inputs">
            <input id="source-input" type="text" placeholder="Local DAG folder path" />
            <input id="output-input" type="text" placeholder="Output folder path" />
            <input id="project-input" type="text" placeholder="Project name" />
          </div>
          <input id="dag-search" type="text" placeholder="Search DAGs" />
          <select id="status-filter">
            <option value="all">All statuses</option>
            <option value="Not Started">Not Started</option>
            <option value="In Progress">In Progress</option>
            <option value="Migrated">Migrated</option>
            <option value="Needs Review">Needs Review</option>
            <option value="Failed">Failed</option>
          </select>
        </div>
        <ul id="dag-list" class="dag-list"></ul>
      </aside>
      <main class="main">
        <header class="topbar">
          <div>
            <h2>Migration Session</h2>
            <p id="session-subtitle">Scan → Index → Analyze → Plan → Generate → Validate → Done</p>
          </div>
          <div class="topbar-actions">
            <button id="migrate-btn" class="primary" disabled>Migrate</button>
            <button id="settings-btn" class="ghost">Settings</button>
          </div>
        </header>
        <section class="timeline" id="timeline"></section>
        <section class="session">
          <div class="summary-card">
            <h3>Selected DAG Summary</h3>
            <div id="dag-summary"></div>
            <div id="dag-warnings" class="warnings"></div>
          </div>
          <div class="activity-card">
            <h3>Activity Feed</h3>
            <ul id="activity-feed"></ul>
          </div>
        </section>
      </main>
      <aside class="output-panel">
        <h2>Databricks Output</h2>
        <div class="output-block">
          <label>Workflow Name</label>
          <div id="workflow-name">—</div>
        </div>
        <div class="output-block">
          <label>Output Location</label>
          <div class="output-path">
            <span id="output-path">—</span>
            <button id="copy-path" class="ghost">Copy</button>
            <a id="open-folder" class="ghost" href="#" target="_blank">Open</a>
          </div>
        </div>
        <div class="output-block">
          <label>Artifacts</label>
          <ul id="artifact-list"></ul>
        </div>
        <div class="output-block">
          <label>Preview</label>
          <pre id="artifact-preview">Select an artifact to preview.</pre>
        </div>
        <div class="output-actions">
          <a id="export-dag" class="primary" href="#">Export DAG</a>
          <a id="export-all" class="ghost" href="./export_bundle.zip">Export All</a>
        </div>
      </aside>
    </div>

    <div id="settings-drawer" class="drawer hidden">
      <div class="drawer-content">
        <div class="drawer-header">
          <h3>Agent Settings</h3>
          <button id="close-settings" class="ghost">Close</button>
        </div>
        <div class="drawer-section">
          <h4>Provider</h4>
          <select id="agent-mode">
            <option value="cursor">Cursor</option>
            <option value="inhouse">In-house</option>
            <option value="groq">Groq</option>
            <option value="openrouter">OpenRouter</option>
          </select>
        </div>
        <div class="drawer-section">
          <h4>Cursor Agent</h4>
          <input id="cursor-key" type="password" placeholder="Cursor API key" />
          <input id="cursor-repo" type="text" placeholder="Repository URL" />
          <input id="cursor-ref" type="text" placeholder="Ref (branch/tag)" />
          <div class="drawer-actions">
            <button id="cursor-test" class="ghost">Test connection</button>
          </div>
        </div>
        <div class="drawer-section">
          <h4>In-house</h4>
          <input id="inhouse-url" type="text" placeholder="Agent endpoint URL" />
          <input id="inhouse-token" type="password" placeholder="Auth token" />
          <input id="inhouse-model" type="text" placeholder="Model name" />
          <div class="drawer-actions">
            <button id="inhouse-test" class="ghost">Test connection</button>
          </div>
        </div>
        <div class="drawer-section">
          <h4>Groq</h4>
          <input id="groq-key" type="password" placeholder="Groq API key" />
          <input id="groq-model" type="text" placeholder="Model name" />
        </div>
        <div class="drawer-section">
          <h4>OpenRouter</h4>
          <input id="openrouter-key" type="password" placeholder="OpenRouter API key" />
          <input id="openrouter-model" type="text" placeholder="Model name" />
        </div>
        <p class="drawer-note">
          Configure Cursor or In-house settings to enable migration.
        </p>
      </div>
    </div>

    <script src="./ui.js"></script>
  </body>
</html>
"""


def write_export_bundle(bundle_path: str, artifacts_root: str) -> None:
    import zipfile

    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as bundle:
        for dirpath, _, filenames in os.walk(artifacts_root):
            for filename in filenames:
                if filename == os.path.basename(bundle_path):
                    continue
                full_path = os.path.join(dirpath, filename)
                relative_path = os.path.relpath(full_path, artifacts_root)
                bundle.write(full_path, arcname=relative_path)


def write_ui_assets(reports_root: str) -> None:
    css_source = os.path.join(os.path.dirname(__file__), "..", "frontend", "static", "css", "styles.css")
    js_source = os.path.join(os.path.dirname(__file__), "..", "frontend", "static", "js", "app.js")
    css_path = os.path.abspath(css_source)
    js_path = os.path.abspath(js_source)
    try:
        css_content = read_text(css_path)
        js_content = read_text(js_path)
    except FileNotFoundError:
        return
    write_text(os.path.join(reports_root, "ui.css"), css_content)
    write_text(os.path.join(reports_root, "ui.js"), js_content)


def write_utils(
    utils_root: str, utils_payload: Dict[str, str], activity_logger: ActivityLogger
) -> List[str]:
    ensure_dir(utils_root)
    paths: List[str] = []
    if "__init__.py" not in utils_payload:
        utils_payload = {**utils_payload, "__init__.py": ""}
    for filename, content in utils_payload.items():
        path = os.path.join(utils_root, filename)
        activity_logger.log("Generate", f"Generating {path}")
        write_text(path, content)
        activity_logger.log("Generate", f"Generated {path}")
        paths.append(path)
    return paths


def write_notebooks_agentic(
    notebooks_root: str,
    notebooks: List[Dict[str, Any]],
    notebook_format: str,
    activity_logger: ActivityLogger,
) -> List[str]:
    generated: List[str] = []
    for notebook in notebooks:
        dag_id = notebook.get("dag_id", "unknown_dag")
        dag_root = os.path.join(notebooks_root, dag_id)
        ensure_dir(dag_root)
        name = notebook.get("notebook_name", "task.py")
        code = notebook.get("code", "")
        if notebook_format in {"py", "both"}:
            path = os.path.join(dag_root, name)
            activity_logger.log("Generate", f"Generating {path}")
            write_text(path, code)
            activity_logger.log("Generate", f"Generated {path}")
            generated.append(path)
        if notebook_format in {"ipynb", "both"}:
            ipynb_name = name.replace(".py", ".ipynb")
            path = os.path.join(dag_root, ipynb_name)
            activity_logger.log("Generate", f"Generating {path}")
            payload = render_ipynb_stub(code)
            write_json(path, payload)
            activity_logger.log("Generate", f"Generated {path}")
            generated.append(path)
    return generated


def write_reports_per_dag(
    reports_root: str,
    index_results: List[Any],
    mapping_results: List[Dict[str, Any]],
    ingest_result,
    assumptions: List[str],
) -> List[str]:
    generated: List[str] = []
    mapping_by_dag = {m["dag_id"]: m for m in mapping_results}
    for index_result in index_results:
        dag_id = index_result.dag_id
        dag_root = os.path.join(reports_root, dag_id)
        ensure_dir(dag_root)

        write_json(os.path.join(dag_root, "task_graph.json"), index_result.task_graph)
        write_json(os.path.join(dag_root, "code_index.json"), index_result.code_index)

        mapping = mapping_by_dag.get(dag_id, {"mappings": []})
        write_json(os.path.join(dag_root, "task_mapping.json"), mapping.get("mappings", []))

        plan_text = format_migration_plan_llm([index_result], mapping.get("mappings", []), ingest_result)
        write_text(os.path.join(dag_root, "migration_plan.md"), plan_text)

        dag_assumptions = assumptions[:]
        dag_assumptions.extend(mapping.get("assumptions", []))
        write_text(os.path.join(dag_root, "assumptions.md"), format_assumptions(dag_assumptions))

        validation_text = format_validation_report_llm([index_result], mapping.get("mappings", []), dag_assumptions, ingest_result)
        write_text(os.path.join(dag_root, "validation_report.md"), validation_text)

        generated.extend(
            [
                os.path.join(dag_root, "task_graph.json"),
                os.path.join(dag_root, "code_index.json"),
                os.path.join(dag_root, "task_mapping.json"),
                os.path.join(dag_root, "migration_plan.md"),
                os.path.join(dag_root, "assumptions.md"),
                os.path.join(dag_root, "validation_report.md"),
            ]
        )
    return generated


def build_session_payload(
    migration_root: str,
    agent_mode: str,
    agent_configured: bool,
    index_results: List[Any],
    mapping_results: List[Dict[str, Any]],
    source_inputs: List[str],
) -> Dict[str, Any]:
    mapping_by_dag = {m["dag_id"]: m for m in mapping_results}
    dags = []
    for index_result in index_results:
        mapping = mapping_by_dag.get(index_result.dag_id, {"mappings": []})
        unknown_count = sum(
            1
            for m in mapping.get("mappings", [])
            if str(m.get("pattern", "")).lower() in {"generic", "generic_notebook_task"}
        )
        dags.append(
            {
                "dag_id": index_result.dag_id,
                "schedule": index_result.schedule_interval,
                "task_count": index_result.task_count,
                "status": "Migrated" if unknown_count == 0 else "Needs Review",
                "unknown_operator_count": unknown_count,
                "reports_path": os.path.join(migration_root, "reports", index_result.dag_id),
            }
        )
    return {
        "migration_root": migration_root,
        "source_inputs": source_inputs,
        "agent_mode": agent_mode,
        "agent_configured": agent_configured,
        "dags": dags,
        "timeline": ["Scan", "Index", "Analyze", "Plan", "Generate", "Validate", "Done"],
    }


def write_validation_reports(
    reports_root: str,
    validation,
    index_results: List[Any],
) -> None:
    if validation is None:
        return
    for index_result in index_results:
        dag_root = os.path.join(reports_root, index_result.dag_id)
        ensure_dir(dag_root)
        lines = ["# Validation Report", ""]
        if validation.ok:
            lines.append("- Status: OK")
        else:
            lines.append("- Status: FAILED")
            lines.append("")
            lines.append("## Errors")
            lines.extend([f"- {err}" for err in validation.errors])
        lines.append("")
        write_text(os.path.join(dag_root, "validation_report.md"), "\n".join(lines))


def write_per_dag_exports(
    migration_root: str,
    reports_root: str,
    index_results: List[Any],
) -> List[str]:
    import zipfile

    generated: List[str] = []
    for index_result in index_results:
        dag_id = index_result.dag_id
        bundle_path = os.path.join(reports_root, dag_id, "export_bundle.zip")
        with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(os.path.join(migration_root, "databricks.yml"), arcname="databricks.yml")
            _zip_folder(bundle, os.path.join(migration_root, "utils"), "utils")
            _zip_folder(bundle, os.path.join(migration_root, "notebooks", dag_id), f"notebooks/{dag_id}")
            _zip_folder(bundle, os.path.join(migration_root, "reports", dag_id), f"reports/{dag_id}")
        generated.append(bundle_path)
    return generated


def _zip_folder(bundle, folder_path: str, arc_root: str) -> None:
    if not os.path.isdir(folder_path):
        return
    for dirpath, _, filenames in os.walk(folder_path):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            relative = os.path.relpath(full_path, folder_path)
            bundle.write(full_path, arcname=os.path.join(arc_root, relative))


def _assert_agent_configured(settings: LLMSettings) -> None:
    mode = settings.agent_mode.lower()
    if mode == "openrouter" and not settings.openrouter_api_key:
        raise RuntimeError("OpenRouter API key missing. Configure AMC_OPENROUTER_API_KEY.")
    if mode == "groq" and not settings.groq_api_key:
        raise RuntimeError("Groq API key missing. Configure AMC_GROQ_API_KEY.")
    if mode == "cursor" and (not settings.cursor_api_key or not settings.cursor_repository or not settings.cursor_ref):
        raise RuntimeError("Cursor settings missing. Configure AMC_CURSOR_API_KEY, AMC_CURSOR_REPOSITORY, AMC_CURSOR_REF.")
    if mode == "inhouse" and not settings.inhouse_agent_url:
        raise RuntimeError("In-house agent URL missing. Configure AMC_INHOUSE_AGENT_URL.")
    if mode == "mock" and not settings.allow_mock:
        raise RuntimeError("Mock mode disabled. Set AMC_ALLOW_MOCK=true for offline tests.")


def _is_agent_configured(settings: LLMSettings) -> bool:
    mode = settings.agent_mode.lower()
    if mode == "openrouter":
        return bool(settings.openrouter_api_key)
    if mode == "groq":
        return bool(settings.groq_api_key)
    if mode == "cursor":
        return bool(settings.cursor_api_key and settings.cursor_repository and settings.cursor_ref)
    if mode == "inhouse":
        return bool(settings.inhouse_agent_url)
    if mode == "mock":
        return settings.allow_mock
    return False


if __name__ == "__main__":
    main()
