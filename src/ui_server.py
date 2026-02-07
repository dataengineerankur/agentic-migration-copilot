import argparse
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional

from .cli import build_migration_artifacts
from .services.indexer import index_airflow_file


SETTINGS_PATH = os.path.join("var", "ui_settings.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Agentic Migration Copilot UI Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    os.makedirs("var", exist_ok=True)
    handler = _make_handler()
    try:
        server = ThreadingHTTPServer((args.host, args.port), handler)
    except PermissionError as exc:
        print(
            "Failed to bind to the requested port. If you are running inside the Cursor terminal, "
            "macOS sandboxing can block local servers. Run this command in Terminal.app/iTerm instead."
        )
        raise SystemExit(1) from exc
    print(f"UI server running at http://{args.host}:{args.port}")
    server.serve_forever()


def _make_handler():
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.startswith("/api/settings"):
                self._send_json(_load_settings())
                return
            if self.path.startswith("/api/session"):
                settings = _load_settings()
                output_root = settings.get("output_root", "")
                session_path = os.path.join(output_root, "reports", "session.json")
                session_payload = _load_json(session_path)
                if not session_payload:
                    session_payload = _build_scan_session(settings)
                self._send_json(session_payload)
                return
            if self.path.startswith("/api/activity"):
                settings = _load_settings()
                output_root = settings.get("output_root", "")
                activity_path = os.path.join(output_root, "reports", "activity.json")
                data = _load_json(activity_path)
                if not isinstance(data, list):
                    data = []
                self._send_json(data)
                return
            if self.path == "/" or self.path.startswith("/index.html"):
                self.path = "/frontend/ui/index.html"
            return super().do_GET()

        def do_POST(self) -> None:
            if self.path.startswith("/api/settings"):
                payload = self._read_json()
                _save_settings(payload)
                self._send_json({"ok": True})
                return
            if self.path.startswith("/api/test"):
                payload = self._read_json()
                mode = payload.get("mode")
                try:
                    _apply_env(_load_settings(), mode_override=mode)
                    from .llm.client import LLMClient
                    from .llm.settings import LLMSettings

                    client = LLMClient(LLMSettings())
                    client.chat(messages=[{"role": "user", "content": "ping"}], max_tokens=32)
                    self._send_json({"ok": True})
                except Exception as exc:  # noqa: BLE001
                    self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            if self.path.startswith("/api/migrate"):
                payload = self._read_json()
                settings = _load_settings()
                inputs = payload.get("inputs") or settings.get("source_inputs") or []
                output_root = payload.get("output_root") or settings.get("output_root") or "migration_output"
                project_name = payload.get("project_name") or settings.get("project_name") or "airflow-migration"
                notebook_format = payload.get("notebook_format") or "py"
                agent_mode = payload.get("agent_mode") or None
                selected_dags = payload.get("selected_dags") or settings.get("selected_dags") or []

                _apply_env(settings, mode_override=agent_mode)
                try:
                    build_migration_artifacts(
                        inputs=inputs,
                        output_root=output_root,
                        project_name=project_name,
                        confluence_url=None,
                        confluence_user=None,
                        confluence_token=None,
                        notebook_format=notebook_format,
                        agent_mode=agent_mode,
                        selected_dags=selected_dags,
                    )
                    self._send_json({"ok": True})
                except Exception as exc:  # noqa: BLE001
                    self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            self.send_response(404)
            self.end_headers()

        def _read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            data = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {}

        def _send_json(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _load_settings() -> Dict[str, Any]:
    defaults = _default_settings()
    if not os.path.isfile(SETTINGS_PATH):
        return defaults
    with open(SETTINGS_PATH, "r", encoding="utf-8") as handle:
        try:
            payload = json.load(handle)
        except json.JSONDecodeError:
            return defaults
    if isinstance(payload, dict):
        return _merge_settings(defaults, payload)
    return defaults


def _save_settings(payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    current = _load_settings()
    merged = _merge_settings(current, payload)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as handle:
        json.dump(merged, handle, indent=2)


def _load_json(path: str) -> Any:
    if not path or not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError:
            return {}


def _default_settings() -> Dict[str, Any]:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return {
        "agent_mode": "inhouse",
        "source_inputs": [os.path.join(repo_root, "demo_data", "airflow", "dags")],
        "output_root": os.path.join(repo_root, "migration_output_demo"),
        "project_name": "demo-postgres-snowflake",
        "groq_api_key": os.getenv("GROQ_API_KEY"),
        "groq_model": os.getenv("GROQ_MODEL"),
        "no_inference": False,
    }


def _build_scan_session(settings: Dict[str, Any]) -> Dict[str, Any]:
    source_inputs = settings.get("source_inputs") or []
    dags: List[Dict[str, Any]] = []
    for path in _collect_dag_files(source_inputs):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()
            index = index_airflow_file(path, content)
            dags.append(
                {
                    "dag_id": index["dag_id"],
                    "schedule": index.get("schedule_interval"),
                    "task_count": len(index.get("tasks", [])),
                    "status": "Not Started",
                    "unknown_operator_count": 0,
                    "reports_path": "",
                }
            )
        except Exception:
            continue
    return {
        "migration_root": settings.get("output_root", ""),
        "source_inputs": source_inputs,
        "agent_mode": settings.get("agent_mode", "inhouse"),
        "agent_configured": _is_agent_configured(settings),
        "dags": dags,
        "timeline": ["Scan", "Index", "Analyze", "Plan", "Generate", "Validate", "Done"],
    }


def _collect_dag_files(inputs: List[str]) -> List[str]:
    files: List[str] = []
    for path in inputs:
        if os.path.isdir(path):
            for dirpath, _, filenames in os.walk(path):
                for filename in filenames:
                    if filename.endswith(".py"):
                        files.append(os.path.join(dirpath, filename))
        elif os.path.isfile(path) and path.endswith(".py"):
            files.append(path)
    return files


def _is_agent_configured(settings: Dict[str, Any]) -> bool:
    mode = (settings.get("agent_mode") or "").lower()
    if mode == "openrouter":
        return bool(settings.get("openrouter_api_key"))
    if mode == "groq":
        return bool(settings.get("groq_api_key") or os.getenv("GROQ_API_KEY"))
    if mode == "cursor":
        return bool(
            settings.get("cursor_api_key")
            and settings.get("cursor_repository")
            and settings.get("cursor_ref")
        )
    if mode == "inhouse":
        return bool(settings.get("inhouse_agent_url"))
    return False


def _apply_env(settings: Dict[str, Any], mode_override: Optional[str] = None) -> None:
    mode = mode_override or settings.get("agent_mode")
    if mode:
        os.environ["AMC_AGENT_MODE"] = mode

    _set_env("AMC_CURSOR_API_KEY", settings.get("cursor_api_key"))
    _set_env("AMC_CURSOR_REPOSITORY", settings.get("cursor_repository"))
    _set_env("AMC_CURSOR_REF", settings.get("cursor_ref"))

    _set_env("AMC_INHOUSE_AGENT_URL", settings.get("inhouse_agent_url"))
    _set_env("AMC_INHOUSE_API_KEY", settings.get("inhouse_api_key"))
    _set_env("AMC_INHOUSE_MODEL", settings.get("inhouse_model"))
    _set_env("AMC_INHOUSE_HEADERS_JSON", settings.get("inhouse_headers_json"))

    _set_env("AMC_GROQ_API_KEY", settings.get("groq_api_key") or os.getenv("GROQ_API_KEY"))
    _set_env("AMC_GROQ_MODEL", settings.get("groq_model"))

    _set_env("AMC_OPENROUTER_API_KEY", settings.get("openrouter_api_key"))
    _set_env("AMC_OPENROUTER_MODEL", settings.get("openrouter_model"))

    _set_env("AMC_NO_INFERENCE", settings.get("no_inference"))


def _merge_settings(current: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(current)
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        if isinstance(value, list) and len(value) == 0:
            continue
        merged[key] = value
    return merged


def _set_env(key: str, value: Any) -> None:
    if value:
        os.environ[key] = str(value)


if __name__ == "__main__":
    main()
