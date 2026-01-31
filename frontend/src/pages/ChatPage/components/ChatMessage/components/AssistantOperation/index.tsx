import CopyButton from "@/components/common/CopyButton";
import { ChatMessage as ChatMessageType, TotalTokenStats } from "@/interfaces";
import { PieChartOutlined, RedoOutlined } from "@ant-design/icons";
import { Button, Tooltip } from "antd";
import classNames from "classnames";
import TokenStatsTooltip from "../TokenStatsTooltip";
import { useTokenStatsDisplay } from "./hooks";

type Props = {
  message: ChatMessageType;
  onReSend: () => void;
  tokenStats: TotalTokenStats;
};

export default function AssistantOperation(props: Props) {
  const { message, onReSend, tokenStats } = props;
  const { titles, tokenStats: tokenStatsList } =
    useTokenStatsDisplay(tokenStats);

  return (
    <div
      className={classNames(
        "w-full flex items-center gap-2 transition duration-300"
      )}
    >
      <CopyButton size="middle" text={message.content} children={null} />
      <Button type="text" icon={<RedoOutlined />} onClick={onReSend} />
      <Tooltip
        trigger={["click", "hover"]}
        styles={{
          container: {
            minWidth: 300,
          },
        }}
        title={
          tokenStatsList.length > 0 ? (
            <TokenStatsTooltip
              titles={titles}
              tokenStats={tokenStatsList}
              startIndex={tokenStatsList.length - 1}
            />
          ) : null
        }
      >
        <PieChartOutlined className="ml-1 cursor-pointer" />
      </Tooltip>
    </div>
  );
}
