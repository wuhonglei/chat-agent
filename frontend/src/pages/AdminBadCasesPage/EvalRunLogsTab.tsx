import { EvalRunLog, EvalRunScoreSummary, EvalRunStatus, EvalRunType } from "@/interfaces/eval";
import { evalAPI } from "@/services";
import { DeleteOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { useRequest } from "ahooks";
import { App, Button, InputNumber, Select, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType, TablePaginationConfig } from "antd/es/table";
import dayjs from "dayjs";
import React, { useEffect, useRef, useState } from "react";

function formatAvg(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  return value.toFixed(2);
}

function formatScoreSummary(summary: EvalRunScoreSummary | null | undefined): string {
  if (!summary?.overall) return "-";
  const { avgCorrectness, avgCompleteness, avgMin, lowRate } = summary.overall;
  return `准 ${formatAvg(avgCorrectness)} / 全 ${formatAvg(avgCompleteness)} / min ${formatAvg(avgMin)} / 低分率 ${(lowRate * 100).toFixed(0)}%`;
}

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

function labelOf<T extends string>(
  options: { label: string; value: T }[],
  value: T | null | undefined,
) {
  if (!value) return "-";
  return options.find((o) => o.value === value)?.label ?? value;
}

function formatBreakdown(breakdown: Record<string, unknown> | undefined): string {
  if (!breakdown || Object.keys(breakdown).length === 0) return "-";
  return Object.entries(breakdown)
    .map(([k, v]) => `${k}: ${String(v)}`)
    .join(", ");
}

const EvalRunLogsTab: React.FC = () => {
  const { message, modal } = App.useApp();
  const [status, setStatus] = useState<EvalRunStatus | undefined>();
  const [runType, setRunType] = useState<EvalRunType | undefined>();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [triggering, setTriggering] = useState(false);
  const [pollingRunId, setPollingRunId] = useState<string | null>(null);
  const confirmHoursRef = useRef<number | null>(null);

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
    },
  );

  const { data: runningCheck, refresh: refreshRunningCheck } = useRequest(
    () => evalAPI.listRunLogs({ status: "running", page: 1, pageSize: 1 }),
    { refreshDeps: [] },
  );

  const { data: polledRun, cancel: cancelPoll } = useRequest(
    () => evalAPI.getRunLog(pollingRunId!),
    {
      ready: Boolean(pollingRunId),
      pollingInterval: 2000,
      refreshDeps: [pollingRunId],
    },
  );

  useEffect(() => {
    if (!polledRun || !pollingRunId) return;
    if (polledRun.status === "running") return;

    cancelPoll();
    setPollingRunId(null);
    refresh();
    refreshRunningCheck();
    if (polledRun.status === "success") {
      message.success(`评估完成：采样 ${polledRun.sampledCount}，低分 ${polledRun.lowScoreCount}`);
    } else {
      message.error(polledRun.errorMessage || "评估失败");
    }
  }, [polledRun, pollingRunId, cancelPoll, refresh, refreshRunningCheck, message]);

  const isPolling = Boolean(pollingRunId);
  const hasRunning = isPolling || (runningCheck?.total ?? 0) > 0;

  const runTrigger = async (hours: number | null) => {
    setTriggering(true);
    try {
      const run = await evalAPI.triggerBatchEval({
        hours: hours ?? undefined,
      });
      message.success("批量评估已开始");
      setPage(1);
      refresh();
      refreshRunningCheck();
      setPollingRunId(run.id);
    } catch {
      // HTTP 错误（含 409「已有评估在运行」）已由 apiClient 拦截器提示
    } finally {
      setTriggering(false);
    }
  };

  const handleTrigger = () => {
    if (hasRunning) return;
    confirmHoursRef.current = null;
    modal.confirm({
      title: "确认手动触发评估？",
      content: (
        <div>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
            将按当前配置启动一次批量评估，请确认回溯时间范围。
          </Typography.Paragraph>
          <InputNumber
            min={1}
            max={168}
            placeholder="回溯小时（默认配置）"
            style={{ width: "100%" }}
            onChange={(v) => {
              confirmHoursRef.current = typeof v === "number" ? v : null;
            }}
          />
        </div>
      ),
      okText: "开始评估",
      cancelText: "取消",
      onOk: () => runTrigger(confirmHoursRef.current),
    });
  };

  const handleDelete = (record: EvalRunLog) => {
    if (record.status === "running") {
      message.warning("评估仍在运行中，无法删除");
      return;
    }
    const startedAt = dayjs(record.startedAt).format("YYYY-MM-DD HH:mm");
    modal.confirm({
      title: "确认删除评估历史？",
      content: `确定删除 ${startedAt} 的「${labelOf(RUN_TYPE_OPTIONS, record.runType)}」评估记录吗？此操作不可恢复。`,
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        try {
          await evalAPI.deleteRunLog(record.id);
          message.success("已删除");
          if (pollingRunId === record.id) {
            cancelPoll();
            setPollingRunId(null);
          }
          refresh();
          refreshRunningCheck();
        } catch {
          // HTTP 错误已由 apiClient 拦截器提示
        }
      },
    });
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
        <Typography.Text ellipsis={{ tooltip: formatBreakdown(v) }}>
          {formatBreakdown(v)}
        </Typography.Text>
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
      title: "低分入队",
      dataIndex: "lowScoreCount",
      width: 90,
    },
    {
      title: "得分汇总",
      dataIndex: "scoreSummary",
      width: 280,
      ellipsis: true,
      render: (v: EvalRunScoreSummary | null) => {
        const text = formatScoreSummary(v);
        return (
          <Typography.Text ellipsis={{ tooltip: text }} style={{ maxWidth: 260 }}>
            {text}
          </Typography.Text>
        );
      },
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
    {
      title: "操作",
      key: "action",
      width: 70,
      fixed: "right",
      render: (_: unknown, record: EvalRunLog) => (
        <Button
          type="link"
          danger
          size="small"
          disabled={record.status === "running"}
          icon={<DeleteOutlined />}
          onClick={() => handleDelete(record)}
        />
      ),
    },
  ];

  const pagination: TablePaginationConfig = {
    current: page,
    pageSize,
    total: listData?.total ?? 0,
    showSizeChanger: true,
    showTotal: (total) => `共 ${total} 条`,
    onChange: (nextPage, nextSize) => {
      setPage(nextPage);
      setPageSize(nextSize);
    },
  };

  return (
    <>
      <Space className="mb-3" wrap>
        <Select
          allowClear
          placeholder="状态"
          style={{ width: 120 }}
          options={STATUS_OPTIONS}
          value={status}
          onChange={(v) => {
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
          onChange={(v) => {
            setRunType(v);
            setPage(1);
          }}
        />
        <Button
          onClick={() => {
            refresh();
            refreshRunningCheck();
          }}
        >
          刷新
        </Button>
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          loading={triggering || isPolling}
          disabled={hasRunning}
          onClick={handleTrigger}
        >
          手动触发评估
        </Button>
        {isPolling ? (
          <Typography.Text type="secondary">评估进行中，正在轮询状态…</Typography.Text>
        ) : null}
      </Space>

      <Table
        rowKey="id"
        size="middle"
        loading={loading}
        columns={columns}
        dataSource={listData?.items ?? []}
        pagination={pagination}
        scroll={{ x: 1750 }}
        locale={{ emptyText: "暂无评估运行记录" }}
      />
    </>
  );
};

export default EvalRunLogsTab;
