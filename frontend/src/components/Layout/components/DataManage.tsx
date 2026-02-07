import { UserProfileItem } from "@/interfaces";
import { profileAPI } from "@/services";
import { DeleteOutlined } from "@ant-design/icons";
import { useRequest } from "ahooks";
import { App, Button, Spin, Table } from "antd";
import dayjs from "dayjs";
import { useEffect } from "react";

const DATE_FORMAT = "YYYY-MM-DD HH:mm";

function useProfileList() {
  const { data, loading, run } = useRequest(profileAPI.getProfileList, {
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
  loading,
  onDelete,
}: {
  title: string;
  dataSource: UserProfileItem[];
  loading: boolean;
  onDelete: (item: UserProfileItem) => void;
}) {
  const { modal } = App.useApp();

  const handleDelete = (item: UserProfileItem) => {
    modal.confirm({
      title: "确认删除",
      content: `确定要删除「${item.text}」吗？`,
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: () => onDelete(item),
    });
  };

  const columns = [
    {
      title,
      dataIndex: "text" as const,
      key: "text",
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
      render: (_: unknown, record: UserProfileItem) => (
        <Button type="link" danger size="small" onClick={() => handleDelete(record)} icon={<DeleteOutlined />}></Button>
      ),
    },
  ];

  return (
    <div style={{ marginBottom: 24 }}>
      <Table
        size="small"
        rowKey="id"
        loading={loading}
        dataSource={dataSource}
        columns={columns}
        pagination={false}
        locale={{ emptyText: "暂无数据" }}
      />
    </div>
  );
}

export default function DataManage() {
  const { message } = App.useApp();
  const { data, loading, refresh } = useProfileList();

  const handleDelete = async (item: UserProfileItem) => {
    try {
      await profileAPI.deleteProfileItem(item.id);
      message.success("已删除");
      refresh();
    } catch {
      message.error("删除失败");
    }
  };

  const facts = data?.facts ?? [];
  const preferences = data?.preferences ?? [];

  return (
    <Spin spinning={loading && !data}>
      <ProfileTable title="用户事实" dataSource={facts} loading={loading} onDelete={handleDelete} />
      <ProfileTable title="用户偏好" dataSource={preferences} loading={loading} onDelete={handleDelete} />
    </Spin>
  );
}
