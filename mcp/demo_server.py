#!/usr/bin/env python3
"""Minimal MCP stdio server for learning: exposes `add` and `echo` (mcp 2.x)."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("demo")


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers and return the sum."""
    return a + b


@mcp.tool()
def echo(message: str) -> str:
    """Echo the message back (useful for verifying MCP round-trips)."""
    return message


if __name__ == "__main__":
    mcp.run(transport="stdio")
