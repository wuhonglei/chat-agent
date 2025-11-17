import { useMemo } from "react";
import hljs from "highlight.js";

const defaultLanguage = "plaintext";
export function useLanguage(
  className: string | undefined,
  code: string,
  inline: boolean | undefined
) {
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
