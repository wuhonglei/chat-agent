import { TokenStats } from "@/interfaces/token";
import { LeftOutlined, RightOutlined } from "@ant-design/icons";
import { ConfigProvider, Descriptions } from "antd";
import { castArray } from "lodash-es";
import React, { useState } from "react";
import { getDescriptionItems } from "./utils";

type TokenStatsTooltipProps = {
  startIndex?: number;
  titles?: string | string[];
  tokenStats: TokenStats | TokenStats[];
};

const TokenStatsTooltip: React.FC<TokenStatsTooltipProps> = ({
  startIndex = 0,
  tokenStats,
  titles,
}) => {
  const tokenStatsList = castArray(tokenStats);
  const showPage = tokenStatsList.length > 1;
  const itemConfigs = tokenStatsList.map((tokenStats, index) => ({
    title: titles?.[index] || `Token 统计信息`,
    items: getDescriptionItems(tokenStats),
  }));
  const [currentIndex, setCurrentIndex] = useState(startIndex);
  const currentItemConfig = itemConfigs.at(currentIndex);
  if (!currentItemConfig) {
    return null;
  }

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
          items={currentItemConfig.items}
          title={
            showPage ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 8,
                }}
              >
                <span>{currentItemConfig.title}</span>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <LeftOutlined
                    style={{
                      cursor: currentIndex > 0 ? "pointer" : "not-allowed",
                      opacity: currentIndex > 0 ? 1 : 0.4,
                    }}
                    onClick={e => {
                      e.stopPropagation();
                      if (currentIndex > 0) setCurrentIndex(i => i - 1);
                    }}
                  />
                  <RightOutlined
                    style={{
                      cursor:
                        currentIndex < tokenStatsList.length - 1
                          ? "pointer"
                          : "not-allowed",
                      opacity:
                        currentIndex < tokenStatsList.length - 1 ? 1 : 0.4,
                    }}
                    onClick={e => {
                      e.stopPropagation();
                      if (currentIndex < tokenStatsList.length - 1)
                        setCurrentIndex(i => i + 1);
                    }}
                  />
                </span>
              </div>
            ) : (
              currentItemConfig.title
            )
          }
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
