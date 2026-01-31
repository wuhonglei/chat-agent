import { TokenStats } from "@/interfaces/token";
import { ConfigProvider, Descriptions } from "antd";
import React from "react";
import { getDescriptionItems } from "./utils";

type TokenStatsTooltipProps = {
  title?: string;
  tokenStats?: TokenStats;
};

const TokenStatsTooltip: React.FC<TokenStatsTooltipProps> = ({
  title = "Token 统计信息",
  tokenStats,
}) => {
  if (!tokenStats) {
    return null;
  }

  const items = getDescriptionItems(tokenStats);

  return (
    <div
      onClick={e => {
        e.stopPropagation();
        e.preventDefault();
      }}
    >
      <ConfigProvider
        theme={{
          token: {
            colorSplit: "rgba(255, 255, 255, 0.45)",
            colorText: "white",
            colorTextHeading: "white",
            colorTextSecondary: "white",
            colorTextTertiary: "white",
            colorTextQuaternary: "white",
          },
        }}
      >
        <Descriptions
          bordered
          column={1}
          size="small"
          items={items}
          title={title}
          styles={{
            header: { marginBottom: 8 },
            label: { fontWeight: "bold" },
          }}
        />
      </ConfigProvider>
    </div>
  );
};

export default React.memo(TokenStatsTooltip);
