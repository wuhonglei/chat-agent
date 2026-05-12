import { EventType, useEmitter } from "@/events";
import type { ProjectBlock } from "@/interfaces/contentBlock";
import type { WorkspaceTreeNode } from "@/services";
import { workspaceAPI } from "@/services";
import { CloseOutlined, ReloadOutlined } from "@ant-design/icons";
import { Folder } from "@ant-design/x";
import Editor from "@monaco-editor/react";
import { useRequest } from "ahooks";
import { Alert, Button, Empty, Spin, Typography } from "antd";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PROJECT_PREVIEW_DIRECTORY_ICONS } from "./file_icons";
import {
  findNodeByPath,
  getLanguageFromPath,
  getMonacoLanguage,
  isDirectoryNode,
  isPlaceholderPath,
  normalizeTreeNodes,
  replaceDirectoryChildren,
} from "./utils";

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

type PreviewMode = "files" | "app";

const ProjectPreviewPanel: React.FC<ProjectPreviewPanelProps> = ({ width: _width, block, onClose }) => {
  const [previewMode, setPreviewMode] = useState<PreviewMode>("files");

  const [treeError, setTreeError] = useState<string | null>(null);
  const [treeData, setTreeData] = useState<WorkspaceTreeNode[]>([]);
  const [expandedPaths, setExpandedPaths] = useState<string[]>([]);
  const [loadedDirPaths, setLoadedDirPaths] = useState<Set<string>>(new Set());
  const loadingDirPathsRef = useRef<Set<string>>(new Set());

  const [fileError, setFileError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<SelectedFile | null>(null);
  const [appPreviewError, setAppPreviewError] = useState<string | null>(null);
  const [appPreviewHtml, setAppPreviewHtml] = useState("");
  const [appPreviewPath, setAppPreviewPath] = useState<string>("");

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
      return await workspaceAPI.getWorkspaceFileTree(block.workspaceId, {
        path: dirPath,
        depth: 1,
      });
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

  const { run: runLoadAppPreview, loading: loadingAppPreview } = useRequest(
    async () => {
      return await workspaceAPI.getWorkspacePreviewContent(block.workspaceId);
    },
    {
      manual: true,
      onBefore: () => {
        setAppPreviewError(null);
      },
      onSuccess: res => {
        setAppPreviewPath(res.path || "");
        setAppPreviewHtml(res.content || "");
      },
      onError: error => {
        const message = error instanceof Error ? error.message : "运行预览加载失败";
        if (message.includes("404") || message.includes("未找到可预览入口文件")) {
          setAppPreviewError("未找到可预览入口文件，请先完成构建产物生成");
          return;
        }
        setAppPreviewError(message);
      },
    }
  );

  useEffect(() => {
    setPreviewMode("files");
    setSelectedFile(null);
    setFileError(null);
    setAppPreviewError(null);
    setAppPreviewHtml("");
    setAppPreviewPath("");
    refreshTree();
  }, [block.id, refreshTree]);

  useEffect(() => {
    if (previewMode !== "app") {
      return;
    }
    if (appPreviewHtml || appPreviewError || loadingAppPreview) {
      return;
    }
    runLoadAppPreview();
  }, [appPreviewError, appPreviewHtml, loadingAppPreview, previewMode, runLoadAppPreview]);

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

  const appPreviewNode = useMemo(() => {
    if (loadingAppPreview) {
      return (
        <div className="h-full w-full flex items-center justify-center">
          <Spin />
        </div>
      );
    }
    if (appPreviewError) {
      return (
        <div className="p-3">
          <Alert type="error" showIcon message={appPreviewError} />
        </div>
      );
    }
    if (!appPreviewHtml.trim()) {
      return <Empty description="未获取到可预览的 HTML 内容" className="mt-12" />;
    }
    return (
      <div className="h-full min-h-0 flex flex-col bg-white">
        <Typography.Text type="secondary" className="px-3 py-2 border-b border-(--ant-color-border-secondary)">
          {appPreviewPath || "预览入口"}
        </Typography.Text>
        <iframe
          title="项目运行预览"
          srcDoc={appPreviewHtml}
          sandbox="allow-scripts"
          className="h-full min-h-0 w-full flex-1 border-0"
        />
      </div>
    );
  }, [appPreviewError, appPreviewHtml, appPreviewPath, loadingAppPreview]);

  const handleRefresh = useCallback(() => {
    if (previewMode === "app") {
      setAppPreviewError(null);
      setAppPreviewHtml("");
      setAppPreviewPath("");
      runLoadAppPreview();
      return;
    }
    refreshTree();
  }, [previewMode, refreshTree, runLoadAppPreview]);

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <header className="flex h-[60px] shrink-0 items-center justify-between gap-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container) px-3">
        <div className="min-w-0 flex items-center gap-2">
          <Typography.Text type="secondary">{block.title || "项目结构预览"}</Typography.Text>
          <div className="flex items-center gap-1">
            <Button
              size="small"
              type={previewMode === "files" ? "primary" : "text"}
              onClick={() => {
                setPreviewMode("files");
              }}
            >
              文件预览
            </Button>
            <Button
              size="small"
              type={previewMode === "app" ? "primary" : "text"}
              onClick={() => {
                setPreviewMode("app");
              }}
            >
              运行预览
            </Button>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            type="text"
            onClick={handleRefresh}
            icon={<ReloadOutlined />}
            loading={previewMode === "app" ? loadingAppPreview : loadingTree}
          />
          <Button type="text" onClick={onClose} icon={<CloseOutlined />} />
        </div>
      </header>
      <div className="flex-1 min-h-0 overflow-hidden">
        {previewMode === "app" ? (
          appPreviewNode
        ) : loadingTree ? (
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
