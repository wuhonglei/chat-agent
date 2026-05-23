import type { BlockPreviewContextValue } from "@/pages/ChatPage/context/blockPreviewContext";
import type { CodeRuntimeLanguage } from "@/interfaces/contentBlock";
import React, { useMemo } from "react";
import CodeExecHeader from "./CodeExecHeader";
import HtmlPreviewHeader from "./HtmlPreviewHeader";

type UseHtmlPreviewHeaderParams = {
  blockPreview: BlockPreviewContextValue | null;
  code: string;
  isSmallScreen: boolean;
  language: string;
};

const CODE_RUNTIME_LANGUAGES = new Set(["python", "javascript", "typescript"]);

function isCodeRuntimeLanguage(language: string): language is CodeRuntimeLanguage {
  return CODE_RUNTIME_LANGUAGES.has(language);
}

export function useCodeBlockHeader({
  blockPreview,
  code,
  isSmallScreen,
  language,
}: UseHtmlPreviewHeaderParams): React.ReactNode | undefined {
  return useMemo(() => {
    if (blockPreview == null) {
      return;
    }
    const { openPreview } = blockPreview;
    if (language === "html") {
      return <HtmlPreviewHeader code={code} language={language} openPreview={openPreview} />;
    }
    if (isCodeRuntimeLanguage(language)) {
      return <CodeExecHeader code={code} language={language} openPreview={openPreview} />;
    }
    return;
  }, [blockPreview, code, isSmallScreen, language]);
}
