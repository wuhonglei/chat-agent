import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { CSSProperties, useEffect, useMemo } from "react";
import { type MenuProps } from "antd";
import {
  clearCurrentConversion,
  setConversationInfoById,
} from "@/store/slices/conversationSlice";
import { useLocation } from "react-router-dom";
import LabelItem from "./LabelItem";
import { useSize } from "ahooks";

export function useMenuItems(onDelete: (id: string) => void) {
  const { conversations } = useAppSelector(state => state.conversation);

  return useMemo(() => {
    const items: MenuProps["items"] = conversations.map(conversation => ({
      key: `/chat/${conversation.id}`,
      label: <LabelItem onDelete={onDelete} conversation={conversation} />,
    }));
    return items;
  }, [conversations, onDelete]);
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
  threshold: number
): CSSProperties {
  const { width } = useSize(document.body) || {};
  const isSmallScreen = width ? width <= threshold : false;
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
