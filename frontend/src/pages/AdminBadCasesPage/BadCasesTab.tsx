import { BadCaseAttribution, BadCaseItem, BadCaseResolution, BadCaseSource, BadCaseStatus } from "@/interfaces/eval";
import { evalAPI } from "@/services";
import { ExportOutlined, LinkOutlined } from "@ant-design/icons";
import { useRequest } from "ahooks";
import { App, Button, Card, Drawer, Form, Input, Select, Space, Statistic, Table, Tag, Typography } from "antd";
import type { ColumnsType, TablePaginationConfig } from "antd/es/table";
import dayjs from "dayjs";
import React, { useState } from "react";

const STATUS_OPTIONS: { label: string; value: BadCaseStatus }[] = [
  { label: "待复核", value: "pending" },
  { label: "复核中", value: "reviewing" },
  { label: "已解决", value: "resolved" },
  { label: "已忽略", value: "dismissed" },
];

const SOURCE_OPTIONS: { label: string; value: BadCaseSource }[] = [
  { label: "规则失败", value: "rule_fail" },
  { label: "低分", value: "low_score" },
  { label: "点踩", value: "thumb_down" },
];

const ATTRIBUTION_OPTIONS: { label: string; value: BadCaseAttribution }[] = [
  { label: "检索缺失", value: "retrieval_miss" },
  { label: "工具失败", value: "tool_failure" },
  { label: "模型能力", value: "model_capability" },
  { label: "上下文丢失", value: "context_loss" },
  { label: "标注问题", value: "annotation_issue" },
  { label: "幻觉", value: "hallucination" },
  { label: "其他", value: "other" },
];

const RESOLUTION_OPTIONS: { label: string; value: BadCaseResolution }[] = [
  { label: "已加入 Dataset", value: "added_to_dataset" },
  { label: "Prompt 修复", value: "prompt_fix" },
  { label: "模型升级", value: "model_upgrade" },
  { label: "标注修复", value: "annotation_fixed" },
  { label: "无需处理", value: "no_action" },
];

const STATUS_COLOR: Record<BadCaseStatus, string> = {
  pending: "gold",
  reviewing: "processing",
  resolved: "success",
  dismissed: "default",
};

function labelOf<T extends string>(options: { label: string; value: T }[], value: T | null | undefined) {
  if (!value) return "-";
  return options.find(o => o.value === value)?.label ?? value;
}

