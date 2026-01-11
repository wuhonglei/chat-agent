import {
  ComponentToolsTokenStats,
  MCPToolsTokenStats,
} from "@/interfaces/token";
import { Descriptions } from "antd";
import React from "react";

type TokenStatsTooltipProps = {
  tokenStats: MCPToolsTokenStats | ComponentToolsTokenStats;
};

const TokenStatsTooltip: React.FC<TokenStatsTooltipProps> = ({
  tokenStats,
}) => {
  const isMCP = tokenStats.agentName === "mcp-tools";
  const isComponentTools = tokenStats.agentName === "component-tools";

  return (
    <div className="max-w-[400px]">
      <Descriptions
        title="Token 统计信息"
        column={1}
        size="small"
        bordered
        labelStyle={{ fontWeight: "bold" }}
      >
        <Descriptions.Item label="Agent 名称">
          {tokenStats.agentName}
        </Descriptions.Item>
        <Descriptions.Item label="模型名称">
          {tokenStats.modelName}
        </Descriptions.Item>
        <Descriptions.Item label="思考模式">
          {tokenStats.thinkMode ? "是" : "否"}
        </Descriptions.Item>
        <Descriptions.Item label="模型限制">
          {tokenStats.modelLimit.toLocaleString()} tokens
        </Descriptions.Item>
        <Descriptions.Item label="输入 tokens">
          {tokenStats.tokenUsage.promptTokens.toLocaleString()}
        </Descriptions.Item>
        <Descriptions.Item label="输出 tokens">
          {tokenStats.tokenUsage.completionTokens.toLocaleString()}
        </Descriptions.Item>
        <Descriptions.Item label="总 tokens">
          {tokenStats.tokenUsage.totalTokens.toLocaleString()}
        </Descriptions.Item>
        {isMCP && (
          <>
            <Descriptions.Item label="工具调用次数">
              {tokenStats.toolCallCount}
            </Descriptions.Item>
            <Descriptions.Item label="工具定义 tokens">
              {tokenStats.toolDefinitionTokens.toLocaleString()}
            </Descriptions.Item>
            {tokenStats.toolCallNames &&
              tokenStats.toolCallNames.length > 0 && (
                <Descriptions.Item label="工具名称">
                  {tokenStats.toolCallNames.join(", ")}
                </Descriptions.Item>
              )}
          </>
        )}
        {isComponentTools && (
          <>
            <Descriptions.Item label="组件工具调用次数">
              {tokenStats.toolCallCount}
            </Descriptions.Item>
            <Descriptions.Item label="组件工具定义 tokens">
              {tokenStats.toolDefinitionTokens.toLocaleString()}
            </Descriptions.Item>
            {tokenStats.toolCallNames &&
              tokenStats.toolCallNames.length > 0 && (
                <Descriptions.Item label="组件工具名称">
                  {tokenStats.toolCallNames.join(", ")}
                </Descriptions.Item>
              )}
          </>
        )}
      </Descriptions>
    </div>
  );
};

export default React.memo(TokenStatsTooltip);
