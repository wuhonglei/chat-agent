import { useBlockPreview } from "@/pages/ChatPage/context/BlockPreviewContext";
import { Mermaid } from "@ant-design/x";
import React, { memo, useMemo } from "react";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useLanguage } from "../hooks";
import CodeHighlighter from "./CodeHighlighter";
import HtmlPreviewHeader from "./HtmlPreviewHeader";
import InlineCode from "./InlineCode";
import { useIsSmallScreen } from "@/hooks";

interface CustomCodeBlockProps {
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
}

const CustomCodeBlock = memo(({ inline, className, children }: CustomCodeBlockProps) => {
  const code = String(children).replace(/\n$/, "");
  const language = useLanguage(className, code, inline);
  const blockPreview = useBlockPreview();
  const isSmallScreen = useIsSmallScreen();

  const htmlHeader = useMemo(() => {
    if (isSmallScreen || language !== "html" || !blockPreview) {
      return undefined;
    }
    return <HtmlPreviewHeader language={language} code={code} openPreview={blockPreview.openPreview} />;
  }, [blockPreview, code, language, isSmallScreen]);

  if (inline || !language) {
    return <InlineCode>{code}</InlineCode>;
  }

  if (language === "mermaid") {
    return (
      <Mermaid
        styles={{ graph: { backgroundColor: "#f8f9fa" } }}
        highlightProps={{
          customStyle: {},
          style: oneLight,
        }}
      >
        {code}
      </Mermaid>
    );
  }

  return (
    <CodeHighlighter lang={language} header={htmlHeader}>
      {code}
    </CodeHighlighter>
  );
});

export default CustomCodeBlock;
