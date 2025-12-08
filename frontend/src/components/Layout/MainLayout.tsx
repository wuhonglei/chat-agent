import CollapseIcon from "@/assets/svg/CollapseIcon.svg?react";
import NewConversionIcon from "@/assets/svg/NewConversionIcon.svg?react";
import { TitleCreatedBy } from "@/constants";
import { useWebTitle } from "@/hooks";
import { EditConversationInfo } from "@/interfaces";
import { useAppDispatch } from "@/store/hooks";
import {
  deleteConversation,
  updateConversationInfo,
} from "@/store/slices/conversationSlice";
import { Conversations, XProvider } from "@ant-design/x";
import { useClickAway, useMemoizedFn, useSize } from "ahooks";
import { App, Button, Layout, theme } from "antd";
import classNames from "classnames";
import { isEmpty } from "lodash-es";
import React, { ReactNode, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import SimpleBar from "simplebar-react";
import SiteLogo from "../common/SiteLogo";
import SiteTitle from "../common/SiteTitle";
import styles from "./css/mainLayout.module.css";
import {
  useConversionInfo,
  useConversionsProps,
  useHideSidebar,
  useSidebarStyles,
} from "./hooks";
import RenameModal from "./modals/RenameModal";
import UserAccount from "./UserAccount";
const { useToken } = theme;

const { Sider, Content } = Layout;
const collapsedWidth = 0;
const DEFAULT_THRESHOLD = 768;

interface MainLayoutProps {
  children: ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const { message, modal } = App.useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = useToken();
  const [editConversionInfo, setEditConversionInfo] =
    useState<EditConversationInfo | null>(null);
  const [collapsed, setCollapsed] = useState(
    () => window.innerWidth <= DEFAULT_THRESHOLD
  );
  const conversationInfo = useConversionInfo();
  useWebTitle(conversationInfo); // 更新 document.title
  const dispatch = useAppDispatch();
  const { width } = useSize(document.body) || {};
  const isSmallScreen = width ? width <= DEFAULT_THRESHOLD : false;
  const sidebarStyles = useSidebarStyles(collapsed, isSmallScreen);
  const hideSidebar = useHideSidebar();
  const siderBarRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const onDeleteConversation = useMemoizedFn(async (id: string) => {
    modal.confirm({
      centered: true,
      title: "确定要删除吗？",
      content: "删除后，该对话将不可恢复。确认删除吗？",
      okButtonProps: {
        color: "danger",
        variant: "solid",
      },
      onOk: async () => {
        await dispatch(deleteConversation(id)).unwrap();
        message.success("删除成功");
        // 如果删除的是当前会话，删除后跳转到新的聊天页面
        if (location.pathname.includes(id)) {
          navigate("/chat");
        }
      },
    });
  });

  const { items, menu, groupable } = useConversionsProps(
    onDeleteConversation,
    setEditConversionInfo
  );

  /**
   * 小屏模式下，点击内容区域时，折叠菜单
   */
  useClickAway(event => {
    const isContentClick = contentRef.current?.contains(event.target as Node);
    if (isSmallScreen && isContentClick && !collapsed) {
      setCollapsed(true);
    }
  }, siderBarRef);

  const handleMenuClick = (pathname: string) => {
    // 点击的菜单和当前路径相同，则不进行跳转
    if (location.pathname === pathname) {
      return;
    }
    // 小屏模式下，点击菜单时，折叠菜单
    if (isSmallScreen) {
      setTimeout(() => {
        setCollapsed(true);
      }, 300);
    }
    navigate(pathname);
  };

  const handleCollapse = () => {
    setCollapsed(!collapsed);
  };

  const handleNewConversion = () => {
    navigate("/chat");
    if (isSmallScreen) {
      setCollapsed(true);
    }
  };

  const handleEditConversationTitle = useMemoizedFn(
    async (info: EditConversationInfo) => {
      await dispatch(
        updateConversationInfo({
          ...info,
          createdBy: TitleCreatedBy.User,
        })
      ).unwrap();
      message.success("重命名成功");
      setEditConversionInfo(null);
    }
  );

  return (
    <XProvider>
      <Layout className="h-screen">
        {/* 左侧导航 */}
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
          <div className="mx-3 my-4 flex justify-between items-center">
            <Link to="/chat" className="flex items-center gap-2 h-9">
              <SiteLogo size={36} />
              <SiteTitle level={5} />
            </Link>
            <Button
              type="text"
              onClick={handleCollapse}
              icon={<CollapseIcon className="w-4 h-4" />}
              style={{ color: token.colorTextDescription }}
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
          <SimpleBar className="flex-1 h-0">
            <Conversations
              items={items}
              menu={menu}
              groupable={groupable}
              activeKey={location.pathname}
              onActiveChange={handleMenuClick}
            />
          </SimpleBar>
          <UserAccount />
          {!isEmpty(editConversionInfo) && (
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
          {/* fixed 定位，不影响布局 */}
          {collapsed && (
            <div className="fixed left-2 md:left-12.5 top-2.5 h-10 flex items-center gap-1 rounded-full border border-gray-200 p-1 shadow bg-white">
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
        </Sider>
        <Content className="h-full bg-white" ref={contentRef}>
          {children}
        </Content>
      </Layout>
    </XProvider>
  );
};

export default React.memo(MainLayout);
