import CopyButton from "@/components/common/CopyButton";
import { EditOutlined } from "@ant-design/icons";
import { Button } from "antd";
import classNames from "classnames";
import React from "react";
import styles from "../UserMessage.module.css";

export interface UserMessageFooterProps {
  textContent: string;
  onEdit: () => void;
}

const UserMessageFooter: React.FC<UserMessageFooterProps> = ({ textContent, onEdit }) => (
  <div className={classNames("flex gap-2", styles.operation)}>
    <Button size="small" type="text" icon={<EditOutlined />} onClick={onEdit} />
    <CopyButton text={textContent} children={null} />
  </div>
);

export default React.memo(UserMessageFooter);
