import os
from typing import Dict, List, Tuple


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
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Failed to read PDF {path}: {exc}")
    return instructions, notes
