import { isPlainObject } from "lodash-es";
import { useMemo } from "react";

export type ToolArgumentsDisplay = {
  markdown: string | null;
  /** 无法解析为 JSON 时的原始文本（含流式过程中的不完整片段） */
  plain: string;
};

function escapeMdKey(key: string): string {
  return key.replace(/\\/g, "\\\\").replace(/\*/g, "\\*");
}

function escapeMdString(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/\*/g, "\\*").replace(/`/g, "\\`");
}

function formatScalar(value: unknown): string {
  if (value === null) {
    return "`null`";
  }
  if (value === undefined) {
    return "`undefined`";
  }
  if (typeof value === "string") {
    if (value.includes("\n")) {
      return `\n\n\`\`\`\n${value}\n\`\`\`\n`;
    }
    return `\`${escapeMdString(value)}\``;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return `\`${String(value)}\``;
}

function formatObject(obj: Record<string, unknown>, indentLevel: number): string {
  const entries = Object.entries(obj);
  if (entries.length === 0) {
    return `${"  ".repeat(indentLevel)}- \`{}\``;
  }
  return entries
    .map(([key, val]) => {
      const prefix = `${"  ".repeat(indentLevel)}- **${escapeMdKey(key)}**: `;
      if (Array.isArray(val)) {
        if (val.length === 0) {
          return `${prefix}\`[]\``;
        }
        const lines = val
          .map(item => {
            if (isPlainObject(item)) {
              return formatObject(item, indentLevel + 1);
            }
            if (Array.isArray(item)) {
              return formatArrayBlock(item, indentLevel + 1);
            }
            const itemPrefix = `${"  ".repeat(indentLevel + 1)}- `;
            return `${itemPrefix}${formatScalar(item).replace(/^\n+/, "")}`;
          })
          .join("\n");
        return `${prefix}\n${lines}`;
      }
      if (isPlainObject(val)) {
        return `${prefix}\n${formatObject(val as Record<string, unknown>, indentLevel + 1)}`;
      }
      const scalar = formatScalar(val);
      if (scalar.startsWith("\n")) {
        return `${prefix}${scalar}`;
      }
      return `${prefix}${scalar}`;
    })
    .join("\n");
}

function formatArrayBlock(arr: unknown[], indentLevel: number): string {
  if (arr.length === 0) {
    return `${"  ".repeat(indentLevel)}- \`[]\``;
  }
  return arr
    .map(item => {
      if (isPlainObject(item)) {
        return formatObject(item as Record<string, unknown>, indentLevel);
      }
      if (Array.isArray(item)) {
        return formatArrayBlock(item, indentLevel + 1);
      }
      const prefix = `${"  ".repeat(indentLevel)}- `;
      return `${prefix}${formatScalar(item).replace(/^\n+/, "")}`;
    })
    .join("\n");
}

export function jsonArgumentsToMarkdown(parsed: unknown): string {
  if (parsed === null || typeof parsed !== "object") {
    return formatScalar(parsed).trimStart();
  }
  if (Array.isArray(parsed)) {
    return formatArrayBlock(parsed, 0);
  }
  return formatObject(parsed as Record<string, unknown>, 0);
}

function tryParseToolArgumentsJson(argumentsText: string, argumentsJson?: Record<string, unknown>): unknown | null {
  if (argumentsJson && isPlainObject(argumentsJson)) {
    return argumentsJson;
  }
  const trimmed = argumentsText.trim();
  if (!trimmed) {
    return null;
  }
  try {
    return JSON.parse(argumentsText) as unknown;
  } catch {
    return null;
  }
}

export function useToolArgumentsDisplay(
  argumentsText: string,
  argumentsJson?: Record<string, unknown>
): ToolArgumentsDisplay {
  return useMemo(() => {
    const parsed = tryParseToolArgumentsJson(argumentsText, argumentsJson);
    if (isPlainObject(parsed)) {
      return {
        markdown: jsonArgumentsToMarkdown(parsed),
        plain: "",
      };
    }
    return {
      markdown: null,
      plain: argumentsText || "",
    };
  }, [argumentsJson, argumentsText]);
}
