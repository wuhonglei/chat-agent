"""Virtual File System module for path abstraction."""

from app.vfs.config import VFSConfig, vfs_config
from app.vfs.mapper import MappingContext, VirtualPathMapper
from app.vfs.resolver import PathPermission, PathResolver
from app.vfs.uploads_provider import UploadsProvider

__all__ = [
    "MappingContext",
    "PathPermission",
    "PathResolver",
    "UploadsProvider",
    "VFSConfig",
    "VirtualPathMapper",
    "vfs_config",
]
