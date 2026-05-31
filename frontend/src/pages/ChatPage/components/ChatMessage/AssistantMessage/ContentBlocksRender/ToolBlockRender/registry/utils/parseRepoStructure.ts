import type { DataNode } from "antd/es/tree";

type ParsedLine = {
  depth: number;
  title: string;
  isDirectory: boolean;
};

let keyCounter = 0;

function nextKey(): string {
  keyCounter += 1;
  return `repo-node-${keyCounter}`;
}

function resetKeys(): void {
  keyCounter = 0;
}

function looksLikeFileName(name: string): boolean {
  const segment = name.split("/").pop() || name;
  return /\.[A-Za-z0-9_-]+$/.test(segment);
}

function parseAsciiLine(line: string): ParsedLine | null {
  let depth = 0;
  let index = 0;

  while (index + 4 <= line.length) {
    const segment = line.slice(index, index + 4);
    if (segment === "│   " || segment === "    ") {
      depth += 1;
      index += 4;
      continue;
    }
    break;
  }

  let rest = line.slice(index);
  const hasBranch = /^(?:├── |└── )/.test(rest);
  if (hasBranch) {
    depth += 1;
    rest = rest.replace(/^(?:├── |└── )/, "");
  }

  rest = rest.trim();
  if (!rest) {
    return null;
  }

  const isDirectory = rest.endsWith("/") || !looksLikeFileName(rest);
  return {
    depth,
    title: rest.replace(/\/$/, ""),
    isDirectory,
  };
}

function looksLikeAsciiTree(content: string): boolean {
  const lines = content.split("\n").map(line => line.trimEnd()).filter(line => line.trim());
  if (!lines.length) {
    return false;
  }
  return lines.some(line => /[├└]──/.test(line) || /\/$/.test(line.trim()));
}

function parseAsciiTree(content: string): DataNode[] | null {
  if (!looksLikeAsciiTree(content)) {
    return null;
  }

  resetKeys();
  const roots: DataNode[] = [];
  const stack: { depth: number; node: DataNode }[] = [];

  for (const rawLine of content.split("\n")) {
    const line = rawLine.replace(/\r$/, "");
    if (!line.trim()) {
      continue;
    }

    const parsed = parseAsciiLine(line);
    if (!parsed) {
      continue;
    }

    const node: DataNode = {
      key: nextKey(),
      title: parsed.title,
      isLeaf: !parsed.isDirectory,
    };

    while (stack.length > 0 && stack[stack.length - 1].depth >= parsed.depth) {
      stack.pop();
    }

    if (stack.length === 0) {
      roots.push(node);
    } else {
      const parent = stack[stack.length - 1].node;
      parent.children = parent.children ?? [];
      parent.children.push(node);
      parent.isLeaf = false;
    }

    stack.push({ depth: parsed.depth, node });
  }

  return roots.length ? roots : null;
}

function normalizeJsonTreeNode(value: unknown, keyPrefix: string): DataNode | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }

  const record = value as Record<string, unknown>;
  const title = String(record.name ?? record.title ?? record.path ?? record.label ?? "").trim();
  if (!title) {
    return null;
  }

  const childSource = record.children ?? record.items ?? record.nodes;
  const children = Array.isArray(childSource)
    ? childSource
        .map((child, index) => normalizeJsonTreeNode(child, `${keyPrefix}-${index}`))
        .filter((child): child is DataNode => child != null)
    : undefined;

  const type = String(record.type ?? record.nodeType ?? record.kind ?? "").toLowerCase();
  const isDirectory =
    type.includes("dir") ||
    type.includes("folder") ||
    Boolean(children?.length) ||
    title.endsWith("/") ||
    !looksLikeFileName(title);

  return {
    key: keyPrefix,
    title: title.replace(/\/$/, ""),
    children: children?.length ? children : undefined,
    isLeaf: !isDirectory,
  };
}

function parseJsonTree(value: unknown): DataNode[] | null {
  resetKeys();

  if (Array.isArray(value)) {
    if (value.every(item => typeof item === "string")) {
      return pathsToTree(value as string[]);
    }

    const nodes = value
      .map((item, index) => normalizeJsonTreeNode(item, nextKey()))
      .filter((item): item is DataNode => item != null);
    return nodes.length ? nodes : null;
  }

  if (!value || typeof value !== "object") {
    return null;
  }

  const record = value as Record<string, unknown>;

  for (const field of ["tree", "structure", "content", "text", "result"]) {
    const nested = record[field];
    if (typeof nested === "string") {
      return parseRepoStructureContent(nested);
    }
  }

  if (Array.isArray(record.children)) {
    const root = normalizeJsonTreeNode(value, nextKey());
    return root ? [root] : null;
  }

  const githubTree = record.tree;
  if (githubTree && typeof githubTree === "object" && !Array.isArray(githubTree)) {
    const entries = (githubTree as Record<string, unknown>).tree;
    if (Array.isArray(entries)) {
      const paths = entries
        .map(entry => {
          if (!entry || typeof entry !== "object") {
            return null;
          }
          const path = (entry as Record<string, unknown>).path;
          return typeof path === "string" ? path : null;
        })
        .filter((path): path is string => Boolean(path));
      return pathsToTree(paths);
    }
  }

  if (Array.isArray(record.files) || Array.isArray(record.paths)) {
    const paths = (record.files ?? record.paths) as unknown[];
    if (paths.every(item => typeof item === "string")) {
      return pathsToTree(paths as string[]);
    }
  }

  const root = normalizeJsonTreeNode(value, nextKey());
  return root ? [root] : null;
}

function pathsToTree(paths: string[]): DataNode[] | null {
  if (!paths.length) {
    return null;
  }

  resetKeys();
  type MutableNode = DataNode & { childMap?: Map<string, MutableNode> };
  const rootMap = new Map<string, MutableNode>();

  const sortedPaths = [...paths].sort((a, b) => a.localeCompare(b));
  for (const rawPath of sortedPaths) {
    const parts = rawPath.split("/").filter(Boolean);
    let currentMap = rootMap;
    let currentPath = "";

    for (let index = 0; index < parts.length; index += 1) {
      const part = parts[index];
      currentPath = currentPath ? `${currentPath}/${part}` : part;
      let node = currentMap.get(part);
      if (!node) {
        const isLeaf = index === parts.length - 1;
        node = {
          key: currentPath,
          title: part,
          isLeaf,
          childMap: new Map<string, MutableNode>(),
        };
        currentMap.set(part, node);
      } else if (index === parts.length - 1) {
        node.isLeaf = true;
      } else {
        node.isLeaf = false;
      }
      currentMap = node.childMap!;
    }
  }

  function mapToNodes(map: Map<string, MutableNode>): DataNode[] {
    return [...map.values()].map(node => {
      const children = node.childMap?.size ? mapToNodes(node.childMap) : undefined;
      return {
        key: node.key,
        title: node.title,
        isLeaf: children?.length ? false : node.isLeaf,
        children,
      };
    });
  }

  const nodes = mapToNodes(rootMap);
  return nodes.length ? nodes : null;
}

export function parseRepoStructureContent(content: string): DataNode[] | null {
  const trimmed = content.trim();
  if (!trimmed) {
    return null;
  }

  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try {
      const parsed = JSON.parse(trimmed) as unknown;
      const jsonTree = parseJsonTree(parsed);
      if (jsonTree?.length) {
        return jsonTree;
      }
    } catch {
      // fall through to text parsing
    }
  }

  return parseAsciiTree(trimmed);
}
