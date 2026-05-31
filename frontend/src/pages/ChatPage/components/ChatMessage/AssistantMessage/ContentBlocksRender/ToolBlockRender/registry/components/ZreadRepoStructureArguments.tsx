import { theme, Typography } from "antd";
import React from "react";

import type { ToolRenderContext } from "../types";

function getRepoName(args: Record<string, unknown>): string | null {
  const value = args.repo_name ?? args.repoName ?? args.repo;
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed || null;
}

function getDirPath(args: Record<string, unknown>): string {
  const value = args.dir_path ?? args.dirPath ?? args.path;
  if (typeof value !== "string" || !value.trim()) {
    return "/";
  }
  return value.trim();
}

function toGithubRepoUrl(repoName: string): string | null {
  if (!/^[\w.-]+\/[\w.-]+$/.test(repoName)) {
    return null;
  }
  return `https://github.com/${repoName}`;
}

const ZreadRepoStructureArguments: React.FC<{ renderContext: ToolRenderContext }> = ({ renderContext }) => {
  const { token } = theme.useToken();
  const args = renderContext.toolUseBlock.argumentsJson;
  if (!args) {
    return null;
  }

  const repoName = getRepoName(args);
  if (!repoName) {
    return null;
  }

  const dirPath = getDirPath(args);
  const githubUrl = toGithubRepoUrl(repoName);

  return (
    <ul
      className="m-0 w-full list-disc pl-5 text-sm"
      style={{ color: token.colorTextSecondary }}
    >
      <li>
        <Typography.Text strong>repoName</Typography.Text>
        {": "}
        {githubUrl ? (
          <Typography.Link href={githubUrl} target="_blank" rel="noopener noreferrer">
            {repoName}
          </Typography.Link>
        ) : (
          <Typography.Text code>{repoName}</Typography.Text>
        )}
      </li>
      <li>
        <Typography.Text strong>dirPath</Typography.Text>
        {": "}
        <Typography.Text code>{dirPath}</Typography.Text>
      </li>
    </ul>
  );
};

export function renderZreadRepoStructureArguments(ctx: ToolRenderContext): React.ReactNode | null {
  if (!ctx.toolUseBlock.argumentsJson) {
    return null;
  }
  return <ZreadRepoStructureArguments renderContext={ctx} />;
};
