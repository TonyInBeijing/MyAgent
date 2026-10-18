"""Scoped tool registry: register / validate / call / export schemas."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from myagent.tools.base import ToolResult, ToolSpec

logger = logging.getLogger(__name__)


def mcp_public_name(server: str, raw_name: str) -> str:
    """Stable MCP tool name, same shape as Claude Code / deepseek-harness."""
    safe_server = "".join(c if c.isalnum() or c in "_-" else "_" for c in server)
    safe_tool = "".join(c if c.isalnum() or c in "_-" else "_" for c in raw_name)
    return f"mcp__{safe_server}__{safe_tool}"


class ToolRegistry:
    def __init__(self, *, default_timeout: float = 15.0) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self.default_timeout = default_timeout

    def register(self, tool: ToolSpec) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool
        logger.debug("registered tool %s (source=%s)", tool.name, tool.source)

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def unregister_by_source(self, source: str) -> list[str]:
        removed = [n for n, t in self._tools.items() if t.source == source]
        for n in removed:
            del self._tools[n]
        return removed

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return sorted(self._tools)

    def openai_tools(self, allowlist: set[str] | None = None) -> list[dict[str, Any]]:
        tools = self._tools.values()
        if allowlist is not None:
            tools = [t for t in tools if t.name in allowlist]
        return [t.openai_schema() for t in tools]

    async def call(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                content=f"error: unknown tool '{name}'. available: {', '.join(self.names()) or '(none)'}",
                is_error=True,
            )

        args = arguments or {}
        try:
            Draft202012Validator(tool.parameters).validate(args)
        except ValidationError as exc:
            return ToolResult(
                content=f"error: invalid arguments for '{name}': {exc.message}",
                is_error=True,
            )

        timeout = self.default_timeout if timeout is None else timeout
        try:
            result = tool.execute(**args)
            if asyncio.iscoroutine(result):
                result = await asyncio.wait_for(result, timeout=timeout)
            return ToolResult(content=_stringify(result), is_error=False)
        except asyncio.TimeoutError:
            return ToolResult(
                content=f"error: tool '{name}' timed out after {timeout}s",
                is_error=True,
            )
        except TypeError as exc:
            return ToolResult(
                content=f"error: bad call to '{name}': {exc}",
                is_error=True,
            )
        except Exception as exc:  # noqa: BLE001 — surface to model, keep loop alive
            logger.exception("tool %s failed", name)
            return ToolResult(content=f"error: tool '{name}' failed: {exc}", is_error=True)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except TypeError:
        return str(value)
