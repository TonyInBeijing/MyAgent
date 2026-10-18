"""Thin Ollama /api/chat client with tool-calling support."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    role: str
    content: str | None = None
    thinking: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_name: str | None = None  # for role=tool

    def to_api(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            msg["content"] = self.content
        if self.thinking:
            msg["thinking"] = self.thinking
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_name:
            msg["tool_name"] = self.tool_name
        return msg


@dataclass
class OllamaResponse:
    message: ChatMessage
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.message.tool_calls)


class OllamaClient:
    def __init__(
        self,
        host: str,
        model: str,
        *,
        timeout: float = 120.0,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        *,
        think: bool | None = None,
    ) -> OllamaResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_api() for m in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        if think is not None:
            payload["think"] = think

        url = f"{self.host}/api/chat"
        logger.debug("POST %s model=%s tools=%d", url, self.model, len(tools or []))

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        msg_raw = data.get("message") or {}
        tool_calls = msg_raw.get("tool_calls") or None
        # Normalize arguments: Ollama may return dict or JSON string
        if tool_calls:
            normalized = []
            for call in tool_calls:
                call = dict(call)
                fn = dict(call.get("function") or {})
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args) if args.strip() else {}
                    except json.JSONDecodeError:
                        args = {"_raw": args}
                fn["arguments"] = args if isinstance(args, dict) else {}
                call["function"] = fn
                if "type" not in call:
                    call["type"] = "function"
                normalized.append(call)
            tool_calls = normalized

        message = ChatMessage(
            role=msg_raw.get("role", "assistant"),
            content=msg_raw.get("content") or "",
            thinking=msg_raw.get("thinking") or None,
            tool_calls=tool_calls,
        )
        return OllamaResponse(message=message, raw=data)
