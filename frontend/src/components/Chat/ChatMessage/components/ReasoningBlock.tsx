import { Collapse, Divider } from "antd";
import { useThrottle } from "ahooks";
import styles from "./css/ReasoningBlock.module.css";
import MarkdownContainer from "./MarkdownContainer";
import ThinkingIcon from "@/assets/svg/dsIcon.svg?react";

type Props = {
  isReasoning: boolean;
  reasoning: string | undefined;
};

export default function ReasoningBlock({ isReasoning, reasoning }: Props) {
  const displayReasoning = useThrottle(reasoning, {
    wait: 100,
  });

  if (!reasoning) {
    return null;
  }

  return (
    <Collapse
      ghost
      collapsible="header"
      expandIconPosition="end"
      defaultActiveKey={["content"]}
      items={[
        {
          key: "content",
          label: (
            <span className="text-gray-600">
              {isReasoning ? "深度思考中" : "已完成深度思考"}
            </span>
          ),
          styles: { header: { padding: 0, justifyContent: "flex-start" } },
          classNames: { header: styles.header },
          children: (
            <section className="flex relative">
              <Divider
                type="vertical"
                style={{ height: "auto", marginLeft: 0, marginRight: "12px" }}
              />
              <div className="absolute top-0 -left-2 bg-white py-1">
                {isReasoning ? (
                  <img
                    alt="thinking"
                    className="w-4 h-4"
                    src={
                      "https://static.deepseek.com/chat/static/thinkIconLight.200a7943a0.png"
                    }
                  />
                ) : (
                  <ThinkingIcon className="w-4 h-4 text-blue-500" />
                )}
              </div>
              <MarkdownContainer className="text-gray-600 flex-1">
                {displayReasoning}
              </MarkdownContainer>
            </section>
          ),
        },
      ]}
    />
  );
}
