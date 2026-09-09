import { MemoryGovernanceStatus, MemoryKind, MemoryListItem } from "@/interfaces";
import { profileAPI } from "@/services";
import { isPlainEnter } from "@/utils/chat";
import { DeleteOutlined, SearchOutlined } from "@ant-design/icons";
import { useDebounceFn, useRequest } from "ahooks";
import { App, Button, Input, Modal, Spin, Table, Tag, Typography } from "antd";
import type { ColumnsType, TablePaginationConfig } from "antd/es/table";
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

type RelatedMemoryRow = {
  id: string;
  memory: string;
  governanceStatus: MemoryGovernanceStatus | null;
  missing: boolean;
};

type RelatedMemoriesModalConfig = {
  title: string;
  summaryText: string;
  emptyText: string;
  missingText: string;
  layout: "table" | "detail";
};

function lookupMemoriesByIds(
  ids: string[],
  memories: MemoryListItem[],
  missingText: string,
): RelatedMemoryRow[] {
  const byId = new Map(memories.map((item) => [item.id, item]));
  return ids.map((id) => {
    const found = byId.get(id);
    if (!found) {
      return {
        id,
        memory: missingText,
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

function MemoryText({
  text,
  type,
  ellipsis = true,
}: {
  text: string;
  type?: "secondary";
  ellipsis?: boolean;
}) {
  return (
    <Typography.Paragraph
      type={type}
      ellipsis={ellipsis ? { rows: 2, tooltip: text } : false}
      className="mb-0 leading-5"
      style={{ whiteSpace: "normal" }}
    >
      {text}
    </Typography.Paragraph>
  );
}

function GovernanceStatusTag({
  status,
  clickable = false,
  title,
  onClick,
}: {
  status: MemoryGovernanceStatus | null | undefined;
  clickable?: boolean;
  title?: string;
  onClick?: () => void;
}) {
  const resolved = resolveGovernanceStatus(status);
  return (
    <Tag
      color={GOVERNANCE_STATUS_COLOR[resolved]}
      className={clickable ? "cursor-pointer" : undefined}
      title={title}
      onClick={onClick}
    >
      {governanceStatusLabel(resolved)}
    </Tag>
  );
}

function fetchMemories(keyword: string, page: number, pageSize: number) {
  const q = trim(keyword);
  if (!q) {
    return profileAPI.getMemories({ page, pageSize });
  }
  return profileAPI.searchMemories(q);
}

function useMemoryList() {
  const [query, setQuery] = useState("");
  const [searchKeyword, setSearchKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const composingRef = useRef(false);

  const { data, loading, run } = useRequest(fetchMemories, {
    manual: true,
  });

  const { run: debouncedSetKeyword, cancel: cancelDebouncedKeyword } = useDebounceFn(
    (keyword: string) => {
      setSearchKeyword(keyword);
      setPage(1);
    },
    { wait: SEARCH_DEBOUNCE_MS },
  );

  const isSearching = Boolean(trim(searchKeyword));

  useEffect(() => {
    if (isSearching) {
      run(searchKeyword, 1, pageSize);
    }
  }, [run, isSearching, searchKeyword, pageSize]);

  useEffect(() => {
    if (!isSearching) {
      run(searchKeyword, page, pageSize);
    }
  }, [run, isSearching, searchKeyword, page, pageSize]);

  const triggerSearch = (value: string, options?: { immediate?: boolean }) => {
    const trimmed = trim(value).slice(0, SEARCH_QUERY_MAX_LENGTH);
    if (!trimmed) {
      cancelDebouncedKeyword();
      setSearchKeyword("");
      setPage(1);
      return;
    }
    if (options?.immediate) {
      cancelDebouncedKeyword();
      setSearchKeyword(trimmed);
      setPage(1);
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
    refresh: () => run(searchKeyword, page, pageSize),
    query,
    searchKeyword,
    page,
    pageSize,
    isSearching,
    setPage,
    setPageSize,
    composingRef,
    handleQueryChange,
    triggerSearch,
  };
}

const RELATED_MEMORY_COLUMNS: ColumnsType<RelatedMemoryRow> = [
  {
    title: "记忆",
    dataIndex: "memory",
    key: "memory",
    render: (v: string, record) => (
      <MemoryText text={v} type={record.missing ? "secondary" : undefined} />
    ),
  },
  {
    title: "状态",
    dataIndex: "governanceStatus",
    key: "governanceStatus",
    width: 80,
    render: (_: RelatedMemoryRow["governanceStatus"], record) =>
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
    page,
    pageSize,
    isSearching,
    setPage,
    setPageSize,
    composingRef,
    handleQueryChange,
    triggerSearch,
  } = useMemoryList();
  const [relatedOpen, setRelatedOpen] = useState(false);
  const [relatedConfig, setRelatedConfig] = useState<RelatedMemoriesModalConfig | null>(null);
  const [relatedRows, setRelatedRows] = useState<RelatedMemoryRow[]>([]);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const relatedRequestIdRef = useRef(0);

  const _handleDelete = async (item: MemoryListItem) => {
    try {
      await profileAPI.deleteMemory(item.id);
      message.success("已删除");
      const currentCount = data?.memories?.length ?? 0;
      if (!isSearching && currentCount <= 1 && page > 1) {
        setPage(page - 1);
        return;
      }
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

  const handleCloseRelatedMemories = () => {
    relatedRequestIdRef.current += 1;
    setRelatedOpen(false);
    setRelatedConfig(null);
    setRelatedRows([]);
    setRelatedLoading(false);
  };

  const handleShowRelatedMemories = async (ids: string[], config: RelatedMemoriesModalConfig) => {
    const requestId = ++relatedRequestIdRef.current;
    const current = data?.memories ?? [];
    const initialRows = lookupMemoriesByIds(ids, current, config.missingText);

    setRelatedConfig(config);
    setRelatedRows(initialRows);
    setRelatedOpen(true);

    if (ids.length === 0 || !initialRows.some((row) => row.missing)) {
      return;
    }

    setRelatedLoading(true);
    try {
      const missingIds = initialRows.filter((row) => row.missing).map((row) => row.id);
      const fetched = await Promise.all(
        missingIds.map(async (id) => {
          try {
            return await profileAPI.getMemory(id);
          } catch {
            return null;
          }
        }),
      );
      if (requestId !== relatedRequestIdRef.current) {
        return;
      }
      const extra = fetched.filter((item): item is MemoryListItem => item != null);
      setRelatedRows(lookupMemoriesByIds(ids, [...current, ...extra], config.missingText));
    } catch {
      if (requestId !== relatedRequestIdRef.current) {
        return;
      }
      message.error("加载关联记忆失败");
    } finally {
      if (requestId === relatedRequestIdRef.current) {
        setRelatedLoading(false);
      }
    }
  };

  const handleShowSourceMemories = (item: MemoryListItem) => {
    void handleShowRelatedMemories(item.synthesizedFrom ?? [], {
      title: "来源记忆",
      summaryText: item.memory,
      emptyText: "暂无来源记忆",
      missingText: "来源记忆不存在或已删除",
      layout: "table",
    });
  };

  const handleShowSuccessorMemory = (item: MemoryListItem) => {
    void handleShowRelatedMemories(item.supersededBy ? [item.supersededBy] : [], {
      title: "新记忆",
      summaryText: item.memory,
      emptyText: "暂无新记忆",
      missingText: "新记忆不存在或已删除",
      layout: "detail",
    });
  };

  const columns: ColumnsType<MemoryListItem> = [
    {
      title: "记忆",
      dataIndex: "memory",
      key: "memory",
      render: (v: string) => <MemoryText text={v} />,
    },
    {
      title: "状态",
      dataIndex: "governanceStatus",
      key: "governanceStatus",
      width: 80,
      render: (v: MemoryListItem["governanceStatus"], record) => {
        const isSuperseded = resolveGovernanceStatus(v) === "superseded";
        return (
          <GovernanceStatusTag
            status={v}
            clickable={isSuperseded}
            title={isSuperseded ? "查看新记忆" : undefined}
            onClick={isSuperseded ? () => handleShowSuccessorMemory(record) : undefined}
          />
        );
      },
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

  const pagination: TablePaginationConfig = {
    current: page,
    pageSize,
    total: isSearching ? (data?.memories?.length ?? 0) : (data?.total ?? 0),
    showSizeChanger: true,
    showTotal: (total) => `共 ${total} 条`,
    onChange: (nextPage, nextSize) => {
      setPage(nextPage);
      setPageSize(nextSize);
    },
  };

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
        pagination={pagination}
        dataSource={data?.memories ?? []}
        locale={{ emptyText: isSearching ? "未找到相关记忆" : "暂无数据" }}
        tableLayout="fixed"
        scroll={{ x: "min-content" }}
      />
      <Modal
        centered
        destroyOnHidden
        open={relatedOpen}
        title={relatedConfig?.title}
        footer={null}
        width="min(720px, calc(100vw - 32px))"
        onCancel={handleCloseRelatedMemories}
      >
        {relatedConfig ? (
          <Typography.Paragraph
            type="secondary"
            className="mb-3"
            ellipsis={{ rows: 2, tooltip: relatedConfig.summaryText }}
          >
            {relatedConfig.summaryText}
          </Typography.Paragraph>
        ) : null}
        {relatedConfig?.layout === "table" ? (
          <Table
            size="small"
            rowKey="id"
            loading={relatedLoading}
            tableLayout="fixed"
            pagination={false}
            columns={RELATED_MEMORY_COLUMNS}
            dataSource={relatedRows}
            locale={{ emptyText: relatedConfig.emptyText }}
          />
        ) : (
          <Spin spinning={relatedLoading}>
            {relatedRows.length === 0 ? (
              <Typography.Text type="secondary">{relatedConfig?.emptyText}</Typography.Text>
            ) : (
              <div className="flex flex-col gap-4">
                {relatedRows.map((row) => (
                  <div key={row.id} className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <MemoryText
                        text={row.memory}
                        type={row.missing ? "secondary" : undefined}
                        ellipsis={false}
                      />
                    </div>
                    {row.missing ? (
                      <Typography.Text type="secondary">—</Typography.Text>
                    ) : (
                      <GovernanceStatusTag status={row.governanceStatus} />
                    )}
                  </div>
                ))}
              </div>
            )}
          </Spin>
        )}
      </Modal>
    </div>
  );
}
