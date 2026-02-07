from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import os
import time

from ..utils.fs import ensure_dir, write_text

from ..llm.client import LLMClient
from ..prompts import render_prompt
from .utils import decode_base64, extract_json


@dataclass
class RequirementsResult:
    summary: str
    assumptions: List[str]


@dataclass
class MappingResult:
    dag_id: str
    mappings: List[Dict[str, Any]]
    assumptions: List[str]


@dataclass
class CodegenResult:
    utils: Dict[str, str]
    notebooks: List[Dict[str, Any]]
    databricks_yml: str
    assumptions: List[str]


class RequirementsAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def run(self, *, requirement_texts: Dict[str, str]) -> RequirementsResult:
        combined = "\n\n".join(
            [f"[{key}]\n{value}" for key, value in requirement_texts.items()]
        )
        prompt = render_prompt(
            "requirements",
            requirements_input=combined if combined.strip() else "NO_EXTERNAL_REQUIREMENTS",
            no_inference_rules=_no_inference_rules(self.llm.settings.no_inference),
        )
        response = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = _extract_with_retry(self.llm, prompt, response.content)
        return RequirementsResult(
            summary=str(data.get("summary", "")),
            assumptions=list(data.get("assumptions", [])),
        )


class PdfRequirementsAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def run(self, *, dag_id: str, requirement_texts: Dict[str, str]) -> RequirementsResult:
        combined = "\n\n".join(
            [f"[{key}]\n{value}" for key, value in requirement_texts.items()]
        )
        prompt = render_prompt(
            "requirements_pdf",
            dag_id=dag_id,
            requirements_input=combined if combined.strip() else "NO_PDF_TEXT",
            no_inference_rules=_no_inference_rules(self.llm.settings.no_inference),
        )
        response = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = _extract_with_retry(self.llm, prompt, response.content)
        return RequirementsResult(
            summary=str(data.get("summary", "")),
            assumptions=list(data.get("assumptions", [])),
        )


class MappingAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def run(self, *, dag_id: str, index_payload: Dict[str, Any], requirements_summary: str) -> MappingResult:
        prompt = render_prompt(
            "mapping",
            dag_id=dag_id,
            requirements_summary=requirements_summary or "None",
            index_payload=index_payload,
            no_inference_rules=_no_inference_rules(self.llm.settings.no_inference),
        )
        response = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = _extract_with_retry(self.llm, prompt, response.content)
        return MappingResult(
            dag_id=str(data.get("dag_id", dag_id)),
            mappings=list(data.get("mappings", [])),
            assumptions=list(data.get("assumptions", [])),
        )


class CodegenAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def run(
        self,
        *,
        project_name: str,
        index_payloads: List[Dict[str, Any]],
        mapping_payloads: List[Dict[str, Any]],
        requirements_summary: str,
    ) -> CodegenResult:
        manifest = _generate_manifest(
            self.llm,
            project_name=project_name,
            index_payloads=index_payloads,
            mapping_payloads=mapping_payloads,
            requirements_summary=requirements_summary,
        )

        utils_payload = {}
        for util_name in manifest.get("utils", []):
            utils_payload[util_name] = _generate_util_file(
                self.llm,
                util_name=util_name,
                requirements_summary=requirements_summary,
                mapping_payloads=mapping_payloads,
            )

        notebooks = []
        for notebook in manifest.get("notebooks", []):
            code = _generate_notebook_code(
                self.llm,
                notebook=notebook,
                requirements_summary=requirements_summary,
                mapping_payloads=mapping_payloads,
            )
            notebooks.append({**notebook, "code": code})

        databricks_yml = _generate_databricks_yml(
            self.llm,
            project_name=project_name,
            index_payloads=index_payloads,
            mapping_payloads=mapping_payloads,
            requirements_summary=requirements_summary,
        )
        _validate_codegen_payload(utils_payload, notebooks, databricks_yml)
        return CodegenResult(
            utils=utils_payload,
            notebooks=notebooks,
            databricks_yml=str(databricks_yml),
            assumptions=list(manifest.get("assumptions", [])),
        )


