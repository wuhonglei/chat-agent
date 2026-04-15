import { useBlockPreview } from "@/pages/ChatPage/context/BlockPreviewContext";
import { Actions, Mermaid } from "@ant-design/x";
import { Button } from "antd";
import React, { memo, useMemo } from "react";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useLanguage } from "../hooks";
import CodeHighlighter from "./CodeHighlighter";
import InlineCode from "./InlineCode";

interface CustomCodeBlockProps {
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
}

function createHtmlPreviewBlockId() {
  return `html_preview_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

const CustomCodeBlock = memo(({ inline, className, children }: CustomCodeBlockProps) => {
  const code = String(children).replace(/\n$/, "");
  const language = useLanguage(className, code, inline);
  const blockPreview = useBlockPreview();

  const htmlHeader = useMemo(() => {
    if (language !== "html" || !blockPreview) {
      return undefined;
    }
    return (
      <>
        <span className="text-(--ant-color-text-secondary)">{language}</span>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            type="link"
            size="small"
            className="px-1!"
            onClick={() =>
              blockPreview.openPreview({
                id: createHtmlPreviewBlockId(),
                type: "html",
                content: code,
              })
            }
          >
            预览
          </Button>
          <Actions.Copy text={code} />
        </div>
      </>
    );
  }, [blockPreview, code, language]);

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
