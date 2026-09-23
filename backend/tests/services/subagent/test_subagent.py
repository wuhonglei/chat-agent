"""Subagent delegation: gates, tool surface, final report, and timeouts."""

from __future__ import annotations

import asyncio
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from fastmcp import Client
from fastmcp.client import FastMCPTransport
from openai.types.chat import ChatCompletionMessageFunctionToolCall
from openai.types.chat.chat_completion_message_function_tool_call import Function

from app.agent_skills.types import AgentSkillManifest
from app.agents.chat_session_agent import resolve_request_mcp_server_names
from app.agents.chat_session_state import SessionOutput
from app.agents.tool_executor import ToolExecutor
from app.core.config import settings
from app.mcp.gateway import MCPToolGateway
from app.mcp.mcp_servers.file_mcp.base import ToolResult
from app.mcp.mcp_servers.subagent_mcp.server import mcp as subagent_mcp
from app.mcp.tool_naming import ToolRoute
from app.prompts.subagent_prompt import (
    build_subagent_system_prompt,
    subagent_workspace_enabled,
)
from app.schemas.config import LLMConfig
from app.schemas.llm import ToolResultMessage
from app.services.subagent import context as delegation_context
from app.services.subagent.budget import goal_rejection_reason
from app.services.subagent.context import (
    TurnDelegationContext,
    append_subagent_run,
    consume_subagent_runs,
    ensure_subagent_run_buffer,
    get_turn_delegation,
    reset_turn_delegation,
    set_turn_delegation,
)
from app.services.subagent.service import SubagentService, resolve_child_skill_catalog
from app.services.subagent.timeouts import DELEGATE_EXECUTOR_GRACE_SECONDS
from app.services.subagent.tool_filter import (
    ExcludedToolConfigError,
    classify_excluded_entry,
    filter_llm_tools,
    is_llm_tool_excluded,
    validate_excluded_tools,
)
from app.utils.context import (
    get_request_context,
    reset_request_context,
    set_request_context,
)


def _route(server_name: str, bare_name: str) -> ToolRoute:
    return ToolRoute(server_name=server_name, mcp_tool_name=bare_name)


def _routes() -> dict[str, ToolRoute]:
    return {
        "file_present_files": _route("file", "present_files"),
        "file_read_file": _route("file", "read_file"),
        "subagent_delegate_task": _route("subagent", "delegate_task"),
        "code_exec_execute_code": _route("code_exec", "execute_code"),
        "skill_manager_load_skill": _route("skill_manager", "load_skill"),
    }


def _get_route(name: str) -> ToolRoute | None:
    routes = _routes()
    if name in routes:
        return routes[name]
    bare_matches = [route for route in routes.values() if route.mcp_tool_name == name]
    if len(bare_matches) == 1:
        return bare_matches[0]
    return None


def _skill_route(name: str) -> ToolRoute | None:
    if name == "skill_manager_load_skill":
        return _route("skill_manager", "load_skill")
    return None


def test_prompt_includes_skill_catalog_when_load_skill_available(
    monkeypatch: Any,
) -> None:
    class _Registry:
        def list_manifests(self) -> list[AgentSkillManifest]:
            return [
                AgentSkillManifest(
                    name="ppt-generation",
                    description="Make slides",
                    location="/mnt/skills/public/ppt-generation/SKILL.md",
                )
            ]

    monkeypatch.setattr(
        "app.services.subagent.service.get_skill_registry",
        lambda _user_id: _Registry(),
    )
    catalog = resolve_child_skill_catalog(
        user_id="user-1",
        mcp_server_names=["file", "skill_manager", "shell"],
        excluded_tools=["subagent_*", "file_present_files"],
        get_tool_route=_skill_route,
    )
    assert catalog is not None
    lines, tool_name = catalog
    prompt = build_subagent_system_prompt(
        context=None,
        model_name="parent-model",
        language="zh",
        skill_catalog_lines=lines,
        load_skill_tool_name=tool_name,
    )
    assert "`ppt-generation`" in prompt
    assert "skill_manager_load_skill" in prompt
    assert "<skill_system>" in prompt
    assert "<available_skills>" in prompt
    empty = build_subagent_system_prompt(
        context=None,
        model_name="parent-model",
        language="zh",
        skill_catalog_lines=[],
        load_skill_tool_name=tool_name,
    )
    assert "<skill_system>" in empty
    assert "(no skills available)" in empty


