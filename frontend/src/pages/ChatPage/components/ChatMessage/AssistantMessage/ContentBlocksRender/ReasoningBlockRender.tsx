import { ContentBlockRenderStatus, ThinkingBlock } from "@/interfaces/contentBlock";
import { Think } from "@ant-design/x";
import { useMemoizedFn, useThrottle } from "ahooks";
import { useEffect, useState } from "react";
import StatusTitle from "../../components/StatusTitle";

type Props = {
  contentBlock: ThinkingBlock;
  status: ContentBlockRenderStatus;
};

function isReasoningStatus(status: ContentBlockRenderStatus): boolean {
  return status === ContentBlockRenderStatus.Start || status === ContentBlockRenderStatus.Streaming;
}

export const ReasoningBlockRender = ({ contentBlock, status }: Props) => {
  const displayReasoning = useThrottle(contentBlock.text, {
    wait: 100,
  });
  const isDoing = isReasoningStatus(status);
  const [expanded, setExpanded] = useState<boolean>(isDoing);

  const handleExpandChange = useMemoizedFn((expand: boolean) => {
    setExpanded(expand);
  });

  useEffect(() => {
    if (isDoing) {
      setExpanded(true);
      return;
    }
    const timer = setTimeout(() => {
      setExpanded(false);
    }, 500);
    return () => clearTimeout(timer);
  }, [isDoing]);

  // 没有思考内容时，则显示来源
  if (!contentBlock.text) {
    return null;
  }

  return (
    <Think
      expanded={expanded}
      blink={isDoing}
      onExpand={handleExpandChange}
      title={
        <StatusTitle
          titles={{
            doing: "深度思考中",
            done: "已完成深度思考",
          }}
          isDoing={isDoing}
        />
      }
    >
      {displayReasoning}
    </Think>
  );
};
