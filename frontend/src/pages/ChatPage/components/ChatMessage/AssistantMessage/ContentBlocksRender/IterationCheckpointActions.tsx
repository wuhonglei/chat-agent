import { IterationCheckpoint } from "@/interfaces";
import { Button, Space } from "antd";
import React from "react";

interface IterationCheckpointActionsProps {
  checkpoint: IterationCheckpoint;
  onContinue: () => void;
  onSummarize: () => void;
}

const IterationCheckpointActions: React.FC<IterationCheckpointActionsProps> = ({
  checkpoint,
  onContinue,
  onSummarize,
}) => {
  return (
    <div className="mt-3 flex flex-col gap-2">
      <div className="text-sm text-gray-500">
        已执行 {checkpoint.iterationsUsed} 轮工具调用。是否继续？
      </div>
      <Space wrap>
        <Button type="primary" onClick={onContinue}>
          继续执行（追加 {checkpoint.continueBudget} 轮）
        </Button>
        <Button onClick={onSummarize}>到此为止，生成总结</Button>
      </Space>
    </div>
  );
};

export default React.memo(IterationCheckpointActions);