def test_prompt_omits_skill_catalog_without_load_skill() -> None:
    assert (
        resolve_child_skill_catalog(
            user_id="user-1",
            mcp_server_names=["time", "subagent"],
            excluded_tools=["subagent_*", "file_present_files"],
            get_tool_route=_skill_route,
        )
        is None
    )
    assert (
        resolve_child_skill_catalog(
            user_id="user-1",
            mcp_server_names=["file", "skill_manager", "shell"],
            excluded_tools=["skill_manager_*"],
            get_tool_route=_skill_route,
        )
        is None
    )
    prompt = build_subagent_system_prompt(
        context=None,
        model_name="parent-model",
        language="zh",
    )
    assert "<context>" not in prompt
    assert "<skill_system>" not in prompt
    assert "<working_directory" not in prompt
    assert "skill_manager_load_skill" not in prompt


def test_workspace_block_follows_file_tools_not_agent_mode() -> None:
    assert subagent_workspace_enabled(["time", "subagent"], ["subagent_*"]) is False
    assert (
        subagent_workspace_enabled(
            ["file", "skill_manager"],
            ["subagent_*", "file_present_files"],
        )
        is True
    )
    assert subagent_workspace_enabled(["file"], ["file_*"]) is False
    with_files = build_subagent_system_prompt(
        context="背景",
        model_name="parent-model",
        language="zh",
        include_workspace=True,
    )
    assert "<context>" in with_files
    assert "背景" in with_files
    assert "<working_directory" in with_files
    assert "<skill_system>" not in with_files


def test_goal_rejection() -> None:
    assert goal_rejection_reason("") == "goal 不能为空"
    assert goal_rejection_reason("   ") == "goal 不能为空"
    assert goal_rejection_reason("see TODO below") is not None
    assert goal_rejection_reason("梳理压缩链路") is None


def test_excluded_tools_match_canonical_and_server_wildcard() -> None:
    excluded = ["subagent_*", "file_present_files"]
    assert is_llm_tool_excluded("subagent_delegate_task", excluded, _get_route)
    assert is_llm_tool_excluded("file_present_files", excluded, _get_route)
    assert not is_llm_tool_excluded("file_read_file", excluded, _get_route)
    assert not is_llm_tool_excluded("code_exec_execute_code", ["code_*"], _get_route)
    assert is_llm_tool_excluded("code_exec_execute_code", ["code_exec_*"], _get_route)


def test_excluded_tools_do_not_match_bare_names() -> None:
    assert not is_llm_tool_excluded("present_files", ["present_files"], _get_route)
    tools = [
        {"type": "function", "function": {"name": "file_present_files"}},
        {"type": "function", "function": {"name": "file_read_file"}},
        {"type": "function", "function": {"name": "subagent_delegate_task"}},
    ]
    kept = filter_llm_tools(tools, ["subagent_*", "file_present_files"], _get_route)
    assert [tool["function"]["name"] for tool in kept] == ["file_read_file"]


def test_validate_excluded_tools_rejects_bare_alias(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        settings.subagent,
        "excluded_tools",
        ["present_files"],
    )
    assert (
        classify_excluded_entry(
            "present_files",
            get_tool_route=_get_route,
            registered_servers={"file", "subagent"},
        )
        == "error"
    )
    try:
        validate_excluded_tools(
            get_tool_route=_get_route,
            registered_servers={"file", "subagent"},
        )
    except ExcludedToolConfigError as exc:
        assert "file_present_files" in str(exc)
    else:
        raise AssertionError("expected ExcludedToolConfigError")


