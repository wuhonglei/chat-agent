import type { BlockPreviewContextValue } from "@/pages/ChatPage/context/BlockPreviewContext";
import React, { useMemo } from "react";
import HtmlPreviewHeader from "./HtmlPreviewHeader";

type UseHtmlPreviewHeaderParams = {
  blockPreview: BlockPreviewContextValue | null;
  code: string;
  isSmallScreen: boolean;
  language: string;
};

export function useHtmlPreviewHeader({
  blockPreview,
  code,
  isSmallScreen,
  language,
}: UseHtmlPreviewHeaderParams): React.ReactNode | undefined {
  return useMemo(() => {
    if (isSmallScreen || language !== "html" || blockPreview == null) {
      return;
    }
    const { openPreview } = blockPreview;
    return <HtmlPreviewHeader code={code} language={language} openPreview={openPreview} />;
  }, [blockPreview, code, isSmallScreen, language]);
}
