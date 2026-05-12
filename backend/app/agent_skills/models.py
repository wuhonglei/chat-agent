"""Agent skill domain models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSkillManifest:
    """Lightweight manifest exposed to the model."""

    name: str
    description: str


@dataclass(frozen=True)
class AgentSkillDocument:
    """Full skill document loaded on demand."""

    manifest: AgentSkillManifest
    body: str
