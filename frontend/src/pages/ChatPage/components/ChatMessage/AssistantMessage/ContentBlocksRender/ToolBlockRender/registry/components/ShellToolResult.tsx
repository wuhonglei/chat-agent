import { isShellExecDisplayItem, type ShellExecDisplayItem } from "@/interfaces/contentBlock";
import { Tag, Typography } from "antd";
import React from "react";

import type { ToolRenderContext } from "../types";

function normalizeOutputText(text: string): string {
  if (text.includes("\\n") && !text.includes("\n")) {
    return text.replace(/\\r\\n/g, "\n").replace(/\\n/g, "\n");
  }
  return text;
}

function findShellDisplayItem(ctx: ToolRenderContext): ShellExecDisplayItem | null {
  const items = ctx.toolResultBlock?.structuredContentForDisplay;
  if (!items?.length) {
    return null;
  }
  const shellItem = items.find(isShellExecDisplayItem);
  return shellItem ?? null;
}

export function renderShellToolResult(ctx: ToolRenderContext): React.ReactNode | null {
  const display = findShellDisplayItem(ctx);
  if (!display) {
    return null;
  }

  const stdout = display.stdout ? normalizeOutputText(display.stdout) : "";
  const stderr = display.stderr ? normalizeOutputText(display.stderr) : "";
  const hasOutput = Boolean(stdout || stderr);

  return (
    <div className="w-full space-y-3 rounded border border-(--ant-color-border-secondary) bg-(--ant-color-bg-container) p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Typography.Text type="secondary">退出码</Typography.Text>
        <Tag>{display.exitCode}</Tag>
        {display.timedOut ? <Tag color="orange">timed out</Tag> : null}
        {display.outputTruncated ? <Tag color="orange">output truncated</Tag> : null}
        {display.blocked ? <Tag color="red">blocked</Tag> : null}
        {display.durationMs != null && display.durationMs > 0 ? (
          <Typography.Text type="secondary">{display.durationMs}ms</Typography.Text>
        ) : null}
      </div>
      {display.blockReason ? (
        <Typography.Text type="danger" className="block">
          {display.blockReason}
        </Typography.Text>
      ) : null}
      {hasOutput ? (
        <>
          {stdout ? (
            <>
              <Typography.Text type="secondary" className="block">
                stdout
              </Typography.Text>
              <pre className="mt-1 mb-0 max-h-[220px] overflow-auto whitespace-pre-wrap wrap-break-word text-sm">
                {stdout}
              </pre>
            </>
          ) : null}
          {stderr ? (
            <>
              <Typography.Text type="secondary" className="block">
                stderr
              </Typography.Text>
              <pre className="mt-1 mb-0 max-h-[220px] overflow-auto whitespace-pre-wrap wrap-break-word text-sm text-(--ant-color-error)">
                {stderr}
              </pre>
            </>
          ) : null}
        </>
      ) : (
        <Typography.Text type="secondary">命令执行完成，无输出。</Typography.Text>
      )}
    </div>
  );
}
