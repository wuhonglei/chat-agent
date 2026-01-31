import { componentMap, validateComponentProps } from "@/componentTools/helper";
import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";
import ComponentErrorBoundary from "@/pages/ChatPage/components/MarkdownContainer/components/ComponentErrorBoundary";
import { reportError } from "@/utils/aegis";
import { Mermaid } from "@ant-design/x";
import XMarkdown from "@ant-design/x-markdown";
import Latex from "@ant-design/x-markdown/plugins/Latex";
import classNames from "classnames";
import { jsonrepair } from "jsonrepair";
import React, { ErrorInfo, memo, Suspense } from "react";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import InlineCode from "./components/InlineCode";
import { useLanguage, useMarkdownTheme } from "./hooks";
import "./index.css";
import styles from "./index.module.css";

interface CustomCodeBlockProps {
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
}

const CustomCodeBlock = memo(({ inline, className, children }: CustomCodeBlockProps) => {
  const code = String(children).replace(/\n$/, "");
  const language = useLanguage(className, code, inline);

  const handleError = (error: Error, errorInfo: ErrorInfo) => {
    console.error("组件渲染错误，降级为代码展示:", error, errorInfo);
    reportError("Component Error", {
      error: error,
      componentStack: errorInfo.componentStack,
    });
  };

  if (inline || !language) {
    return <InlineCode>{code}</InlineCode>;
  }

  // 处理 Mermaid 代码块
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

  if (language === "json" && code.includes("component_name") && code.includes("props")) {
    // 降级渲染：当组件渲染失败时，显示原始 JSON 代码
    const fallbackCodeBlock = <CodeHighlighter lang="json">{code}</CodeHighlighter>;

    try {
      const parsedData = JSON.parse(jsonrepair(code));
      const componentName = parsedData.component_name;
      const Component = componentMap.get(componentName);
      if (!Component) {
        throw new Error(`未找到组件: ${componentName}`);
      }
      const props = parsedData.props;
      const { valid, errors } = validateComponentProps(componentName, props);
      if (!valid) {
        throw new Error(`组件 ${componentName} 的 props 不合法: ${errors?.join(", ")}`);
      }

      // 使用错误边界和 Suspense 包裹组件，支持懒加载和错误捕获
      return (
        <ComponentErrorBoundary onError={handleError} fallback={fallbackCodeBlock}>
          <Suspense fallback={fallbackCodeBlock}>
            <Component {...props} />
          </Suspense>
        </ComponentErrorBoundary>
      );
    } catch {
      return fallbackCodeBlock;
    }
  }

  return <CodeHighlighter lang={language}>{code}</CodeHighlighter>;
});

type Props = {
  gray?: boolean;
  className?: string;
  styles?: React.CSSProperties;
  children: string | undefined;
};

const MarkdownContainer = ({ children, gray, className, styles: markdownStyles }: Props) => {
  const [markdownClassName] = useMarkdownTheme();

  if (!children) {
    return null;
  }

  return (
    <XMarkdown
      openLinksInNewTab
      components={{
        code: CustomCodeBlock,
      }}
      style={markdownStyles}
      config={{ extensions: [...Latex()] }}
      className={classNames(markdownClassName, styles["x-markdown"], gray && styles["gray"], className)}
    >
      {children}
    </XMarkdown>
  );
};

export default memo(MarkdownContainer);
