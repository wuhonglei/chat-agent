import CopyButton from "@/components/common/CopyButton";
import { EditOutlined } from "@ant-design/icons";
import { Button } from "antd";
import classNames from "classnames";
import React from "react";
import styles from "../UserMessage.module.css";

export interface UserMessageFooterProps {
  textContent: string;
  onEdit: () => void;
  /** 为 false 时不展示编辑（例如消息含图片等非文本块） */
  canEdit?: boolean;
}

const UserMessageFooter: React.FC<UserMessageFooterProps> = ({ textContent, onEdit, canEdit = true }) => (
  <div className={classNames("flex gap-2", styles.operation)}>
    {canEdit ? <Button size="small" type="text" icon={<EditOutlined />} onClick={onEdit} /> : null}
    <CopyButton text={textContent} children={null} />
  </div>
);

export default React.memo(UserMessageFooter);
