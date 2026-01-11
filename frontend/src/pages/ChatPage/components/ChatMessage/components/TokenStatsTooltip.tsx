import {
  ComponentToolsTokenStats,
  MCPToolsTokenStats,
} from "@/interfaces/token";
import { prettyCount } from "@/utils";
import { ConfigProvider, Descriptions } from "antd";
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
      label: "深度思考",
      children: tokenStats.thinkMode ? "启用" : "未启用",
    },
    {
      key: "modelLimit",
      label: "模型限制",
      children: prettyCount(tokenStats.modelLimit),
    },
    {
      key: "promptTokens",
      label: "输入 tokens",
      children: prettyCount(tokenStats.tokenUsage.promptTokens),
    },
    {
      key: "completionTokens",
      label: "输出 tokens",
      children: prettyCount(tokenStats.tokenUsage.completionTokens),
    },
    {
      key: "totalTokens",
      label: "总 tokens",
      children: prettyCount(tokenStats.tokenUsage.totalTokens),
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
            children: prettyCount(tokenStats.toolDefinitionTokens),
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
            children: prettyCount(tokenStats.toolDefinitionTokens),
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
    <div
      onClick={e => {
        e.stopPropagation();
        e.preventDefault();
      }}
    >
      <ConfigProvider
        theme={{
          token: {
            colorSplit: "rgba(255, 255, 255, 0.45)",
            colorText: "white",
            colorTextHeading: "white",
            colorTextSecondary: "white",
            colorTextTertiary: "white",
            colorTextQuaternary: "white",
          },
        }}
      >
        <Descriptions
          bordered
          column={1}
          size="small"
          items={items}
          title="Token 统计信息"
          styles={{
            header: { marginBottom: 8 },
            label: { fontWeight: "bold" },
          }}
        />
      </ConfigProvider>
    </div>
  );
};

export default React.memo(TokenStatsTooltip);
