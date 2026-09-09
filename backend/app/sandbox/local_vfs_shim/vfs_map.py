"""Translate virtual /mnt paths for local-sandbox Python processes.

Local sandbox only rewrites virtual prefixes in the *command string*. A script
that does ``open("/mnt/user-data/workspace/foo.png")`` still hits a path that
does not exist on the host (macOS has no ``/mnt``). This module is loaded via
``sitecustomize`` when ``CHAT_AGENT_VFS_MAPPINGS`` is set.
"""

from __future__ import annotations

import builtins
import json
import os
from pathlib import Path
from typing import Any

VFS_MAPPINGS_ENV = "CHAT_AGENT_VFS_MAPPINGS"
SHIM_DIR = Path(__file__).resolve().parent

_PATH_FIRST_OS_FUNCS = (
    "access",
    "chdir",
    "chmod",
    "chown",
    "listdir",
    "lstat",
    "mkdir",
    "makedirs",
    "remove",
    "removedirs",
    "rmdir",
    "scandir",
    "stat",
    "truncate",
    "unlink",
    "readlink",
)
_PATH_PAIR_OS_FUNCS = ("rename", "replace", "link", "symlink")

_applied = False
_orig_open = builtins.open
_orig_os: dict[str, Any] = {}


def serialize_mappings(mappings: dict[str, str]) -> str:
    """JSON-encode mappings with longest virtual prefix first."""
    ordered = dict(
        sorted(mappings.items(), key=lambda item: len(item[0]), reverse=True)
    )
    return json.dumps(ordered, ensure_ascii=True)


def load_mappings_from_env(
    raw: str | None = None,
) -> dict[str, str]:
    payload = raw if raw is not None else os.environ.get(VFS_MAPPINGS_ENV, "")
    if not payload.strip():
        return {}
    try:
        loaded = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    if not isinstance(loaded, dict):
        return {}
    mappings = {str(key): str(value) for key, value in loaded.items()}
    return dict(sorted(mappings.items(), key=lambda item: len(item[0]), reverse=True))


def rewrite_virtual_path(path: Any, mappings: dict[str, str] | None = None) -> Any:
    """Rewrite a virtual path to its physical counterpart; leave others unchanged."""
    if isinstance(path, int):
        return path
    table = mappings if mappings is not None else load_mappings_from_env()
    if not table:
        return path
    try:
        text = os.fspath(path)
    except TypeError:
        return path

    is_bytes = isinstance(text, (bytes, bytearray))
    as_str = text.decode("utf-8", "surrogateescape") if is_bytes else text
    for virtual_base, actual_base in table.items():
        if as_str == virtual_base or as_str.startswith(f"{virtual_base}/"):
            rewritten = actual_base + as_str[len(virtual_base) :]
            if is_bytes:
                return rewritten.encode("utf-8", "surrogateescape")
            return rewritten
    return path


def _wrap_path_args(fn: Any, count: int) -> Any:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if args:
            rewritten = list(args)
            limit = min(count, len(rewritten))
            for index in range(limit):
                rewritten[index] = rewrite_virtual_path(rewritten[index])
            args = tuple(rewritten)
        return fn(*args, **kwargs)

    wrapped.__name__ = getattr(fn, "__name__", "wrapped")
    wrapped.__doc__ = getattr(fn, "__doc__", None)
    return wrapped


def apply_path_patches(mappings: dict[str, str] | None = None) -> bool:
    """Patch builtins.open and common os.path operations. Idempotent."""
    global _applied
    table = mappings if mappings is not None else load_mappings_from_env()
    if _applied or not table:
        return False

    os.environ[VFS_MAPPINGS_ENV] = serialize_mappings(table)

    def patched_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        return _orig_open(rewrite_virtual_path(file), *args, **kwargs)

    builtins.open = patched_open

    names = dict.fromkeys(_PATH_FIRST_OS_FUNCS)
    for name in names:
        original = getattr(os, name, None)
        if original is None:
            continue
        _orig_os[name] = original
        setattr(os, name, _wrap_path_args(original, 1))

    for name in _PATH_PAIR_OS_FUNCS:
        original = getattr(os, name, None)
        if original is None:
            continue
        _orig_os[name] = original
        setattr(os, name, _wrap_path_args(original, 2))

    original_os_open = os.open
    _orig_os["open"] = original_os_open

    def patched_os_open(path: Any, *args: Any, **kwargs: Any) -> int:
        return original_os_open(rewrite_virtual_path(path), *args, **kwargs)

    os.open = patched_os_open
    _applied = True
    return True
