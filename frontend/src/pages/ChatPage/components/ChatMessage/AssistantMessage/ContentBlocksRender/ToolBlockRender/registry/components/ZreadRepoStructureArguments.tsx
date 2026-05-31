import { Typography } from "antd";
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

export function renderZreadRepoStructureArguments(ctx: ToolRenderContext): React.ReactNode | null {
  const args = ctx.toolUseBlock.argumentsJson;
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
    <ul className="m-0 w-full list-disc pl-5 text-sm">
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
        <Typography.Text strong type="secondary">
          dirPath
        </Typography.Text>
        {": "}
        <Typography.Text code type="secondary">
          {dirPath}
        </Typography.Text>
      </li>
    </ul>
  );
}
