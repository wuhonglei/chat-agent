import CopyButton from "@/components/common/CopyButton";
import { ChatMessage as ChatMessageType, MessageFeedbackValue } from "@/interfaces";
import { getMessageTextFromBlocks } from "@/interfaces/contentBlock";
import { DeleteOutlined, RedoOutlined } from "@ant-design/icons";
import { Actions } from "@ant-design/x";
import { useRequest } from "ahooks";
import { Button, Popconfirm, Tooltip } from "antd";
import classNames from "classnames";

type Props = {
  message: ChatMessageType;
  showDelete: boolean;
  onReSend: () => void;
  onDelete: () => void | Promise<void>;
  onFeedback: (value: MessageFeedbackValue) => Promise<void>;
};

export default function AssistantOperation(props: Props) {
  const { message, showDelete, onReSend, onDelete, onFeedback } = props;
  const textContent = getMessageTextFromBlocks(message.contentBlocks);
  const currentFeedback = message.feedback?.value || "default";
  const { runAsync: runFeedbackUpdate } = useRequest(onFeedback, {
    manual: true,
  });

  return (
    <div className={classNames("w-full flex items-center gap-2 transition duration-300")}>
      <Tooltip title="复制">
        <CopyButton size="middle" text={textContent} children={null} />
      </Tooltip>
      <Tooltip title="重新发送">
        <Button type="text" icon={<RedoOutlined />} onClick={onReSend} />
      </Tooltip>
      <Actions.Feedback value={currentFeedback} onChange={runFeedbackUpdate} />
      {showDelete ? (
        <Popconfirm title="确定删除这条消息？" okText="删除" cancelText="取消" onConfirm={onDelete}>
          <Button size="small" type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ) : null}
    </div>
  );
}
