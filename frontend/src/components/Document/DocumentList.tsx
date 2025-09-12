import React, { useEffect } from "react";
import {
  Table,
  Button,
  Tag,
  Popconfirm,
  Space,
  message,
  TableProps,
} from "antd";
import {
  DeleteOutlined,
  FileTextOutlined,
  CloudOutlined,
  LinkOutlined,
} from "@ant-design/icons";
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import {
  fetchDocuments,
  deleteDocument,
} from "../../store/slices/documentSlice";
import { Document, DocumentSource } from "../../types";
import dayjs from "dayjs";

const DocumentList: React.FC = () => {
  const dispatch = useAppDispatch();
  const { documents, isLoading } = useAppSelector((state) => state.document);

  useEffect(() => {
    dispatch(fetchDocuments());
  }, [dispatch]);

  const handleDelete = async (id: string) => {
    try {
      await dispatch(deleteDocument(id)).unwrap();
      message.success("文档删除成功");
    } catch (error: any) {
      message.error("删除失败: " + error.message);
    }
  };

  const getSourceIcon = (source: DocumentSource) => {
    switch (source) {
      case DocumentSource.CONFLUENCE:
      case DocumentSource.GOOGLE_DOCS:
      case DocumentSource.GOOGLE_SLIDES:
        return <CloudOutlined />;
      default:
        return <FileTextOutlined />;
    }
  };

  const getSourceColor = (source: DocumentSource) => {
    switch (source) {
      case DocumentSource.CONFLUENCE:
        return "blue";
      case DocumentSource.GOOGLE_DOCS:
        return "green";
      case DocumentSource.GOOGLE_SLIDES:
        return "orange";
      default:
        return "default";
    }
  };

  const columns: TableProps<Document>["columns"] = [
    {
      title: "文档名称",
      dataIndex: "name",
      key: "name",
      render: (text: string, record: Document) => (
        <Space>
          {getSourceIcon(record.source)}
          <span>{text}</span>
          {record.source_url && <LinkOutlined className="text-gray-400" />}
        </Space>
      ),
    },
    {
      title: "来源",
      dataIndex: "source",
      key: "source",
      width: 120,
      render: (source: DocumentSource) => (
        <Tag color={getSourceColor(source)}>
          {source.replace("_", " ").toUpperCase()}
        </Tag>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (status: string) => (
        <Tag color={status === "completed" ? "success" : "processing"}>
          {status === "completed" ? "已完成" : "处理中"}
        </Tag>
      ),
    },
    {
      title: "文本块",
      dataIndex: "chunk_count",
      key: "chunk_count",
      width: 100,
      align: "center",
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (date: string) => dayjs(date).format("YYYY-MM-DD HH:mm"),
    },
    {
      title: "操作",
      key: "action",
      width: 100,
      render: (_: any, record: Document) => (
        <Popconfirm
          title="确定要删除这个文档吗？"
          onConfirm={() => handleDelete(record.id)}
          okText="确定"
          cancelText="取消"
        >
          <Button type="text" danger icon={<DeleteOutlined />} size="small">
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div className="p-4">
      <Table
        columns={columns}
        dataSource={documents}
        rowKey="id"
        loading={isLoading}
        pagination={{
          pageSize: 10,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 个文档`,
        }}
      />
    </div>
  );
};

export default DocumentList;
