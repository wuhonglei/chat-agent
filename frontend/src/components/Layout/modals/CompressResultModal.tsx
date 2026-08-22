import { ConversationCompressResponse } from "@/interfaces";
import MarkdownContainer from "@/pages/ChatPage/components/MarkdownContainer";
import { Modal } from "antd";
import type { CSSProperties } from "react";

type Props = {
  open: boolean;
  result: ConversationCompressResponse | null;
  onClose: () => void;
};

const summaryMarkdownStyle = {
  "--font-size": "14px",
  "--margin-block": "4px",
} as CSSProperties;

export default function CompressResultModal({ open, result, onClose }: Props) {
  return (
    <Modal
      centered
      width={560}
      open={open}
      title="会话压缩完成"
      onCancel={onClose}
      onOk={onClose}
      cancelButtonProps={{ style: { display: "none" } }}
      okText="知道了"
    >
      {result ? (
        <div className="flex flex-col gap-3">
          <div className="text-sm text-black-secondary">
            压缩前 {result.tokensBefore} tokens → {result.tokensAfter} tokens
            <span className="ml-2 text-black-tertiary">
              （共 {result.summarizedMessageCount} 条消息）
            </span>
          </div>
          <div className="max-h-80 overflow-y-auto rounded-md bg-black/[0.03] p-3">
            <MarkdownContainer className="w-full" style={summaryMarkdownStyle}>
              {result.summary}
            </MarkdownContainer>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
