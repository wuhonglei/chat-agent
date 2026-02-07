import AccountManage from "@/components/Layout/components/AccountManage";
import DataManage from "@/components/Layout/components/DataManage";
import { DatabaseOutlined, UserOutlined } from "@ant-design/icons";
import { Modal, Tabs } from "antd";

type Props = {
  open: boolean;
  onCancel: () => void;
};

const TAB_ITEMS = [
  {
    key: "account",
    label: (
      <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <UserOutlined />
        账号管理
      </span>
    ),
    children: <AccountManage />,
  },
  {
    key: "data",
    label: (
      <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <DatabaseOutlined />
        数据管理
      </span>
    ),
    children: <DataManage />,
  },
];

export default function SettingModal({ open, onCancel }: Props) {
  return (
    <Modal
      centered
      open={open}
      title="系统设置"
      width={640}
      onCancel={onCancel}
      styles={{
        header: { paddingLeft: 24 },
        container: { paddingLeft: 0 },
        body: {
          paddingTop: 16,
          paddingRight: 16,
        },
      }}
    >
      <Tabs tabPlacement="start" size="small" tabBarGutter={8} items={TAB_ITEMS} style={{ minHeight: 320 }} />
    </Modal>
  );
}
