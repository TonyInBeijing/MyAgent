"""Minimal built-in tools for learning the tool-calling loop."""

from __future__ import annotations

import ast
import operator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from myagent.tools.base import ToolSpec, define_tool
from myagent.tools.registry import ToolRegistry

# Safe subset for calculator
_BINOPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARYOPS: dict[type, Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
        return _UNARYOPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("only numbers and + - * / // % ** are allowed")


def _safe_calc(expression: str) -> str:
    tree = ast.parse(expression, mode="eval")
    value = _eval_node(tree)
    if value == int(value):
        return str(int(value))
    return str(value)


def _resolve_under(workspace: Path, path: str) -> Path:
    target = (workspace / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    try:
        target.relative_to(workspace)
    except ValueError as exc:
        raise PermissionError(f"path escapes workspace: {path}") from exc
    return target


def register_builtin_tools(registry: ToolRegistry, workspace: Path) -> None:
    workspace = workspace.resolve()

    @define_tool(
        name="calculator",
        description="Evaluate a simple arithmetic expression. Use for any math instead of mental math.",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Arithmetic expression, e.g. '(12 * 34) + 5'",
                }
            },
            "required": ["expression"],
            "additionalProperties": False,
        },
    )
    async def calculator(expression: str) -> str:
        return _safe_calc(expression)

    @define_tool(
        name="now",
        description="Return the current date and time in ISO-8601 (UTC).",
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    )
    async def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @define_tool(
        name="read_file",
        description="Read a UTF-8 text file under the agent workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path under the workspace",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Optional max characters to return (default 8000)",
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    )
    async def read_file(path: str, max_chars: int = 8000) -> str:
        target = _resolve_under(workspace, path)
        if not target.is_file():
            raise FileNotFoundError(f"not a file: {path}")
        text = target.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            return text[:max_chars] + f"\n… [truncated, {len(text)} chars total]"
        return text

    @define_tool(
        name="list_dir",
        description="List files and directories under a path in the agent workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative directory path (default '.')",
                }
            },
            "required": [],
            "additionalProperties": False,
        },
    )
    async def list_dir(path: str = ".") -> dict[str, Any]:
        target = _resolve_under(workspace, path)
        if not target.is_dir():
            raise NotADirectoryError(f"not a directory: {path}")
        entries = []
        for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            entries.append(
                {
                    "name": child.name,
                    "type": "dir" if child.is_dir() else "file",
                }
            )
        return {"path": str(target.relative_to(workspace)), "entries": entries}

    for tool in (calculator, now, read_file, list_dir):
        assert isinstance(tool, ToolSpec)
        registry.register(tool)
