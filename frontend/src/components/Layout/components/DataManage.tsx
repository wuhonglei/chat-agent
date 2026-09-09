import { MemoryGovernanceStatus, MemoryKind, MemoryListItem } from "@/interfaces";
import { profileAPI } from "@/services";
import { isPlainEnter } from "@/utils/chat";
import { DeleteOutlined, SearchOutlined } from "@ant-design/icons";
import { useDebounceFn, useRequest } from "ahooks";
import { App, Button, Input, Modal, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { trim } from "lodash-es";
import { useEffect, useRef, useState } from "react";

const SEARCH_DEBOUNCE_MS = 500;
const SEARCH_QUERY_MAX_LENGTH = 200;

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

type SourceMemoryRow = {
  id: string;
  memory: string;
  governanceStatus: MemoryGovernanceStatus | null;
  missing: boolean;
};

function lookupSourceMemories(ids: string[], memories: MemoryListItem[]): SourceMemoryRow[] {
  const byId = new Map(memories.map((item) => [item.id, item]));
  return ids.map((id) => {
    const found = byId.get(id);
    if (!found) {
      return {
        id,
        memory: "来源记忆不存在或已删除",
        governanceStatus: null,
        missing: true,
      };
    }
    return {
      id: found.id,
      memory: found.memory,
      governanceStatus: found.governanceStatus ?? null,
      missing: false,
    };
  });
}

function GovernanceStatusTag({ status }: { status: MemoryGovernanceStatus | null | undefined }) {
  const resolved = resolveGovernanceStatus(status);
  return <Tag color={GOVERNANCE_STATUS_COLOR[resolved]}>{governanceStatusLabel(resolved)}</Tag>;
}

function fetchMemories(keyword: string) {
  const q = trim(keyword);
  if (!q) {
    return profileAPI.getMemories();
  }
  return profileAPI.searchMemories(q);
}

function useMemoryList() {
  const [query, setQuery] = useState("");
  const [searchKeyword, setSearchKeyword] = useState("");
  const composingRef = useRef(false);

  const { data, loading, run } = useRequest(fetchMemories, {
    manual: true,
  });

  const { run: debouncedSetKeyword, cancel: cancelDebouncedKeyword } = useDebounceFn(
    (keyword: string) => {
      setSearchKeyword(keyword);
    },
    { wait: SEARCH_DEBOUNCE_MS },
  );

  useEffect(() => {
    run(searchKeyword);
  }, [run, searchKeyword]);

  const triggerSearch = (value: string, options?: { immediate?: boolean }) => {
    const trimmed = trim(value).slice(0, SEARCH_QUERY_MAX_LENGTH);
    if (!trimmed) {
      cancelDebouncedKeyword();
      setSearchKeyword("");
      return;
    }
    if (options?.immediate) {
      cancelDebouncedKeyword();
      setSearchKeyword(trimmed);
      return;
    }
    debouncedSetKeyword(trimmed);
  };

  const handleQueryChange = (value: string, isComposing: boolean) => {
    setQuery(value);
    if (composingRef.current || isComposing) {
      return;
    }
    triggerSearch(value);
  };

  return {
    data,
    loading,
    refresh: () => run(searchKeyword),
    query,
    searchKeyword,
    composingRef,
    handleQueryChange,
    triggerSearch,
  };
}

const SOURCE_MEMORY_COLUMNS: ColumnsType<SourceMemoryRow> = [
  {
    title: "记忆",
    dataIndex: "memory",
    key: "memory",
    ellipsis: true,
    render: (v: string, record) =>
      record.missing ? (
        <Typography.Text type="secondary">{v}</Typography.Text>
      ) : (
        <Typography.Text ellipsis={{ tooltip: v }}>{v}</Typography.Text>
      ),
  },
  {
    title: "状态",
    dataIndex: "governanceStatus",
    key: "governanceStatus",
    width: 80,
    render: (_: SourceMemoryRow["governanceStatus"], record) =>
      record.missing ? (
        <Typography.Text type="secondary">—</Typography.Text>
      ) : (
        <GovernanceStatusTag status={record.governanceStatus} />
      ),
  },
];

export default function DataManage() {
  const { message, modal } = App.useApp();
  const {
    data,
    loading,
    refresh,
    query,
    searchKeyword,
    composingRef,
    handleQueryChange,
    triggerSearch,
  } = useMemoryList();
  const [sourceOpen, setSourceOpen] = useState(false);
  const [sourcePattern, setSourcePattern] = useState<MemoryListItem | null>(null);
  const [sourceRows, setSourceRows] = useState<SourceMemoryRow[]>([]);
  const [sourceLoading, setSourceLoading] = useState(false);
  const sourceRequestIdRef = useRef(0);

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

  const handleCloseSourceMemories = () => {
    sourceRequestIdRef.current += 1;
    setSourceOpen(false);
    setSourcePattern(null);
    setSourceRows([]);
    setSourceLoading(false);
  };

  const handleShowSourceMemories = async (item: MemoryListItem) => {
    const requestId = ++sourceRequestIdRef.current;
    const ids = item.synthesizedFrom ?? [];
    const current = data?.memories ?? [];
    const initialRows = lookupSourceMemories(ids, current);

    setSourcePattern(item);
    setSourceRows(initialRows);
    setSourceOpen(true);

    if (ids.length === 0 || !initialRows.some((row) => row.missing)) {
      return;
    }

    setSourceLoading(true);
    try {
      const full = await profileAPI.getMemories();
      if (requestId !== sourceRequestIdRef.current) {
        return;
      }
      setSourceRows(lookupSourceMemories(ids, full.memories ?? []));
    } catch {
      if (requestId !== sourceRequestIdRef.current) {
        return;
      }
      message.error("加载来源记忆失败");
    } finally {
      if (requestId === sourceRequestIdRef.current) {
        setSourceLoading(false);
      }
    }
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
      render: (v: MemoryListItem["governanceStatus"]) => <GovernanceStatusTag status={v} />,
    },
    {
      title: "类型",
      dataIndex: "memoryKind",
      key: "memoryKind",
      width: 72,
      render: (v: MemoryListItem["memoryKind"], record) => {
        const isPattern = v === "pattern";
        return (
          <Tag
            color={isPattern ? "purple" : "default"}
            className={isPattern ? "cursor-pointer" : undefined}
            title={isPattern ? "查看来源记忆" : undefined}
            onClick={isPattern ? () => handleShowSourceMemories(record) : undefined}
          >
            {memoryKindLabel(v)}
          </Tag>
        );
      },
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

  const isSearching = Boolean(trim(searchKeyword));

  return (
    <div className="flex flex-col gap-3">
      <Input
        allowClear
        maxLength={SEARCH_QUERY_MAX_LENGTH}
        prefix={<SearchOutlined className="text-gray-400" />}
        placeholder="搜索记忆"
        value={query}
        onChange={(e) => {
          const isComposing = Boolean((e.nativeEvent as InputEvent).isComposing);
          handleQueryChange(e.target.value, isComposing);
        }}
        onCompositionStart={() => {
          composingRef.current = true;
        }}
        onCompositionEnd={(e) => {
          composingRef.current = false;
          triggerSearch(e.currentTarget.value);
        }}
        onPressEnter={(e) => {
          if (!isPlainEnter(e)) return;
          triggerSearch(query, { immediate: true });
        }}
      />
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
        locale={{ emptyText: isSearching ? "未找到相关记忆" : "暂无数据" }}
        scroll={{ x: "min-content" }}
      />
      <Modal
        centered
        destroyOnHidden
        open={sourceOpen}
        title="来源记忆"
        footer={null}
        width="min(720px, calc(100vw - 32px))"
        onCancel={handleCloseSourceMemories}
      >
        {sourcePattern ? (
          <Typography.Paragraph
            type="secondary"
            className="mb-3"
            ellipsis={{ rows: 2, tooltip: sourcePattern.memory }}
          >
            模式：{sourcePattern.memory}
          </Typography.Paragraph>
        ) : null}
        <Table
          size="small"
          rowKey="id"
          loading={sourceLoading}
          pagination={false}
          columns={SOURCE_MEMORY_COLUMNS}
          dataSource={sourceRows}
          locale={{ emptyText: "暂无来源记忆" }}
        />
      </Modal>
    </div>
  );
}
