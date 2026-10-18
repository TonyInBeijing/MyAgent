"""MCP stdio bridge: list_tools → register on ToolRegistry as mcp__server__tool."""

from __future__ import annotations

import logging
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from myagent.config import McpServerConfig, project_root
from myagent.tools.base import ToolSpec
from myagent.tools.registry import ToolRegistry, mcp_public_name

logger = logging.getLogger(__name__)


class McpBridge:
    """Connects to configured MCP servers and registers their tools."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry
        self._stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}
        self._entered = False

    async def __aenter__(self) -> McpBridge:
        await self._stack.__aenter__()
        self._entered = True
        return self

    async def __aexit__(self, *exc: Any) -> None:
        for server in list(self._sessions):
            self.registry.unregister_by_source(f"mcp:{server}")
        self._sessions.clear()
        if self._entered:
            await self._stack.__aexit__(*exc)
            self._entered = False

    async def connect_all(self, servers: dict[str, McpServerConfig]) -> None:
        for name, cfg in servers.items():
            if not cfg.enabled:
                logger.info("mcp server %s disabled, skip", name)
                continue
            if cfg.transport != "stdio":
                logger.warning("mcp server %s: only stdio supported in this learning build", name)
                continue
            try:
                await self.connect_one(name, cfg)
            except Exception as exc:  # noqa: BLE001
                logger.error("mcp server %s failed to connect: %s", name, exc)

    async def connect_one(self, server_name: str, cfg: McpServerConfig) -> None:
        root = project_root()
        args = [_resolve_arg(a, root) for a in cfg.args]
        cwd = cfg.cwd
        if cwd:
            cwd_path = Path(cwd)
            if not cwd_path.is_absolute():
                cwd_path = (root / cwd_path).resolve()
            cwd = str(cwd_path)
        else:
            cwd = str(root)

        env = {**os.environ, **cfg.env}
        params = StdioServerParameters(
            command=cfg.command,
            args=args,
            env=env,
            cwd=cwd,
        )
        logger.info("connecting mcp/%s: %s %s", server_name, cfg.command, args)

        read, write = await self._stack.enter_async_context(stdio_client(params))
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._sessions[server_name] = session

        listed = await session.list_tools()
        source = f"mcp:{server_name}"
        # Clear previous generation for this server
        self.registry.unregister_by_source(source)

        for tool in listed.tools:
            public = mcp_public_name(server_name, tool.name)
            # mcp 2.x: input_schema; mcp 1.x: inputSchema
            raw_schema = getattr(tool, "input_schema", None) or getattr(
                tool, "inputSchema", None
            )
            schema = _input_schema(raw_schema)
            description = tool.description or f"MCP tool {tool.name} from {server_name}"

            async def _execute(
                *,
                _session: ClientSession = session,
                _raw: str = tool.name,
                **kwargs: Any,
            ) -> Any:
                result = await _session.call_tool(_raw, arguments=kwargs)
                return _format_call_result(result)

            spec = ToolSpec(
                name=public,
                description=description,
                parameters=schema,
                execute=_execute,
                source=source,
                tags={"mcp_server": server_name, "mcp_raw": tool.name},
            )
            self.registry.register(spec)
            logger.info("registered %s ← %s", public, tool.name)


def _resolve_arg(arg: str, root: Path) -> str:
    p = Path(arg)
    if not p.is_absolute() and (root / p).exists():
        return str((root / p).resolve())
    return arg


def _input_schema(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict) and raw.get("type"):
        return raw
    return {"type": "object", "properties": {}, "additionalProperties": True}


def _format_call_result(result: Any) -> str:
    # mcp CallToolResult: content is list of TextContent / ImageContent / …
    parts: list[str] = []
    content = getattr(result, "content", None) or []
    is_error = bool(
        getattr(result, "isError", None)
        if getattr(result, "isError", None) is not None
        else getattr(result, "is_error", False)
    )
    for block in content:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append(str(block))
    # Prefer structured payload when present (mcp 2.x)
    structured = getattr(result, "structured_content", None) or getattr(
        result, "structuredContent", None
    )
    if structured is not None and not parts:
        import json

        try:
            body = json.dumps(structured, ensure_ascii=False)
        except TypeError:
            body = str(structured)
    else:
        body = "\n".join(parts) if parts else str(result)
    if is_error:
        return f"error: {body}"
    return body
