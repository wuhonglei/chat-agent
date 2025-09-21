import { SearchSource } from "@/types";
import { Avatar, Typography } from "antd";
import React from "react";
import { getWebIconUrl, getWebMainDomain } from "@/utils";

const { Title, Paragraph } = Typography;

interface SourceCardProps {
  rank: number;
  source: SearchSource;
}

const SourceCard: React.FC<SourceCardProps> = ({ rank, source }) => {
  if (!source) return null;
  console.log(source);
  return (
    <div
      className="flex flex-col p-3 gap-[6px] cursor-pointer rounded-lg hover:bg-gray-100 transition"
      onClick={() => {
        window.open(source.url, "_blank");
      }}
    >
      {/* 第一行: 来源 */}
      <div className="flex justify-between items-center text-gray-600">
        <div className="flex items-center gap-2">
          <Avatar size={18} src={getWebIconUrl(source.url)} />
          <span title={source.url}>{getWebMainDomain(source.url, true)}</span>
        </div>
        <div className="flex items-center justify-center rounded-full bg-gray-200 h-4.5 w-4.5 text-xs">
          {rank}
        </div>
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

export default SourceCard;
