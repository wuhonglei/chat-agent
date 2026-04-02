import { ToolUseBlock } from "@/interfaces/contentBlock";
import { useMemo } from "react";

import { isPlainObject } from "lodash-es";

import { stringifyJsonLike } from "./utils";

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
