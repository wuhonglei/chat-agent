import { EventType, useEmitter } from "@/events";
import type { ProjectBlock } from "@/interfaces/contentBlock";
import type { WorkspaceTreeNode } from "@/services";
import { workspaceAPI } from "@/services";
import { downloadFileByUrl } from "@/utils/file";
import { CloseOutlined, DownloadOutlined, ExportOutlined, ReloadOutlined } from "@ant-design/icons";
import { Folder } from "@ant-design/x";
import Editor from "@monaco-editor/react";
import { useRequest } from "ahooks";
import { Alert, Button, Empty, Segmented, Spin, Tooltip, Typography } from "antd";
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
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [appPreviewError, setAppPreviewError] = useState<string | null>(null);
  const [appPreviewReloadKey, setAppPreviewReloadKey] = useState(0);

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

  const { refresh: refreshSelectedFile, loading: loadingFile } = useRequest(
    async () => {
      return await workspaceAPI.getWorkspaceFileContent(block.workspaceId, selectedFilePath!);
    },
    {
      ready: !!selectedFilePath,
      refreshDeps: [block.workspaceId, selectedFilePath],
      ...(selectedFilePath ? { cacheKey: `workspace-file-content:${block.workspaceId}:${selectedFilePath}` } : {}),
      staleTime: 0,
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

  const { run: runDownloadWorkspaceZip, loading: loadingWorkspaceZip } = useRequest(
    async () => {
      const workspaceZip = await workspaceAPI.downloadWorkspaceZip(block.workspaceId);
      const downloadUrl = URL.createObjectURL(workspaceZip);
      try {
        await downloadFileByUrl(downloadUrl, `${block.workspaceId}.zip`);
      } finally {
        URL.revokeObjectURL(downloadUrl);
      }
    },
    {
      manual: true,
      onError: error => {
        setTreeError(error instanceof Error ? error.message : "下载失败，请稍后重试");
      },
    }
  );

  useEffect(() => {
    setPreviewMode("files");
    setSelectedFilePath(null);
    setSelectedFile(null);
    setFileError(null);
    setAppPreviewError(null);
    setAppPreviewReloadKey(0);
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
      if (filePath === selectedFilePath) {
        void refreshSelectedFile();
        return;
      }
      setSelectedFilePath(filePath);
    },
    [handleFolderClick, refreshSelectedFile, selectedFilePath, treeData]
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
    if (appPreviewError) {
      return (
        <div className="p-3">
          <Alert type="error" showIcon message={appPreviewError} />
        </div>
      );
    }
    const previewBaseUrl = workspaceAPI.getWorkspacePreviewContentUrl(block.workspaceId);
    const previewUrl = `${previewBaseUrl}${previewBaseUrl.includes("?") ? "&" : "?"}t=${appPreviewReloadKey}`;
    return (
      <div className="h-full min-h-0 flex flex-col bg-white">
        <iframe
          title="项目运行预览"
          src={previewUrl}
          sandbox="allow-scripts allow-same-origin allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox allow-downloads allow-pointer-lock allow-presentation allow-top-navigation-by-user-activation"
          onLoad={() => {
            setAppPreviewError(null);
          }}
          onError={() => {
            setAppPreviewError("运行预览加载失败，请确认构建产物是否已生成");
          }}
          className="h-full min-h-0 w-full flex-1 border-0"
        />
      </div>
    );
  }, [appPreviewError, appPreviewReloadKey, block.workspaceId]);

  const handleRefresh = useCallback(() => {
    if (previewMode === "app") {
      setAppPreviewError(null);
      setAppPreviewReloadKey(prev => prev + 1);
      return;
    }
    refreshTree();
  }, [previewMode, refreshTree]);

  const handleOpenAppPreviewInNewPage = useCallback(() => {
    const previewUrl = workspaceAPI.getWorkspacePreviewContentUrl(block.workspaceId);
    window.open(previewUrl, "_blank", "noopener,noreferrer");
  }, [block.workspaceId]);

  const handleDownloadWorkspaceZip = useCallback(() => {
    setTreeError(null);
    runDownloadWorkspaceZip();
  }, [runDownloadWorkspaceZip]);

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <header className="flex h-[60px] shrink-0 items-center justify-between gap-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container) px-3">
        <div className="min-w-0 flex items-center gap-2">
          <Segmented<PreviewMode>
            size="small"
            value={previewMode}
            onChange={setPreviewMode}
            options={[
              { label: "文件预览", value: "files" },
              {
                label: <Tooltip title="项目构建完成后才支持运行预览">运行预览</Tooltip>,
                value: "app",
              },
            ]}
          />
        </div>
        <div className="flex items-center gap-1">
          {previewMode === "files" ? (
            <Tooltip title="下载项目（zip）">
              <Button
                type="text"
                icon={<DownloadOutlined />}
                onClick={handleDownloadWorkspaceZip}
                loading={loadingWorkspaceZip}
                disabled={loadingTree}
              />
            </Tooltip>
          ) : null}
          {previewMode === "app" ? (
            <Tooltip title="在新页面打开">
              <Button type="text" icon={<ExportOutlined />} onClick={handleOpenAppPreviewInNewPage} />
            </Tooltip>
          ) : null}
          <Button
            type="text"
            onClick={handleRefresh}
            icon={<ReloadOutlined />}
            loading={previewMode === "app" ? false : loadingTree}
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
