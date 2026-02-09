import { UserMemoryItem } from "@/interfaces";
import { profileAPI } from "@/services";
import { DeleteOutlined } from "@ant-design/icons";
import { useRequest } from "ahooks";
import { App, Button, Table } from "antd";
import dayjs from "dayjs";
import { useEffect } from "react";

function useMemoryList() {
  const { data, loading, run } = useRequest(profileAPI.getMemories, {
    manual: true,
  });
  useEffect(() => {
    run();
  }, [run]);
  return { data, loading, refresh: run };
}

export default function DataManage({ height }: { height: number }) {
  const { message } = App.useApp();
  const { modal } = App.useApp();
  const { data, loading, refresh } = useMemoryList();

  const _handleDelete = async (item: UserMemoryItem) => {
    try {
      await profileAPI.deleteMemory(item.id);
      message.success("已删除");
      refresh();
    } catch {
      message.error("删除失败");
    }
  };

  const handleDelete = (item: UserMemoryItem) => {
    modal.confirm({
      title: "确认删除",
      content: `确定要删除「${item.memory}」吗？`,
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: () => _handleDelete(item),
    });
  };

  const columns = [
    {
      title: "记忆",
      dataIndex: "memory" as const,
      key: "memory",
    },
    {
      width: 100,
      title: "创建时间",
      key: "createdAt",
      dataIndex: "createdAt" as const,
      render: (v: string) => <span className="text-black-secondary text-sm">{dayjs(v).fromNow()}</span>,
    },
    {
      title: "操作",
      key: "action",
      width: 50,
      render: (_: unknown, record: UserMemoryItem) => (
        <Button type="link" danger size="small" onClick={() => handleDelete(record)} icon={<DeleteOutlined />}></Button>
      ),
    },
  ];

  return (
    <Table
      size="small"
      rowKey="id"
      loading={loading}
      columns={columns}
      pagination={false}
      dataSource={data?.memories ?? []}
      locale={{ emptyText: "暂无数据" }}
      scroll={{ x: "min-content", y: height - 39 }} // 39 是表格头部高度
    />
  );
}
