import { useMemo } from "react";
import { useTitle } from "ahooks";
import { ConversationInfo } from "@/interfaces";
import { isEmpty } from "lodash-es";
import { WEB_TITLE } from "@/constants";
import { isTitleCreatedByDefault } from "@/utils";

export function useWebTitle(conversationInfo: ConversationInfo | undefined | null): void {
  const title = useMemo(() => {
    if (isEmpty(conversationInfo)) {
      return WEB_TITLE;
    } else if (isTitleCreatedByDefault(conversationInfo.createdBy)) {
      return WEB_TITLE;
    } else {
      return conversationInfo.title;
    }
  }, [conversationInfo]);

  useTitle(title);
}
