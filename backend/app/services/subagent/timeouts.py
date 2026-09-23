"""Grace windows so the structured subagent timeout wins over outer cancellations."""

# FastMCP client.call_tool 的超时必须晚于 SubagentService 的 wait_for，
# 否则 handler 会在写出 status=timeout 之前被取消。
DELEGATE_GATEWAY_GRACE_SECONDS = 30

# ToolExecutor 的外层 wait_for 再晚一点，作为 handler 卡死时的兜底。
DELEGATE_EXECUTOR_GRACE_SECONDS = 45
