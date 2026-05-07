import AccountManage from "@/components/Layout/components/AccountManage";
import DataManage from "@/components/Layout/components/DataManage";
import { useIsSmallScreen } from "@/hooks";
import { DatabaseOutlined, UserOutlined } from "@ant-design/icons";
import { Modal, Tabs } from "antd";

type Props = {
  open: boolean;
  onCancel: () => void;
};

export default function SettingModal({ open, onCancel }: Props) {
  const isSmallScreen = useIsSmallScreen();
  const tabPlacement = isSmallScreen ? "top" : "start";
  const tabHeight = 320;
  const contentHeight = isSmallScreen ? tabHeight - 54 : tabHeight;
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
      children: <DataManage height={contentHeight} />,
    },
  ];

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
        size="small"
        tabBarGutter={16}
        items={TAB_ITEMS}
        styles={{
          root: {
            height: tabHeight,
          },
          content: {
            height: contentHeight,
          },
        }}
        tabPlacement={tabPlacement}
      />
    </Modal>
  );
}