const BadCasesTab: React.FC = () => {
  const { message, modal } = App.useApp();
  const [status, setStatus] = useState<BadCaseStatus | undefined>();
  const [source, setSource] = useState<BadCaseSource | undefined>();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [editing, setEditing] = useState<BadCaseItem | null>(null);
  const [form] = Form.useForm();

  const {
    data: listData,
    loading,
    refresh,
  } = useRequest(
    () =>
      evalAPI.listBadCases({
        status,
        source,
        page,
        pageSize,
      }),
    {
      refreshDeps: [status, source, page, pageSize],
    }
  );

  const { data: stats, refresh: refreshStats } = useRequest(evalAPI.getBadCaseStats);

  const openEdit = (item: BadCaseItem) => {
    setEditing(item);
    form.setFieldsValue({
      status: item.status,
      attribution: item.attribution ?? undefined,
      resolution: item.resolution ?? undefined,
      reviewerNotes: item.reviewerNotes ?? "",
    });
  };

  const handleSave = async () => {
    if (!editing) return;
    const values = await form.validateFields();
    try {
      await evalAPI.updateBadCase(editing.id, {
        status: values.status,
        attribution: values.attribution ?? null,
        resolution: values.resolution ?? null,
        reviewerNotes: values.reviewerNotes ?? null,
      });
      message.success("更新成功");
      setEditing(null);
      refresh();
      refreshStats();
    } catch {
      message.error("更新失败");
    }
  };

  const handleAddToDataset = (item: BadCaseItem) => {
    modal.confirm({
      title: "添加到 Langfuse Dataset",
      content: "确认将此 Bad Case 推送到固定 Dataset，并标记为已解决？",
      okText: "确认推送",
      cancelText: "取消",
      onOk: async () => {
        try {
          await evalAPI.addToDataset(item.id);
          message.success("已添加到 Dataset");
          refresh();
          refreshStats();
          if (editing?.id === item.id) {
            setEditing(null);
          }
        } catch {
          message.error("推送失败");
        }
      },
    });
  };

  const columns: ColumnsType<BadCaseItem> = [
    {
      title: "来源",
      dataIndex: "source",
      width: 100,
      render: (v: BadCaseSource) => <Tag>{labelOf(SOURCE_OPTIONS, v)}</Tag>,
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (v: BadCaseStatus) => <Tag color={STATUS_COLOR[v]}>{labelOf(STATUS_OPTIONS, v)}</Tag>,
    },
    {
      title: "问题",
      dataIndex: "query",
      ellipsis: true,
      render: (v: string) => (
        <Typography.Text ellipsis={{ tooltip: v }} style={{ maxWidth: 320 }}>
          {v || "-"}
        </Typography.Text>
      ),
    },
    {
      title: "归因",
      dataIndex: "attribution",
      width: 120,
      render: (v: BadCaseAttribution | null) => labelOf(ATTRIBUTION_OPTIONS, v),
    },
    {
      title: "处理",
      dataIndex: "resolution",
      width: 130,
      render: (v: BadCaseResolution | null) => labelOf(RESOLUTION_OPTIONS, v),
    },
    {
      title: "创建时间",
      dataIndex: "createdAt",
      width: 170,
      render: (v: string) => dayjs(v).format("YYYY-MM-DD HH:mm"),
    },
    {
      title: "操作",
      key: "action",
      width: 260,
      fixed: "right",
      render: (_: unknown, record: BadCaseItem) => (
        <Space size="small" wrap>
          <Button type="link" size="small" onClick={() => openEdit(record)}>
            编辑
          </Button>
          {record.langfuseTraceUrl ? (
            <Button
              type="link"
              size="small"
              icon={<LinkOutlined />}
              href={record.langfuseTraceUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              Trace
            </Button>
          ) : null}
          <Button
            type="link"
            size="small"
            icon={<ExportOutlined />}
            disabled={record.resolution === "added_to_dataset"}
            onClick={() => handleAddToDataset(record)}
          >
            Dataset
          </Button>
        </Space>
      ),
    },
  ];

  const pagination: TablePaginationConfig = {
    current: page,
    pageSize,
    total: listData?.total ?? 0,
    showSizeChanger: true,
    showTotal: total => `共 ${total} 条`,
    onChange: (nextPage, nextSize) => {
      setPage(nextPage);
      setPageSize(nextSize);
    },
  };

  return (
    <>
      <Space size="middle" wrap className="mb-4">
        <Card size="small">
          <Statistic title="总数" value={stats?.total ?? 0} />
        </Card>
        {STATUS_OPTIONS.map(opt => (
          <Card size="small" key={opt.value}>
            <Statistic title={opt.label} value={stats?.byStatus?.[opt.value] ?? 0} />
          </Card>
        ))}
      </Space>

      <Space className="mb-3" wrap>
        <Select
          allowClear
          placeholder="状态"
          style={{ width: 140 }}
          options={STATUS_OPTIONS}
          value={status}
          onChange={v => {
            setStatus(v);
            setPage(1);
          }}
        />
        <Select
          allowClear
          placeholder="来源"
          style={{ width: 140 }}
          options={SOURCE_OPTIONS}
          value={source}
          onChange={v => {
            setSource(v);
            setPage(1);
          }}
        />
        <Button onClick={() => refresh()}>刷新</Button>
      </Space>

      <Table
        rowKey="id"
        size="middle"
        loading={loading}
        columns={columns}
        dataSource={listData?.items ?? []}
        pagination={pagination}
        scroll={{ x: 1100 }}
        locale={{ emptyText: "暂无 Bad Case" }}
      />

      <Drawer
        title="编辑 Bad Case"
        open={Boolean(editing)}
        onClose={() => setEditing(null)}
        size={480}
        destroyOnHidden
        extra={
          <Space>
            {editing ? (
              <Button disabled={editing.resolution === "added_to_dataset"} onClick={() => handleAddToDataset(editing)}>
                加入 Dataset
              </Button>
            ) : null}
            <Button type="primary" onClick={handleSave}>
              保存
            </Button>
          </Space>
        }
      >
        {editing ? (
          <>
            <Typography.Paragraph type="secondary" className="mb-2">
              <strong>问题：</strong>
              {editing.query || "-"}
            </Typography.Paragraph>
            <Typography.Paragraph type="secondary" className="mb-4">
              <strong>回答：</strong>
              {editing.answer || "-"}
            </Typography.Paragraph>
            {editing.langfuseTraceUrl ? (
              <Button
                className="mb-4"
                type="link"
                icon={<LinkOutlined />}
                href={editing.langfuseTraceUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                在 Langfuse 中查看 Trace
              </Button>
            ) : null}
            <Form form={form} layout="vertical">
              <Form.Item name="status" label="状态" rules={[{ required: true }]}>
                <Select options={STATUS_OPTIONS} />
              </Form.Item>
              <Form.Item name="attribution" label="归因">
                <Select allowClear options={ATTRIBUTION_OPTIONS} />
              </Form.Item>
              <Form.Item name="resolution" label="处理方式">
                <Select allowClear options={RESOLUTION_OPTIONS} />
              </Form.Item>
              <Form.Item name="reviewerNotes" label="复核备注">
                <Input.TextArea rows={4} placeholder="记录复核结论..." />
              </Form.Item>
            </Form>
          </>
        ) : null}
      </Drawer>
    </>
  );
};

export default BadCasesTab;
