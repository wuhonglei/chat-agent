"""Agent skills + sandbox workspace tools MCP server."""

from __future__ import annotations

import shutil
import subprocess

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from pydantic import Field

from app.agent_skills import (
    skill_registry,
)
from app.mcp.mcp_servers.agent_skills_mcp.config import (
    MAX_READ_CHARS,
    MAX_SKILL_BODY_CHARS,
)
from app.mcp.mcp_servers.agent_skills_mcp.utils import (
    ensure_safe_bash_command,
    ensure_write_quota,
    format_usage,
    get_workspace_root,
    resolve_workspace_path,
    truncate_content,
)
from app.utils.logger import logger

mcp = FastMCP(name="Agent Skills MCP Service")


@mcp.tool(name="load_skill")
async def load_skill(
    name: str = Field(
        description=(
            "技能名称（技能唯一标识），传入需要加载的 skill name；"
            "具体可用项由服务端注册表与白名单配置决定"
        )
    ),
) -> ToolResult:
    """加载指定技能文档内容，返回技能正文与基础元信息。"""
    document = skill_registry.load(name)
    body = document.body
    truncated = False
    if len(body) > MAX_SKILL_BODY_CHARS:
        body = body[:MAX_SKILL_BODY_CHARS]
        truncated = True
    content = body + ("\n\n[Truncated by system limit]" if truncated else "")
    logger.info(
        "Agent skill loaded",
        skill_name=name,
        truncated=truncated,
        body_length=len(content),
    )
    return ToolResult(
        content=content,
        structured_content={
            "name": document.manifest.name,
            "description": document.manifest.description,
            "truncated": truncated,
        },
    )


@mcp.tool(name="list_workspace_files")
async def list_workspace_files(
    user_id: str = Field(description="当前用户ID"),
    path: str = Field(default="", description="相对 workspace 根目录路径"),
) -> ToolResult:
    """列出用户工作区指定目录下的文件与子目录信息。"""
    root, target = resolve_workspace_path(user_id, path)
    if not target.exists():
        raise ValueError("path does not exist")
    if not target.is_dir():
        raise ValueError("path is not a directory")

    items: list[dict[str, str | int]] = []
    for child in sorted(target.iterdir(), key=lambda item: item.name.lower()):
        items.append(
            {
                "name": child.name,
                "type": "dir" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else 0,
            }
        )
    logger.info(
        "Workspace listed",
        user_id=user_id,
        path=str(target),
        items_count=len(items),
    )
    return ToolResult(
        content=f"Listed {len(items)} items under {target}",
        structured_content={"items": items, "usage": format_usage(root)},
    )


@mcp.tool(name="read_workspace_file")
async def read_workspace_file(
    user_id: str = Field(description="当前用户ID"),
    path: str = Field(description="相对 workspace 根目录的文件路径"),
) -> ToolResult:
    """读取用户工作区内单个文件内容，超长内容会被截断。"""
    _, target = resolve_workspace_path(user_id, path)
    if not target.exists() or not target.is_file():
        raise ValueError("file does not exist")
    content = target.read_text(encoding="utf-8", errors="replace")
    truncated = False
    if len(content) > MAX_READ_CHARS:
        content = content[:MAX_READ_CHARS]
        truncated = True
    logger.info(
        "Workspace file read",
        user_id=user_id,
        path=str(target),
        truncated=truncated,
    )
    return ToolResult(
        content=content + ("\n\n[Truncated by system limit]" if truncated else ""),
        structured_content={
            "path": str(path),
            "truncated": truncated,
            "size": target.stat().st_size,
        },
    )


@mcp.tool(name="write_workspace_file")
async def write_workspace_file(
    user_id: str = Field(description="当前用户ID"),
    path: str = Field(description="相对 workspace 根目录的文件路径"),
    content: str = Field(description="要写入的文本内容"),
) -> ToolResult:
    """向用户工作区写入文本文件，必要时自动创建父目录。"""
    root, target = resolve_workspace_path(user_id, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    ensure_write_quota(root, target=target, content=content)
    target.write_text(content, encoding="utf-8")
    logger.info(
        "Workspace file written",
        user_id=user_id,
        path=str(target),
        bytes=len(content.encode("utf-8")),
    )
    return ToolResult(
        content=f"Wrote file: {target}",
        structured_content={"path": str(path), "usage": format_usage(root)},
    )


@mcp.tool(name="delete_workspace_file")
async def delete_workspace_file(
    user_id: str = Field(description="当前用户ID"),
    path: str = Field(description="相对 workspace 根目录的文件或目录路径"),
) -> ToolResult:
    """删除用户工作区中的文件或目录（不允许删除工作区根目录）。"""
    root, target = resolve_workspace_path(user_id, path)
    if not target.exists():
        raise ValueError("path does not exist")
    if target == root:
        raise ValueError("cannot delete workspace root")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    logger.info("Workspace path deleted", user_id=user_id, path=str(target))
    return ToolResult(
        content=f"Deleted path: {target}",
        structured_content={"path": str(path), "usage": format_usage(root)},
    )


@mcp.tool(name="clear_workspace")
async def clear_workspace(
    user_id: str = Field(description="当前用户ID"),
) -> ToolResult:
    """清空用户工作区根目录下的全部内容。"""
    root = get_workspace_root(user_id)
    if root.exists():
        for child in root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    logger.info("Workspace cleared", user_id=user_id, path=str(root))
    return ToolResult(
        content=f"Workspace cleared: {root}",
        structured_content={"usage": format_usage(root)},
    )


@mcp.tool(name="run_bash")
async def run_bash(
    user_id: str = Field(description="当前用户ID"),
    command: str = Field(description="要执行的 bash 命令"),
    cwd: str = Field(default="", description="命令执行目录（相对 workspace 根目录）"),
    timeout_seconds: int = Field(default=30, ge=1, le=300, description="超时秒数"),
) -> ToolResult:
    """在用户工作区内执行受限 bash 命令并返回执行结果（cwd 相对 workspace 根目录）。"""
    ensure_safe_bash_command(command)
    root, target = resolve_workspace_path(user_id, cwd)
    if not target.exists():
        raise ValueError("cwd does not exist")
    if not target.is_dir():
        raise ValueError("cwd is not a directory")

    try:
        completed = subprocess.run(
            command,
            cwd=target,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        exit_code = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout_raw = exc.stdout or ""
        stderr_raw = exc.stderr or ""
        stdout = (
            stdout_raw.decode("utf-8", errors="replace")
            if isinstance(stdout_raw, bytes)
            else stdout_raw
        )
        stderr = (
            stderr_raw.decode("utf-8", errors="replace")
            if isinstance(stderr_raw, bytes)
            else stderr_raw
        )
        exit_code = None
        timed_out = True

    output = (
        f"$ {command}\n"
        f"[cwd={target}]\n"
        f"[exit_code={exit_code}]\n"
        f"[timed_out={timed_out}]\n\n"
        f"--- stdout ---\n{stdout}\n"
        f"--- stderr ---\n{stderr}"
    )
    content, truncated = truncate_content(output)
    if truncated:
        content += "\n\n[Truncated by system limit]"

    logger.info(
        "Bash command executed",
        user_id=user_id,
        path=str(target),
        exit_code=exit_code,
        timed_out=timed_out,
        truncated=truncated,
    )
    return ToolResult(
        content=content,
        structured_content={
            "workspace_root": str(root),
            "cwd": str(target),
            "exit_code": exit_code,
            "timed_out": timed_out,
            "truncated": truncated,
        },
    )
