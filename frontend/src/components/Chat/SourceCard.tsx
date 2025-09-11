import React from 'react'
import { Card, Tag, Tooltip } from 'antd'
import { FileTextOutlined, LinkOutlined } from '@ant-design/icons'
import { SearchSource } from '../../types'

interface SourceCardProps {
  sources: SearchSource[]
}

const SourceCard: React.FC<SourceCardProps> = ({ sources }) => {
  if (!sources || sources.length === 0) return null

  return (
    <div className="mt-4">
      <h4 className="text-sm font-medium text-gray-600 mb-2">参考来源</h4>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {sources.map((source, index) => (
          <Card
            key={index}
            size="small"
            className="hover:shadow-md transition-shadow cursor-pointer"
            bodyStyle={{ padding: '8px 12px' }}
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
    </div>
  )
}

export default SourceCard