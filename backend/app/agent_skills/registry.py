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

        for skills_dir in skills_dirs:
            root = Path(skills_dir)
            if not root.exists():
                continue
            location_prefix = _location_prefix_for_dir(skills_dir)
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
            source_path=path.resolve(),
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
        """Load a skill by name, re-reading SKILL.md from disk when possible."""
        cached = self._documents.get(name)
        if cached is None:
            raise ValueError(f'skill "{name}" is unknown or no longer available')

        source = cached.source_path
        if source is None or not source.is_file():
            return cached

        # location = {prefix}/{dir}/SKILL.md → prefix
        loc = cached.manifest.location.rstrip("/")
        if loc.endswith("/SKILL.md"):
            without_file = loc[: -len("/SKILL.md")]
            location_prefix = without_file.rsplit("/", 1)[0]
        else:
            location_prefix = _location_prefix_for_dir(source.parent.parent)

        return self._load_document(source, location_prefix=location_prefix)


def _skill_dirs_for_user(user_id: str | None) -> list[str]:
    dirs = [str(SKILLS_PUBLIC_DIR)]
    if user_id:
        dirs.append(str(get_paths().user_skills_dir(user_id)))
    return dirs


def _location_prefix_for_dir(skills_dir: str | Path) -> str:
    """Map a skills root directory to its virtual path prefix by path suffix."""
    public_prefix = vfs_config.skills_public_prefix.rstrip("/")
    custom_prefix = vfs_config.skills_custom_prefix.rstrip("/")
    name = Path(skills_dir).resolve().name

    if name == "public":
        return public_prefix
    if name == "skills":
        return custom_prefix
    return custom_prefix


@lru_cache
def get_skill_registry(user_id: str | None = None) -> AgentSkillRegistry:
    """Return a cached registry for *user_id* (``None`` = public skills only)."""
    return AgentSkillRegistry(skills_dirs=_skill_dirs_for_user(user_id))


def invalidate_skill_registry() -> None:
    """Drop cached registries so the next lookup rescans skill directories."""
    get_skill_registry.cache_clear()
