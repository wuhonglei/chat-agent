import {
  DatabaseOutlined,
  FileMarkdownOutlined,
  FileTextOutlined,
  MessageOutlined,
} from "@ant-design/icons";
import { Layout, Menu, MenuProps } from "antd";
import classNames from "classnames";
import React, { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import styles from "./mainLayout.module.css";

const { Sider } = Layout;
const collapsedWidth = 64;

interface MainLayoutProps {
  children: ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems: MenuProps["items"] = [
    {
      key: "/",
      icon: <MessageOutlined />,
      label: "智能问答",
    },
    {
      key: "/markdown",
      icon: <FileMarkdownOutlined />,
      label: "Markdown",
    },
  ];

  const handleMenuClick: MenuProps["onClick"] = ({ key }) => {
    navigate(key);
  };

  return (
    <Layout className="h-screen">
      {/* 左侧导航 */}
      <Sider
        collapsed
        theme="light"
        trigger={null}
        collapsedWidth={collapsedWidth}
        className="flex flex-col items-center border-r-1"
        style={{
          borderColor: "#E2E2E2",
        }}
      >
        <img
          src="/logo.png"
          alt="logo"
          width={32}
          height={32}
          className="mx-auto my-4"
        />
        <Menu
          mode="vertical"
          items={menuItems}
          onClick={handleMenuClick}
          selectedKeys={[location.pathname]}
          className={classNames(styles["menu-item"])}
          style={{
            backgroundColor: "transparent",
            width: collapsedWidth,
            border: "none",
          }}
        />
      </Sider>
      <Layout className="h-full bg-white">{children}</Layout>
    </Layout>
  );
};

export default React.memo(MainLayout);
