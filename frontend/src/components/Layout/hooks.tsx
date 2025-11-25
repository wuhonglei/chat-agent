import { EditConversationInfo } from "@/interfaces";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  clearCurrentConversion,
  setConversationInfoById,
} from "@/store/slices/conversationSlice";
import {
  CommentOutlined,
  DeleteOutlined,
  EditOutlined,
} from "@ant-design/icons";
import { ConversationItemType, ConversationsProps } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import type { MenuProps } from "antd";
import dayjs from "dayjs";
import { CSSProperties, useEffect, useMemo } from "react";
import { useLocation } from "react-router-dom";
import { dateGroups } from "./constant";

const getConversationGroup = (lastMessageCreatedAt: string) => {
  const lastMessageDayjs = dayjs(lastMessageCreatedAt);
  return (
    dateGroups.find(group => lastMessageDayjs.isSameOrAfter(group.value))
      ?.label ?? "更早"
  );
};

export function useConversionsProps(
  onDelete: (id: string) => void,
  onRename: (info: EditConversationInfo) => void
) {
  const { conversations } = useAppSelector(state => state.conversation);

  const menu: ConversationsProps["menu"] = useMemoizedFn(
    (conversation: ConversationItemType) => ({
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
    })
  );

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
  const conversationsLoaded = useAppSelector(
    state => state.conversation.conversationsLoaded
  );
  const conversationInfo = useAppSelector(
    state => state.conversation.conversationInfo
  );

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
export function useSidebarStyles(
  collapsed: boolean,
  isSmallScreen: boolean
): CSSProperties {
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
  return useMemo(
    () => /^\/(login|register)/.test(location.pathname),
    [location.pathname]
  );
}
