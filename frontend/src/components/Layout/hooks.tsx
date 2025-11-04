import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { useEffect, useMemo } from "react";
import { MenuProps } from "antd";
import {
  clearCurrentConversion,
  setConversationInfoById,
} from "@/store/slices/conversationSlice";
import { useLocation } from "react-router-dom";

export function useMenuItems() {
  const { conversations } = useAppSelector(state => state.conversation);
  return useMemo(() => {
    const items: MenuProps["items"] = conversations.map(conversation => ({
      key: `/chat/${conversation.id}`,
      label: conversation.title,
    }));
    return items;
  }, [conversations]);
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