def _extract_with_retry(llm: LLMClient, prompt: str, content: str) -> Dict[str, Any]:
    try:
        return extract_json(content)
    except ValueError as exc:
        repair_prompt = f"""
Your previous response was invalid JSON. Error: {exc}.
Return ONLY a valid JSON object. Start with '{{' and end with '}}'. No prose.
Original prompt:
{prompt}
"""
        repair = llm.chat(
            messages=[{"role": "user", "content": repair_prompt}],
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        try:
            return extract_json(repair.content)
        except ValueError:
            final_prompt = f"""
Return ONLY a valid JSON object. Do not include explanations, markdown, or extra text.
"""
            final = llm.chat(
                messages=[{"role": "user", "content": final_prompt}],
                max_tokens=4096,
                response_format={"type": "json_object"},
            )
            return extract_json(final.content)


def _generate_databricks_yml(
    llm: LLMClient,
    *,
    project_name: str,
    index_payloads: List[Dict[str, Any]],
    mapping_payloads: List[Dict[str, Any]],
    requirements_summary: str,
) -> str:
    if llm.settings.agent_mode.lower() == "openrouter":
        prompt = render_prompt(
            "databricks_yml_plain",
            project_name=project_name,
            requirements_summary=requirements_summary or "None",
            index_payloads=index_payloads,
            mapping_payloads=mapping_payloads,
            no_inference_rules=_no_inference_rules(llm.settings.no_inference),
        )
        response = llm.chat(messages=[{"role": "user", "content": prompt}], max_tokens=2048)
        return response.content
    prompt = render_prompt(
        "databricks_yml",
        project_name=project_name,
        requirements_summary=requirements_summary or "None",
        index_payloads=index_payloads,
        mapping_payloads=mapping_payloads,
        no_inference_rules=_no_inference_rules(llm.settings.no_inference),
    )
    data = _call_for_json(llm, prompt, max_tokens=2048)
    if "databricks_yml_base64" in data:
        return decode_base64(data["databricks_yml_base64"])
    if "content" in data and isinstance(data["content"], str):
        return data["content"]
    fallback_prompt = f"""
Return ONLY the Databricks Asset Bundle YAML content wrapped in:
BEGIN_BASE64
<base64>
END_BASE64

Original request:
{prompt}
"""
    raw = llm.chat(messages=[{"role": "user", "content": fallback_prompt}], max_tokens=2048)
    marked = _extract_marked_base64(raw.content)
    if marked is not None:
        return marked
    raise ValueError("Codegen missing databricks.yml content.")


def _generate_manifest(
    llm: LLMClient,
    *,
    project_name: str,
    index_payloads: List[Dict[str, Any]],
    mapping_payloads: List[Dict[str, Any]],
    requirements_summary: str,
) -> Dict[str, Any]:
    prompt = render_prompt(
        "manifest",
        project_name=project_name,
        requirements_summary=requirements_summary or "None",
        index_payloads=index_payloads,
        mapping_payloads=mapping_payloads,
        no_inference_rules=_no_inference_rules(llm.settings.no_inference),
    )
    response = llm.chat(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
        response_format={"type": "json_object"},
    )
    return _extract_with_retry(llm, prompt, response.content)


def _generate_util_file(
    llm: LLMClient,
    *,
    util_name: str,
    requirements_summary: str,
    mapping_payloads: List[Dict[str, Any]],
) -> str:
    if llm.settings.agent_mode.lower() == "openrouter":
        prompt = render_prompt(
            "util_plain",
            util_name=util_name,
            requirements_summary=requirements_summary or "None",
            mapping_payloads=mapping_payloads,
            no_inference_rules=_no_inference_rules(llm.settings.no_inference),
        )
        response = llm.chat(messages=[{"role": "user", "content": prompt}], max_tokens=2048)
        return response.content
    prompt = render_prompt(
        "util",
        util_name=util_name,
        requirements_summary=requirements_summary or "None",
        mapping_payloads=mapping_payloads,
        no_inference_rules=_no_inference_rules(llm.settings.no_inference),
    )
    data = _call_for_json(llm, prompt, max_tokens=2048)
    try:
        return _extract_content(data, "Util generation")
    except ValueError:
        if set(data.keys()).issubset({"message", "required_format"}):
            # Provider rejected format; request plain content
            plain = llm.chat(
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Return ONLY the file content as plain text (no JSON, no base64).\n\n"
                            f"Original request:\n{prompt}"
                        ),
                    }
                ],
                max_tokens=2048,
            )
            return plain.content
        fallback = f"""
Return ONLY the file content wrapped in:
BEGIN_BASE64
<base64>
END_BASE64

Original request:
{prompt}
"""
        raw = llm.chat(messages=[{"role": "user", "content": fallback}], max_tokens=2048)
        marked = _extract_marked_base64(raw.content)
        if marked is not None:
            return marked
        raise


