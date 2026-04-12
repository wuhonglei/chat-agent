import { ContentBlockRenderStatus, ToolUseBlock } from "@/interfaces/contentBlock";
import { useDebounceFn, useMemoizedFn } from "ahooks";
import { useEffect, useMemo, useState } from "react";

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
  const [expanded, setExpanded] = useState<boolean>(isActiveStatus(status));

  const { run: delayCollapse, cancel: cancelDelayCollapse } = useDebounceFn(
    () => {
      setExpanded(false);
    },
    { wait: TOOL_BLOCK_COLLAPSE_DEBOUNCE_MS }
  );

  useEffect(() => {
    if (isActiveStatus(status)) {
      cancelDelayCollapse();
      setExpanded(true);
      return;
    }
    delayCollapse();
    return () => {
      cancelDelayCollapse();
    };
  }, [status, delayCollapse, cancelDelayCollapse]);

  const onExpandChange = useMemoizedFn((nextExpanded: boolean) => {
    cancelDelayCollapse();
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
