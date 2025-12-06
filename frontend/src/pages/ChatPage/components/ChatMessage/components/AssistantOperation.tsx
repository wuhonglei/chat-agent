import CopyButton from "@/components/common/CopyButton";
import { ChatMessage as ChatMessageType } from "@/interfaces";
import { RedoOutlined } from "@ant-design/icons";
import { Button } from "antd";
import classNames from "classnames";

type Props = {
  message: ChatMessageType;
  onReSend: () => void;
};

export default function AssistantOperation(props: Props) {
  const { message, onReSend } = props;

  return (
    <div
      className={classNames(
        "w-full flex items-center gap-2 transition duration-300"
      )}
    >
      <CopyButton size="middle" text={message.content} children={null} />
      <Button type="text" icon={<RedoOutlined />} onClick={onReSend} />
    </div>
  );
}
