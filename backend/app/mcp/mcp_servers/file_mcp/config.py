"""File MCP configuration."""

from __future__ import annotations

from app.vfs.config import VFSConfig, vfs_config

# Re-export VFS config for convenience
__all__ = ["vfs_config", "VFSConfig"]
