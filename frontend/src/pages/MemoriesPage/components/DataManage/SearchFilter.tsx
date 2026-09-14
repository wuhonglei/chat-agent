import {
  MemoryCategory,
  MemoryGovernanceStatus,
  MemoryKindQuery,
} from "@/interfaces";
import { isPlainEnter } from "@/utils/chat";
import { SearchOutlined } from "@ant-design/icons";
import { Button, DatePicker, Form, Input, Select } from "antd";
import type { Dayjs } from "dayjs";
import { trim } from "lodash-es";

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

const MEMORY_CATEGORY_FILTER_OPTIONS: { value: MemoryCategory; label: string }[] = [
  { value: "personal_core", label: "个人核心" },
  { value: "preferences", label: "偏好" },
  { value: "interests", label: "兴趣" },
  { value: "state", label: "状态" },
  { value: "knowledge", label: "知识" },
  { value: "misc", label: "其他" },
];

export type CreatedRange = [Dayjs, Dayjs] | null;

export interface SearchFilterValues {
  query?: string;
  governanceStatus?: MemoryGovernanceStatus;
  memoryKind?: MemoryKindQuery;
  category?: MemoryCategory;
  createdRange?: CreatedRange;
}

interface SearchFilterProps {
  onSearch: (values: SearchFilterValues) => void;
}

function normalizeCreatedRange(
  dates: [Dayjs | null, Dayjs | null] | null,
): CreatedRange {
  return dates?.[0] && dates[1] ? [dates[0], dates[1]] : null;
}

export default function SearchFilter({ onSearch }: SearchFilterProps) {
  const [form] = Form.useForm<SearchFilterValues>();

  const handleFinish = (values: SearchFilterValues) => {
    onSearch({
      ...values,
      query: trim(values.query ?? "").slice(0, SEARCH_QUERY_MAX_LENGTH),
      createdRange: values.createdRange ?? null,
    });
  };

  return (
    <Form form={form} colon={false} onFinish={handleFinish}>
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
        <Form.Item name="query" noStyle>
          <Input
            allowClear
            maxLength={SEARCH_QUERY_MAX_LENGTH}
            prefix={<SearchOutlined className="text-gray-400" />}
            placeholder="搜索记忆"
            className="w-full min-w-40 sm:flex-1"
            onPressEnter={(event) => {
              if (!isPlainEnter(event)) {
                event.preventDefault();
              }
            }}
          />
        </Form.Item>
        <div className="flex w-full flex-wrap gap-2 sm:w-auto sm:flex-nowrap sm:shrink-0">
          <div className="min-w-0 w-[calc(50%-4px)] sm:w-[110px]">
            <Form.Item name="governanceStatus" noStyle>
              <Select
                allowClear
                placeholder="状态"
                style={{ width: "100%" }}
                options={GOVERNANCE_STATUS_FILTER_OPTIONS}
              />
            </Form.Item>
          </div>
          <div className="min-w-0 w-[calc(50%-4px)] sm:w-[110px]">
            <Form.Item name="memoryKind" noStyle>
              <Select
                allowClear
                placeholder="类型"
                style={{ width: "100%" }}
                options={MEMORY_KIND_FILTER_OPTIONS}
              />
            </Form.Item>
          </div>
          <div className="min-w-0 w-[calc(50%-4px)] sm:w-[130px]">
            <Form.Item name="category" noStyle>
              <Select
                allowClear
                placeholder="类别"
                style={{ width: "100%" }}
                options={MEMORY_CATEGORY_FILTER_OPTIONS}
              />
            </Form.Item>
          </div>
        </div>
        <div className="w-full min-w-0 sm:w-[220px] sm:shrink-0">
          <Form.Item name="createdRange" noStyle getValueFromEvent={normalizeCreatedRange}>
            <DatePicker.RangePicker
              allowClear
              inputReadOnly
              style={{ width: "100%" }}
              placeholder={["开始日期", "结束日期"]}
            />
          </Form.Item>
        </div>
        <Button
          type="primary"
          htmlType="submit"
          className="w-full sm:w-auto sm:shrink-0"
          icon={<SearchOutlined />}
        >
          搜索
        </Button>
      </div>
    </Form>
  );
}
