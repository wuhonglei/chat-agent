import type { ProjectBlock } from "@/interfaces/contentBlock";
import { EventType, useEmitter } from "@/events";
import { FILE_EXTENSION_LANGUAGE_MAP } from "@/constants";
import { workspaceAPI } from "@/services";
import type { WorkspaceTreeNode } from "@/services";
import { PROJECT_PREVIEW_DIRECTORY_ICONS } from "./file_icons";
import { Folder } from "@ant-design/x";
import { CloseOutlined, ReloadOutlined } from "@ant-design/icons";
import Editor from "@monaco-editor/react";
import { useRequest } from "ahooks";
import { Alert, Button, Empty, Spin, Typography } from "antd";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

export interface ProjectPreviewPanelProps {
  width: number;
  block: ProjectBlock;
  onClose: () => void;
}

type SelectedFile = {
  path: string;
  title: string;
  content: string;
  language: string;
};

const DIRECTORY_PLACEHOLDER_SEGMENT = "__directory_placeholder__";

function isDirectoryNode(node: WorkspaceTreeNode): boolean {
  return Array.isArray(node.children);
}

function isPlaceholderPath(path: string): boolean {
  return path.split("/").includes(DIRECTORY_PLACEHOLDER_SEGMENT);
}

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

function normalizeTreeNodes(nodes: WorkspaceTreeNode[], parentFullPath = ""): WorkspaceTreeNode[] {
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

function replaceDirectoryChildren(
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

function findNodeByPath(nodes: WorkspaceTreeNode[], targetPath: string): WorkspaceTreeNode | undefined {
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

function getLanguageFromPath(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase();
  if (!ext) {
    return "text";
  }
  return FILE_EXTENSION_LANGUAGE_MAP[ext] || "text";
}

function getMonacoLanguage(language: string): string {
  if (language === "text") {
    return "plaintext";
  }
  return language || "plaintext";
}

const ProjectPreviewPanel: React.FC<ProjectPreviewPanelProps> = ({ width: _width, block, onClose }) => {
  const [treeError, setTreeError] = useState<string | null>(null);
  const [treeData, setTreeData] = useState<WorkspaceTreeNode[]>([]);
  const [expandedPaths, setExpandedPaths] = useState<string[]>([]);
  const [loadedDirPaths, setLoadedDirPaths] = useState<Set<string>>(new Set());
  const loadingDirPathsRef = useRef<Set<string>>(new Set());

  const [fileError, setFileError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<SelectedFile | null>(null);

  const { run: runLoadRootTree, loading: loadingTree } = useRequest(
    async () => {
      return await workspaceAPI.getWorkspaceFileTree(block.workspaceId, { path: "", depth: 1 });
    },
    {
      manual: true,
      onBefore: () => {
        setTreeError(null);
      },
      onSuccess: res => {
        setTreeData(normalizeTreeNodes(res.treeData || []));
        setLoadedDirPaths(new Set([""]));
      },
      onError: error => {
        setTreeError(error instanceof Error ? error.message : "文件树加载失败");
      },
    }
  );

  const { runAsync: runLoadDirTree } = useRequest(
    async (dirPath: string) => {
      return await workspaceAPI.getWorkspaceFileTree(block.workspaceId, { path: dirPath, depth: 1 });
    },
    {
      manual: true,
      onError: error => {
        setTreeError(error instanceof Error ? error.message : "子目录加载失败");
      },
      onSuccess: (res, params) => {
        const dirPath = params[0] || "";
        setTreeData(prev => replaceDirectoryChildren(prev, dirPath, normalizeTreeNodes(res.treeData || [], dirPath)));
        setLoadedDirPaths(prev => {
          const next = new Set(prev);
          next.add(dirPath);
          return next;
        });
      },
    }
  );

  const refreshTree = useCallback(() => {
    setExpandedPaths([]);
    setLoadedDirPaths(new Set());
    loadingDirPathsRef.current.clear();
    runLoadRootTree();
  }, [runLoadRootTree]);

  const loadDirTreeIfNeeded = useCallback(
    async (dirPath: string) => {
      if (loadedDirPaths.has(dirPath) || loadingDirPathsRef.current.has(dirPath)) {
        return;
      }
      loadingDirPathsRef.current.add(dirPath);
      try {
        await runLoadDirTree(dirPath);
      } finally {
        loadingDirPathsRef.current.delete(dirPath);
      }
    },
    [loadedDirPaths, runLoadDirTree]
  );

  const { run: runLoadFile, loading: loadingFile } = useRequest(
    async (filePath: string) => {
      return await workspaceAPI.getWorkspaceFileContent(block.workspaceId, filePath);
    },
    {
      manual: true,
      onBefore: () => {
        setFileError(null);
      },
      onSuccess: res => {
        setSelectedFile({
          path: res.path,
          title: res.path.split("/").pop() || res.path,
          content: res.content || "",
          language: getLanguageFromPath(res.path),
        });
      },
      onError: error => {
        setFileError(error instanceof Error ? error.message : "文件内容加载失败");
      },
    }
  );

  useEffect(() => {
    setSelectedFile(null);
    setFileError(null);
    refreshTree();
  }, [block.id, refreshTree]);

  useEmitter(EventType.WorkspaceTreeRefresh, payload => {
    if (payload.workspaceId === block.workspaceId) {
      refreshTree();
    }
  });

  const handleExpandedPathsChange = useCallback(
    (paths: string[]) => {
      setExpandedPaths(paths);
      for (const path of paths) {
        void loadDirTreeIfNeeded(path);
      }
    },
    [loadDirTreeIfNeeded]
  );

  const handleFolderClick = useCallback(
    async (folderPath: string) => {
      setFileError(null);
      const alreadyExpanded = expandedPaths.includes(folderPath);
      if (alreadyExpanded) {
        setExpandedPaths(prev => prev.filter(path => path !== folderPath));
        return;
      }

      try {
        await loadDirTreeIfNeeded(folderPath);
      } catch {
        return;
      }
      setExpandedPaths(prev => (prev.includes(folderPath) ? prev : [...prev, folderPath]));
    },
    [expandedPaths, loadDirTreeIfNeeded]
  );

  const handleFileClick = useCallback(
    (filePath: string) => {
      if (isPlaceholderPath(filePath)) {
        return;
      }
      const targetNode = findNodeByPath(treeData, filePath);
      const isDirectoryPath = targetNode ? isDirectoryNode(targetNode) : false;
      if (isDirectoryPath) {
        void handleFolderClick(filePath);
        return;
      }
      runLoadFile(filePath);
    },
    [handleFolderClick, runLoadFile, treeData]
  );

  const previewNode = useMemo(() => {
    if (loadingFile) {
      return (
        <div className="h-full w-full flex items-center justify-center">
          <Spin />
        </div>
      );
    }
    if (fileError) {
      return <Alert type="error" showIcon message={fileError} />;
    }
    if (!selectedFile) {
      return <Empty description="请选择左侧文件查看内容" className="mt-12" />;
    }
    return (
      <div className="h-full min-h-0 flex flex-col">
        <Typography.Text type="secondary" className="px-3 py-2 border-b border-(--ant-color-border-secondary)">
          {selectedFile.path}
        </Typography.Text>
        <div className="min-h-0 flex-1 overflow-hidden">
          <Editor
            height="100%"
            language={getMonacoLanguage(selectedFile.language)}
            value={selectedFile.content}
            options={{
              readOnly: true,
              minimap: { enabled: false },
              wordWrap: "on",
              scrollBeyondLastLine: false,
              automaticLayout: true,
              renderLineHighlight: "none",
              padding: { top: 12, bottom: 12 },
            }}
          />
        </div>
      </div>
    );
  }, [fileError, loadingFile, selectedFile]);

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <header className="flex h-[60px] shrink-0 items-center justify-between gap-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container) px-3">
        <Typography.Text type="secondary">{block.title || "项目结构预览"}</Typography.Text>
        <div className="flex items-center gap-1">
          <Button type="text" onClick={refreshTree} icon={<ReloadOutlined />} loading={loadingTree} />
          <Button type="text" onClick={onClose} icon={<CloseOutlined />} />
        </div>
      </header>
      <div className="flex-1 min-h-0 overflow-hidden">
        {loadingTree ? (
          <div className="h-full w-full flex items-center justify-center">
            <Spin />
          </div>
        ) : treeError ? (
          <div className="p-3">
            <Alert type="error" showIcon message={treeError} />
          </div>
        ) : (
          <Folder
            treeData={treeData}
            directoryTreeWith={237}
            styles={{
              directoryTree: { background: "#fff" },
            }}
            previewTitle={false}
            expandedPaths={expandedPaths}
            onExpandedPathsChange={handleExpandedPathsChange}
            onFileClick={filePath => {
              handleFileClick(filePath);
            }}
            onFolderClick={folderPath => {
              void handleFolderClick(folderPath);
            }}
            previewRender={previewNode}
            directoryIcons={PROJECT_PREVIEW_DIRECTORY_ICONS}
          />
        )}
      </div>
    </section>
  );
};

export default React.memo(ProjectPreviewPanel);
