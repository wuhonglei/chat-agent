"""Agent skill discovery and loading utilities."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from app.agent_skills.models import (
    AgentSkillDocument,
    AgentSkillManifest,
)
from app.vfs.paths import SKILLS_ROOT

_FRONTMATTER_RE = re.compile(
    r"\A---\n(?P<meta>.*?)\n---\n(?P<body>.*)\Z",
    re.DOTALL,
)

DEFAULT_ALLOWED_SKILL_NAMES = {
    "frontend-codegen-pipeline",
    # "frontend-project-templates",
    "next-best-practices",
    "shadcn",
    "tailwind-design-system",
    "vite",
}


class AgentSkillRegistry:
    """Central registry for available and loadable skills."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        base_dir = skills_dir if skills_dir is not None else SKILLS_ROOT
        self.skills_dir = base_dir
        self._documents = self._load_all()

    def _load_all(self) -> dict[str, AgentSkillDocument]:
        documents: dict[str, AgentSkillDocument] = {}
        if not self.skills_dir.exists():
            return documents

        for path in sorted(self.skills_dir.glob("*/SKILL.md")):
            document = self._load_document(path)
            documents[document.manifest.name] = document
        return documents

    def _load_document(self, path: Path) -> AgentSkillDocument:
        raw_text = path.read_text(encoding="utf-8").strip()
        match = _FRONTMATTER_RE.match(raw_text)
        skill_dir_name = path.parent.name

        if match:
            metadata = self._parse_frontmatter(match.group("meta"))
            body = match.group("body").strip()
            name = metadata.get("name", skill_dir_name).strip() or skill_dir_name
            description = metadata.get("description", "").strip()
        else:
            body = raw_text
            name = skill_dir_name
            description = self._extract_first_non_empty_line(body)

        return AgentSkillDocument(
            manifest=AgentSkillManifest(name=name, description=description),
            body=body,
        )

    @staticmethod
    def _parse_frontmatter(meta_text: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for line in meta_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            result[key.strip()] = value.strip().strip("\"'")
        return result

    @staticmethod
    def _extract_first_non_empty_line(text: str) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
        return ""

    def list_manifests(
        self, *, allowed_names: Iterable[str] | None = None
    ) -> list[AgentSkillManifest]:
        if allowed_names is None:
            return sorted(
                [doc.manifest for doc in self._documents.values()],
                key=lambda item: item.name,
            )
        allowed_set = set(allowed_names)
        return sorted(
            [
                doc.manifest
                for name, doc in self._documents.items()
                if name in allowed_set
            ],
            key=lambda item: item.name,
        )

    def load(
        self, name: str, *, allowed_names: Iterable[str] | None = None
    ) -> AgentSkillDocument:
        if allowed_names is not None and name not in set(allowed_names):
            raise ValueError(f"Skill '{name}' is not allowed")
        document = self._documents.get(name)
        if document is None:
            raise ValueError(f"Skill '{name}' not found")
        return document


skill_registry = AgentSkillRegistry()
