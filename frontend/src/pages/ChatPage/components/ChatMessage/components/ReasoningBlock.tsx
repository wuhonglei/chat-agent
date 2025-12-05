import { emitter, EventType, useEmitterWithCondition } from "@/events";
import { SearchSource } from "@/interfaces";
import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { Think } from "@ant-design/x";
import { useMemoizedFn, useThrottle } from "ahooks";
import React, { useState } from "react";
import SourceAbstract from "./SourceAbstract";

type Props = {
  isReasoning: boolean;
  isStreaming: boolean;
  reasoning: string | undefined;
  sources: SearchSource[] | undefined;
  onSourceClick: () => void;
};

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
  const [expanded, setExpanded] = useState<boolean>(isStreaming ? true : false);
  const handleExpandChange = useMemoizedFn((expand: boolean) => {
    setExpanded(expand);
    emitter.emit(EventType.BlockCollapse, expand);
  });

  /**
   * 思考内容结束后，折叠思考内容
   */
  useEmitterWithCondition(
    EventType.ReasoningDone,
    () => {
      setTimeout(() => {
        setExpanded(false);
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
    <Think
      expanded={expanded}
      blink={isReasoning}
      onExpand={handleExpandChange}
      title={isReasoning ? "深度思考中" : "已完成深度思考"}
    >
      <SourceAbstract
        sources={sources}
        mode="preSource"
        bordered={false}
        className="-ml-4"
        onClick={onSourceClick}
      />
      <MarkdownContainer gray className="flex-1">
        {displayReasoning}
      </MarkdownContainer>
    </Think>
  );
};

export default React.memo(ReasoningBlock);
