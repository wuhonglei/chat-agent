import { useIsSmallScreen } from "@/hooks";
import { isPlainEnter } from "@/utils";
import { Sender } from "@ant-design/x";
import { Button } from "antd";
import { trim } from "lodash-es";
import React, { useState } from "react";

export interface UserMessageEditContentProps {
  defaultValue: string;
  onCancel: () => void;
  onConfirm: (content: string) => void;
}

const UserMessageEditContent: React.FC<UserMessageEditContentProps> = ({ defaultValue, onCancel, onConfirm }) => {
  const [draft, setDraft] = useState(() => trim(defaultValue));
  const isSmallScreen = useIsSmallScreen();

  function handleConfirm() {
    const content = trim(draft);
    if (!content) {
      return;
    }
    onConfirm(content);
  }

  function handleKeyDown(event: React.KeyboardEvent<Element>) {
    if (!isPlainEnter(event)) {
      return;
    }
    if (isSmallScreen) {
      return;
    }
    event.preventDefault();
    handleConfirm();
  }

  return (
    <Sender
      suffix={false}
      value={draft}
      onKeyDown={handleKeyDown}
      onChange={value => setDraft(trim(value))}
      footer={
        <div className="flex justify-end gap-2">
          <Button shape="round" type="default" onClick={onCancel}>
            取消
          </Button>
          <Button shape="round" type="primary" onClick={handleConfirm} disabled={!trim(draft)}>
            发送
          </Button>
        </div>
      }
    />
  );
};

export default React.memo(UserMessageEditContent);
