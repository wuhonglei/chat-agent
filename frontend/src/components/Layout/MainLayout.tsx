import { Button, Layout, Typography } from "antd";
import { Link, useLocation, useNavigate } from "react-router-dom";
import React, { ReactNode, useState } from "react";
import classNames from "classnames";
import CollapseIcon from "@/assets/svg/CollapseIcon.svg?react";
import NewConversionIcon from "@/assets/svg/NewConversionIcon.svg?react";
import styles from "./css/mainLayout.module.css";
import { theme } from "antd";
import { useAppDispatch } from "@/store/hooks";
import { useConversionInfo, useMenuItems, useSidebarStyles } from "./hooks";
import {
  deleteConversation,
  updateConversationInfo,
} from "@/store/slices/conversationSlice";
import HoverButton from "./HoverButton";
import { useMemoizedFn } from "ahooks";
import { TitleCreatedBy, WebTitle } from "@/constants";
import { useWebTitle } from "@/hooks";
import SimpleBar from "simplebar-react";
import { Conversations, XProvider } from "@ant-design/x";
const { useToken } = theme;
const { Title } = Typography;

const { Sider, Header, Content } = Layout;
const collapsedWidth = 0;
const DEFAULT_THRESHOLD = 768;

interface MainLayoutProps {
  children: ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = useToken();
  const [collapsed, setCollapsed] = useState(
    () => window.innerWidth <= DEFAULT_THRESHOLD
  );
  const conversationInfo = useConversionInfo();
  const dispatch = useAppDispatch();
  const onDeleteConversation = useMemoizedFn(async (id: string) => {
    await dispatch(deleteConversation(id)).unwrap();
    // 如果删除的是当前会话，删除后跳转到新的聊天页面
    if (location.pathname.includes(id)) {
      navigate("/chat");
    }
  });
  const sidebarStyles = useSidebarStyles(collapsed, DEFAULT_THRESHOLD);
  const menuItems = useMenuItems(onDeleteConversation);
  useWebTitle(conversationInfo);
  const handleMenuClick = (pathname: string) => {
    // 点击的菜单和当前路径相同，则不进行跳转
    if (location.pathname === pathname) {
      return;
    }
    navigate(pathname);
  };

  const handleCollapse = () => {
    setCollapsed(!collapsed);
  };

  const handleNewConversion = () => {
    navigate("/chat");
  };

  const handleEditConversationTitle = (id: string, title: string) => {
    dispatch(
      updateConversationInfo({ id, title, createdBy: TitleCreatedBy.User })
    );
  };

  return (
    <XProvider>
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
          className={classNames(
            "flex flex-col border-r-1",
            styles["aside-container"],
            !collapsed && "px-3"
          )}
          style={{
            padding: 0,
            borderColor: "#E2E2E2",
            backgroundColor: "#F9FAFB",
            ...sidebarStyles,
          }}
          breakpoint="md"
        >
          <div className="mx-3 my-4 flex justify-between items-center">
            <Link to="/chat" className="flex items-center gap-2 h-9">
              <img alt="logo" width={32} height={32} src="/logo.png" />
              <Title level={5} style={{ marginBottom: 0 }}>
                {WebTitle}
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
            className="mx-3"
            onClick={handleNewConversion}
            icon={<NewConversionIcon />}
          >
            开启新对话
          </Button>
          <SimpleBar className="flex-1 h-0 mt-4">
            <Conversations
              onActiveChange={handleMenuClick}
              items={menuItems}
              activeKey={location.pathname}
            />
          </SimpleBar>
        </Sider>
        <Layout className="flex flex-col h-full" hasSider={false}>
          <Header
            className="flex justify-center items-center relative"
            style={{ backgroundColor: token.colorBgContainer, height: 60 }}
          >
            {collapsed && (
              <div className="absolute left-2 md:left-12.5 h-10 flex items-center gap-1 rounded-full border border-gray-200 p-1 shadow">
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
            {conversationInfo && (
              <HoverButton
                title={conversationInfo.title}
                onConfirm={newTitle =>
                  handleEditConversationTitle(conversationInfo.id, newTitle)
                }
              />
            )}
          </Header>
          <Content className="flex-1 bg-white">{children}</Content>
        </Layout>
      </Layout>
    </XProvider>
  );
};

export default React.memo(MainLayout);
