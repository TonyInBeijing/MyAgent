"""CLI entry: myagent chat | tools | skills."""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from myagent import __version__
from myagent.agent.loop import RunTrace, TurnTrace
from myagent.runtime import create_runtime
from myagent.session import Session

app = typer.Typer(
    name="myagent",
    help="MyAgent — learn Tool / MCP / Skill with qwen3.5 via Ollama.",
    no_args_is_help=True,
)
console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )
    # Keep library HTTP chatter off unless -v
    for name in ("httpx", "httpcore", "openai", "mcp", "myagent.mcp.client"):
        logging.getLogger(name).setLevel(logging.DEBUG if verbose else logging.WARNING)


def _print_run_start(run: RunTrace) -> None:
    skills = ", ".join(run.skills) if run.skills else "(none)"
    console.print(f"[dim]  · skills:[/dim] {skills}")


def _print_turn(trace: TurnTrace) -> None:
    import json

    for name, args, content, is_error in trace.tool_results:
        args_s = json.dumps(args, ensure_ascii=False)
        preview = content.replace("\n", " ")
        if len(preview) > 120:
            preview = preview[:117] + "…"
        kind = "mcp" if name.startswith("mcp__") else "tool"
        color = "red" if is_error else "yellow"
        console.print(
            f"[{color}]  · {kind} {name}({args_s}) → {preview}[/{color}]"
        )


def _verbose(ctx: typer.Context) -> bool:
    return bool(ctx.obj and ctx.obj.get("verbose"))


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logs + loop traces"),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    _setup_logging(verbose)


@app.command()
def version() -> None:
    """Print package version."""
    console.print(__version__)


@app.command("tools")
def list_tools(ctx: typer.Context) -> None:
    """List registered tools (builtin + MCP)."""

    async def _run() -> None:
        rt = await create_runtime(verbose=_verbose(ctx))
        try:
            table = Table(title="Registered tools")
            table.add_column("name")
            table.add_column("source")
            table.add_column("description")
            for tool in sorted(rt.registry.list(), key=lambda t: t.name):
                table.add_row(tool.name, tool.source, (tool.description or "")[:80])
            console.print(table)
        finally:
            await rt.aclose()

    asyncio.run(_run())


@app.command("skills")
def list_skills(ctx: typer.Context) -> None:
    """List discovered SKILL.md packages."""

    async def _run() -> None:
        rt = await create_runtime(verbose=_verbose(ctx))
        try:
            table = Table(title="Skills")
            table.add_column("name")
            table.add_column("tools")
            table.add_column("description")
            for skill in rt.skills.skills:
                tools = ", ".join(skill.tools) if skill.tools else "(all)"
                table.add_row(skill.name, tools, skill.description[:80])
            if not rt.skills.skills:
                console.print("[yellow]No skills found under skills/[/yellow]")
            else:
                console.print(table)
        finally:
            await rt.aclose()

    asyncio.run(_run())


@app.command()
def chat(
    ctx: typer.Context,
    message: Optional[str] = typer.Argument(
        None,
        help="Single-shot user message. Omit for interactive REPL.",
    ),
) -> None:
    """Chat with the agent (tool loop)."""

    async def _run() -> None:
        verbose = _verbose(ctx)
        rt = await create_runtime(
            verbose=verbose,
            show_trace=True,
            on_run_start=_print_run_start,
            on_trace=_print_turn,
        )
        session = Session()
        try:
            if message is not None:
                answer = await rt.loop.run(message, session)
                console.print(answer)
                return

            console.print(
                f"[bold]MyAgent[/bold] {__version__} · model={rt.config.model.name} · "
                f"tools={len(rt.registry.list())} · skills={len(rt.skills.skills)}"
            )
            console.print(
                "每轮会显示激活的 skill 与实际调用的 tool/MCP；"
                "Type a message, or /quit /tools /skills /clear\n"
            )
            while True:
                try:
                    line = console.input("[bold cyan]you>[/bold cyan] ").strip()
                except (EOFError, KeyboardInterrupt):
                    console.print()
                    break
                if not line:
                    continue
                if line in {"/quit", "/exit", ":q"}:
                    break
                if line == "/clear":
                    session.clear()
                    console.print("[dim]session cleared[/dim]")
                    continue
                if line == "/tools":
                    for t in rt.registry.names():
                        console.print(f"  · {t}")
                    continue
                if line == "/skills":
                    for s in rt.skills.skills:
                        console.print(f"  · {s.name}: {s.description}")
                    continue

                try:
                    answer = await rt.loop.run(line, session)
                except Exception as exc:  # noqa: BLE001
                    console.print(f"[red]error:[/red] {exc}")
                    continue
                console.print(f"[bold green]agent>[/bold green] {answer}\n")
        finally:
            await rt.aclose()

    asyncio.run(_run())


if __name__ == "__main__":
    app()
