import { UserMemoryItem } from "@/interfaces";
import { profileAPI } from "@/services";
import { DeleteOutlined } from "@ant-design/icons";
import { useRequest } from "ahooks";
import { App, Button, Spin, Table } from "antd";
import dayjs from "dayjs";
import { useEffect } from "react";

const DATE_FORMAT = "YYYY-MM-DD HH:mm";

function useMemoryList() {
  const { data, loading, run } = useRequest(profileAPI.getMemories, {
    manual: true,
  });
  useEffect(() => {
    run();
  }, [run]);
  return { data, loading, refresh: run };
}

function ProfileTable({
  title,
  dataSource,
  onDelete,
}: {
  title: string;
  dataSource: UserMemoryItem[];
  onDelete: (item: UserMemoryItem) => void;
}) {
  const { modal } = App.useApp();

  const handleDelete = (item: UserMemoryItem) => {
    modal.confirm({
      title: "确认删除",
      content: `确定要删除「${item.memory}」吗？`,
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: () => onDelete(item),
    });
  };

  const columns = [
    {
      title,
      dataIndex: "memory" as const,
      key: "memory",
      ellipsis: true,
    },
    {
      title: "创建时间",
      dataIndex: "createdAt" as const,
      key: "createdAt",
      width: 140,
      render: (v: string) => <span className="text-black-secondary text-sm">{dayjs(v).format(DATE_FORMAT)}</span>,
    },
    {
      title: "操作",
      key: "action",
      width: 60,
      render: (_: unknown, record: UserMemoryItem) => (
        <Button type="link" danger size="small" onClick={() => handleDelete(record)} icon={<DeleteOutlined />}></Button>
      ),
    },
  ];

  return (
    <div style={{ marginBottom: 24 }}>
      <Table
        size="small"
        rowKey="id"
        dataSource={dataSource}
        columns={columns}
        pagination={false}
        locale={{ emptyText: "暂无数据" }}
        scroll={{ x: "max-content" }}
      />
    </div>
  );
}

export default function DataManage() {
  const { message } = App.useApp();
  const { data, loading, refresh } = useMemoryList();

  const handleDelete = async (item: UserMemoryItem) => {
    try {
      await profileAPI.deleteMemory(item.id);
      message.success("已删除");
      refresh();
    } catch {
      message.error("删除失败");
    }
  };

  return (
    <Spin spinning={loading && !data}>
      <ProfileTable title="用户记忆" dataSource={data?.memories ?? []} onDelete={handleDelete} />
    </Spin>
  );
}
