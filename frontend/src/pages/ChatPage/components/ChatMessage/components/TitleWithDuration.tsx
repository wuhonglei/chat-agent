import { MCPToolsTokenStats } from "@/interfaces/token";
import { PieChartOutlined } from "@ant-design/icons";
import { Tooltip } from "antd";
import { isEmpty } from "lodash-es";
import React from "react";
import TokenStatsTooltip from "./TokenStatsTooltip";

type Props = {
  titles: {
    doing: string;
    done: string;
  };
  isDoing: boolean;
  duration?: number;
  tokenStats?: MCPToolsTokenStats;
};

const TitleWithDuration: React.FC<Props> = ({ titles, isDoing, duration, tokenStats }) => {
  if (isDoing) {
    return <>{titles.doing}</>;
  }
  if (!duration) {
    return <>{titles.done}</>;
  }

  return (
    <>
      {titles.done}
      {!isEmpty(tokenStats) && (
        <span
          onClick={e => {
            e.stopPropagation();
            e.preventDefault();
          }}
        >
          <Tooltip
            trigger={["click", "hover"]}
            styles={{
              container: {
                minWidth: 300,
              },
            }}
            title={<TokenStatsTooltip tokenStats={tokenStats} />}
          >
            <PieChartOutlined className="ml-1 cursor-pointer" />
          </Tooltip>
        </span>
      )}
      <span className="ml-1 text-black-tertiary">{duration}s</span>
    </>
  );
};

export default React.memo(TitleWithDuration);
