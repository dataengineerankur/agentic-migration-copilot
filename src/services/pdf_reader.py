import os
import re
from typing import Dict, List, Optional, Tuple


def load_pdf_instructions(
    pdfs_dir: str,
    dag_ids: List[str],
    aliases: Optional[Dict[str, List[str]]] = None,
) -> Tuple[Dict[str, str], List[str]]:
    notes: List[str] = []
    if not pdfs_dir or not os.path.isdir(pdfs_dir):
        return {}, notes
    try:
        from PyPDF2 import PdfReader  # type: ignore
    except Exception:
        notes.append("PyPDF2 not installed; skipping PDF instructions.")
        return {}, notes

    dag_lookup = {dag_id.lower(): dag_id for dag_id in dag_ids if dag_id}
    alias_lookup: Dict[str, str] = {}
    if aliases:
        for dag_id, alias_list in aliases.items():
            for alias in alias_list:
                alias_lookup[alias.lower()] = dag_id
    instructions: Dict[str, str] = {}
    for filename in os.listdir(pdfs_dir):
        if not filename.lower().endswith(".pdf"):
            continue
        base = filename[:-4].strip().lower()
        dag_id = dag_lookup.get(base) or alias_lookup.get(base) or _fuzzy_match_dag_id(base, dag_ids, aliases)
        if not dag_id:
            continue
        path = os.path.join(pdfs_dir, filename)
        try:
            reader = PdfReader(path)
            text = []
            for page in reader.pages:
                page_text = page.extract_text() if page else ""
                if page_text:
                    text.append(page_text)
            instructions[dag_id] = "\n".join(text).strip()
            if not instructions[dag_id]:
                notes.append(f"PDF {path} had no extractable text.")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Failed to read PDF {path}: {exc}")
    return instructions, notes


def get_pdf_text_for_dag(pdfs_dir: str, dag_id: str) -> Tuple[Optional[str], Optional[str]]:
    if not pdfs_dir or not dag_id:
        return None, "missing_pdfs_dir_or_dag_id"
    if not os.path.isdir(pdfs_dir):
        return None, "pdfs_dir_not_found"
    try:
        from PyPDF2 import PdfReader  # type: ignore
    except Exception:
        return None, "pypdf2_not_installed"

    matched_path = _find_pdf_path(pdfs_dir, dag_id)
    if not matched_path:
        return None, "pdf_not_found"
    try:
        reader = PdfReader(matched_path)
        text = []
        for page in reader.pages:
            page_text = page.extract_text() if page else ""
            if page_text:
                text.append(page_text)
        joined = "\n".join(text).strip()
        if not joined:
            return None, "pdf_no_text"
        return joined, None
    except Exception as exc:  # noqa: BLE001
        return None, f"pdf_read_error: {exc}"


def _normalize_name(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\{[^}]+\}", "", value)
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"__+", "_", value).strip("_")
    return value


def _fuzzy_match_dag_id(
    base: str,
    dag_ids: List[str],
    aliases: Optional[Dict[str, List[str]]] = None,
) -> Optional[str]:
    base_norm = _normalize_name(base)
    for dag_id in dag_ids:
        if not dag_id:
            continue
        dag_norm = _normalize_name(dag_id)
        if base_norm and dag_norm and (base_norm in dag_norm or dag_norm in base_norm):
            return dag_id
        if aliases and dag_id in aliases:
            for alias in aliases[dag_id]:
                alias_norm = _normalize_name(alias)
                if base_norm and alias_norm and (base_norm in alias_norm or alias_norm in base_norm):
                    return dag_id
    return None


def _find_pdf_path(pdfs_dir: str, dag_id: str) -> Optional[str]:
    candidates = []
    for filename in os.listdir(pdfs_dir):
        if not filename.lower().endswith(".pdf"):
            continue
        base = filename[:-4].strip().lower()
        candidates.append((base, filename))
    target = dag_id.lower()
    for base, filename in candidates:
        if base == target:
            return os.path.join(pdfs_dir, filename)
    for base, filename in candidates:
        if _fuzzy_match_dag_id(base, [dag_id]):
            return os.path.join(pdfs_dir, filename)
    return None
