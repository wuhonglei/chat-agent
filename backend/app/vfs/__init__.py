"""Virtual File System module for path abstraction."""

from app.vfs.config import VFSConfig, vfs_config
from app.vfs.mapper import MappingContext, VirtualPathMapper
from app.vfs.paths import USER_DATA_ROOT, VIRTUAL_PATH_PREFIX, get_paths
from app.vfs.resolver import (
    FORBIDDEN_SEGMENTS,
    PathPermission,
    PathResolver,
    resolve_relative_under_root,
)
from app.vfs.uploads_provider import UploadsProvider

__all__ = [
    "FORBIDDEN_SEGMENTS",
    "MappingContext",
    "PathPermission",
    "PathResolver",
    "resolve_relative_under_root",
    "UploadsProvider",
    "USER_DATA_ROOT",
    "VFSConfig",
    "VIRTUAL_PATH_PREFIX",
    "VirtualPathMapper",
    "get_paths",
    "vfs_config",
]
