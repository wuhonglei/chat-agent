import { Collapse, Divider } from "antd";
import { useMemoizedFn, useThrottle } from "ahooks";
import styles from "./css/ReasoningBlock.module.css";
import MarkdownContainer from "@/components/Chat/MarkdownContainer";
import ThinkModeIcon from "@/assets/svg/ThinkModeIcon.svg?react";
import { SearchSource } from "@/interfaces";
import SourceAbstract from "./SourceAbstract";
import React, { useState } from "react";
import { emitter, EventType, useEmitterWithCondition } from "@/events";
import { isEmpty } from "lodash-es";

type Props = {
  isReasoning: boolean;
  isStreaming: boolean;
  reasoning: string | undefined;
  sources: SearchSource[] | undefined;
  onSourceClick: () => void;
};

const contentKey = "content";

const ReasoningBlock = ({
  isReasoning,
  sources,
  reasoning,
  isStreaming,
  onSourceClick,
}: Props) => {
  const displayReasoning = useThrottle(reasoning, {
    wait: 100,
  });
  const [activeKeys, setActiveKeys] = useState<string[]>(
    isStreaming ? [contentKey] : []
  );
  const handleCollapseChange = useMemoizedFn((keys: string[]) => {
    setActiveKeys(keys);
    emitter.emit(EventType.BlockCollapse, isEmpty(keys));
  });

  /**
   * 思考内容结束后，折叠思考内容
   */
  useEmitterWithCondition(
    EventType.ReasoningDone,
    () => {
      setTimeout(() => {
        setActiveKeys([]);
      }, 500);
    },
    isReasoning
  );

  // 没有思考内容时，则显示来源
  if (!reasoning) {
    return (
      <SourceAbstract
        sources={sources}
        mode="preSource"
        bordered={false}
        className="-ml-4"
        onClick={onSourceClick}
      />
    );
  }

  return (
    <Collapse
      ghost
      collapsible="header"
      expandIconPosition="end"
      activeKey={activeKeys}
      onChange={handleCollapseChange}
      items={[
        {
          key: contentKey,
          label: (
            <span className="text-gray-600">
              {isReasoning ? "深度思考中" : "已完成深度思考"}
            </span>
          ),
          styles: {
            header: { padding: 0, justifyContent: "flex-start" },
            body: { padding: 0 },
          },
          classNames: { header: styles.header },
          children: (
            <section className="flex flex-col gap-1 mt-2 items-start">
              <SourceAbstract
                sources={sources}
                mode="preSource"
                bordered={false}
                className="-ml-4"
                onClick={onSourceClick}
              />
              <div className="flex gap-1">
                <div className="flex flex-col py-1 w-4 items-center gap-1 pb-3">
                  {isReasoning ? (
                    <img
                      alt="thinking"
                      className="w-4 h-4"
                      src={
                        "https://static.deepseek.com/chat/static/thinkIconLight.200a7943a0.png"
                      }
                    />
                  ) : (
                    <ThinkModeIcon className="w-4 h-4 text-primary" />
                  )}
                  <Divider
                    type="vertical"
                    style={{
                      flex: 1,
                      marginLeft: 0,
                      marginRight: 0,
                    }}
                  />
                </div>
                <MarkdownContainer
                  sources={sources}
                  className="flex-1 text-gray-600 text-sm"
                >
                  {displayReasoning}
                </MarkdownContainer>
              </div>
            </section>
          ),
        },
      ]}
    />
  );
};

export default React.memo(ReasoningBlock);
