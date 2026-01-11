import {
  ComponentToolsTokenStats,
  MCPToolsTokenStats,
} from "@/interfaces/token";
import { PieChartOutlined } from "@ant-design/icons";
import { Tooltip } from "antd";
import React from "react";
import TokenStatsTooltip from "./TokenStatsTooltip";

type Props = {
  titles: {
    doing: string;
    done: string;
  };
  isDoing: boolean;
  duration?: number;
  tokenStats?: MCPToolsTokenStats | ComponentToolsTokenStats;
};

const TitleWithDuration: React.FC<Props> = ({
  titles,
  isDoing,
  duration,
  tokenStats,
}) => {
  if (isDoing) {
    return <>{titles.doing}</>;
  }
  if (!duration) {
    return <>{titles.done}</>;
  }

  return (
    <>
      {titles.done}
      <span className="ml-1 text-black-tertiary">{duration}s</span>
      {tokenStats && (
        <Tooltip
          placement="topLeft"
          trigger={["click", "hover"]}
          title={<TokenStatsTooltip tokenStats={tokenStats} />}
        >
          <PieChartOutlined className="ml-1 cursor-pointer" />
        </Tooltip>
      )}
    </>
  );
};

export default React.memo(TitleWithDuration);
