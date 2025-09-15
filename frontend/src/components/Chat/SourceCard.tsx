import { SearchSource } from "@/types";
import { FileTextOutlined, LinkOutlined } from "@ant-design/icons";
import { Card, Tag, Tooltip } from "antd";
import React from "react";

interface SourceCardProps {
  sources: SearchSource[] | undefined;
}

const SourceCard: React.FC<SourceCardProps> = ({ sources }) => {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="flex flex-col gap-4">
      {sources.map((source, index) => (
        <Card
          key={index}
          size="small"
          className="hover:shadow-md transition-shadow cursor-pointer"
          styles={{ body: { padding: "8px 12px" } }}
        >
          <div className="flex items-start gap-2">
            <FileTextOutlined className="text-blue-500 mt-1" />
            <div className="flex-1 min-w-0">
              <Tooltip title={source.document_name}>
                <div className="font-medium text-sm truncate">
                  {source.document_name}
                </div>
              </Tooltip>
              <p className="text-xs text-gray-500 line-clamp-2 mt-1">
                {source.content}
              </p>
              <div className="flex items-center gap-2 mt-2">
                <Tag color="blue" className="text-xs">
                  相关度: {(source.score * 100).toFixed(1)}%
                </Tag>
                {source.source_url && (
                  <LinkOutlined className="text-gray-400 text-xs" />
                )}
              </div>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
};

export default SourceCard;
