import { useWebTitle } from "@/hooks";
import { XProvider } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import { Layout } from "antd";
import classNames from "classnames";
import React, { ReactNode } from "react";
import SidebarContent from "./components/SidebarContent";
import SidebarHeader from "./components/SidebarHeader";
import styles from "./css/mainLayout.module.css";
import { useConversionInfo, useMainLayoutSidebar } from "./hooks";

const { Sider, Content } = Layout;
const collapsedWidth = 0;

interface MainLayoutProps {
  children: ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const conversationInfo = useConversionInfo();
  useWebTitle(conversationInfo);

  const {
    siderBarRef,
    contentRef,
    collapsed,
    sidebarStyles,
    hideSidebar,
    handleCollapse,
    handleNewConversion,
    isSmallScreen,
    setCollapsed,
  } = useMainLayoutSidebar();

  const handleAfterActiveChange = useMemoizedFn(() => {
    if (isSmallScreen) {
      setTimeout(() => setCollapsed(true), 300);
    }
  });

  return (
    <XProvider>
      <Layout className="h-screen">
        <Sider
          theme="light"
          collapsible
          width={261}
          trigger={null}
          ref={siderBarRef}
          collapsed={collapsed}
          onCollapse={handleCollapse}
          collapsedWidth={collapsedWidth}
          className={classNames(
            "flex flex-col border-r",
            styles["aside-container"],
            hideSidebar && "hidden",
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
          <SidebarHeader collapsed={collapsed} onCollapse={handleCollapse} onNewConversation={handleNewConversion} />
          <SidebarContent onAfterActiveChange={handleAfterActiveChange} />
        </Sider>
        <Content className="h-full bg-white" ref={contentRef}>
          {children}
        </Content>
      </Layout>
    </XProvider>
  );
};

export default React.memo(MainLayout);
