"""Auto-loaded when the local sandbox prepends this directory to PYTHONPATH."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_vfs_map_path = Path(__file__).resolve().parent / "vfs_map.py"
_spec = importlib.util.spec_from_file_location("_chat_agent_vfs_map", _vfs_map_path)
if _spec is not None and _spec.loader is not None:
    _module = importlib.util.module_from_spec(_spec)
    try:
        _spec.loader.exec_module(_module)
        _module.apply_path_patches()
    except Exception:
        pass
