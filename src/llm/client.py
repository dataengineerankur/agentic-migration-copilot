import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .settings import LLMSettings


class LLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMResponse:
    content: str
    raw: Dict[str, Any]


class LLMClient:
    def __init__(self, settings: Optional[LLMSettings] = None) -> None:
        self.settings = settings or LLMSettings()

    def chat(
        self,
        *,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        mode = self.settings.agent_mode.lower()
        if mode == "openrouter":
            return self._openai_compatible_chat(
                base_url=self.settings.openrouter_base_url,
                api_key=self.settings.openrouter_api_key,
                model=self.settings.openrouter_model,
                max_tokens=max_tokens or self.settings.openrouter_max_tokens,
                headers=_optional_headers(
                    {
                        "HTTP-Referer": self.settings.openrouter_site_url,
                        "X-Title": self.settings.openrouter_site_name,
                    }
                ),
                messages=messages,
                response_format=response_format,
            )
        if mode == "groq":
            model = self.settings.groq_model
            if model and "/" not in model:
                model = f"openai/{model}"
            return self._openai_compatible_chat(
                base_url=self.settings.groq_base_url,
                api_key=self.settings.groq_api_key,
                model=model,
                max_tokens=max_tokens or self.settings.groq_max_tokens,
                headers={},
                messages=messages,
                response_format=response_format,
            )
        if mode == "inhouse":
            return self._inhouse_chat(
                base_url=self.settings.inhouse_agent_url,
                api_key=self.settings.inhouse_api_key,
                model=self.settings.inhouse_model or "default",
                max_tokens=max_tokens or 2048,
                headers=self.settings.inhouse_headers(),
                messages=messages,
                timeout_s=self.settings.inhouse_timeout_s,
                response_format=response_format,
            )
        if mode == "cursor":
            return self._cursor_agent_chat(messages=messages)
        if mode == "mock":
            raise LLMError("mock_mode_requires_agent_runner")
        raise LLMError(f"Unsupported agent mode: {self.settings.agent_mode}")

    def _openai_compatible_chat(
        self,
        *,
        base_url: Optional[str],
        api_key: Optional[str],
        model: str,
        max_tokens: int,
        headers: Dict[str, str],
        messages: List[Dict[str, str]],
        timeout_s: float = 60.0,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        if not base_url:
            raise LLMError("LLM base_url is not configured")
        if not api_key:
            raise LLMError("LLM api_key is not configured")

        url = base_url.rstrip("/") + "/chat/completions"
        payload = {"model": model, "messages": messages, "max_tokens": int(max_tokens)}
        if response_format:
            payload["response_format"] = response_format
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"))
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "curl/8.0")
        req.add_header("Authorization", f"Bearer {api_key}")
        for key, value in headers.items():
            req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw)
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="ignore")
            except Exception:
                body = ""
            raise LLMError(f"LLM request failed: HTTP {exc.code} {exc.reason} {body[:1000]}") from exc
        except Exception as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:
            # Some providers return a "status"/"message" envelope instead of choices.
            if isinstance(data, dict) and "status" in data and "message" in data:
                content = json.dumps(data)
            else:
                raise LLMError(f"LLM response parse error: {data}") from exc
        return LLMResponse(content=str(content), raw=data)

    def _inhouse_chat(
        self,
        *,
        base_url: Optional[str],
        api_key: Optional[str],
        model: str,
        max_tokens: int,
        headers: Dict[str, str],
        messages: List[Dict[str, str]],
        timeout_s: float = 60.0,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        if not base_url:
            raise LLMError("LLM base_url is not configured")

        request_headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "curl/8.0"}
        request_headers.update(headers)
        if api_key and "Authorization" not in request_headers:
            request_headers["Authorization"] = f"Bearer {api_key}"

        url = base_url.rstrip("/")
        prompt_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
        use_chat = "/chat" in url
        use_completions = "/completions" in url and not use_chat

        if use_chat:
            payload = {"model": model, "messages": messages, "max_tokens": int(max_tokens)}
            if response_format:
                payload["response_format"] = response_format
            return _post_json(url, payload, request_headers, timeout_s)

        if use_completions:
            payload = {"model": model, "prompt": prompt_text, "max_tokens": int(max_tokens)}
            return _post_json(url, payload, request_headers, timeout_s)

        # Unknown inhouse endpoint: try chat first, then fallback to completions-style.
        payload = {"model": model, "messages": messages, "max_tokens": int(max_tokens)}
        if response_format:
            payload["response_format"] = response_format
        try:
            return _post_json(url, payload, request_headers, timeout_s)
        except LLMError:
            payload = {"model": model, "prompt": prompt_text, "max_tokens": int(max_tokens)}
            return _post_json(url, payload, request_headers, timeout_s)

    def _cursor_agent_chat(self, *, messages: List[Dict[str, str]]) -> LLMResponse:
        if not self.settings.cursor_api_key:
            raise LLMError("Cursor API key is not configured")
        if not self.settings.cursor_repository or not self.settings.cursor_ref:
            raise LLMError("Cursor repository/ref are required for cursor agent mode")

        prompt_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
        branch_name = f"{self.settings.cursor_branch_prefix}-{int(time.time())}"
        payload: Dict[str, Any] = {
            "source": {
                "repository": self.settings.cursor_repository,
                "ref": self.settings.cursor_ref,
            },
            "target": {"branchName": branch_name, "autoCreatePr": False, "openAsCursorGithubApp": True},
            "prompt": {"text": prompt_text},
        }
        agent = _cursor_request(
            api_key=self.settings.cursor_api_key,
            base_url=self.settings.cursor_base_url,
            method="POST",
            path="/v0/agents",
            payload=payload,
        )
        agent_id = agent.get("id")
        if not agent_id:
            raise LLMError(f"Cursor agent launch failed: {agent}")
        status = agent.get("status", "")
        deadline = time.monotonic() + float(self.settings.cursor_max_wait_s)
        while status not in ("FINISHED", "FAILED", "STOPPED", "CANCELLED"):
            if time.monotonic() >= deadline:
                raise LLMError("Cursor agent timed out")
            time.sleep(float(self.settings.cursor_poll_interval_s))
            agent = _cursor_request(
                api_key=self.settings.cursor_api_key,
                base_url=self.settings.cursor_base_url,
                method="GET",
                path=f"/v0/agents/{agent_id}",
            )
            status = agent.get("status", "")
        summary = agent.get("summary") or ""
        return LLMResponse(content=str(summary), raw=agent)


