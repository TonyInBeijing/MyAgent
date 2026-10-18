"""Agent loop: model ↔ tools until final answer (deepseek-harness-inspired)."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from myagent.llm.ollama import ChatMessage, OllamaClient
from myagent.session import Session
from myagent.skills.loader import Skill, SkillLoader
from myagent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

BASE_SYSTEM = """You are MyAgent, a helpful personal assistant.
You may call tools when they help answer accurately.
Prefer tools over guessing for math, time, and file contents.
When the user asks to use MCP (or names an mcp__* tool), you MUST call the matching mcp__* tool, not a builtin substitute like calculator.
When you are done, reply with a clear final answer (no unnecessary tool calls).
You are running in a multi-turn tool loop: you can call tools, see results, then continue.
"""


@dataclass
class TurnTrace:
    turn: int
    assistant: ChatMessage
    tool_results: list[tuple[str, dict[str, Any], str, bool]]  # name, args, content, is_error


@dataclass
class RunTrace:
    skills: list[str]
    available_tools: list[str]
    turns: list[TurnTrace]


class AgentLoop:
    def __init__(
        self,
        llm: OllamaClient,
        registry: ToolRegistry,
        skills: SkillLoader,
        *,
        max_turns: int = 8,
        skill_match: bool = True,
        verbose: bool = False,
        show_trace: bool = True,
        on_trace: Callable[[TurnTrace], None] | None = None,
        on_run_start: Callable[[RunTrace], None] | None = None,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.skills = skills
        self.max_turns = max_turns
        self.skill_match = skill_match
        self.verbose = verbose
        self.show_trace = show_trace
        self.on_trace = on_trace
        self.on_run_start = on_run_start

    async def run(self, user_text: str, session: Session) -> str:
        active = self.skills.match(user_text, match=self.skill_match)
        system = self._build_system(active)
        allowlist = self._resolve_allowlist(active)
        tools = self.registry.openai_tools(allowlist)
        skill_names = [s.name for s in active]
        tool_names = [t["function"]["name"] for t in tools]
        run_trace = RunTrace(skills=skill_names, available_tools=tool_names, turns=[])

        if self.on_run_start:
            self.on_run_start(run_trace)
        elif self.show_trace:
            _default_print_run_start(run_trace)

        # Working messages for this request: system + prior history + new user
        messages: list[ChatMessage] = [ChatMessage(role="system", content=system)]
        messages.extend(session.messages)
        user_msg = ChatMessage(role="user", content=user_text)
        messages.append(user_msg)
        session.add(user_msg)

        final_text = ""
        for turn in range(1, self.max_turns + 1):
            response = await self.llm.chat(messages, tools=tools or None)
            assistant = response.message
            if self.verbose and assistant.thinking:
                preview = assistant.thinking[:400].replace("\n", " ")
                print(f"[verbose] thinking: {preview}…")

            messages.append(assistant)
            session.add(assistant)

            if not response.has_tool_calls:
                final_text = (assistant.content or "").strip()
                if self.verbose:
                    print(f"[verbose] turn {turn}: final answer (no tool_calls)")
                break

            tool_results: list[tuple[str, dict[str, Any], str, bool]] = []
            for call in assistant.tool_calls or []:
                name, args, call_id = _parse_tool_call(call)
                result = await self.registry.call(name, args)
                tool_results.append((name, args, result.content, result.is_error))
                tool_msg = ChatMessage(
                    role="tool",
                    content=result.content,
                    tool_name=name,
                )
                # Some Ollama builds also accept tool_call_id; keep minimal contract
                messages.append(tool_msg)
                session.add(tool_msg)

            turn_trace = TurnTrace(turn=turn, assistant=assistant, tool_results=tool_results)
            run_trace.turns.append(turn_trace)
            if self.on_trace:
                self.on_trace(turn_trace)
            elif self.show_trace:
                _default_print_turn(turn_trace)
        else:
            final_text = final_text or (
                "(stopped: max_turns reached without a final answer)"
            )

        return final_text

    def _build_system(self, active: list[Skill]) -> str:
        skill_section = self.skills.build_prompt_section(active)
        if skill_section:
            return f"{BASE_SYSTEM}\n\n{skill_section}"
        return BASE_SYSTEM

    def _resolve_allowlist(self, active: list[Skill]) -> set[str] | None:
        """
        If a skill declares tools, restrict to that set PLUS any MCP tools
        (mcp__*), so demos still work when a skill narrows builtins.
        """
        base = self.skills.tools_allowlist(active)
        if base is None:
            return None
        mcp_tools = {t.name for t in self.registry.list() if t.name.startswith("mcp__")}
        return set(base) | mcp_tools


def _default_print_run_start(run: RunTrace) -> None:
    skills = ", ".join(run.skills) if run.skills else "(none)"
    print(f"  · skills: {skills}")


def _default_print_turn(trace: TurnTrace) -> None:
    for name, args, content, is_error in trace.tool_results:
        args_s = json.dumps(args, ensure_ascii=False)
        preview = content.replace("\n", " ")
        if len(preview) > 120:
            preview = preview[:117] + "…"
        tag = "mcp" if name.startswith("mcp__") else "tool"
        status = "error" if is_error else "ok"
        print(f"  · {tag} {name}({args_s}) → [{status}] {preview}")


def _parse_tool_call(call: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    fn = call.get("function") or {}
    name = str(fn.get("name") or call.get("name") or "")
    args = fn.get("arguments")
    if args is None:
        args = call.get("arguments") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args) if args.strip() else {}
        except json.JSONDecodeError:
            args = {}
    if not isinstance(args, dict):
        args = {}
    call_id = call.get("id") or call.get("tool_call_id")
    return name, args, call_id
