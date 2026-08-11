import { useWebTitle } from "@/hooks";
import { XProvider } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import { Layout } from "antd";
import classNames from "classnames";
import React, { ReactNode, useEffect, useState } from "react";
import SidebarContent from "./components/SidebarContent";
import SidebarHeader from "./components/SidebarHeader";
import styles from "./css/mainLayout.module.css";
import { useConversionInfo, useMainLayoutSidebar } from "./hooks";
import SearchModal from "./modals/SearchModal";

const { Sider, Content } = Layout;
const collapsedWidth = 0;

interface MainLayoutProps {
  children: ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const conversationInfo = useConversionInfo();
  useWebTitle(conversationInfo);
  const [searchOpen, setSearchOpen] = useState(false);

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

  const handleOpenSearch = useMemoizedFn(() => {
    setSearchOpen(true);
  });

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

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
            !collapsed && "px-3",
          )}
          style={{
            padding: 0,
            borderColor: "#E2E2E2",
            backgroundColor: "#F9FAFB",
            ...sidebarStyles,
          }}
          breakpoint="md"
        >
          {!hideSidebar ? (
            <>
              <SidebarHeader
                collapsed={collapsed}
                onCollapse={handleCollapse}
                onNewConversation={handleNewConversion}
                onOpenSearch={handleOpenSearch}
              />
              <SidebarContent onAfterActiveChange={handleAfterActiveChange} />
            </>
          ) : null}
        </Sider>
        <Content className="h-full bg-white" ref={contentRef}>
          {children}
        </Content>
      </Layout>
      {searchOpen ? <SearchModal open={searchOpen} onClose={() => setSearchOpen(false)} /> : null}
    </XProvider>
  );
};

export default React.memo(MainLayout);
