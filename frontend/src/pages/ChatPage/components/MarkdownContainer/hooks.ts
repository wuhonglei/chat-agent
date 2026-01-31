import { theme } from "antd";
import hljs from "highlight.js";
import React, { useMemo } from "react";

const defaultLanguage = "plaintext";
export function useLanguage(className: string | undefined, code: string, inline: boolean | undefined) {
  return useMemo(() => {
    const match = /language-(\w+)/.exec(className || "");
    if (match) {
      return match[1];
    } else if (!inline && code.includes("\n")) {
      return hljs.highlightAuto(code)?.language || defaultLanguage;
    } else {
      return "";
    }
  }, [className, code, inline]);
}

export function useMarkdownTheme() {
  const token = theme.useToken();

  // 使用 Ant Design 的主题系统判断亮色还是暗色
  const isLightMode = React.useMemo(() => {
    return token?.theme?.id === 0;
  }, [token]);

  const className = React.useMemo(() => {
    return isLightMode ? "x-markdown-light" : "x-markdown-dark";
  }, [isLightMode]);

  return [className];
}
