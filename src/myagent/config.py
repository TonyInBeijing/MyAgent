"""Load YAML config + environment overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


def project_root() -> Path:
    """Repo root: …/MyAgent (parent of src/)."""
    return Path(__file__).resolve().parents[2]


class ModelConfig(BaseModel):
    host: str = "http://127.0.0.1:11434"
    name: str = "qwen3.5:9b"
    timeout_sec: float = 120.0


class AgentConfig(BaseModel):
    max_turns: int = 8
    tool_timeout_sec: float = 15.0
    workspace: str = "."


class SkillsConfig(BaseModel):
    dir: str = "skills"
    match: bool = True


class McpServerConfig(BaseModel):
    transport: str = "stdio"
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    cwd: str | None = None


class McpConfig(BaseModel):
    servers: dict[str, McpServerConfig] = Field(default_factory=dict)


class AppConfig(BaseModel):
    model: ModelConfig = Field(default_factory=ModelConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    mcp: McpConfig = Field(default_factory=McpConfig)

    @property
    def workspace_path(self) -> Path:
        root = project_root()
        ws = Path(self.agent.workspace)
        return (root / ws).resolve() if not ws.is_absolute() else ws.resolve()

    @property
    def skills_path(self) -> Path:
        root = project_root()
        d = Path(self.skills.dir)
        return (root / d).resolve() if not d.is_absolute() else d.resolve()


def _load_dotenv(root: Path) -> None:
    env_file = root / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(path: Path | None = None) -> AppConfig:
    root = project_root()
    _load_dotenv(root)

    cfg_path = path or (root / "config" / "default.yaml")
    raw: dict[str, Any] = {}
    if cfg_path.is_file():
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    cfg = AppConfig.model_validate(raw)

    # Env overrides (scripts/start.sh already export these)
    if host := os.environ.get("OLLAMA_HOST"):
        cfg.model.host = host.rstrip("/")
        if not cfg.model.host.startswith(("http://", "https://")):
            cfg.model.host = f"http://{cfg.model.host}"
    if name := os.environ.get("OLLAMA_MODEL"):
        cfg.model.name = name

    return cfg
