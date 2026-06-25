import { FILE_EXTENSION_LANGUAGE_MAP } from "@/constants";
import type { WorkspaceTreeNode } from "@/services";

const DIRECTORY_PLACEHOLDER_SEGMENT = "__directory_placeholder__";

function toDisplayPath(fullPath: string, parentFullPath: string): string {
  if (!parentFullPath) {
    return fullPath;
  }
  const prefix = `${parentFullPath}/`;
  if (fullPath.startsWith(prefix)) {
    return fullPath.slice(prefix.length);
  }
  return fullPath.split("/").pop() || fullPath;
}

export function isDirectoryNode(node: WorkspaceTreeNode): boolean {
  return Array.isArray(node.children);
}

export function isPlaceholderPath(path: string): boolean {
  return path.split("/").includes(DIRECTORY_PLACEHOLDER_SEGMENT);
}

export function normalizeTreeNodes(nodes: WorkspaceTreeNode[], parentFullPath = ""): WorkspaceTreeNode[] {
  return nodes.map(node => {
    const fullPath = node.path;
    const displayPath = toDisplayPath(fullPath, parentFullPath);
    if (node.nodeType === "dir") {
      const normalizedChildren = normalizeTreeNodes(node.children || [], fullPath);
      const shouldAddPlaceholder = normalizedChildren.length === 0 && node.hasChildren;
      return {
        title: node.title,
        path: displayPath,
        fullPath,
        nodeType: "dir",
        hasChildren: node.hasChildren,
        isLeaf: false,
        children: shouldAddPlaceholder
          ? [
              {
                title: "",
                path: DIRECTORY_PLACEHOLDER_SEGMENT,
                fullPath: `${fullPath}/${DIRECTORY_PLACEHOLDER_SEGMENT}`,
                nodeType: "file",
                isLeaf: true,
                key: `${fullPath}/${DIRECTORY_PLACEHOLDER_SEGMENT}`,
              },
            ]
          : normalizedChildren,
      };
    }
    return {
      title: node.title,
      path: displayPath,
      fullPath,
      nodeType: "file",
      isLeaf: true,
    };
  });
}

export function replaceDirectoryChildren(
  nodes: WorkspaceTreeNode[],
  targetPath: string,
  nextChildren: WorkspaceTreeNode[]
): WorkspaceTreeNode[] {
  return nodes.map(node => {
    if ((node.fullPath || node.path) === targetPath) {
      return { ...node, children: nextChildren };
    }
    if (!node.children?.length) {
      return node;
    }
    return {
      ...node,
      children: replaceDirectoryChildren(node.children, targetPath, nextChildren),
    };
  });
}

export function findNodeByPath(nodes: WorkspaceTreeNode[], targetPath: string): WorkspaceTreeNode | undefined {
  for (const node of nodes) {
    if ((node.fullPath || node.path) === targetPath) {
      return node;
    }
    if (!node.children?.length) {
      continue;
    }
    const nestedNode = findNodeByPath(node.children, targetPath);
    if (nestedNode) {
      return nestedNode;
    }
  }
  return undefined;
}

export function getLanguageFromPath(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase();
  if (!ext) {
    return "text";
  }
  return FILE_EXTENSION_LANGUAGE_MAP[ext] || "text";
}

export function getMonacoLanguage(language: string): string {
  if (language === "text") {
    return "plaintext";
  }
  return language || "plaintext";
}

export function isMarkdownPath(path: string): boolean {
  return getLanguageFromPath(path) === "markdown";
}
