import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import aiofiles
from fastapi import UploadFile
from loguru import logger


def get_file_extension(filename: str) -> str:
    """
    获取文件扩展名

    Returns:
        str: 文件扩展名

    Examples:
        >>> get_file_extension('test.pdf')
        '.pdf'
        >>> get_file_extension('test.docx')
        '.docx'
        >>> get_file_extension('test.txt')
        '.txt'
    """
    return Path(filename).suffix.lower() if filename else ''


def get_file_name(filename: str) -> str:
    """
    获取文件名

    Returns:
        str: 文件名

    Examples:
        >>> get_file_name('test.pdf')
        'test'
        >>> get_file_name('test.docx')
        'test'
        >>> get_file_name('test.txt')
        'test' 
    """
    return Path(filename).stem if filename else ''


async def write_file_async(file_path: str, file: UploadFile):
    """
    写入文件

    Returns:
        str: 文件路径
    """
    content = await file.read()

    # 异步写入临时文件
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)


class TempFileManager:
    """
    临时文件上下文管理器

    自动管理临时文件的创建和删除，确保资源被正确清理

    Examples:
        ```python
        # 同步使用
        with TempFileManager(base_dir, file_ext) as temp_file:
            # 使用 temp_file.path 访问文件路径
            do_something(temp_file.path)
        # 文件自动删除

        # 异步使用
        async with TempFileManager(base_dir, file_ext) as temp_file:
            await do_something_async(temp_file.path)
        # 文件自动删除
        ```
    """

    def __init__(
        self,
        base_dir: Path | str,
        file_extension: str = "",
        prefix: str = "",
        auto_cleanup: bool = True,
    ):
        """
        初始化临时文件管理器

        Args:
            base_dir: 临时文件所在的基础目录
            file_extension: 文件扩展名（如 '.png', '.pdf'）
            prefix: 文件名前缀
            auto_cleanup: 是否自动清理文件（退出上下文时删除）
        """
        self.base_dir = Path(base_dir)
        self.file_extension = file_extension
        self.prefix = prefix
        self.auto_cleanup = auto_cleanup
        self.file_path: Path | None = None
        self._ensure_dir_exists()

    def _ensure_dir_exists(self):
        """确保目录存在"""
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _generate_file_path(self) -> Path:
        """生成唯一的文件路径"""
        file_id = str(uuid.uuid4())
        file_name = f"{self.prefix}{file_id}{self.file_extension}" if self.prefix else f"{file_id}{self.file_extension}"
        return self.base_dir / file_name

    def __enter__(self) -> "TempFileManager":
        """同步上下文管理器入口"""
        self.file_path = self._generate_file_path()
        logger.debug(f"创建临时文件: {self.file_path}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """同步上下文管理器出口"""
        if self.auto_cleanup:
            self._cleanup()

    async def __aenter__(self) -> "TempFileManager":
        """异步上下文管理器入口"""
        self.file_path = self._generate_file_path()
        logger.debug(f"创建临时文件: {self.file_path}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.auto_cleanup:
            self._cleanup()

    def _cleanup(self):
        """清理临时文件"""
        if self.file_path and self.file_path.exists():
            try:
                self.file_path.unlink()
                logger.debug(f"已删除临时文件: {self.file_path}")
            except Exception as e:
                logger.warning(f"删除临时文件失败 {self.file_path}: {e}")

    @property
    def path(self) -> Path:
        """获取文件路径"""
        if self.file_path is None:
            raise RuntimeError("临时文件尚未创建，请先进入上下文管理器")
        return self.file_path

    def keep(self):
        """保留文件（不自动删除）"""
        self.auto_cleanup = False

    def remove(self):
        """手动删除文件"""
        self._cleanup()


@asynccontextmanager
async def temp_file_context(
    base_dir: Path | str,
    file_extension: str = "",
    prefix: str = "",
    auto_cleanup: bool = True,
):
    """
    异步临时文件上下文管理器（函数式接口）

    这是一个便捷函数，提供更简洁的使用方式

    Args:
        base_dir: 临时文件所在的基础目录
        file_extension: 文件扩展名
        prefix: 文件名前缀
        auto_cleanup: 是否自动清理文件

    Yields:
        Path: 临时文件路径

    Examples:
        ```python
        async with temp_file_context(avatar_dir, '.png') as temp_file:
            await write_file_async(temp_file, file)
            # 使用 temp_file
        # 文件自动删除
        ```
    """
    manager = TempFileManager(base_dir, file_extension, prefix, auto_cleanup)
    async with manager:
        yield manager.path
