import base64
import json
from typing import Any, Dict


def extract_json(content: str) -> Dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in agent response.")
    payload = content[start : end + 1]
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        snippet = payload[:1000]
        raise ValueError(f"Invalid JSON from agent: {exc}. Snippet: {snippet}") from exc


def decode_base64(value: str) -> str:
    cleaned = "".join(value.split())
    # Fix missing padding if necessary
    padding = (-len(cleaned)) % 4
    if padding:
        cleaned += "=" * padding
    try:
        raw = base64.b64decode(cleaned.encode("utf-8"), validate=False)
        return raw.decode("utf-8", errors="replace")
    except Exception:
        try:
            raw = base64.urlsafe_b64decode(cleaned.encode("utf-8"))
            return raw.decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Failed to decode base64 content: {exc}") from exc
