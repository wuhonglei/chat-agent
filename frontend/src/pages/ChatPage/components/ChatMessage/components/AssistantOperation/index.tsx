import CopyButton from "@/components/common/CopyButton";
import {
  ChatMessage as ChatMessageType,
  MessageFeedbackDetails,
  MessageFeedbackValue,
} from "@/interfaces";
import { getMessageTextFromBlocks } from "@/interfaces/contentBlock";
import { DeleteOutlined, RedoOutlined } from "@ant-design/icons";
import { Actions } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import { Button, Popconfirm, Tooltip } from "antd";
import classNames from "classnames";
import { useState } from "react";
import FeedbackDetailModal from "./FeedbackDetailModal";

type FeedbackModalType = Extract<MessageFeedbackValue, "like" | "dislike">;

type Props = {
  message: ChatMessageType;
  showDelete: boolean;
  onReSend: () => void;
  onDelete: () => void | Promise<void>;
  onFeedback: (value: MessageFeedbackValue, details?: MessageFeedbackDetails) => Promise<void>;
};

export default function AssistantOperation(props: Props) {
  const { message, showDelete, onReSend, onDelete, onFeedback } = props;
  const textContent = getMessageTextFromBlocks(message.contentBlocks);
  const currentFeedback = message.feedback?.value || "default";
  const [modalType, setModalType] = useState<FeedbackModalType | null>(null);
  const [pendingFeedback, setPendingFeedback] = useState<FeedbackModalType | null>(null);
  const [submittingDetail, setSubmittingDetail] = useState(false);
  const displayFeedback = pendingFeedback ?? currentFeedback;

  const handleFeedbackChange = useMemoizedFn(async (value: MessageFeedbackValue) => {
    if (value === "like" || value === "dislike") {
      // 先展示选中态并弹窗，确认后再统一发送 feedback
      setPendingFeedback(value);
      setModalType(value);
      return;
    }
    setPendingFeedback(null);
    setModalType(null);
    try {
      await onFeedback(value);
    } catch {
      // 错误已在 onFeedback 中提示
    }
  });

  const handleCloseModal = useMemoizedFn(() => {
    setModalType(null);
    setPendingFeedback(null);
  });

  const handleSubmitDetail = useMemoizedFn(
    async (payload: { reasons: string[]; comment: string }) => {
      if (!modalType) {
        return;
      }
      setSubmittingDetail(true);
      try {
        await onFeedback(modalType, {
          reasons: payload.reasons,
          comment: payload.comment,
        });
        setModalType(null);
        setPendingFeedback(null);
      } catch {
        // 错误已在 onFeedback 中提示，保留弹窗便于重试
      } finally {
        setSubmittingDetail(false);
      }
    },
  );

  return (
    <div className={classNames("w-full flex items-center gap-2 transition duration-300")}>
      <Tooltip title="复制">
        <CopyButton size="middle" text={textContent} children={null} />
      </Tooltip>
      <Tooltip title="重新发送">
        <Button type="text" icon={<RedoOutlined />} onClick={onReSend} />
      </Tooltip>
      <Actions.Feedback
        value={displayFeedback}
        onChange={(value) => void handleFeedbackChange(value)}
      />
      {showDelete ? (
        <Popconfirm title="确定删除这条消息？" okText="删除" cancelText="取消" onConfirm={onDelete}>
          <Button size="small" type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ) : null}
      <FeedbackDetailModal
        open={modalType !== null}
        type={modalType}
        submitting={submittingDetail}
        onCancel={handleCloseModal}
        onSubmit={handleSubmitDetail}
      />
    </div>
  );
}
