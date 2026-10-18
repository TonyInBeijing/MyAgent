"""Wire config → registry → MCP → skills → agent loop."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from myagent.agent.loop import AgentLoop, RunTrace, TurnTrace
from myagent.config import AppConfig, load_config
from myagent.llm.ollama import OllamaClient
from myagent.mcp.client import McpBridge
from myagent.skills.loader import SkillLoader
from myagent.tools.builtin import register_builtin_tools
from myagent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class Runtime:
    config: AppConfig
    registry: ToolRegistry
    skills: SkillLoader
    llm: OllamaClient
    mcp: McpBridge
    loop: AgentLoop

    async def aclose(self) -> None:
        await self.mcp.__aexit__(None, None, None)


async def create_runtime(
    *,
    verbose: bool = False,
    show_trace: bool = True,
    on_run_start: Callable[[RunTrace], None] | None = None,
    on_trace: Callable[[TurnTrace], None] | None = None,
    config: AppConfig | None = None,
) -> Runtime:
    cfg = config or load_config()
    registry = ToolRegistry(default_timeout=cfg.agent.tool_timeout_sec)
    register_builtin_tools(registry, cfg.workspace_path)

    skills = SkillLoader(cfg.skills_path)
    skills.load()

    llm = OllamaClient(
        host=cfg.model.host,
        model=cfg.model.name,
        timeout=cfg.model.timeout_sec,
    )

    mcp = McpBridge(registry)
    await mcp.__aenter__()
    await mcp.connect_all(cfg.mcp.servers)

    loop = AgentLoop(
        llm=llm,
        registry=registry,
        skills=skills,
        max_turns=cfg.agent.max_turns,
        skill_match=cfg.skills.match,
        verbose=verbose,
        show_trace=show_trace,
        on_run_start=on_run_start,
        on_trace=on_trace,
    )
    return Runtime(
        config=cfg,
        registry=registry,
        skills=skills,
        llm=llm,
        mcp=mcp,
        loop=loop,
    )
