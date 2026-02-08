import CopyButton from "@/components/common/CopyButton";
import { ChatMessage as ChatMessageType } from "@/interfaces";
import { PieChartOutlined, RedoOutlined } from "@ant-design/icons";
import { Button, Tooltip } from "antd";
import classNames from "classnames";
import TokenStatsTooltip from "../TokenStatsTooltip";

type Props = {
  message: ChatMessageType;
  onReSend: () => void;
};

export default function AssistantOperation(props: Props) {
  const { message, onReSend } = props;
  const { tokenStats, contentDuration } = message;

  return (
    <div className={classNames("w-full flex items-center gap-2 transition duration-300")}>
      <CopyButton size="middle" text={message.content} children={null} />
      <Button type="text" icon={<RedoOutlined />} onClick={onReSend} />
      {tokenStats?.responseGeneration && (
        <Tooltip
          trigger={["click", "hover"]}
          styles={{
            container: {
              minWidth: 300,
            },
          }}
          title={<TokenStatsTooltip title="响应内容 Token 统计信息" tokenStats={tokenStats.responseGeneration} />}
        >
          <PieChartOutlined className="ml-1 cursor-pointer" />
        </Tooltip>
      )}
      {contentDuration && <span className="text-sm text-gray-500">{contentDuration}s</span>}
    </div>
  );
}
