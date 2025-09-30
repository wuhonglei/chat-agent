import { ChatMessage as ChatMessageType } from "@/interfaces";
import classNames from "classnames";
import CopyButton from "@/components/common/CopyButton";
import { Button, Divider } from "antd";
import { RedoOutlined } from "@ant-design/icons";
import { isEmpty } from "lodash-es";
import SourceAbstract from "./SourceAbstract";

type Props = {
  isStreaming: boolean;
  message: ChatMessageType;
  onReSend: () => void;
  onSourceClick: () => void;
};

export default function AssistantOperation(props: Props) {
  const { isStreaming, message, onReSend, onSourceClick } = props;
  if (isStreaming) {
    return null;
  }

  return (
    <div
      className={classNames(
        "mt-2 w-full flex items-center gap-2 transition duration-300"
      )}
    >
      <CopyButton size="middle" text={message.content} children={null} />
      <Button type="text" icon={<RedoOutlined />} onClick={onReSend} />
      {!isEmpty(message.sources) && (
        <>
          <Divider type="vertical" />
          <SourceAbstract
            mode="postSource"
            bordered={false}
            sources={message.sources}
            onClick={onSourceClick}
          />
        </>
      )}
    </div>
  );
}
