import json
import os
from typing import Dict, Optional


class LLMSettings:
    def __init__(self) -> None:
        self.agent_mode: str = os.getenv("AMC_AGENT_MODE", "openrouter")

        self.openrouter_api_key: Optional[str] = os.getenv("AMC_OPENROUTER_API_KEY")
        self.openrouter_base_url: str = os.getenv(
            "AMC_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )
        self.openrouter_model: str = os.getenv("AMC_OPENROUTER_MODEL", "openai/gpt-5.2")
        self.openrouter_max_tokens: int = int(os.getenv("AMC_OPENROUTER_MAX_TOKENS", "2048"))
        self.openrouter_site_url: Optional[str] = os.getenv("AMC_OPENROUTER_SITE_URL")
        self.openrouter_site_name: Optional[str] = os.getenv("AMC_OPENROUTER_SITE_NAME")

        self.groq_api_key: Optional[str] = os.getenv("AMC_GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
        self.groq_base_url: str = os.getenv(
            "AMC_GROQ_BASE_URL", "https://api.groq.com/openai/v1"
        )
        self.groq_model: str = os.getenv("AMC_GROQ_MODEL", os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
        self.groq_max_tokens: int = int(os.getenv("AMC_GROQ_MAX_TOKENS", "2048"))

        self.cursor_api_key: Optional[str] = os.getenv("AMC_CURSOR_API_KEY")
        self.cursor_base_url: str = os.getenv("AMC_CURSOR_BASE_URL", "https://api.cursor.com")
        self.cursor_repository: Optional[str] = os.getenv("AMC_CURSOR_REPOSITORY")
        self.cursor_ref: Optional[str] = os.getenv("AMC_CURSOR_REF")
        self.cursor_branch_prefix: str = os.getenv("AMC_CURSOR_BRANCH_PREFIX", "amc/cursor")
        self.cursor_poll_interval_s: float = float(os.getenv("AMC_CURSOR_POLL_INTERVAL_S", "3.0"))
        self.cursor_max_wait_s: float = float(os.getenv("AMC_CURSOR_MAX_WAIT_S", "600.0"))

        self.inhouse_agent_url: Optional[str] = os.getenv("AMC_INHOUSE_AGENT_URL")
        self.inhouse_api_key: Optional[str] = os.getenv("AMC_INHOUSE_API_KEY")
        self.inhouse_headers_json: Optional[str] = os.getenv("AMC_INHOUSE_HEADERS_JSON")
        self.inhouse_model: Optional[str] = os.getenv("AMC_INHOUSE_MODEL")
        self.inhouse_timeout_s: float = float(os.getenv("AMC_INHOUSE_TIMEOUT_S", "60.0"))

        self.no_inference: bool = os.getenv("AMC_NO_INFERENCE", "false").lower() == "true"

        self.allow_mock: bool = os.getenv("AMC_ALLOW_MOCK", "false").lower() == "true"

    def inhouse_headers(self) -> Dict[str, str]:
        if not self.inhouse_headers_json:
            return {}
        try:
            payload = json.loads(self.inhouse_headers_json)
        except json.JSONDecodeError:
            return {}
        if isinstance(payload, dict):
            return {str(k): str(v) for k, v in payload.items()}
        return {}
