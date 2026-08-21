"""Agent skill domain types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentSkillManifest:
    """Lightweight manifest exposed to the model."""

    name: str
    description: str
    location: str


@dataclass(frozen=True)
class AgentSkillDocument:
    """Full skill document loaded on demand."""

    manifest: AgentSkillManifest
    body: str
    source_path: Path | None = None
