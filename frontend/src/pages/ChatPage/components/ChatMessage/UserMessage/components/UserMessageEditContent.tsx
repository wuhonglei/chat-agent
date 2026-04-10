import { Sender } from "@ant-design/x";
import { Button } from "antd";
import React from "react";

export interface UserMessageEditContentProps {
  defaultValue: string;
  messageContent: string;
  onChange: (value: string) => void;
  onKeyDown: React.KeyboardEventHandler<Element>;
  onCancel: () => void;
  onConfirm: () => void;
}

const UserMessageEditContent: React.FC<UserMessageEditContentProps> = ({
  defaultValue,
  messageContent,
  onChange,
  onKeyDown,
  onCancel,
  onConfirm,
}) => (
  <Sender
    suffix={false}
    defaultValue={defaultValue}
    onKeyDown={onKeyDown}
    onChange={onChange}
    footer={
      <div className="flex justify-end gap-2">
        <Button shape="round" type="default" onClick={onCancel}>
          取消
        </Button>
        <Button shape="round" type="primary" onClick={onConfirm} disabled={!messageContent}>
          发送
        </Button>
      </div>
    }
  />
);

export default React.memo(UserMessageEditContent);
