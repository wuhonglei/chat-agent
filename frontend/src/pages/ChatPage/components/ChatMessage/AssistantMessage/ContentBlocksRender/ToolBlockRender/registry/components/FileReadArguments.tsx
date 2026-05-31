import { Typography } from "antd";
import React from "react";

import type { ToolRenderContext } from "../types";
import { parseToolArguments } from "../utils/parseToolArguments";

const DEFAULT_OFFSET = 1;
const DEFAULT_LIMIT = 1000;

function readNumberArg(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  return undefined;
}

export function renderReadFileArguments(ctx: ToolRenderContext): React.ReactNode | null {
  const args = parseToolArguments(ctx);
  if (!args) {
    return null;
  }

  const offset = readNumberArg(args.offset) ?? DEFAULT_OFFSET;
  const limit = readNumberArg(args.limit) ?? DEFAULT_LIMIT;
  const hasCustomRange = offset !== DEFAULT_OFFSET || limit !== DEFAULT_LIMIT;
  if (!hasCustomRange) {
    return <></>;
  }

  return (
    <Typography.Text type="secondary" className="text-sm">
      offset: {offset}, limit: {limit}
    </Typography.Text>
  );
}
