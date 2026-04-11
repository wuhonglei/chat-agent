import { useMemo } from "react";

export type ExecuteCodeToolArgumentsResult = {
  code: string;
  language: string;
} | null;

export function useToolArgumentsDisplayText(argumentsText: string, argumentsJson?: Record<string, unknown>): string {
  return useMemo(() => {
    if (argumentsText) {
      return argumentsText;
    }
    if (!argumentsJson) {
      return "";
    }
    return JSON.stringify(argumentsJson, null, 2);
  }, [argumentsJson, argumentsText]);
}

export function useExecuteCodeToolArguments(
  toolName: string | undefined,
  argumentsText: string,
  argumentsJson?: Record<string, unknown>
): ExecuteCodeToolArgumentsResult {
  return useMemo(() => {
    if (toolName !== "execute_code") {
      return null;
    }

    const parsedArguments = (() => {
      if (argumentsJson) {
        return argumentsJson;
      }
      if (!argumentsText) {
        return null;
      }
      try {
        return JSON.parse(argumentsText) as Record<string, unknown>;
      } catch {
        return null;
      }
    })();

    if (!parsedArguments) {
      return null;
    }

    const code = parsedArguments.code;
    if (typeof code !== "string" || !code) {
      return null;
    }
    const language = parsedArguments.language;
    return {
      code,
      language: typeof language === "string" && language ? language : "plaintext",
    };
  }, [argumentsJson, argumentsText, toolName]);
}
