import { MemoryGovernanceStatus, MemoryKind, MemoryListItem } from "@/interfaces";
import { profileAPI } from "@/services";
import { DeleteOutlined } from "@ant-design/icons";
import { useRequest } from "ahooks";
import { App, Button, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { useEffect } from "react";

const GOVERNANCE_STATUS_COLOR: Record<MemoryGovernanceStatus, string> = {
  active: "success",
  merged: "blue",
  superseded: "orange",
  archived: "default",
};

function resolveGovernanceStatus(
  status: MemoryGovernanceStatus | null | undefined,
): MemoryGovernanceStatus {
  return status ?? "active";
}

function governanceStatusLabel(status: MemoryGovernanceStatus): string {
  switch (status) {
    case "active":
      return "生效";
    case "merged":
      return "已合并";
    case "superseded":
      return "已取代";
    case "archived":
      return "已归档";
    default: {
      const _exhaustive: never = status;
      return _exhaustive;
    }
  }
}

function memoryKindLabel(kind: MemoryKind | null | undefined): string {
  if (!kind) {
    return "普通";
  }
  switch (kind) {
    case "pattern":
      return "模式";
    default: {
      const _exhaustive: never = kind;
      return _exhaustive;
    }
  }
}

function useMemoryList() {
  const { data, loading, run } = useRequest(profileAPI.getMemories, {
    manual: true,
  });
  useEffect(() => {
    run();
  }, [run]);
  return { data, loading, refresh: run };
}

export default function DataManage() {
  const { message } = App.useApp();
  const { modal } = App.useApp();
  const { data, loading, refresh } = useMemoryList();

  const _handleDelete = async (item: MemoryListItem) => {
    try {
      await profileAPI.deleteMemory(item.id);
      message.success("已删除");
      refresh();
    } catch {
      message.error("删除失败");
    }
  };

  const handleDelete = (item: MemoryListItem) => {
    modal.confirm({
      title: "确认删除",
      content: `确定要删除「${item.memory}」吗？`,
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: () => _handleDelete(item),
    });
  };

  const columns: ColumnsType<MemoryListItem> = [
    {
      title: "记忆",
      dataIndex: "memory",
      key: "memory",
      ellipsis: true,
      render: (v: string) => <Typography.Text ellipsis={{ tooltip: v }}>{v}</Typography.Text>,
    },
    {
      title: "状态",
      dataIndex: "governanceStatus",
      key: "governanceStatus",
      width: 80,
      render: (v: MemoryListItem["governanceStatus"]) => {
        const status = resolveGovernanceStatus(v);
        return <Tag color={GOVERNANCE_STATUS_COLOR[status]}>{governanceStatusLabel(status)}</Tag>;
      },
    },
    {
      title: "类型",
      dataIndex: "memoryKind",
      key: "memoryKind",
      width: 72,
      render: (v: MemoryListItem["memoryKind"]) => (
        <Tag color={v === "pattern" ? "purple" : "default"}>{memoryKindLabel(v)}</Tag>
      ),
    },
    {
      width: 100,
      title: "创建时间",
      key: "createdAt",
      dataIndex: "createdAt",
      render: (v: string) => (
        <span className="text-black-secondary text-sm">{dayjs(v).fromNow()}</span>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 50,
      render: (_: unknown, record: MemoryListItem) => (
        <Button
          type="link"
          danger
          size="small"
          onClick={() => handleDelete(record)}
          icon={<DeleteOutlined />}
        ></Button>
      ),
    },
  ];

  return (
    <Table
      size="small"
      rowKey="id"
      loading={loading}
      columns={columns}
      pagination={{
        pageSize: 20,
        showSizeChanger: true,
        showTotal: (total) => `共 ${total} 条`,
      }}
      dataSource={data?.memories ?? []}
      locale={{ emptyText: "暂无数据" }}
      scroll={{ x: "min-content" }}
    />
  );
}
