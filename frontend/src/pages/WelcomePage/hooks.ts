import { ConversationInfo } from "@/interfaces";
import { conversationAPI } from "@/services/conversation";
import { useAppDispatch } from "@/store/hooks";
import { activateConversation } from "@/store/slices/conversationSlice";
import { useMemoizedFn } from "ahooks";
import { useRef, useState } from "react";

export function useDraftConversation() {
  const dispatch = useAppDispatch();
  const [draftConversation, setDraftConversation] = useState<ConversationInfo>();
  const draftConversationPromiseRef = useRef<Promise<ConversationInfo> | null>(null);

  const ensureDraftConversationInfo = useMemoizedFn(async () => {
    if (draftConversation) {
      return draftConversation;
    }
    if (draftConversationPromiseRef.current) {
      return await draftConversationPromiseRef.current;
    }
    draftConversationPromiseRef.current = conversationAPI
      .registerConversation({ isActive: false })
      .then(conversation => {
        setDraftConversation(conversation);
        return conversation;
      })
      .finally(() => {
        draftConversationPromiseRef.current = null;
      });
    return await draftConversationPromiseRef.current;
  });

  const ensureDraftConversationId = useMemoizedFn(async () => {
    return (await ensureDraftConversationInfo()).id;
  });

  const publishDraftConversation = useMemoizedFn(async (conversation: ConversationInfo) => {
    const activeConversation = await dispatch(activateConversation(conversation.id)).unwrap();
    setDraftConversation(activeConversation);
    return activeConversation;
  });

  return {
    draftConversation,
    ensureDraftConversationId,
    ensureDraftConversationInfo,
    publishDraftConversation,
  };
}
