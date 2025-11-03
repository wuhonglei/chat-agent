import { Button, Layout, Menu, MenuProps, Typography } from "antd";
import { Link, useLocation, useNavigate } from "react-router-dom";
import React, { ReactNode, useEffect, useState } from "react";
import classNames from "classnames";
import CollapseIcon from "@/assets/svg/CollapseIcon.svg?react";
import NewConversionIcon from "@/assets/svg/NewConversionIcon.svg?react";
import styles from "./mainLayout.module.css";
import { theme } from "antd";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { clearCurrentChat } from "@/store/slices/chatSlice";
import { loadConversations } from "@/store/slices/conversationSlice";
const { useToken } = theme;
const { Title } = Typography;

const { Sider, Header, Content } = Layout;
const collapsedWidth = 0;

interface MainLayoutProps {
  children: ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const location = useLocation();
  const { token } = useToken();
  const [collapsed, setCollapsed] = useState(false);
  const { conversations } = useAppSelector(state => state.conversation);
  console.log(conversations);

  useEffect(() => {
    dispatch(loadConversations());
  }, [dispatch]);

  const menuItems: MenuProps["items"] = [
    // {
    //   key: "/markdown",
    //   icon: <FileMarkdownOutlined />,
    //   label: "Markdown",
    // },
  ];

  const handleMenuClick: MenuProps["onClick"] = ({ key }) => {
    navigate(key);
  };

  const handleCollapse = () => {
    setCollapsed(!collapsed);
  };

  const handleNewConversion = () => {
    dispatch(clearCurrentChat());
    navigate("/chat");
  };

  return (
    <Layout className="h-screen">
      {/* 左侧导航 */}
      <Sider
        theme="light"
        collapsible
        width={261}
        trigger={null}
        collapsed={collapsed}
        onCollapse={handleCollapse}
        collapsedWidth={collapsedWidth}
        className={classNames("flex flex-col border-r-1", !collapsed && "px-3")}
        style={{
          borderColor: "#E2E2E2",
          backgroundColor: "#F9FAFB",
        }}
      >
        <div className="my-4 flex justify-between items-center">
          <Link to="/" className="flex items-center gap-2 h-9">
            <img alt="logo" width={32} height={32} src="/logo.png" />
            <Title level={5} style={{ marginBottom: 0 }}>
              Ai Assistant
            </Title>
          </Link>
          <Button
            type="text"
            onClick={handleCollapse}
            style={{ color: token.colorTextDescription }}
            icon={<CollapseIcon className="w-4 h-4" />}
          />
        </div>
        <Button
          size="large"
          shape="round"
          className="w-full"
          onClick={handleNewConversion}
          icon={<NewConversionIcon />}
        >
          开启新对话
        </Button>
        <Menu
          mode="vertical"
          items={menuItems}
          onClick={handleMenuClick}
          selectedKeys={[location.pathname]}
          className={classNames(styles["menu-item"])}
          style={{
            backgroundColor: "transparent",
            width: "100%",
            border: "none",
          }}
        />
      </Sider>
      <Layout className="flex flex-col h-full" hasSider={false}>
        <Header
          className="h-14 flex justify-between items-center"
          style={{ backgroundColor: token.colorBgContainer }}
        >
          {collapsed && (
            <div className="h-10 flex items-center gap-1 rounded-full border border-gray-200 p-1 shadow">
              <Button
                type="text"
                shape="circle"
                onClick={handleCollapse}
                icon={<CollapseIcon className="w-4 h-4" />}
              />
              <Button
                type="text"
                shape="circle"
                onClick={handleNewConversion}
                icon={<NewConversionIcon className="w-4 h-4" />}
              />
            </div>
          )}
        </Header>
        <Content className="flex-1 bg-white">{children}</Content>
      </Layout>
    </Layout>
  );
};

export default React.memo(MainLayout);
