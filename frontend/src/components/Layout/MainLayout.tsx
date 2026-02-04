import CollapseIcon from "@/assets/svg/CollapseIcon.svg?react";
import NewConversionIcon from "@/assets/svg/NewConversionIcon.svg?react";
import { useWebTitle } from "@/hooks";
import { Conversations, XProvider } from "@ant-design/x";
import { Button, Layout, Spin } from "antd";
import classNames from "classnames";
import React, { ReactNode, useRef } from "react";
import { useLocation } from "react-router-dom";
import SimpleBar from "simplebar-react";
import SidebarHeader from "./components/SidebarHeader";
import UserAccount from "./components/UserAccount";
import styles from "./css/mainLayout.module.css";
import { useConversationInfiniteScroll, useConversionInfo, useMainLayoutSidebar } from "./hooks";
import RenameModal from "./modals/RenameModal";

const { Sider, Content } = Layout;
const collapsedWidth = 0;

interface MainLayoutProps {
  children: ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const location = useLocation();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const { loadingMore } = useConversationInfiniteScroll(scrollContainerRef);
  const conversationInfo = useConversionInfo();
  useWebTitle(conversationInfo);

  const {
    siderBarRef,
    contentRef,
    collapsed,
    editConversionInfo,
    setEditConversionInfo,
    items,
    menu,
    groupable,
    sidebarStyles,
    hideSidebar,
    handleCollapse,
    handleNewConversion,
    handleMenuClick,
    handleEditConversationTitle,
  } = useMainLayoutSidebar();

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
          <SidebarHeader onCollapse={handleCollapse} onNewConversation={handleNewConversion} />
          <div ref={scrollContainerRef} className="flex-1 min-h-0 flex flex-col">
            <SimpleBar className="flex-1 h-0">
              <Conversations
                items={items}
                menu={menu}
                groupable={groupable}
                activeKey={location.pathname}
                onActiveChange={handleMenuClick}
              />
              {loadingMore && (
                <div className="flex justify-center py-3">
                  <Spin size="small" />
                </div>
              )}
            </SimpleBar>
          </div>
          <UserAccount />
          {editConversionInfo && (
            <RenameModal
              open
              title={editConversionInfo.title}
              onCancel={() => setEditConversionInfo(null)}
              onOk={title =>
                handleEditConversationTitle({
                  id: editConversionInfo.id,
                  title,
                })
              }
            />
          )}
          {collapsed && (
            <div className="fixed left-2 md:left-12.5 top-2.5 h-10 flex items-center gap-1 rounded-full border border-gray-200 p-1 shadow bg-white">
              <Button type="text" shape="circle" onClick={handleCollapse} icon={<CollapseIcon className="w-4 h-4" />} />
              <Button
                type="text"
                shape="circle"
                onClick={handleNewConversion}
                icon={<NewConversionIcon className="w-4 h-4" />}
              />
            </div>
          )}
        </Sider>
        <Content className="h-full bg-white" ref={contentRef}>
          {children}
        </Content>
      </Layout>
    </XProvider>
  );
};

export default React.memo(MainLayout);
