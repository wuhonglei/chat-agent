import AccountManage from "@/components/Layout/components/AccountManage";
import DataManage from "@/components/Layout/components/DataManage";
import { useIsSmallScreen } from "@/hooks";
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
  const isSmallScreen = useIsSmallScreen();
  console.info("isSmallScreen", isSmallScreen);
  const tabPlacement = isSmallScreen ? "top" : "start";
  const styles = isSmallScreen
    ? {
        header: { paddingLeft: 24 },
        container: { paddingLeft: 0 },
        body: {
          paddingTop: 0,
          paddingRight: 0,
          paddingLeft: 24,
        },
      }
    : {
        header: { paddingLeft: 24 },
        container: { paddingLeft: 0 },
        body: {
          paddingTop: 16,
          paddingRight: 0,
        },
      };

  return (
    <Modal
      centered
      open={open}
      title="系统设置"
      footer={null}
      styles={styles}
      onCancel={onCancel}
      width="min(640px, calc(100vw - 32px))"
    >
      <Tabs
        tabPlacement={tabPlacement}
        size="small"
        tabBarGutter={16}
        items={TAB_ITEMS}
        style={{ height: 320 }}
        styles={{
          content: {
            height: 320,
            overflow: "auto",
          },
        }}
      />
    </Modal>
  );
}
