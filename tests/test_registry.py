import asyncio
from pathlib import Path

from myagent.skills.loader import SkillLoader
from myagent.tools.builtin import register_builtin_tools
from myagent.tools.registry import ToolRegistry, mcp_public_name


def test_mcp_public_name() -> None:
    assert mcp_public_name("demo", "add") == "mcp__demo__add"


def test_calculator() -> None:
    reg = ToolRegistry()
    register_builtin_tools(reg, Path(".").resolve())

    async def _run() -> None:
        r = await reg.call("calculator", {"expression": "(12 * 34) + 5"})
        assert not r.is_error
        assert r.content == "413"

    asyncio.run(_run())


def test_unknown_tool() -> None:
    reg = ToolRegistry()

    async def _run() -> None:
        r = await reg.call("nope", {})
        assert r.is_error

    asyncio.run(_run())


def test_skill_match() -> None:
    root = Path(__file__).resolve().parents[1]
    loader = SkillLoader(root / "skills")
    loader.load()
    assert any(s.name == "hello-math" for s in loader.skills)
    active = loader.match("帮我验算一下 99*99")
    assert any(s.name == "hello-math" for s in active)
