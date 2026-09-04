import {
  ConversationSearchItem,
  ConversationSearchMatchType,
  ConversationSearchResponse,
} from "@/interfaces";
import { conversationAPI } from "@/services/conversation";
import { isPlainEnter } from "@/utils/chat";
import {
  addSearchHistory,
  clearSearchHistory,
  getSearchHistory,
  removeSearchHistory,
} from "@/utils/searchHistory";
import { CloseOutlined, CommentOutlined, SearchOutlined } from "@ant-design/icons";
import { useDebounceFn, useInfiniteScroll, useMemoizedFn } from "ahooks";
import { Button, Empty, Input, Modal, Spin, Tag } from "antd";
import dayjs from "dayjs";
import React, { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

type Props = {
  open: boolean;
  onClose: () => void;
};

type SearchScrollData = {
  list: ConversationSearchItem[];
  nextCursor: string | null;
  hasMore: boolean;
};

const SEARCH_PAGE_LIMIT = 20;

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function HighlightText({ text, keyword }: { text: string; keyword: string }) {
  if (!keyword.trim() || !text) return <>{text}</>;
  const parts = text.split(new RegExp(`(${escapeRegExp(keyword.trim())})`, "gi"));
  return (
    <>
      {parts.map((part, index) =>
        part.toLowerCase() === keyword.trim().toLowerCase() ? (
          <span key={`${part}-${index}`} className="text-[#1677ff] font-medium">
            {part}
          </span>
        ) : (
          <span key={`${part}-${index}`}>{part}</span>
        ),
      )}
    </>
  );
}

function formatSearchTime(iso: string): string {
  const time = dayjs(iso);
  if (!time.isValid()) return "";
  if (time.isSame(dayjs(), "day")) return time.format("HH:mm");
  if (time.isSame(dayjs().subtract(1, "day"), "day")) return `昨天 ${time.format("HH:mm")}`;
  if (time.isSame(dayjs(), "year")) return time.format("M月D日 HH:mm");
  return time.format("YYYY-MM-DD HH:mm");
}

function snippetPrefix(matchType: ConversationSearchMatchType): string {
  switch (matchType) {
    case "user":
      return "你: ";
    case "assistant":
      return "助手: ";
    case "title":
      return "";
    default: {
      const _exhaustive: never = matchType;
      return _exhaustive;
    }
  }
}

const SearchModal: React.FC<Props> = ({ open, onClose }) => {
  const navigate = useNavigate();
  const listRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  /** 实际发起搜索的关键词（输入防抖 / 历史点击 / 回车后写入） */
  const [searchKeyword, setSearchKeyword] = useState("");
  const [searched, setSearched] = useState(false);
  const [history, setHistory] = useState<string[]>(() => getSearchHistory());
  // 中文输入法组合输入中，避免用拼音中间态触发搜索
  const composingRef = useRef(false);

  const { run: debouncedSetKeyword, cancel: cancelDebouncedKeyword } = useDebounceFn(
    (keyword: string) => {
      setSearchKeyword(keyword);
    },
    { wait: 500 },
  );

  const {
    data: scrollData,
    loading,
    loadingMore,
    noMore,
    mutate,
  } = useInfiniteScroll<SearchScrollData>(
    async (lastData) => {
      if (!searchKeyword) {
        return { list: [], nextCursor: null, hasMore: false };
      }
      if (lastData && !lastData.hasMore) {
        return lastData;
      }
      const res: ConversationSearchResponse = await conversationAPI.searchConversations({
        q: searchKeyword,
        cursor: lastData?.nextCursor ?? undefined,
        limit: SEARCH_PAGE_LIMIT,
      });
      // 仅首页写入搜索历史，避免翻页重复记录
      if (!lastData) {
        setHistory(addSearchHistory(searchKeyword));
      }
      return {
        list: res.conversations,
        nextCursor: res.nextCursor,
        hasMore: res.hasMore,
      };
    },
    {
      target: () => listRef.current ?? undefined,
      isNoMore: (data) => !data?.hasMore,
      threshold: 5,
      reloadDeps: [searchKeyword],
    },
  );

  const results = scrollData?.list ?? [];
  const isDebouncing = searched && !!query.trim() && query.trim() !== searchKeyword;

  const clearSearchResults = useMemoizedFn(() => {
    cancelDebouncedKeyword();
    setSearchKeyword("");
    setSearched(false);
    mutate(undefined);
  });

  const triggerSearch = useMemoizedFn((value: string, options?: { immediate?: boolean }) => {
    const trimmed = value.trim();
    if (!trimmed) {
      clearSearchResults();
      return;
    }
    setSearched(true);
    if (options?.immediate) {
      cancelDebouncedKeyword();
      setSearchKeyword(trimmed);
      return;
    }
    debouncedSetKeyword(trimmed);
  });

  const handleQueryChange = (value: string, isComposing: boolean) => {
    setQuery(value);
    // 组合输入过程中只更新展示，不发起搜索
    if (composingRef.current || isComposing) {
      return;
    }
    triggerSearch(value);
  };

  const handleSelectHistory = (keyword: string) => {
    setQuery(keyword);
    triggerSearch(keyword, { immediate: true });
  };

  const handleClearHistory = () => {
    clearSearchHistory();
    setHistory([]);
  };

  const handleRemoveHistory = (keyword: string) => {
    setHistory(removeSearchHistory(keyword));
  };

  const handleSelectResult = (item: ConversationSearchItem) => {
    if (query.trim()) {
      setHistory(addSearchHistory(query.trim()));
    }
    onClose();
    navigate(`/chat/${item.id}`);
  };

  // 无关键词，或中文组合输入尚未确认上屏时，继续展示搜索历史
  const showHistory = !query.trim() || !searched;
  const showInitialLoading = (loading || isDebouncing) && results.length === 0;
  const showEmpty = searched && !loading && !isDebouncing && results.length === 0;

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      centered
      width={600}
      closable={false}
      destroyOnHidden
      className="search-conversation-modal"
      styles={{ body: { padding: 0 } }}
    >
      <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-3">
        <SearchOutlined className="text-gray-400 text-base" />
        <Input
          autoFocus
          variant="borderless"
          placeholder="搜索对话..."
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
            // 确认上屏后再搜索（部分浏览器 compositionend 早于最终 onChange）
            triggerSearch(e.currentTarget.value);
          }}
          onPressEnter={(e) => {
            if (!isPlainEnter(e)) return;
            triggerSearch(query, { immediate: true });
          }}
          className="flex-1 text-base"
        />
        {query ? (
          <Button
            type="link"
            size="small"
            onClick={() => {
              setQuery("");
              clearSearchResults();
            }}
          >
            清除
          </Button>
        ) : null}
        <Button type="text" size="small" icon={<CloseOutlined />} onClick={onClose} />
      </div>

      <div ref={listRef} className="max-h-[60vh] overflow-y-auto px-4 py-3">
        {showHistory ? (
          <div>
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs text-black-tertiary">搜索历史</span>
              {history.length > 0 ? (
                <Button type="link" size="small" className="px-0" onClick={handleClearHistory}>
                  清除
                </Button>
              ) : null}
            </div>
            {history.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无搜索历史" />
            ) : (
              <div className="flex flex-wrap gap-2">
                {history.map((item) => (
                  <Tag
                    key={item}
                    title={item}
                    closable
                    className="cursor-pointer m-0 px-3 py-1 rounded-full border-0 bg-gray-100 hover:bg-gray-200"
                    onClick={() => handleSelectHistory(item)}
                    onClose={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      handleRemoveHistory(item);
                    }}
                  >
                    {item.length > 10 ? `${item.slice(0, 10)}…` : item}
                  </Tag>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div>
            {showInitialLoading ? (
              <div className="flex justify-center py-10">
                <Spin />
              </div>
            ) : null}
            {showEmpty ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未找到相关对话" />
            ) : null}
            {!showInitialLoading &&
              results.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="w-full text-left px-2 py-3 rounded-lg hover:bg-gray-50 border-0 bg-transparent cursor-pointer"
                  onClick={() => handleSelectResult(item)}
                >
                  <div className="flex items-start gap-2">
                    <CommentOutlined className="mt-1 text-gray-400" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-3">
                        <div className="truncate text-sm text-black">
                          <HighlightText text={item.title} keyword={searchKeyword || query} />
                        </div>
                        <span className="shrink-0 text-xs text-black-tertiary">
                          {formatSearchTime(item.updatedAt)}
                        </span>
                      </div>
                      {item.snippet ? (
                        <div className="mt-1 truncate text-xs text-black-secondary">
                          {snippetPrefix(item.matchType)}
                          <HighlightText text={item.snippet} keyword={searchKeyword || query} />
                        </div>
                      ) : null}
                    </div>
                  </div>
                </button>
              ))}
            {loadingMore ? (
              <div className="flex justify-center py-3">
                <Spin size="small" />
              </div>
            ) : null}
            {!loadingMore && noMore && results.length > 0 ? (
              <div className="py-2 text-center text-sm text-black-tertiary">暂无更多数据</div>
            ) : null}
          </div>
        )}
      </div>
    </Modal>
  );
};

export default React.memo(SearchModal);
