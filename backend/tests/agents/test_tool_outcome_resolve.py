"""shell / code 工具成功判定（按退出码）单元测试。"""

from __future__ import annotations

from app.agents.tool_executor import ToolExecutor
from app.mcp.constants import CODE_SERVER, SHELL_SERVER


def test_resolve_shell_success_when_exit_code_zero() -> None:
    success, error_type, meta = ToolExecutor._resolve_tool_outcome(
        server_name=SHELL_SERVER,
        content="$ echo hi\n[exit_code=0]\nhi",
        structured_content={"exit_code": 0, "stdout": "hi", "blocked": False},
    )
    assert success is True
    assert error_type is None
    assert meta == {"exit_code": 0}


def test_resolve_shell_failure_on_non_zero_exit() -> None:
    success, error_type, meta = ToolExecutor._resolve_tool_outcome(
        server_name=SHELL_SERVER,
        content="$ false\n[exit_code=1]",
        structured_content={"exit_code": 1, "stderr": "fail"},
    )
    assert success is False
    assert error_type == "non_zero_exit"
    assert meta == {"exit_code": 1}


def test_resolve_shell_failure_on_blocked() -> None:
    success, error_type, meta = ToolExecutor._resolve_tool_outcome(
        server_name=SHELL_SERVER,
        content="$ rm -rf /\n[blocked] denied",
        structured_content={
            "exit_code": -1,
            "blocked": True,
            "block_reason": "denied",
        },
    )
    assert success is False
    assert error_type == "blocked"
    assert meta["exit_code"] == -1


def test_resolve_shell_failure_on_timed_out() -> None:
    success, error_type, _meta = ToolExecutor._resolve_tool_outcome(
        server_name=SHELL_SERVER,
        content="$ sleep 999\n[exit_code=124]\n[timed_out=true]",
        structured_content={"exit_code": 124, "timed_out": True},
    )
    assert success is False
    assert error_type == "timed_out"


def test_resolve_shell_audit_block_without_structured() -> None:
    success, error_type, _meta = ToolExecutor._resolve_tool_outcome(
        server_name=SHELL_SERVER,
        content="Error: Command blocked: security violation detected",
        structured_content=None,
    )
    assert success is False
    assert error_type == "blocked"


def test_resolve_code_success_when_run_code_zero() -> None:
    success, error_type, meta = ToolExecutor._resolve_tool_outcome(
        server_name=CODE_SERVER,
        content="退出码: 0\n标准输出:\nok",
        structured_content={
            "language": "python",
            "version": "3.12",
            "run": {"code": 0, "stdout": "ok", "stderr": "", "signal": None},
            "compile": None,
        },
    )
    assert success is True
    assert error_type is None
    assert meta == {"exit_code": 0}


def test_resolve_code_failure_on_non_zero_run() -> None:
    success, error_type, meta = ToolExecutor._resolve_tool_outcome(
        server_name=CODE_SERVER,
        content="退出码: 1",
        structured_content={
            "run": {"code": 1, "stdout": "", "stderr": "boom", "signal": None},
        },
    )
    assert success is False
    assert error_type == "non_zero_exit"
    assert meta == {"exit_code": 1}


def test_resolve_code_failure_on_compile() -> None:
    success, error_type, meta = ToolExecutor._resolve_tool_outcome(
        server_name=CODE_SERVER,
        content="编译退出码: 1",
        structured_content={
            "compile": {"code": 1, "stderr": "syntax error"},
            "run": {"code": None, "stdout": "", "stderr": "", "signal": None},
        },
    )
    assert success is False
    assert error_type == "compile_failed"
    assert meta == {"compile_code": 1}


def test_resolve_code_failure_on_signal() -> None:
    success, error_type, meta = ToolExecutor._resolve_tool_outcome(
        server_name=CODE_SERVER,
        content="终止信号: SIGKILL",
        structured_content={
            "run": {"code": None, "stdout": "", "stderr": "", "signal": "SIGKILL"},
        },
    )
    assert success is False
    assert error_type == "signal"
    assert meta["signal"] == "SIGKILL"


def test_resolve_default_empty_content_is_failure() -> None:
    success, error_type, meta = ToolExecutor._resolve_tool_outcome(
        server_name="tavily",
        content="",
        structured_content=None,
    )
    assert success is False
    assert error_type == "empty_result"
    assert meta == {}
