import os
from typing import Dict, List, Optional, Tuple


def load_pdf_instructions(pdfs_dir: str, dag_ids: List[str]) -> Tuple[Dict[str, str], List[str]]:
    notes: List[str] = []
    if not pdfs_dir or not os.path.isdir(pdfs_dir):
        return {}, notes
    try:
        from PyPDF2 import PdfReader  # type: ignore
    except Exception:
        notes.append("PyPDF2 not installed; skipping PDF instructions.")
        return {}, notes

    dag_lookup = {dag_id.lower(): dag_id for dag_id in dag_ids if dag_id}
    instructions: Dict[str, str] = {}
    for filename in os.listdir(pdfs_dir):
        if not filename.lower().endswith(".pdf"):
            continue
        base = filename[:-4].strip().lower()
        dag_id = dag_lookup.get(base)
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

    filename = f"{dag_id}.pdf"
    path = os.path.join(pdfs_dir, filename)
    if not os.path.isfile(path):
        return None, "pdf_not_found"
    try:
        reader = PdfReader(path)
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
