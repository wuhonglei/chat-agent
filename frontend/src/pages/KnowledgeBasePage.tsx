import React, { useEffect, useState } from "react";
import { Card, Statistic, Button, Row, Col, message, Spin } from "antd";
import {
  DatabaseOutlined,
  FileTextOutlined,
  CloudDownloadOutlined,
  ShareAltOutlined,
  ExportOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { knowledgeBaseAPI } from "../services/api";
import { KnowledgeBaseStats } from "../types";

const KnowledgeBasePage: React.FC = () => {
  const [stats, setStats] = useState<KnowledgeBaseStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const response = await knowledgeBaseAPI.getStats();
      setStats(response.data);
    } catch (error) {
      message.error("获取统计信息失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const handleExport = async () => {
    setExporting(true);
    try {
      const response = await knowledgeBaseAPI.exportKnowledgeBase();

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `knowledge_base_${Date.now()}.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();

      message.success("知识库导出成功");
    } catch (error: any) {
      message.error("导出失败: " + error.message);
    } finally {
      setExporting(false);
    }
  };

  const handleShare = async () => {
    message.info("分享功能开发中...");
  };

  if (loading && !stats) {
    return (
      <div className="flex justify-center items-center h-96">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="p-4">
      <Card>
        <div className="mb-6 flex justify-between items-center">
          <h1 className="text-xl font-semibold">知识库管理</h1>
          <Button
            icon={<ReloadOutlined />}
            onClick={fetchStats}
            loading={loading}
          >
            刷新
          </Button>
        </div>

        {/* Statistics */}
        <Row gutter={16} className="mb-6">
          <Col span={6}>
            <Card>
              <Statistic
                title="文档总数"
                value={stats?.document_count || 0}
                prefix={<FileTextOutlined />}
                suffix="篇"
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="文本块总数"
                value={stats?.total_chunks || 0}
                prefix={<DatabaseOutlined />}
                suffix="个"
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="本地文档"
                value={stats?.sources?.local || 0}
                valueStyle={{ color: "#3f8600" }}
                suffix="篇"
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="外部文档"
                value={
                  (stats?.sources?.confluence || 0) +
                  (stats?.sources?.google_docs || 0) +
                  (stats?.sources?.google_slides || 0)
                }
                valueStyle={{ color: "#1890ff" }}
                suffix="篇"
              />
            </Card>
          </Col>
        </Row>

        {/* Actions */}
        <Card title="知识库操作" className="mb-6">
          <Row gutter={16}>
            <Col span={8}>
              <Card
                hoverable
                className="text-center cursor-pointer"
                onClick={handleExport}
              >
                <ExportOutlined style={{ fontSize: 32, color: "#1890ff" }} />
                <div className="mt-2">
                  <h3 className="font-medium">导出知识库</h3>
                  <p className="text-gray-500 text-sm mt-1">
                    下载完整知识库备份
                  </p>
                </div>
                {exporting && <Spin className="mt-2" />}
              </Card>
            </Col>
            <Col span={8}>
              <Card
                hoverable
                className="text-center cursor-pointer opacity-50"
                style={{ cursor: "not-allowed" }}
              >
                <CloudDownloadOutlined
                  style={{ fontSize: 32, color: "#52c41a" }}
                />
                <div className="mt-2">
                  <h3 className="font-medium">导入知识库</h3>
                  <p className="text-gray-500 text-sm mt-1">
                    从备份文件恢复（开发中）
                  </p>
                </div>
              </Card>
            </Col>
            <Col span={8}>
              <Card
                hoverable
                className="text-center cursor-pointer"
                onClick={handleShare}
              >
                <ShareAltOutlined style={{ fontSize: 32, color: "#fa8c16" }} />
                <div className="mt-2">
                  <h3 className="font-medium">分享知识库</h3>
                  <p className="text-gray-500 text-sm mt-1">
                    生成分享链接（开发中）
                  </p>
                </div>
              </Card>
            </Col>
          </Row>
        </Card>

        {/* Source Distribution */}
        {stats && (
          <Card title="文档来源分布">
            <Row gutter={16}>
              <Col span={6}>
                <div className="text-center">
                  <div className="text-2xl font-bold text-gray-700">
                    {stats.sources.local || 0}
                  </div>
                  <div className="text-gray-500">本地文档</div>
                </div>
              </Col>
              <Col span={6}>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-600">
                    {stats.sources.confluence || 0}
                  </div>
                  <div className="text-gray-500">Confluence</div>
                </div>
              </Col>
              <Col span={6}>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {stats.sources.google_docs || 0}
                  </div>
                  <div className="text-gray-500">Google Docs</div>
                </div>
              </Col>
              <Col span={6}>
                <div className="text-center">
                  <div className="text-2xl font-bold text-orange-600">
                    {stats.sources.google_slides || 0}
                  </div>
                  <div className="text-gray-500">Google Slides</div>
                </div>
              </Col>
            </Row>
          </Card>
        )}
      </Card>
    </div>
  );
};

export default KnowledgeBasePage;
