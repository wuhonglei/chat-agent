import { useAppSelector } from "@/store/hooks";
import { useMemo } from "react";
import { MenuProps } from "antd";

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
