import type { MessageFeedbackValue } from "@/interfaces";
import { Button, Input, Modal } from "antd";
import classNames from "classnames";
import { useEffect, useState } from "react";

const LIKE_REASONS = ["准确理解问题", "完成任务能力强", "有帮助", "文风好"] as const;

const DISLIKE_REASONS = [
  "没有理解问题",
  "没有完成任务",
  "编造事实",
  "废话太多",
  "没有创意",
  "文风不好",
] as const;

const MODAL_COPY: Record<
  "like" | "dislike",
  {
    title: string;
    subtitle: string;
    reasons: readonly string[];
  }
> = {
  like: {
    title: "然宝会努力做得更好",
    subtitle: "请选择理由帮助我们做得更好",
    reasons: LIKE_REASONS,
  },
  dislike: {
    title: "抱歉，然宝让你有不好的感受",
    subtitle: "请选择理由帮助我们做得更好",
    reasons: DISLIKE_REASONS,
  },
};

type FeedbackModalType = Extract<MessageFeedbackValue, "like" | "dislike">;

type Props = {
  open: boolean;
  type: FeedbackModalType | null;
  submitting?: boolean;
  onCancel: () => void;
  onSubmit: (payload: { reasons: string[]; comment: string }) => void | Promise<void>;
};

export default function FeedbackDetailModal({ open, type, submitting = false, onCancel, onSubmit }: Props) {
  const [selectedReasons, setSelectedReasons] = useState<string[]>([]);
  const [comment, setComment] = useState("");

  useEffect(() => {
    if (open) {
      setSelectedReasons([]);
      setComment("");
    }
  }, [open, type]);

  if (!type) {
    return null;
  }

  const copy = MODAL_COPY[type];

  const toggleReason = (reason: string) => {
    setSelectedReasons(prev => (prev.includes(reason) ? prev.filter(item => item !== reason) : [...prev, reason]));
  };

  const handleSubmit = () => {
    void onSubmit({
      reasons: selectedReasons,
      comment: comment.trim(),
    });
  };

  return (
    <Modal
      centered
      open={open}
      title={copy.title}
      onCancel={onCancel}
      footer={null}
      width={560}
      destroyOnHidden
      styles={{
        body: { paddingTop: 8 },
      }}
    >
      <p className="mb-4 text-sm text-gray-500">{copy.subtitle}</p>
      <div className="mb-4 flex flex-wrap gap-2">
        {copy.reasons.map(reason => {
          const selected = selectedReasons.includes(reason);
          return (
            <button
              key={reason}
              type="button"
              onClick={() => toggleReason(reason)}
              className={classNames(
                "rounded-lg border px-3 py-1.5 text-sm transition-colors cursor-pointer",
                selected
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-transparent bg-gray-100 text-gray-700 hover:bg-gray-200"
              )}
            >
              {reason}
            </button>
          );
        })}
      </div>
      <Input.TextArea
        value={comment}
        onChange={event => setComment(event.target.value)}
        placeholder="欢迎说说你的想法"
        autoSize={{ minRows: 4, maxRows: 8 }}
        maxLength={500}
        className="!rounded-xl !bg-gray-100 !border-transparent hover:!bg-gray-100 focus:!bg-white"
      />
      <div className="mt-6 flex justify-end gap-3">
        <Button onClick={onCancel} className="!bg-gray-100 !border-transparent">
          取消
        </Button>
        <Button type="primary" loading={submitting} onClick={handleSubmit}>
          提交反馈
        </Button>
      </div>
    </Modal>
  );
}
