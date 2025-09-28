import { SearchSource } from "@/types";
import { Avatar, Typography } from "antd";
import React, { memo } from "react";
import { getWebIconUrl, getWebMainDomain } from "@/utils";
import RoundTag from "@/components/common/RoundTag";
import classNames from "classnames";

const { Title, Paragraph } = Typography;

interface SourceCardProps {
  rank?: number;
  hoverable?: boolean;
  className?: string;
  source: SearchSource | undefined;
}

const SourceCard: React.FC<SourceCardProps> = ({
  rank,
  source,
  className,
  hoverable = true,
}) => {
  if (!source) return null;
  return (
    <div
      className={classNames(
        "flex flex-col p-3 gap-[6px] cursor-pointer rounded-lg",
        hoverable && "hover:bg-gray-100 transition",
        className
      )}
      onClick={() => {
        window.open(source.url, "_blank");
      }}
    >
      {/* 第一行: 来源 */}
      <div className="flex justify-between items-center text-gray-600">
        <div className="flex items-center gap-2">
          <Avatar size={18} src={source.favicon || getWebIconUrl(source.url)} />
          <span title={source.url}>{getWebMainDomain(source.url, true)}</span>
        </div>
        {rank && <RoundTag>{rank}</RoundTag>}
      </div>
      {/* 第二行: 文章标题 */}
      <Title
        level={5}
        style={{ margin: 0, fontWeight: 500 }}
        ellipsis={{ rows: 2, expandable: false }}
      >
        {source.title}
      </Title>
      {/* 第三行: 文章内容 */}
      <Paragraph
        ellipsis={{ rows: 2, expandable: false }}
        style={{ margin: 0 }}
      >
        {source.content}
      </Paragraph>
    </div>
  );
};

export default memo(SourceCard);
