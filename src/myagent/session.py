"""Simple in-memory chat session (optional disk dump under .myagent/)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from myagent.llm.ollama import ChatMessage


class Session:
    def __init__(self) -> None:
        self.messages: list[ChatMessage] = []

    def add(self, message: ChatMessage) -> None:
        self.messages.append(message)

    def clear(self) -> None:
        self.messages.clear()

    def dump(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "messages": [m.to_api() for m in self.messages],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