def _generate_notebook_code(
    llm: LLMClient,
    *,
    notebook: Dict[str, Any],
    requirements_summary: str,
    mapping_payloads: List[Dict[str, Any]],
) -> str:
    if llm.settings.agent_mode.lower() == "openrouter":
        prompt = render_prompt(
            "notebook_plain",
            notebook=notebook,
            requirements_summary=requirements_summary or "None",
            mapping_payloads=mapping_payloads,
            no_inference_rules=_no_inference_rules(llm.settings.no_inference),
        )
        response = llm.chat(messages=[{"role": "user", "content": prompt}], max_tokens=4096)
        return response.content
    prompt = render_prompt(
        "notebook",
        notebook=notebook,
        requirements_summary=requirements_summary or "None",
        mapping_payloads=mapping_payloads,
        no_inference_rules=_no_inference_rules(llm.settings.no_inference),
    )
    data = _call_for_json(llm, prompt, max_tokens=4096)
    try:
        return _extract_content(data, "Notebook generation")
    except ValueError:
        if set(data.keys()).issubset({"message", "required_format"}):
            plain = llm.chat(
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Return ONLY the notebook content as plain text (no JSON, no base64).\n\n"
                            f"Original request:\n{prompt}"
                        ),
                    }
                ],
                max_tokens=4096,
            )
            return plain.content
        fallback = f"""
Return ONLY the notebook content wrapped in:
BEGIN_BASE64
<base64>
END_BASE64

Original request:
{prompt}
"""
        raw = llm.chat(messages=[{"role": "user", "content": fallback}], max_tokens=4096)
        marked = _extract_marked_base64(raw.content)
        if marked is not None:
            return marked
        raise


def _call_for_json(llm: LLMClient, prompt: str, *, max_tokens: int) -> Dict[str, Any]:
    try:
        response = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
    except Exception as exc:  # noqa: BLE001
        if "json_validate_failed" in str(exc).lower():
            response = llm.chat(messages=[{"role": "user", "content": prompt}], max_tokens=max_tokens)
        else:
            raise
    _dump_debug("json_primary", prompt, response.content)
    data = _extract_with_retry(llm, prompt, response.content)
    if set(data.keys()).issubset({"error", "prompt"}):
        retry = llm.chat(messages=[{"role": "user", "content": prompt}], max_tokens=max_tokens)
        _dump_debug("json_error_retry", prompt, retry.content)
        data = _extract_with_retry(llm, prompt, retry.content)
        if set(data.keys()).issubset({"error", "prompt"}):
            raise ValueError(f"Provider returned error: {data.get('error')}")
    if set(data.keys()).issubset({"status", "message"}):
        retry_prompt = f"""
Return ONLY valid JSON for this request. No prose, no extra keys.
If you cannot comply, return {{}}.

Original request:
{prompt}
"""
        retry = llm.chat(messages=[{"role": "user", "content": retry_prompt}], max_tokens=max_tokens)
        _dump_debug("json_retry", retry_prompt, retry.content)
        data = _extract_with_retry(llm, retry_prompt, retry.content)
        if set(data.keys()).issubset({"status", "message"}):
            raw_prompt = f"""
Return ONLY the BASE64 content for this request (no JSON, no prose).
If you cannot comply, return an empty string.

Original request:
{prompt}
"""
            raw = llm.chat(messages=[{"role": "user", "content": raw_prompt}], max_tokens=max_tokens)
            _dump_debug("raw_base64", raw_prompt, raw.content)
            decoded = _extract_base64_text(raw.content)
            if decoded is not None:
                return {"content": decoded}
            marked = _extract_marked_base64(raw.content)
            if marked is not None:
                return {"content": marked}
    if set(data.keys()).issubset({"error", "prompt"}):
        raise ValueError(f"Provider returned error: {data.get('error')}")
    return data