def _optional_headers(headers: Dict[str, Optional[str]]) -> Dict[str, str]:
    cleaned: Dict[str, str] = {}
    for key, value in headers.items():
        if value:
            cleaned[key] = str(value)
    return cleaned


def _post_json(
    url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout_s: float
) -> LLMResponse:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"))
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw) if raw.strip().startswith("{") else {}
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        raise LLMError(f"LLM request failed: HTTP {exc.code} {exc.reason} {body[:1000]}") from exc
    except Exception as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc

    content = _extract_openai_content(data)
    if not content:
        # Fallback: accept direct content keys for inhouse proxies
        for key in ("content", "response", "output", "text", "message"):
            val = data.get(key) if isinstance(data, dict) else None
            if isinstance(val, str) and val.strip():
                content = val
                break
    if not content:
        content = json.dumps(data) if isinstance(data, dict) else ""
    return LLMResponse(content=str(content), raw=data if isinstance(data, dict) else {})


def _extract_openai_content(data: Dict[str, Any]) -> str:
    try:
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            texts: List[str] = []
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                if isinstance(choice.get("text"), str):
                    texts.append(choice["text"])
                message = choice.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    texts.append(message["content"])
            merged = "\n".join([t for t in texts if t.strip()])
            if merged.strip():
                return merged
    except Exception:
        return ""
    return ""


def _cursor_request(
    *,
    api_key: str,
    base_url: str,
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    url = base_url.rstrip("/") + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60.0) as response:
        return json.loads(response.read().decode("utf-8"))
