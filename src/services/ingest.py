import base64
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ..utils.fs import list_files, read_text


@dataclass
class IngestResult:
    requirements: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    sinks: List[str] = field(default_factory=list)
    schedules: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)


def ingest_inputs(
    inputs: Sequence[str],
    confluence_url: Optional[str] = None,
    confluence_user: Optional[str] = None,
    confluence_token: Optional[str] = None,
) -> Tuple[IngestResult, Dict[str, str]]:
    result = IngestResult()
    text_blobs: Dict[str, str] = {}

    for path in inputs:
        if path.endswith("/"):
            path = path[:-1]
        if _is_dir(path):
            files = list_files(path, (".py", ".md", ".txt", ".json", ".yml", ".yaml"))
            for file_path in files:
                text_blobs[file_path] = read_text(file_path)
                result.files.append(file_path)
        else:
            text_blobs[path] = read_text(path)
            result.files.append(path)

    if confluence_url:
        content = _fetch_confluence(confluence_url, confluence_user, confluence_token)
        if content:
            text_blobs[confluence_url] = content
        else:
            result.notes.append("Confluence content could not be retrieved.")

    for key, content in text_blobs.items():
        result.requirements.extend(_extract_requirements(content))
        sources, sinks, schedules = _extract_metadata(content)
        result.sources.extend(sources)
        result.sinks.extend(sinks)
        result.schedules.extend(schedules)

    result.sources = sorted(set(result.sources))
    result.sinks = sorted(set(result.sinks))
    result.schedules = sorted(set(result.schedules))
    return result, text_blobs


def _is_dir(path: str) -> bool:
    import os

    return os.path.isdir(path)


def _fetch_confluence(
    url: str, user: Optional[str], token: Optional[str]
) -> Optional[str]:
    request = urllib.request.Request(url)
    if user and token:
        auth = f"{user}:{token}".encode("utf-8")
        request.add_header("Authorization", "Basic " + base64.b64encode(auth).decode())
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = response.read().decode("utf-8", errors="ignore")
            return _strip_html(payload)
    except Exception:
        return None


def _strip_html(content: str) -> str:
    return re.sub(r"<[^>]+>", " ", content)


def _extract_requirements(content: str) -> List[str]:
    requirements: List[str] = []
    for line in content.splitlines():
        if line.strip().startswith(("-", "*")):
            requirements.append(line.strip().lstrip("-* ").strip())
    if not requirements:
        snippet = content.strip().splitlines()[:5]
        requirements.extend([line.strip() for line in snippet if line.strip()])
    return requirements


def _extract_metadata(content: str) -> Tuple[List[str], List[str], List[str]]:
    sources: List[str] = []
    sinks: List[str] = []
    schedules: List[str] = []
    lower = content.lower()
    for keyword in ["hdfs", "oracle", "sqoop", "s3", "adls", "gcs", "kafka", "hive"]:
        if keyword in lower:
            sources.append(keyword)
    for keyword in ["delta", "redshift", "snowflake", "bigquery", "iceberg"]:
        if keyword in lower:
            sinks.append(keyword)
    schedule_match = re.findall(r"schedule[_\s]interval\s*[:=]\s*([^\n]+)", lower)
    schedules.extend([match.strip() for match in schedule_match])
    return sources, sinks, schedules
