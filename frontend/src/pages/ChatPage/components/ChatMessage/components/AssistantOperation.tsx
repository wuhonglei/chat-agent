import CopyButton from "@/components/common/CopyButton";
import { ChatMessage as ChatMessageType } from "@/interfaces";
import { RedoOutlined } from "@ant-design/icons";
import { Button, Divider } from "antd";
import classNames from "classnames";
import { isEmpty } from "lodash-es";
import SourceAbstract from "./SourceAbstract";

type Props = {
  message: ChatMessageType;
  onReSend: () => void;
  onSourceClick: () => void;
};

export default function AssistantOperation(props: Props) {
  const { message, onReSend, onSourceClick } = props;

  return (
    <div
      className={classNames(
        "w-full flex items-center gap-2 transition duration-300"
      )}
    >
      <CopyButton size="middle" text={message.content} children={null} />
      <Button type="text" icon={<RedoOutlined />} onClick={onReSend} />
      {!isEmpty(message.sources) && (
        <>
          <Divider orientation="vertical" />
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
