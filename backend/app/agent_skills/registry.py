"""Agent skill discovery and loading utilities."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from app.agent_skills.models import (
    AgentSkillDocument,
    AgentSkillManifest,
)
from app.vfs.config import vfs_config
from app.vfs.paths import SKILLS_PUBLIC_DIR, get_paths

_FRONTMATTER_RE = re.compile(
    r"\A---\n(?P<meta>.*?)\n---\n(?P<body>.*)\Z",
    re.DOTALL,
)


class AgentSkillRegistry:
    """Central registry for available and loadable skills."""

    def __init__(
        self,
        *,
        user_id: str | None = None,
        skills_dir: Path | None = None,
    ) -> None:
        self.user_id = user_id
        self.skills_dir = skills_dir if skills_dir is not None else SKILLS_PUBLIC_DIR
        self._documents = self._load_all()

    def _load_all(self) -> dict[str, AgentSkillDocument]:
        documents: dict[str, AgentSkillDocument] = {}

        if self.skills_dir.exists():
            for path in sorted(self.skills_dir.glob("*/SKILL.md")):
                document = self._load_document(
                    path,
                    location_prefix=f"{vfs_config.skills_prefix}public",
                )
                documents[document.manifest.name] = document

        if self.user_id:
            custom_dir = get_paths().user_skills_dir(self.user_id)
            if custom_dir.exists():
                for path in sorted(custom_dir.glob("*/SKILL.md")):
                    document = self._load_document(
                        path,
                        location_prefix=vfs_config.skills_custom_prefix.rstrip("/"),
                    )
                    documents[document.manifest.name] = document

        return documents

    def _load_document(self, path: Path, *, location_prefix: str) -> AgentSkillDocument:
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

        location = f"{location_prefix}/{skill_dir_name}/SKILL.md"
        return AgentSkillDocument(
            manifest=AgentSkillManifest(
                name=name,
                description=description,
                location=location,
            ),
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

    def list_manifests(self) -> list[AgentSkillManifest]:
        return sorted(
            [doc.manifest for doc in self._documents.values()],
            key=lambda item: item.name,
        )

    def load(self, name: str) -> AgentSkillDocument:
        document = self._documents.get(name)
        if document is None:
            raise ValueError(f"Skill '{name}' not found")
        return document


@lru_cache
def get_skill_registry(user_id: str | None = None) -> AgentSkillRegistry:
    """Return a cached registry for *user_id* (``None`` = public skills only)."""
    return AgentSkillRegistry(user_id=user_id)
