import { theme, Typography } from "antd";
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

function getQuery(args: Record<string, unknown>): string | null {
  if (typeof args.query !== "string") {
    return null;
  }
  const trimmed = args.query.trim();
  return trimmed || null;
}

function getLanguage(args: Record<string, unknown>): string | null {
  if (typeof args.language !== "string") {
    return null;
  }
  const trimmed = args.language.trim();
  return trimmed || null;
}

const ZreadSearchDocArguments: React.FC<{ args: Record<string, unknown> }> = ({ args }) => {
  const { token } = theme.useToken();
  const query = getQuery(args);
  const repoName = getRepoName(args);
  const language = getLanguage(args);

  return (
    <ul className="m-0 w-full list-disc pl-5 text-sm" style={{ color: token.colorTextSecondary }}>
      {query ? (
        <li>
          <Typography.Text strong>query</Typography.Text>
          {": "}
          <Typography.Text code>{query}</Typography.Text>
        </li>
      ) : null}
      {repoName ? (
        <li>
          <Typography.Text strong>repoName</Typography.Text>
          {": "}
          <Typography.Text code>{repoName}</Typography.Text>
        </li>
      ) : null}
      {language ? (
        <li>
          <Typography.Text strong>language</Typography.Text>
          {": "}
          <Typography.Text code>{language}</Typography.Text>
        </li>
      ) : null}
    </ul>
  );
};

export function renderZreadSearchDocArguments(ctx: ToolRenderContext): React.ReactNode | null {
  const args = parseToolArguments(ctx);
  if (!args) {
    return null;
  }

  const query = getQuery(args);
  const repoName = getRepoName(args);
  const language = getLanguage(args);
  if (!query && !repoName && !language) {
    return <></>;
  }

  return <ZreadSearchDocArguments args={args} />;
}
