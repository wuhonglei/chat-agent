import CopyButton from "@/components/common/CopyButton";
import { DeleteOutlined, EditOutlined } from "@ant-design/icons";
import { Button, Popconfirm } from "antd";
import classNames from "classnames";
import React from "react";
import styles from "../UserMessage.module.css";

export interface UserMessageFooterProps {
  textContent: string;
  onEdit: () => void;
  /** 为 true 时在右侧展示删除（当前为会话最后一条用户消息时由上层传入） */
  showDelete?: boolean;
  onDelete: () => void | Promise<void>;
}

const UserMessageFooter: React.FC<UserMessageFooterProps> = ({ textContent, onEdit, showDelete = false, onDelete }) => (
  <div className={classNames("flex gap-2", styles.operation)}>
    <Button size="small" type="text" icon={<EditOutlined />} onClick={onEdit} />
    <CopyButton text={textContent} children={null} />
    {showDelete ? (
      <Popconfirm title="确定删除这条消息？" okText="删除" cancelText="取消" onConfirm={onDelete}>
        <Button size="small" type="text" danger icon={<DeleteOutlined />} />
      </Popconfirm>
    ) : null}
  </div>
);

export default React.memo(UserMessageFooter);
