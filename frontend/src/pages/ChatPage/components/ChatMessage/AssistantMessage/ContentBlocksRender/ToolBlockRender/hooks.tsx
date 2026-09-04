import { ContentBlockRenderStatus, ToolUseBlock } from "@/interfaces/contentBlock";
import { useMemoizedFn } from "ahooks";
import { useEffect, useMemo, useRef, useState } from "react";

import { isPlainObject } from "lodash-es";

import { isActiveStatus, stringifyJsonLike } from "./utils";

const TOOL_BLOCK_COLLAPSE_DEBOUNCE_MS = 1000;

type ArgumentsLanguage = "json" | "plaintext";

type UseParsedArgumentsResult = {
  parsedArguments: string;
  argumentsLanguage: ArgumentsLanguage;
};

function canParseAsJson(value: string): boolean {
  if (!value) {
    return false;
  }
  try {
    JSON.parse(value);
    return true;
  } catch {
    return false;
  }
}

export function useToolBlockExpanded(status: ContentBlockRenderStatus): {
  expanded: boolean;
  onExpandChange: (nextExpanded: boolean) => void;
} {
  const isActive = isActiveStatus(status);
  const [expanded, setExpanded] = useState<boolean>(isActive);
  const [wasActive, setWasActive] = useState(isActive);
  const collapseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  if (isActive !== wasActive) {
    setWasActive(isActive);
    if (isActive) {
      setExpanded(true);
    }
  }

  useEffect(() => {
    if (isActive) {
      return;
    }
    const timer = setTimeout(() => {
      collapseTimerRef.current = null;
      setExpanded(false);
    }, TOOL_BLOCK_COLLAPSE_DEBOUNCE_MS);
    collapseTimerRef.current = timer;
    return () => {
      clearTimeout(timer);
      if (collapseTimerRef.current === timer) {
        collapseTimerRef.current = null;
      }
    };
  }, [isActive]);

  const onExpandChange = useMemoizedFn((nextExpanded: boolean) => {
    if (collapseTimerRef.current != null) {
      clearTimeout(collapseTimerRef.current);
      collapseTimerRef.current = null;
    }
    setExpanded(nextExpanded);
  });

  return { expanded, onExpandChange };
}

export function useParsedArguments(contentBlock: ToolUseBlock): UseParsedArgumentsResult {
  return useMemo(() => {
    if (isPlainObject(contentBlock.argumentsJson)) {
      return {
        parsedArguments: JSON.stringify(contentBlock.argumentsJson, null, 2),
        argumentsLanguage: "json",
      };
    }

    const argumentsText = contentBlock.argumentsText || "";
    return {
      parsedArguments: stringifyJsonLike(argumentsText),
      argumentsLanguage: canParseAsJson(argumentsText) ? "json" : "plaintext",
    };
  }, [contentBlock.argumentsJson, contentBlock.argumentsText]);
}
