import json
from datetime import datetime, timezone
from typing import Dict, List

from typing import Optional

from ..utils.fs import write_json


class ActivityLogger:
    def __init__(self, output_path: str) -> None:
        self.output_path = output_path
        self._events: List[Dict[str, str]] = []

    def log(self, event: str, detail: str, dag_id: Optional[str] = None) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "detail": detail,
            "dag_id": dag_id,
        }
        self._events.append(payload)
        write_json(self.output_path, self._events)
