"""Local-sandbox helpers that make virtual /mnt paths work inside Python."""

from app.sandbox.local_vfs_shim.vfs_map import (
    SHIM_DIR,
    VFS_MAPPINGS_ENV,
    apply_path_patches,
    rewrite_virtual_path,
    serialize_mappings,
)

__all__ = [
    "SHIM_DIR",
    "VFS_MAPPINGS_ENV",
    "apply_path_patches",
    "rewrite_virtual_path",
    "serialize_mappings",
]
