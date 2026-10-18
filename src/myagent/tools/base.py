"""Tool contract: schema + execute (inspired by deepseek-harness defineTool)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Normalized tool outcome fed back to the model."""

    content: str
    is_error: bool = False


ExecuteFn = Callable[..., Awaitable[Any] | Any]


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object
    execute: ExecuteFn
    # Optional metadata (e.g. mcp server name)
    source: str = "builtin"
    tags: dict[str, str] = field(default_factory=dict)

    def openai_schema(self) -> dict[str, Any]:
        """Shape expected by Ollama / OpenAI-style tool calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
                or {"type": "object", "properties": {}},
            },
        }


def define_tool(
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
    *,
    source: str = "builtin",
) -> Callable[[ExecuteFn], ToolSpec]:
    """Decorator: turn an async/sync function into a ToolSpec."""

    def decorator(fn: ExecuteFn) -> ToolSpec:
        return ToolSpec(
            name=name,
            description=description,
            parameters=parameters
            or {"type": "object", "properties": {}, "additionalProperties": False},
            execute=fn,
            source=source,
        )

    return decorator
