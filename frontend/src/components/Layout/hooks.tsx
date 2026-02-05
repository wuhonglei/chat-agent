import { TitleCreatedBy } from "@/constants";
import { useIsSmallScreen } from "@/hooks";
import { EditConversationInfo } from "@/interfaces";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  clearCurrentConversion,
  deleteConversation,
  loadConversations,
  setConversationInfoById,
  updateConversationInfo,
} from "@/store/slices/conversationSlice";
import { CommentOutlined, DeleteOutlined, EditOutlined } from "@ant-design/icons";
import { ConversationItemType, ConversationsProps } from "@ant-design/x";
import { useClickAway, useInfiniteScroll, useMemoizedFn } from "ahooks";
import type { MenuProps } from "antd";
import { App } from "antd";
import dayjs from "dayjs";
import { CSSProperties, RefObject, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { dateGroups } from "./constant";

const getConversationGroup = (lastMessageCreatedAt: string) => {
  const lastMessageDayjs = dayjs(lastMessageCreatedAt);
  return dateGroups.find(group => lastMessageDayjs.isSameOrAfter(group.value))?.label ?? "更早";
};

export function useConversionsProps(onDelete: (id: string) => void, onRename: (info: EditConversationInfo) => void) {
  const { conversations } = useAppSelector(state => state.conversation);

  const menu: ConversationsProps["menu"] = useMemoizedFn((conversation: ConversationItemType) => ({
    items: [
      {
        label: "重命名",
        key: "rename",
        icon: <EditOutlined />,
      },
      {
        label: "删除",
        key: "delete",
        danger: true,
        icon: <DeleteOutlined />,
      },
    ],
    onClick: (menuInfo: Parameters<NonNullable<MenuProps["onClick"]>>[0]) => {
      menuInfo.domEvent.stopPropagation();
      if (menuInfo.key === "rename") {
        onRename({
          id: conversation.id as string,
          title: conversation.label as string,
        });
      } else if (menuInfo.key === "delete") {
        onDelete(conversation.id!);
      }
    },
  }));

  const items = useMemo(() => {
    const items: ConversationItemType[] = conversations.map(conversation => ({
      id: conversation.id,
      key: `/chat/${conversation.id}`,
      label: conversation.title,
      // 今天、昨天、7 天内、30 天内、更早
      group: getConversationGroup(conversation.lastMessageCreatedAt),
    }));
    return items;
  }, [conversations]);

  const groupable: ConversationsProps["groupable"] = useMemo(
    () => ({
      label: (group: string) => {
        return (
          <div className="mt-4 mb-1 flex gap-2 text-black-tertiary text-xs">
            <CommentOutlined />
            <span>{group}</span>
          </div>
        );
      },
    }),
    []
  );

  return {
    items,
    menu,
    groupable,
  };
}

/**
 * 路由变化时，更新当前对话信息
 */
export function useConversionInfo() {
  const dispatch = useAppDispatch();
  const location = useLocation();
  const conversationsLoaded = useAppSelector(state => state.conversation.conversationsLoaded);
  const conversationInfo = useAppSelector(state => state.conversation.conversationInfo);

  // 监听路由
  useEffect(() => {
    // 初始时，如果对话列表未加载完成，则不更新当前对话信息
    if (!conversationsLoaded) return;

    const id = location.pathname.split("/").pop();
    // 如果路由是 /chat/ 开头，并且有 id，则更新当前对话信息
    if (location.pathname.startsWith("/chat/") && id) {
      dispatch(setConversationInfoById(id));
    } else {
      // 如果路由不是 /chat/ 开头，或者没有 id，则清除当前对话信息
      dispatch(clearCurrentConversion());
    }
  }, [conversationsLoaded, location.pathname, dispatch]);

  return conversationInfo;
}

/**
 * 小屏模式下，使用 fixed 布局, 这样展开菜单时，不会挤压右侧内容区域
 * @param collapsed
 */
export function useSidebarStyles(collapsed: boolean, isSmallScreen: boolean): CSSProperties {
  return useMemo(() => {
    if (!isSmallScreen) return {};

    return {
      position: "fixed",
      left: collapsed ? -261 : 0,
      top: 0,
      bottom: 0,
      zIndex: 1000,
      transition: "left 0.3s ease-in-out",
    };
  }, [isSmallScreen, collapsed]);
}

export function useHideSidebar() {
  const location = useLocation();
  return useMemo(() => /^\/(login|register)/.test(location.pathname), [location.pathname]);
}

const CONVERSATION_PAGE_LIMIT = 20;

/** 对话列表无限滚动：使用 offset/limit 分页，初始 offset=0，limit=20 */
export function useConversationInfiniteScroll(containerRef: RefObject<HTMLDivElement | null>) {
  const dispatch = useAppDispatch();

  const { loadingMore, noMore, data } = useInfiniteScroll(
    async (lastData?) => {
      const offset = lastData ? lastData.offset + lastData.limit : 0;
      const res = await dispatch(loadConversations({ offset, limit: CONVERSATION_PAGE_LIMIT })).unwrap();
      return {
        list: res.conversations,
        total: res.total,
        offset: res.offset,
        limit: res.limit,
      };
    },
    {
      target: () => containerRef.current ?? undefined,
      isNoMore: data => !data || data.list.length >= data.total,
      threshold: 50,
      reloadDeps: [],
    }
  );

  return { loadingMore, noMore: !loadingMore && noMore && data?.total > 0 };
}

/** 侧边栏内容：对话列表、重命名等状态与操作，供 SidebarContent 内部使用 */
export function useSidebarContent() {
  const { message, modal } = App.useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useAppDispatch();

  const [editConversionInfo, setEditConversionInfo] = useState<EditConversationInfo | null>(null);

  const onDeleteConversation = useMemoizedFn(async (id: string) => {
    modal.confirm({
      centered: true,
      title: "确定要删除吗？",
      content: "删除后，该对话将不可恢复。确认删除吗？",
      okButtonProps: { color: "danger", variant: "solid" },
      onOk: async () => {
        await dispatch(deleteConversation(id)).unwrap();
        message.success("删除成功");
        if (location.pathname.includes(id)) navigate("/chat");
      },
    });
  });

  const { items, menu, groupable } = useConversionsProps(onDeleteConversation, setEditConversionInfo);

  const handleMenuClick = useMemoizedFn((pathname: string) => {
    if (location.pathname === pathname) return;
    navigate(pathname);
  });

  const handleEditConversationTitle = useMemoizedFn(async (info: EditConversationInfo) => {
    await dispatch(updateConversationInfo({ ...info, createdBy: TitleCreatedBy.User })).unwrap();
    message.success("重命名成功");
    setEditConversionInfo(null);
  });

  return {
    items,
    menu,
    groupable,
    activeKey: location.pathname,
    editConversionInfo,
    setEditConversionInfo,
    handleMenuClick,
    handleEditConversationTitle,
  };
}

/** 侧边栏布局：折叠、ref、样式等，供 MainLayout 使用 */
export function useMainLayoutSidebar() {
  const navigate = useNavigate();
  const isSmallScreen = useIsSmallScreen();

  const [collapsed, setCollapsed] = useState(isSmallScreen);
  const siderBarRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useClickAway(event => {
    const isContentClick = contentRef.current?.contains(event.target as Node);
    if (isSmallScreen && isContentClick && !collapsed) setCollapsed(true);
  }, siderBarRef);

  const handleCollapse = useMemoizedFn(() => setCollapsed(prev => !prev));

  const handleNewConversion = useMemoizedFn(() => {
    navigate("/chat");
    if (isSmallScreen) setCollapsed(true);
  });

  const sidebarStyles = useSidebarStyles(collapsed, isSmallScreen);
  const hideSidebar = useHideSidebar();

  return {
    siderBarRef,
    contentRef,
    collapsed,
    sidebarStyles,
    hideSidebar,
    handleCollapse,
    handleNewConversion,
    isSmallScreen,
    setCollapsed,
  };
}
