const ZREAD_CONTENT_TAGS = [
  "repo_structure",
  "directory_structure",
  "directory_tree",
  "structure",
  "tree",
  "file_content",
] as const;

export function normalizeEscapedNewlines(text: string): string {
  if (!text.includes("\n") && text.includes("\\n")) {
    return text.replace(/\\r\\n/g, "\n").replace(/\\n/g, "\n").replace(/\\t/g, "\t").replace(/\\"/g, '"');
  }
  return text;
}

export function unwrapJsonStringLiteral(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed.startsWith('"') || !trimmed.endsWith('"')) {
    return raw;
  }
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    return typeof parsed === "string" ? parsed : raw;
  } catch {
    return raw;
  }
}

export function extractZreadTaggedContent(text: string): string | null {
  for (const tag of ZREAD_CONTENT_TAGS) {
    const closedMatch = new RegExp(`<${tag}>([\\s\\S]*?)</${tag}>`, "i").exec(text);
    if (closedMatch?.[1]?.trim()) {
      return closedMatch[1].trim();
    }

    const openMatch = new RegExp(`<${tag}>([\\s\\S]*)$`, "i").exec(text);
    if (openMatch?.[1]?.trim()) {
      return openMatch[1].trim();
    }
  }
  return null;
}

export function stripZreadPreamble(text: string): string {
  return text
    .replace(
      /^(?:File content|Directory [Ss]tructure(?: of [^\n]+)?|Repo structure|Repository structure)[^\n]*\n(?:Source:[^\n]*\n?)?\n?/i,
      ""
    )
    .trim();
}

export function formatZreadRepoStructureDisplay(raw: string): string | null {
  const display = findStructureBody(unwrapZreadToolContent(raw)).trim();
  return display || null;
}

function extractCodeFence(text: string): string | null {
  const match = /```(?:[\w-]*)?\n([\s\S]*?)```/.exec(text);
  return match?.[1]?.trim() ?? null;
}

export function unwrapZreadToolContent(raw: string): string {
  let text = unwrapJsonStringLiteral(raw.trim());
  if (!text) {
    return text;
  }

  text = normalizeEscapedNewlines(text);

  const tagged = extractZreadTaggedContent(text);
  if (tagged) {
    return tagged;
  }

  const fenced = extractCodeFence(text);
  if (fenced) {
    return fenced;
  }

  return stripZreadPreamble(text);
}

export function findStructureBody(text: string): string {
  const lines = text.split("\n");
  const startIndex = lines.findIndex(line => {
    const trimmed = line.trim();
    return (
      /[├└]──/.test(trimmed) ||
      trimmed.endsWith("/") ||
      /^[-*]\s+[\w./-]+\/?$/.test(trimmed) ||
      /^[\w.-]+\/$/.test(trimmed)
    );
  });

  if (startIndex >= 0) {
    return lines.slice(startIndex).join("\n");
  }

  return text;
}
