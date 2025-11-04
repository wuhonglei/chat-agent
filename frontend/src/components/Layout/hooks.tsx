import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { useEffect, useMemo } from "react";
import { Button, type MenuProps } from "antd";
import {
  clearCurrentConversion,
  setConversationInfoById,
  deleteConversation,
} from "@/store/slices/conversationSlice";
import { useLocation } from "react-router-dom";
import { DeleteOutlined } from "@ant-design/icons";

export function useMenuItems() {
  const { conversations } = useAppSelector(state => state.conversation);
  const dispatch = useAppDispatch();

  return useMemo(() => {
    const items: MenuProps["items"] = conversations.map(conversation => ({
      key: `/chat/${conversation.id}`,
      label: (
        <div className="h-10 w-full overflow-hidden flex items-center justify-between gap-2">
          <span
            title={conversation.title}
            className="flex-1 overflow-hidden text-ellipsis"
          >
            {conversation.title}
          </span>
          <Button
            type="text"
            shape="circle"
            icon={<DeleteOutlined />}
            onClick={() => dispatch(deleteConversation(conversation.id))}
          />
        </div>
      ),
    }));
    return items;
  }, [conversations, dispatch]);
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
