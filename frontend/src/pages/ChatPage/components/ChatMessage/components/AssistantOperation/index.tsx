import CopyButton from "@/components/common/CopyButton";
import { ChatMessage as ChatMessageType } from "@/interfaces";
import { getMessageTextFromBlocks } from "@/interfaces/contentBlock";
import { DeleteOutlined, RedoOutlined } from "@ant-design/icons";
import { Button, Popconfirm } from "antd";
import classNames from "classnames";

type Props = {
  message: ChatMessageType;
  showDelete: boolean;
  onReSend: () => void;
  onDelete: () => void | Promise<void>;
};

export default function AssistantOperation(props: Props) {
  const { message, showDelete, onReSend, onDelete } = props;
  const textContent = getMessageTextFromBlocks(message.contentBlocks);

  return (
    <div className={classNames("w-full flex items-center gap-2 transition duration-300")}>
      <CopyButton size="middle" text={textContent} children={null} />
      <Button type="text" icon={<RedoOutlined />} onClick={onReSend} />
      {showDelete ? (
        <Popconfirm title="确定删除这条消息？" okText="删除" cancelText="取消" onConfirm={onDelete}>
          <Button size="small" type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ) : null}
    </div>
  );
}
