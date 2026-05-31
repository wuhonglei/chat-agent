import { Typography } from "antd";
import React from "react";

import type { ToolRenderContext } from "../types";
import { parseToolArguments } from "../utils/parseToolArguments";

function getRepoName(args: Record<string, unknown>): string | null {
  const value = args.repo_name ?? args.repoName ?? args.repo;
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed || null;
}

export function renderZreadReadFileArguments(ctx: ToolRenderContext): React.ReactNode | null {
  const args = parseToolArguments(ctx);
  if (!args) {
    return null;
  }

  const repoName = getRepoName(args);
  if (!repoName) {
    return <></>;
  }

  return (
    <Typography.Text type="secondary" className="text-sm">
      repoName: {repoName}
    </Typography.Text>
  );
}
