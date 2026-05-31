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

  return (
    <ul className="m-0 w-full list-disc pl-5 text-sm">
      {query ? (
        <li>
          <Typography.Text strong type="secondary">
            query
          </Typography.Text>
          {": "}
          <Typography.Text code type="secondary">
            {query}
          </Typography.Text>
        </li>
      ) : null}
      {repoName ? (
        <li>
          <Typography.Text strong type="secondary">
            repoName
          </Typography.Text>
          {": "}
          <Typography.Text code type="secondary">
            {repoName}
          </Typography.Text>
        </li>
      ) : null}
      {language ? (
        <li>
          <Typography.Text strong type="secondary">
            language
          </Typography.Text>
          {": "}
          <Typography.Text code type="secondary">
            {language}
          </Typography.Text>
        </li>
      ) : null}
    </ul>
  );
}
