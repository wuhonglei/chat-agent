"""Centralized path layout for user data and sandbox virtual mapping."""

from __future__ import annotations

import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
USER_DATA_ROOT = BACKEND_ROOT / "data" / "user_data"
SKILLS_ROOT = BACKEND_ROOT / "skills"
SKILLS_PUBLIC_DIR = SKILLS_ROOT / "public"
SKILLS_CUSTOM_SEGMENT = "custom"
VIRTUAL_PATH_PREFIX = "/mnt/user-data"

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


class Paths:
    """Host paths under ``data/user_data`` and conversation-scoped sandbox dirs."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = Path(base_dir).resolve() if base_dir is not None else None

    @property
    def base_dir(self) -> Path:
        if self._base_dir is not None:
            return self._base_dir
        return USER_DATA_ROOT

    def validate_user_id(self, user_id: str) -> str:
        return self._validate_id(user_id, label="user_id")

    def validate_conversation_id(self, conversation_id: str) -> str:
        return self._validate_id(conversation_id, label="conversation_id")

    @staticmethod
    def _validate_id(value: str, *, label: str) -> str:
        normalized = (value or "").strip()
        if not normalized or not _SAFE_ID_RE.match(normalized):
            raise ValueError(f"invalid {label}")
        return normalized

    def user_dir(self, user_id: str) -> Path:
        return self.base_dir / self.validate_user_id(user_id)

    def conversations_dir(self, user_id: str) -> Path:
        return self.user_dir(user_id) / "conversations"

    def conversation_dir(self, user_id: str, conversation_id: str) -> Path:
        return self.conversations_dir(user_id) / self.validate_conversation_id(
            conversation_id
        )

    def sandbox_work_dir(self, user_id: str, conversation_id: str) -> Path:
        return self.conversation_dir(user_id, conversation_id) / "workspace"

    def sandbox_uploads_dir(self, user_id: str, conversation_id: str) -> Path:
        return self.conversation_dir(user_id, conversation_id) / "uploads"

    def sandbox_outputs_dir(self, user_id: str, conversation_id: str) -> Path:
        return self.conversation_dir(user_id, conversation_id) / "outputs"

    def user_skills_dir(self, user_id: str) -> Path:
        """Per-user custom skills root (virtual ``/mnt/skills/custom/``)."""
        return self.user_dir(user_id) / "skills"

    def ensure_user_skills_dir(self, user_id: str) -> Path:
        """Create user skills directory if missing."""
        root = self.user_skills_dir(self.validate_user_id(user_id)).resolve()
        root.mkdir(parents=True, exist_ok=True)
        root.chmod(0o777)
        return root

    def ensure_conversation_dir(self, user_id: str, conversation_id: str) -> Path:
        """Return conversation dir ``.../conversations/{cid}/``, creating it if missing."""
        root = self.conversation_dir(
            self.validate_user_id(user_id),
            self.validate_conversation_id(conversation_id),
        ).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def ensure_sandbox_work_dir(self, user_id: str, conversation_id: str) -> Path:
        """Return workspace dir, creating it if missing."""
        root = self.sandbox_work_dir(
            self.validate_user_id(user_id),
            self.validate_conversation_id(conversation_id),
        ).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def ensure_conversation_dirs(self, user_id: str, conversation_id: str) -> None:
        for directory in (
            self.sandbox_work_dir(user_id, conversation_id),
            self.sandbox_uploads_dir(user_id, conversation_id),
            self.sandbox_outputs_dir(user_id, conversation_id),
        ):
            directory.mkdir(parents=True, exist_ok=True)
            directory.chmod(0o777)

    def resolve_user_data_virtual_path(
        self,
        virtual_path: str,
        user_id: str,
        conversation_id: str,
    ) -> tuple[Path, str]:
        """Resolve ``/mnt/user-data/{workspace,uploads,outputs}/...`` to host path.

        Returns:
            (physical_path, kind) where kind is ``workspace``, ``uploads``, or ``outputs``.
        """
        from app.vfs.config import vfs_config

        stripped = virtual_path.strip()
        prefixes = (
            (vfs_config.workspace_prefix, "workspace", self.sandbox_work_dir),
            (vfs_config.uploads_prefix, "uploads", self.sandbox_uploads_dir),
            (vfs_config.outputs_prefix, "outputs", self.sandbox_outputs_dir),
        )
        for prefix, kind, root_fn in prefixes:
            if stripped == prefix.rstrip("/") or stripped.startswith(prefix):
                relative = stripped[len(prefix) :].lstrip("/")
                base = root_fn(user_id, conversation_id).resolve()
                base.mkdir(parents=True, exist_ok=True)
                if not relative:
                    return base, kind
                physical = (base / relative).resolve()
                if not str(physical).startswith(str(base)):
                    raise ValueError("path traversal detected")
                return physical, kind
        raise ValueError(
            f"path must start with {vfs_config.workspace_prefix}, "
            f"{vfs_config.uploads_prefix}, or {vfs_config.outputs_prefix}"
        )


_paths: Paths | None = None


def get_paths() -> Paths:
    global _paths
    if _paths is None:
        _paths = Paths()
    return _paths
