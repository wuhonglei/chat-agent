import { EvalRunLog, EvalRunStatus, EvalRunType } from "@/interfaces/eval";
import { evalAPI } from "@/services";
import { PlayCircleOutlined } from "@ant-design/icons";
import { useRequest } from "ahooks";
import { App, Button, InputNumber, Select, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType, TablePaginationConfig } from "antd/es/table";
import dayjs from "dayjs";
import React, { useEffect, useState } from "react";

const STATUS_OPTIONS: { label: string; value: EvalRunStatus }[] = [
  { label: "运行中", value: "running" },
  { label: "成功", value: "success" },
  { label: "失败", value: "failed" },
];

const RUN_TYPE_OPTIONS: { label: string; value: EvalRunType }[] = [
  { label: "定时", value: "scheduled" },
  { label: "手动", value: "manual" },
];

const STATUS_COLOR: Record<EvalRunStatus, string> = {
  running: "processing",
  success: "success",
  failed: "error",
};

function labelOf<T extends string>(options: { label: string; value: T }[], value: T | null | undefined) {
  if (!value) return "-";
  return options.find(o => o.value === value)?.label ?? value;
}

function formatBreakdown(breakdown: Record<string, unknown> | undefined): string {
  if (!breakdown || Object.keys(breakdown).length === 0) return "-";
  return Object.entries(breakdown)
    .map(([k, v]) => `${k}: ${String(v)}`)
    .join(", ");
}

const EvalRunLogsTab: React.FC = () => {
  const { message } = App.useApp();
  const [status, setStatus] = useState<EvalRunStatus | undefined>();
  const [runType, setRunType] = useState<EvalRunType | undefined>();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [hours, setHours] = useState<number | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [pollingRunId, setPollingRunId] = useState<string | null>(null);

  const {
    data: listData,
    loading,
    refresh,
  } = useRequest(
    () =>
      evalAPI.listRunLogs({
        status,
        runType,
        page,
        pageSize,
      }),
    {
      refreshDeps: [status, runType, page, pageSize],
    }
  );

  const { data: polledRun, cancel: cancelPoll } = useRequest(() => evalAPI.getRunLog(pollingRunId!), {
    ready: Boolean(pollingRunId),
    pollingInterval: 2000,
    refreshDeps: [pollingRunId],
  });

  useEffect(() => {
    if (!polledRun || !pollingRunId) return;
    if (polledRun.status === "running") return;

    cancelPoll();
    setPollingRunId(null);
    refresh();
    if (polledRun.status === "success") {
      message.success(`评估完成：采样 ${polledRun.sampledCount}，低分 ${polledRun.lowScoreCount}`);
    } else {
      message.error(polledRun.errorMessage || "评估失败");
    }
  }, [polledRun, pollingRunId, cancelPoll, refresh, message]);

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      const run = await evalAPI.triggerBatchEval({
        hours: hours ?? undefined,
      });
      message.success("批量评估已开始");
      setPage(1);
      refresh();
      setPollingRunId(run.id);
    } catch {
      // HTTP 错误（含 409「已有评估在运行」）已由 apiClient 拦截器提示
    } finally {
      setTriggering(false);
    }
  };

  const columns: ColumnsType<EvalRunLog> = [
    {
      title: "类型",
      dataIndex: "runType",
      width: 90,
      render: (v: EvalRunType) => <Tag>{labelOf(RUN_TYPE_OPTIONS, v)}</Tag>,
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (v: EvalRunStatus) => <Tag color={STATUS_COLOR[v]}>{labelOf(STATUS_OPTIONS, v)}</Tag>,
    },
    {
      title: "开始时间",
      dataIndex: "startedAt",
      width: 170,
      render: (v: string) => dayjs(v).format("YYYY-MM-DD HH:mm"),
    },
    {
      title: "结束时间",
      dataIndex: "finishedAt",
      width: 170,
      render: (v: string | null) => (v ? dayjs(v).format("YYYY-MM-DD HH:mm") : "-"),
    },
    {
      title: "Trace",
      dataIndex: "totalTraces",
      width: 80,
    },
    {
      title: "去重后",
      dataIndex: "afterDedup",
      width: 80,
    },
    {
      title: "采样",
      dataIndex: "sampledCount",
      width: 70,
    },
    {
      title: "分层明细",
      dataIndex: "sampleBreakdown",
      width: 220,
      ellipsis: true,
      render: (v: Record<string, unknown>) => (
        <Typography.Text ellipsis={{ tooltip: formatBreakdown(v) }}>{formatBreakdown(v)}</Typography.Text>
      ),
    },
    {
      title: "裁判成功",
      dataIndex: "judgeSuccess",
      width: 90,
    },
    {
      title: "裁判失败",
      dataIndex: "judgeFailed",
      width: 90,
    },
    {
      title: "低分",
      dataIndex: "lowScoreCount",
      width: 70,
    },
    {
      title: "错误",
      dataIndex: "errorMessage",
      ellipsis: true,
      render: (v: string | null) =>
        v ? (
          <Typography.Text type="danger" ellipsis={{ tooltip: v }}>
            {v}
          </Typography.Text>
        ) : (
          "-"
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

  const isPolling = Boolean(pollingRunId);

  return (
    <>
      <Space className="mb-3" wrap>
        <InputNumber
          min={1}
          max={168}
          placeholder="回溯小时（默认配置）"
          style={{ width: 180 }}
          value={hours}
          onChange={v => setHours(typeof v === "number" ? v : null)}
        />
        <Button type="primary" icon={<PlayCircleOutlined />} loading={triggering || isPolling} onClick={handleTrigger}>
          手动触发评估
        </Button>
        <Select
          allowClear
          placeholder="状态"
          style={{ width: 120 }}
          options={STATUS_OPTIONS}
          value={status}
          onChange={v => {
            setStatus(v);
            setPage(1);
          }}
        />
        <Select
          allowClear
          placeholder="类型"
          style={{ width: 120 }}
          options={RUN_TYPE_OPTIONS}
          value={runType}
          onChange={v => {
            setRunType(v);
            setPage(1);
          }}
        />
        <Button onClick={() => refresh()}>刷新</Button>
        {isPolling ? <Typography.Text type="secondary">评估进行中，正在轮询状态…</Typography.Text> : null}
      </Space>

      <Table
        rowKey="id"
        size="middle"
        loading={loading}
        columns={columns}
        dataSource={listData?.items ?? []}
        pagination={pagination}
        scroll={{ x: 1400 }}
        locale={{ emptyText: "暂无评估运行记录" }}
      />
    </>
  );
};

export default EvalRunLogsTab;
