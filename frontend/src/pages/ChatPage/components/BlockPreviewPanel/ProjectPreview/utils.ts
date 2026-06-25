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

/** 过滤掉空目录（nodeType 为 dir 且没有可见子项），用于根目录展示 */
export function filterEmptyDirectories(nodes: WorkspaceTreeNode[]): WorkspaceTreeNode[] {
  return nodes.filter(node => !(node.nodeType === "dir" && !node.hasChildren));
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

const EXCEL_EXTENSIONS = new Set(["xlsx", "xls"]);

/** 工作区 file-content 接口不支持的二进制扩展名（按扩展名预判，避免无效请求）。 */
const NON_TEXT_WORKSPACE_EXTENSIONS = new Set([
  ...EXCEL_EXTENSIONS,
  "pdf",
  "png",
  "jpg",
  "jpeg",
  "gif",
  "webp",
  "zip",
  "gz",
  "tar",
  "7z",
  "rar",
  "doc",
  "docx",
  "ppt",
  "pptx",
  "mp3",
  "mp4",
  "wav",
  "ico",
  "woff",
  "woff2",
  "ttf",
  "eot",
  "bin",
  "exe",
  "dll",
  "so",
  "dylib",
]);

export function isExcelPath(path: string): boolean {
  const ext = path.split(".").pop()?.toLowerCase();
  return Boolean(ext && EXCEL_EXTENSIONS.has(ext));
}

export function isNonTextWorkspaceFile(path: string): boolean {
  const ext = path.split(".").pop()?.toLowerCase();
  return Boolean(ext && NON_TEXT_WORKSPACE_EXTENSIONS.has(ext));
}

export function getRequestErrorMessage(error: unknown, fallback: string): string {
  if (error && typeof error === "object" && "msg" in error && typeof error.msg === "string") {
    return error.msg;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

/** 会话相对路径 → Folder 组件所需的 path 分段（如 outputs/a.md → ['outputs', 'a.md']） */
export function toPathSegments(filePath: string): string[] {
  return filePath.split("/").filter(Boolean);
}

/** 获取文件所有祖先目录的会话相对路径（如 outputs/a/b.md → ['outputs', 'outputs/a']） */
export function getAncestorDirPaths(filePath: string): string[] {
  const segments = toPathSegments(filePath);
  if (segments.length <= 1) {
    return [];
  }
  const dirs: string[] = [];
  for (let i = 1; i < segments.length; i += 1) {
    dirs.push(segments.slice(0, i).join("/"));
  }
  return dirs;
}