def _extract_content(data: Dict[str, Any], label: str) -> str:
    if "content_base64" in data:
        return decode_base64(data["content_base64"])
    if "code_base64" in data:
        return decode_base64(data["code_base64"])
    if "content" in data and isinstance(data["content"], str):
        return data["content"]
    if set(data.keys()).issubset({"status", "message"}):
        raise ValueError(
            f"{label} failed; provider returned status: {data.get('status')} {data.get('message')}"
        )
    raise ValueError(f"{label} missing content_base64. Keys: {list(data.keys())}")


def _extract_base64_text(text: str) -> Optional[str]:
    cleaned = text.strip().strip("`").strip()
    if not cleaned:
        return None
    # Allow the model to wrap base64 in quotes
    if cleaned.startswith("\"") and cleaned.endswith("\""):
        cleaned = cleaned.strip("\"")
    try:
        return decode_base64(cleaned)
    except Exception:
        return None


def _extract_marked_base64(text: str) -> Optional[str]:
    marker_start = "BEGIN_BASE64"
    marker_end = "END_BASE64"
    if marker_start not in text or marker_end not in text:
        return None
    start = text.find(marker_start) + len(marker_start)
    end = text.find(marker_end, start)
    if end <= start:
        return None
    payload = text[start:end].strip()
    if not payload:
        return None
    try:
        return decode_base64(payload)
    except Exception:
        return None


def _dump_debug(label: str, prompt: str, response: str) -> None:
    debug_dir = os.getenv("AMC_DEBUG_DIR")
    if not debug_dir:
        return
    ensure_dir(debug_dir)
    ts = int(time.time() * 1000)
    write_text(os.path.join(debug_dir, f"{label}_{ts}_prompt.txt"), prompt)
    write_text(os.path.join(debug_dir, f"{label}_{ts}_response.txt"), response)


def _no_inference_rules(enabled: bool) -> str:
    if not enabled:
        return ""
    return (
        "STRICT NO-INFERENCE MODE:\n"
        "- Only use facts present in the DAG code or external requirements.\n"
        "- Do NOT infer data movement, sources, or sinks from task names.\n"
        "- If a callable only prints/logs, output print/log logic only.\n"
        "- If details are missing, add an assumption and leave a TODO.\n"
    )


def _validate_codegen_payload(
    utils_payload: Dict[str, str],
    notebooks: List[Dict[str, Any]],
    databricks_yml: str,
) -> None:
    if not databricks_yml or "resources:" not in databricks_yml:
        raise ValueError("Codegen missing databricks.yml content.")
    if not notebooks:
        raise ValueError("Codegen returned no notebooks.")
    for notebook in notebooks:
        code = (notebook.get("code") or "").strip()
        if not code:
            raise ValueError(f"Notebook {notebook.get('notebook_name')} has empty code.")
        if not code.startswith("# Databricks notebook source"):
            raise ValueError(f"Notebook {notebook.get('notebook_name')} missing Databricks header.")
