"""Agent skill discovery and loading utilities."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from app.agent_skills.types import (
    AgentSkillDocument,
    AgentSkillManifest,
)
from app.vfs.config import vfs_config
from app.vfs.paths import SKILLS_PUBLIC_DIR, get_paths

_SKILL_LOCATION_PREFIXES: tuple[str, ...] = (
    vfs_config.skills_public_prefix.rstrip("/"),
    vfs_config.skills_custom_prefix.rstrip("/"),
)

_FRONTMATTER_RE = re.compile(
    r"\A---\n(?P<meta>.*?)\n---\n(?P<body>.*)\Z",
    re.DOTALL,
)


class AgentSkillRegistry:
    """Central registry for available and loadable skills."""

    def __init__(self, *, skills_dirs: list[str]) -> None:
        self._documents = self._load_all(skills_dirs)

    def _load_all(self, skills_dirs: list[str]) -> dict[str, AgentSkillDocument]:
        documents: dict[str, AgentSkillDocument] = {}

        for index, skills_dir in enumerate(skills_dirs):
            root = Path(skills_dir)
            if not root.exists():
                continue
            location_prefix = _location_prefix_for_index(index)
            for path in sorted(root.glob("*/SKILL.md")):
                document = self._load_document(path, location_prefix=location_prefix)
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


def _skill_dirs_for_user(user_id: str | None) -> list[str]:
    dirs = [str(SKILLS_PUBLIC_DIR)]
    if user_id:
        dirs.append(str(get_paths().user_skills_dir(user_id)))
    return dirs


def _location_prefix_for_index(index: int) -> str:
    if index < len(_SKILL_LOCATION_PREFIXES):
        return _SKILL_LOCATION_PREFIXES[index]
    return vfs_config.skills_custom_prefix.rstrip("/")


@lru_cache
def get_skill_registry(user_id: str | None = None) -> AgentSkillRegistry:
    """Return a cached registry for *user_id* (``None`` = public skills only)."""
    return AgentSkillRegistry(skills_dirs=_skill_dirs_for_user(user_id))
