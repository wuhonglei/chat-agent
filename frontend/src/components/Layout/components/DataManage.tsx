import {
  MemoryGovernanceStatus,
  MemoryKind,
  MemoryKindQuery,
  MemoryListItem,
  MemoryListParams,
} from "@/interfaces";
import { profileAPI } from "@/services";
import { isPlainEnter } from "@/utils/chat";
import { DeleteOutlined, SearchOutlined } from "@ant-design/icons";
import { useRequest } from "ahooks";
import { App, Button, DatePicker, Input, Modal, Select, Spin, Table, Tag, Typography } from "antd";
import type { ColumnsType, TablePaginationConfig } from "antd/es/table";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";
import { trim } from "lodash-es";
import { useEffect, useRef, useState } from "react";

const SEARCH_QUERY_MAX_LENGTH = 200;

const GOVERNANCE_STATUS_FILTER_OPTIONS: { value: MemoryGovernanceStatus; label: string }[] = [
  { value: "active", label: "生效" },
  { value: "merged", label: "已合并" },
  { value: "superseded", label: "已取代" },
  { value: "archived", label: "已归档" },
];

const MEMORY_KIND_FILTER_OPTIONS: { value: MemoryKindQuery; label: string }[] = [
  { value: "ordinary", label: "普通" },
  { value: "pattern", label: "模式" },
];

type CreatedRange = [Dayjs, Dayjs] | null;

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

function createdRangeToIso(
  range: CreatedRange,
): Pick<MemoryListParams, "createdFrom" | "createdTo"> {
  if (!range) {
    return {};
  }
  return {
    createdFrom: range[0].startOf("day").toISOString(),
    createdTo: range[1].endOf("day").toISOString(),
  };
}

function memoryFilterParams(
  governanceStatus?: MemoryGovernanceStatus,
  memoryKind?: MemoryKindQuery,
  createdRange?: CreatedRange,
): Pick<MemoryListParams, "governanceStatus" | "memoryKind" | "createdFrom" | "createdTo"> {
  const { createdFrom, createdTo } = createdRangeToIso(createdRange ?? null);
  return {
    ...(governanceStatus ? { governanceStatus } : {}),
    ...(memoryKind ? { memoryKind } : {}),
    ...(createdFrom ? { createdFrom } : {}),
    ...(createdTo ? { createdTo } : {}),
  };
}

function fetchMemories(
  keyword: string,
  page: number,
  pageSize: number,
  governanceStatus?: MemoryGovernanceStatus,
  memoryKind?: MemoryKindQuery,
  createdRange?: CreatedRange,
) {
  const filters = memoryFilterParams(governanceStatus, memoryKind, createdRange);
  const q = trim(keyword);
  if (!q) {
    return profileAPI.getMemories({ page, pageSize, ...filters });
  }
  return profileAPI.searchMemories({ q, ...filters });
}

function useMemoryList() {
  const [query, setQuery] = useState("");
  const [governanceStatus, setGovernanceStatus] = useState<MemoryGovernanceStatus | undefined>();
  const [memoryKind, setMemoryKind] = useState<MemoryKindQuery | undefined>();
  const [createdRange, setCreatedRange] = useState<CreatedRange>(null);
  const [appliedKeyword, setAppliedKeyword] = useState("");
  const [appliedStatus, setAppliedStatus] = useState<MemoryGovernanceStatus | undefined>();
  const [appliedKind, setAppliedKind] = useState<MemoryKindQuery | undefined>();
  const [appliedRange, setAppliedRange] = useState<CreatedRange>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const { data, loading, run } = useRequest(fetchMemories, {
    manual: true,
  });

  const isSearching = Boolean(trim(appliedKeyword));
  const hasFilters = Boolean(appliedStatus || appliedKind || appliedRange);
  const isFiltered = isSearching || hasFilters;

  useEffect(() => {
    if (isSearching) {
      run(appliedKeyword, 1, pageSize, appliedStatus, appliedKind, appliedRange);
    }
  }, [run, isSearching, appliedKeyword, pageSize, appliedStatus, appliedKind, appliedRange]);

  useEffect(() => {
    if (!isSearching) {
      run(appliedKeyword, page, pageSize, appliedStatus, appliedKind, appliedRange);
    }
  }, [run, isSearching, appliedKeyword, page, pageSize, appliedStatus, appliedKind, appliedRange]);

  const submitSearch = () => {
    setAppliedKeyword(trim(query).slice(0, SEARCH_QUERY_MAX_LENGTH));
    setAppliedStatus(governanceStatus);
    setAppliedKind(memoryKind);
    setAppliedRange(createdRange);
    setPage(1);
  };

  return {
    data,
    loading,
    refresh: () =>
      run(
        appliedKeyword,
        isSearching ? 1 : page,
        pageSize,
        appliedStatus,
        appliedKind,
        appliedRange,
      ),
    query,
    page,
    pageSize,
    isSearching,
    isFiltered,
    governanceStatus,
    memoryKind,
    createdRange,
    setQuery,
    setPage,
    setPageSize,
    setGovernanceStatus,
    setMemoryKind,
    setCreatedRange,
    submitSearch,
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
    isFiltered,
    governanceStatus,
    memoryKind,
    createdRange,
    setQuery,
    setPage,
    setPageSize,
    setGovernanceStatus,
    setMemoryKind,
    setCreatedRange,
    submitSearch,
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
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
        <Input
          allowClear
          maxLength={SEARCH_QUERY_MAX_LENGTH}
          prefix={<SearchOutlined className="text-gray-400" />}
          placeholder="搜索记忆"
          className="w-full min-w-0 sm:min-w-40 sm:flex-1"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onPressEnter={(e) => {
            if (!isPlainEnter(e)) return;
            submitSearch();
          }}
        />
        <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto sm:shrink-0">
          <div className="min-w-0 sm:w-[110px]">
            <Select
              allowClear
              placeholder="状态"
              style={{ width: "100%" }}
              options={GOVERNANCE_STATUS_FILTER_OPTIONS}
              value={governanceStatus}
              onChange={(value) => setGovernanceStatus(value)}
            />
          </div>
          <div className="min-w-0 sm:w-[110px]">
            <Select
              allowClear
              placeholder="类型"
              style={{ width: "100%" }}
              options={MEMORY_KIND_FILTER_OPTIONS}
              value={memoryKind}
              onChange={(value) => setMemoryKind(value)}
            />
          </div>
        </div>
        <div className="w-full min-w-0 sm:w-[220px] sm:shrink-0">
          <DatePicker.RangePicker
            allowClear
            inputReadOnly
            style={{ width: "100%" }}
            placeholder={["开始日期", "结束日期"]}
            value={createdRange}
            onChange={(dates) => {
              setCreatedRange(dates?.[0] && dates[1] ? [dates[0], dates[1]] : null);
            }}
          />
        </div>
        <Button
          type="primary"
          className="w-full sm:w-auto sm:shrink-0"
          icon={<SearchOutlined />}
          onClick={submitSearch}
        >
          搜索
        </Button>
      </div>
      <Table
        size="small"
        rowKey="id"
        loading={loading}
        columns={columns}
        pagination={pagination}
        dataSource={data?.memories ?? []}
        locale={{ emptyText: isFiltered ? "未找到相关记忆" : "暂无数据" }}
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
