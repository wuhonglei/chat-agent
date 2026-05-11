import type { ProjectBlock } from "@/interfaces/contentBlock";
import { EventType, useEmitter } from "@/events";
import { workspaceAPI } from "@/services";
import type { WorkspaceTreeNode } from "@/services";
import { Folder } from "@ant-design/x";
import { CloseOutlined, ReloadOutlined } from "@ant-design/icons";
import { useRequest } from "ahooks";
import { Alert, Button, Empty, Spin, Typography } from "antd";
import React, { useCallback, useEffect, useMemo, useState } from "react";

import CodeHighlighter from "@/pages/ChatPage/components/MarkdownContainer/components/CodeHighlighter";

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

function replaceDirectoryChildren(
  nodes: WorkspaceTreeNode[],
  targetPath: string,
  nextChildren: WorkspaceTreeNode[]
): WorkspaceTreeNode[] {
  return nodes.map(node => {
    if (node.path === targetPath) {
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

function getLanguageFromPath(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase();
  if (!ext) {
    return "text";
  }
  const map: Record<string, string> = {
    ts: "typescript",
    tsx: "typescript",
    js: "javascript",
    jsx: "javascript",
    py: "python",
    json: "json",
    md: "markdown",
    html: "html",
    css: "css",
    yml: "yaml",
    yaml: "yaml",
    sh: "bash",
  };
  return map[ext] || "text";
}

const ProjectPreviewPanel: React.FC<ProjectPreviewPanelProps> = ({ width, block, onClose }) => {
  const [treeError, setTreeError] = useState<string | null>(null);
  const [treeData, setTreeData] = useState<WorkspaceTreeNode[]>([]);
  const [expandedPaths, setExpandedPaths] = useState<string[]>([]);
  const [loadedDirPaths, setLoadedDirPaths] = useState<Set<string>>(new Set());

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
        setTreeData(res.treeData || []);
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
        setTreeData(prev => replaceDirectoryChildren(prev, dirPath, res.treeData || []));
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
    runLoadRootTree();
  }, [runLoadRootTree]);

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
          language: res.language || getLanguageFromPath(res.path),
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
        if (!loadedDirPaths.has(path)) {
          void runLoadDirTree(path);
        }
      }
    },
    [loadedDirPaths, runLoadDirTree]
  );

  const handleFolderClick = useCallback(
    async (folderPath: string) => {
      const alreadyExpanded = expandedPaths.includes(folderPath);
      if (alreadyExpanded) {
        setExpandedPaths(prev => prev.filter(path => path !== folderPath));
        return;
      }

      if (!loadedDirPaths.has(folderPath)) {
        try {
          await runLoadDirTree(folderPath);
        } catch {
          return;
        }
      }
      setExpandedPaths(prev => (prev.includes(folderPath) ? prev : [...prev, folderPath]));
    },
    [expandedPaths, loadedDirPaths, runLoadDirTree]
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
        <div className="min-h-0 flex-1 overflow-auto">
          <CodeHighlighter
            lang={selectedFile.language}
            styles={{
              code: { width: "100%", minHeight: "100%", borderRadius: 0 },
            }}
          >
            {selectedFile.content}
          </CodeHighlighter>
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
            directoryTreeWith={Math.max(220, Math.round(width * 0.42))}
            directoryTitle="项目文件"
            previewTitle={false}
            expandedPaths={expandedPaths}
            onExpandedPathsChange={handleExpandedPathsChange}
            onFileClick={filePath => {
              runLoadFile(filePath);
            }}
            onFolderClick={folderPath => {
              void handleFolderClick(folderPath);
            }}
            previewRender={previewNode}
          />
        )}
      </div>
    </section>
  );
};

export default React.memo(ProjectPreviewPanel);
