"""Load Cursor-style SKILL.md packages and match them to user messages."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


@dataclass
class Skill:
    name: str
    description: str
    body: str
    tools: list[str] | None = None  # optional allowlist when skill is active
    path: Path | None = None
    # Extra tokens derived from description for naive matching
    keywords: list[str] = field(default_factory=list)

    def matches(self, user_text: str) -> bool:
        text = user_text.lower()
        if self.name.lower() in text:
            return True
        desc = self.description.lower()
        # Whole-phrase / significant word overlap
        for token in self.keywords:
            if token and token in text:
                return True
        # Also match if several description words appear
        words = [w for w in re.split(r"\W+", desc) if len(w) >= 3]
        hits = sum(1 for w in words if w in text)
        return hits >= 2 and hits >= max(2, len(words) // 3)


class SkillLoader:
    def __init__(self, skills_dir: Path) -> None:
        self.skills_dir = skills_dir
        self.skills: list[Skill] = []

    def load(self) -> list[Skill]:
        self.skills = []
        if not self.skills_dir.is_dir():
            logger.warning("skills dir missing: %s", self.skills_dir)
            return self.skills

        for skill_md in sorted(self.skills_dir.glob("**/SKILL.md")):
            try:
                skill = _parse_skill(skill_md)
                self.skills.append(skill)
                logger.debug("loaded skill %s from %s", skill.name, skill_md)
            except Exception as exc:  # noqa: BLE001
                logger.warning("skip skill %s: %s", skill_md, exc)
        return self.skills

    def match(self, user_text: str, *, match: bool = True) -> list[Skill]:
        if not match:
            return list(self.skills)
        return [s for s in self.skills if s.matches(user_text)]

    def build_prompt_section(self, active: list[Skill]) -> str:
        if not active:
            return ""
        parts = ["# Active skills", "Follow these skill instructions when relevant."]
        for skill in active:
            parts.append(f"\n## Skill: {skill.name}\n{skill.description}\n\n{skill.body.strip()}")
        return "\n".join(parts)

    def tools_allowlist(self, active: list[Skill]) -> set[str] | None:
        """Union of skill tool allowlists. None = no restriction from skills."""
        lists = [s.tools for s in active if s.tools]
        if not lists:
            return None
        allowed: set[str] = set()
        for lst in lists:
            allowed.update(lst)
        return allowed


def _parse_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER.match(text)
    if not m:
        raise ValueError("SKILL.md must start with YAML frontmatter ---")
    meta = yaml.safe_load(m.group(1)) or {}
    body = m.group(2) or ""
    name = str(meta.get("name") or path.parent.name)
    description = str(meta.get("description") or "")
    tools = meta.get("tools")
    if tools is not None and not isinstance(tools, list):
        raise ValueError("frontmatter 'tools' must be a list of tool names")
    keywords = _keywords_from_description(description)
    return Skill(
        name=name,
        description=description,
        body=body,
        tools=list(tools) if tools else None,
        path=path,
        keywords=keywords,
    )


def _keywords_from_description(description: str) -> list[str]:
    # Prefer multi-char tokens; keep Chinese phrases roughly by splitting on punctuation
    tokens = re.split(r"[\s,，、；;。.!？?]+", description)
    out: list[str] = []
    for t in tokens:
        t = t.strip().lower()
        if len(t) >= 2:
            out.append(t)
    # Common math triggers for the hello-math demo
    extras = ["计算", "算", "加减", "乘除", "数学", "验算", "换算", "math", "calculate", "compute"]
    for e in extras:
        if e in description.lower() and e not in out:
            out.append(e)
    return out
