import { useMemo } from "react";
import { useTitle } from "ahooks";
import { ConversationInfo } from "@/interfaces";
import { isEmpty } from "lodash-es";
import { WebTitle } from "@/constants";
import { isTitleCreatedByDefault } from "@/utils";

export function useWebTitle(
  conversationInfo: ConversationInfo | undefined | null
): void {
  const title = useMemo(() => {
    if (isEmpty(conversationInfo)) {
      return WebTitle;
    } else if (isTitleCreatedByDefault(conversationInfo.createdBy)) {
      return WebTitle;
    } else {
      return conversationInfo.title;
    }
  }, [conversationInfo]);

  useTitle(title);
}
