import { TokenStatsAgentName } from "@/interfaces";
import { TokenStats } from "@/interfaces/token";
import { prettyCount } from "@/utils";
import { DescriptionsProps } from "antd";
import { isEmpty } from "lodash-es";

export const getDescriptionItems = (tokenStats: TokenStats) => {
  const isTitleGeneration = tokenStats.agentName === TokenStatsAgentName.TitleGeneration;
  const isMCP = tokenStats.agentName === TokenStatsAgentName.McpTools;
  const isResponseGeneration = tokenStats.agentName === TokenStatsAgentName.ResponseGeneration;

  const items: DescriptionsProps["items"] = [
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
  ];

  if (isTitleGeneration) {
    items.push({
      key: "titleGenerationTokens",
      label: "标题生成 tokens",
      children: tokenStats.title || "",
    });
  }

  if (isMCP) {
    items.push(
      {
        key: "toolCallCount",
        label: "工具调用次数",
        children: tokenStats.toolCallCount,
      },
      {
        key: "toolDefinitionTokens",
        label: "工具定义 tokens",
        children: prettyCount(tokenStats.toolDefinitionTokens),
      }
    );

    if (!isEmpty(tokenStats.toolCallNames)) {
      items.push({
        key: "toolCallNames",
        label: "工具名称",
        children: tokenStats.toolCallNames.join("\n"),
      });
    }
  }

  if (isResponseGeneration) {
    items.push(
      {
        key: "responseGenerationReasoningTokens",
        label: "推理 tokens",
        children: prettyCount(tokenStats.reasoningTokens || 0),
      },
      {
        key: "responseGenerationContentTokens",
        label: "内容 tokens",
        children: prettyCount(tokenStats.contentTokens || 0),
      }
    );
  }

  return items;
};