def test_validate_excluded_tools_warns_for_unknown(monkeypatch: Any) -> None:
    monkeypatch.setattr(settings.subagent, "excluded_tools", ["missing_*"])
    validate_excluded_tools(
        get_tool_route=_get_route,
        registered_servers={"file"},
    )


def test_resolve_servers_follows_mode_lists(monkeypatch: Any) -> None:
    monkeypatch.setattr(settings.mcp, "normal_mode_servers", ["time", "subagent"])
    monkeypatch.setattr(settings.mcp, "agent_mode_servers", ["file"])
    assert resolve_request_mcp_server_names(agent_mode=0) == ["time", "subagent"]
    assert resolve_request_mcp_server_names(agent_mode=1) == ["file"]


def test_delegate_timeout_is_separate_from_batch_timeout() -> None:
    executor = ToolExecutor(
        cast(Any, object()),
        "message",
        "gpt-4o-mini",
        131072,
    )
    assert executor.timeout_seconds_for_tool("file_read_file") == float(
        ToolExecutor.OVERALL_TIMEOUT_SECONDS
    )
    assert executor.timeout_seconds_for_tool("subagent_delegate_task") == float(
        settings.subagent.timeout_seconds
    ) + float(DELEGATE_EXECUTOR_GRACE_SECONDS)


def test_child_iteration_override_constant() -> None:
    assert settings.subagent.max_iterations == 10


async def _run_delegate_beside_slow_tool(
    executor: ToolExecutor,
) -> list[ToolResultMessage]:
    async def execute_single_tool(
        *,
        tool_call: ChatCompletionMessageFunctionToolCall,
        current_iteration: int,
        extracted_urls: set[str],
        on_arguments_recorded: Any,
    ) -> ToolResultMessage:
        _ = (current_iteration, extracted_urls, on_arguments_recorded)
        if tool_call.function.name == "subagent_delegate_task":
            await asyncio.sleep(0.15)
            content = "delegated"
        else:
            await asyncio.sleep(0.2)
            content = "normal-finished"
        return ToolResultMessage(
            role="tool",
            is_error=False,
            content=content,
            tool_call_id=tool_call.id,
        )

    executor.execute_single_tool = execute_single_tool  # type: ignore[method-assign]
    executor.OVERALL_TIMEOUT_SECONDS = 0.05  # type: ignore[misc]

    def tool_call(name: str, call_id: str) -> ChatCompletionMessageFunctionToolCall:
        return ChatCompletionMessageFunctionToolCall(
            id=call_id,
            type="function",
            function=Function(name=name, arguments="{}"),
        )

    return await executor.execute_tool_calls_parallel(
        tool_calls=[
            tool_call("time_get_current_time", "normal"),
            tool_call("subagent_delegate_task", "delegate"),
        ],
        current_iteration=0,
        extracted_urls=set(),
        on_arguments_recorded=lambda *_args: None,
    )


