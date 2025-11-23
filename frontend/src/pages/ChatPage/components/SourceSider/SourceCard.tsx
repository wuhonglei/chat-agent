import RoundTag from "@/components/common/RoundTag";
import { SearchSource } from "@/interfaces";
import {
  getSortedIconUrl,
  getWebMainDomain,
  isFromConfluence,
  isFromWebSearch,
} from "@/utils";
import { Avatar, Divider, Typography } from "antd";
import classNames from "classnames";
import dayjs from "dayjs";
import React, { memo } from "react";

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
      <div className="flex justify-between items-center text-black-tertiary">
        <div className="flex items-center gap-2">
          <Avatar
            size={18}
            src={getSortedIconUrl(source.url, source.favicon)}
          />
          {isFromWebSearch(source.source) && (
            <span title={source.url}>{getWebMainDomain(source.url, true)}</span>
          )}
          {isFromConfluence(source.source) && (
            <span title={source.messageMetadata.spaceName}>
              {source.messageMetadata.spaceKey}
            </span>
          )}
          {/* 最后修改时间 */}
          {source.messageMetadata.lastModifiedTime && (
            <>
              <Divider
                orientation="vertical"
                style={{ marginLeft: 4, marginRight: 4 }}
              />
              <span className="text-xs">
                {dayjs(source.messageMetadata.lastModifiedTime).format(
                  "YYYY-MM-DD"
                )}
              </span>
            </>
          )}
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
        {/* 使用 MarkdownContainer 渲染时，信息密度较低，可能出现前面 2 行展示内容过少问题 */}
        {source.content}
      </Paragraph>
    </div>
  );
};

export default memo(SourceCard);
