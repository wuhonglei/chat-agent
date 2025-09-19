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
      key: "/documents",
      icon: <FileTextOutlined />,
      label: "文档管理",
    },
    {
      key: "/knowledge-base",
      icon: <DatabaseOutlined />,
      label: "知识库",
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
        style={{ backgroundColor: "#F3F4F6" }}
        className="shadow-md flex flex-col items-center"
      >
        <img
          src="/logo.png"
          alt="logo"
          width={36}
          height={36}
          className="rounded-full mx-auto my-4"
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
      <Layout>{children}</Layout>
    </Layout>
  );
};

export default MainLayout;