@pytest.mark.asyncio
async def test_delegate_is_not_cancelled_by_batch_timeout(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(settings.subagent, "timeout_seconds", 1)
    monkeypatch.setattr(
        "app.agents.tool_executor.DELEGATE_EXECUTOR_GRACE_SECONDS",
        0,
    )
    executor = ToolExecutor(
        cast(Any, object()),
        "message",
        "gpt-4o-mini",
        131072,
    )
    executor.reset_for_request("message", user_id="user-1", conversation_id="conv-1")
    results = await _run_delegate_beside_slow_tool(executor)
    by_id = {result.tool_call_id: result for result in results}
    assert by_id["delegate"].content == "delegated"
    assert by_id["normal"].is_error
    assert "超时" in by_id["normal"].content


def _parent_llm() -> LLMConfig:
    return LLMConfig(
        api_key="test",
        api_base="http://example.invalid",
        model_name="parent-model",
        context_limit=8192,
        max_output_tokens=1024,
    )


@pytest.mark.asyncio
async def test_service_returns_full_report(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "app.services.subagent.service.resolve_subagent_llm",
        lambda parent: parent,
    )
    captured: dict[str, Any] = {}

    class FakeAgent:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.session_output = SessionOutput()
            self.session_output.content = "H" * 30 + "M" * 40 + "T" * 30
            self.session_output.input_tokens = 11
            self.session_output.output_tokens = 4
            self.content = self.session_output.content
            self.tool_round_messages: list[Any] = []

        async def stream_session_events(self, **kwargs: Any) -> Any:
            captured["stream"] = kwargs
            if False:
                yield ""

    monkeypatch.setattr("app.services.subagent.service.ChatSessionAgent", FakeAgent)
    monkeypatch.setattr(
        "app.services.subagent.service.HistoryContextService",
        lambda **_kwargs: object(),
    )
    set_turn_delegation(
        TurnDelegationContext(
            llm_config=_parent_llm(),
            agent_mode=0,
            language="zh",
            think_mode=False,
            mcp_server_names=["time", "subagent"],
        )
    )
    ensure_subagent_run_buffer()
    set_request_context(user_id="user-1", conversation_id="conv-1")

    result = await SubagentService(cast(Any, object())).run(
        goal="梳理压缩链路", context="只看 guard"
    )
    assert result.is_error is False
    assert result.content == "H" * 30 + "M" * 40 + "T" * 30
    stream = captured["stream"]
    assert stream["max_tool_iterations"] == settings.subagent.max_iterations
    assert stream["llm_rendered_text"] == "梳理压缩链路"
    assert "<context>" in stream["system_prompt_override"]
    assert "只看 guard" in stream["system_prompt_override"]
    assert "梳理压缩链路" not in stream["system_prompt_override"]
    assert "<skill_system>" not in stream["system_prompt_override"]
    assert "<working_directory" not in stream["system_prompt_override"]
    assert stream["history_messages"] == []
    assert stream["mcp_server_names"] == ["time", "subagent"]
    assert "subagent_*" in stream["excluded_tools"]
    assert "file_present_files" in stream["excluded_tools"]
    runs = consume_subagent_runs()
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert runs[0]["tokens"] == {"input": 11, "output": 4}
    assert "goal" not in runs[0]
    assert runs[0]["goal_digest"].startswith("sha256:")
    assert "梳理" not in runs[0]["goal_digest"]


@pytest.mark.asyncio
async def test_service_rejects_todo_before_running(monkeypatch: Any) -> None:
    called = False

    class FakeAgent:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            nonlocal called
            called = True

    monkeypatch.setattr("app.services.subagent.service.ChatSessionAgent", FakeAgent)
    result = await SubagentService(cast(Any, object())).run(goal="TODO: fill this")
    assert result.is_error
    assert called is False


@pytest.mark.asyncio
async def test_open_session_still_receives_parent_turn(monkeypatch: Any) -> None:
    """A FastMCP session started before set_turn_delegation must still see it.

    The in-process server runs the tool on the session task, which copied
    contextvars at connect time. The gateway republishes the caller snapshot
    through request meta.
    """

    async def fake_run(
        self: Any, *, goal: str, context: str | None = None
    ) -> ToolResult:
        del self, goal, context
        parent = get_turn_delegation()
        if parent is None:
            return ToolResult(content="缺少父对话上下文，无法委派", is_error=True)
        request = get_request_context()
        append_subagent_run({"status": "completed"})
        return ToolResult(
            content=(
                f"{parent.llm_config.model_name}|{request.user_id}|"
                f"{request.conversation_id}"
            ),
            is_error=False,
        )

    monkeypatch.setattr(SubagentService, "run", fake_run)
    monkeypatch.setattr(
        "app.mcp.mcp_servers.subagent_mcp.delegate_task.get_mcp_client_manager",
        lambda: object(),
    )

    reset_turn_delegation()
    reset_request_context()
    client: Client[Any] = Client(transport=FastMCPTransport(subagent_mcp))
    try:
        async with client:
            tools = await client.list_tools()
            delegate = next(tool for tool in tools if tool.name == "delegate_task")
            assert "ctx" not in (delegate.inputSchema or {}).get("properties", {})

            registry = MagicMock()
            registry.get_servers.return_value = {"subagent"}
            pool = MagicMock()
            pool._initialized = True
            pool.ensure_initialized = MagicMock()
            pool.clients = {"subagent": client}
            pool.tools_by_server = {"subagent": tools}
            gateway = MCPToolGateway(pool, registry)
            gateway.rebuild_tool_index()

            set_turn_delegation(
                TurnDelegationContext(
                    llm_config=_parent_llm(),
                    agent_mode=1,
                    language="zh",
                    think_mode=False,
                    mcp_server_names=["subagent", "file"],
                )
            )
            set_request_context(user_id="user-1", conversation_id="conv-1")
            ensure_subagent_run_buffer()

            result, _warnings = await gateway.call_tool(
                "subagent_delegate_task",
                {"goal": "整理父对话看不到的子任务"},
            )
        text = MCPToolGateway.format_mcp_result(result)
        assert text == "parent-model|user-1|conv-1"
        assert get_turn_delegation() is not None
        assert get_request_context().user_id == "user-1"
        runs = consume_subagent_runs()
        assert len(runs) == 1
        assert runs[0]["status"] == "completed"
    finally:
        reset_turn_delegation()
        reset_request_context()


@pytest.mark.asyncio
async def test_resumed_generator_task_still_delegates(monkeypatch: Any) -> None:
    """Title streaming resumes the agent generator in a fresh task per chunk.

    That task does not keep ``ContextVar.set`` from the previous chunk. The
    snapshot has to ride on the request object created before those tasks.
    """

    async def fake_run(
        self: Any, *, goal: str, context: str | None = None
    ) -> ToolResult:
        del self, goal, context
        parent = get_turn_delegation()
        if parent is None:
            return ToolResult(content="缺少父对话上下文，无法委派", is_error=True)
        return ToolResult(content=parent.llm_config.model_name, is_error=False)

    monkeypatch.setattr(SubagentService, "run", fake_run)
    monkeypatch.setattr(
        "app.mcp.mcp_servers.subagent_mcp.delegate_task.get_mcp_client_manager",
        lambda: object(),
    )
    reset_turn_delegation()
    reset_request_context()
    set_request_context(user_id="user-1", conversation_id="conv-1")
    client: Client[Any] = Client(transport=FastMCPTransport(subagent_mcp))

    async def generate() -> Any:
        set_turn_delegation(
            TurnDelegationContext(
                llm_config=_parent_llm(),
                agent_mode=1,
                language="zh",
                think_mode=False,
                mcp_server_names=["subagent"],
            )
        )
        yield "armed"
        assert delegation_context._turn_delegation.get() is None
        assert get_turn_delegation() is not None
        registry = MagicMock()
        registry.get_servers.return_value = {"subagent"}
        pool = MagicMock()
        pool._initialized = True
        pool.ensure_initialized = MagicMock()
        pool.clients = {"subagent": client}
        pool.tools_by_server = {"subagent": tools}
        gateway = MCPToolGateway(pool, registry)
        gateway.rebuild_tool_index()
        result, _warnings = await gateway.call_tool(
            "subagent_delegate_task",
            {"goal": "在新任务里继续委派"},
        )
        yield MCPToolGateway.format_mcp_result(result)

    try:
        async with client:
            tools = await client.list_tools()
            generator = generate()
            assert await asyncio.create_task(generator.__anext__()) == "armed"
            assert await asyncio.create_task(generator.__anext__()) == "parent-model"
    finally:
        reset_turn_delegation()
        reset_request_context()
