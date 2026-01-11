import {
  ComponentToolsTokenStats,
  MCPToolsTokenStats,
} from "@/interfaces/token";
import { Descriptions } from "antd";
import { isEmpty } from "lodash-es";
import React from "react";

type TokenStatsTooltipProps = {
  tokenStats: MCPToolsTokenStats | ComponentToolsTokenStats;
};

const getDescriptionItems = (
  tokenStats: MCPToolsTokenStats | ComponentToolsTokenStats
) => {
  const isMCP = tokenStats.agentName === "mcp-tools";
  const isComponentTools = tokenStats.agentName === "component-tools";

  return [
    {
      key: "agentName",
      label: "Agent 名称",
      children: tokenStats.agentName,
    },
    {
      key: "modelName",
      label: "模型名称",
      children: tokenStats.modelName,
    },
    {
      key: "thinkMode",
      label: "思考模式",
      children: tokenStats.thinkMode ? "是" : "否",
    },
    {
      key: "modelLimit",
      label: "模型限制",
      children: `${tokenStats.modelLimit.toLocaleString()} tokens`,
    },
    {
      key: "promptTokens",
      label: "输入 tokens",
      children: tokenStats.tokenUsage.promptTokens.toLocaleString(),
    },
    {
      key: "completionTokens",
      label: "输出 tokens",
      children: tokenStats.tokenUsage.completionTokens.toLocaleString(),
    },
    {
      key: "totalTokens",
      label: "总 tokens",
      children: tokenStats.tokenUsage.totalTokens.toLocaleString(),
    },
    ...(isMCP
      ? [
          {
            key: "toolCallCount",
            label: "工具调用次数",
            children: tokenStats.toolCallCount,
          },
          {
            key: "toolDefinitionTokens",
            label: "工具定义 tokens",
            children: tokenStats.toolDefinitionTokens.toLocaleString(),
          },
          ...(isEmpty(tokenStats.toolCallNames)
            ? []
            : [
                {
                  key: "toolCallNames",
                  label: "工具名称",
                  children: tokenStats.toolCallNames.join(", "),
                },
              ]),
        ]
      : []),
    ...(isComponentTools
      ? [
          {
            key: "componentToolCallCount",
            label: "组件工具调用次数",
            children: tokenStats.toolCallCount,
          },
          {
            key: "componentToolDefinitionTokens",
            label: "组件工具定义 tokens",
            children: tokenStats.toolDefinitionTokens.toLocaleString(),
          },
          ...(isEmpty(tokenStats.toolCallNames)
            ? []
            : [
                {
                  key: "toolCallNames",
                  label: "工具名称",
                  children: tokenStats.toolCallNames.join(", "),
                },
              ]),
        ]
      : []),
  ];
};

const TokenStatsTooltip: React.FC<TokenStatsTooltipProps> = ({
  tokenStats,
}) => {
  const items = getDescriptionItems(tokenStats);

  return (
    <div className="max-w-[400px]">
      <Descriptions
        bordered
        column={1}
        size="small"
        items={items}
        title="Token 统计信息"
        labelStyle={{ fontWeight: "bold" }}
      />
    </div>
  );
};

export default React.memo(TokenStatsTooltip);
