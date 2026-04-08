import CopyButton from "@/components/common/CopyButton";
import { ChatMessage as ChatMessageType } from "@/interfaces";
import { getMessageTextFromBlocks } from "@/interfaces/contentBlock";
import { RedoOutlined } from "@ant-design/icons";
import { Button } from "antd";
import classNames from "classnames";

type Props = {
  message: ChatMessageType;
  onReSend: () => void;
};

export default function AssistantOperation(props: Props) {
  const { message, onReSend } = props;
  const textContent = getMessageTextFromBlocks(message.contentBlocks);

  return (
    <div className={classNames("w-full flex items-center gap-2 transition duration-300")}>
      <CopyButton size="middle" text={textContent} children={null} />
      <Button type="text" icon={<RedoOutlined />} onClick={onReSend} />
    </div>
  );
}
