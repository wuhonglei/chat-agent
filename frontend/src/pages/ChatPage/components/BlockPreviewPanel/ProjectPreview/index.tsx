import { EventType, useEmitter } from "@/events";
import type { ProjectBlock } from "@/interfaces/contentBlock";
import type { WorkspaceTreeNode } from "@/services";
import { workspaceAPI } from "@/services";
import { downloadFileByUrl } from "@/utils/file";
import { CloseOutlined, DownloadOutlined, ExportOutlined, ReloadOutlined } from "@ant-design/icons";
import { Folder } from "@ant-design/x";
import { useRequest } from "ahooks";
import { Alert, Button, Segmented, Spin, Tooltip } from "antd";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { SelectedFile } from "./FilePreviewContent";
import FilePreviewContent from "./FilePreviewContent";
import { PROJECT_PREVIEW_DIRECTORY_ICONS } from "./file_icons";
import { useWorkspaceExcelWorkbook } from "./hooks";
import {
  filterEmptyDirectories,
  findNodeByPath,
  getAncestorDirPaths,
  getLanguageFromPath,
  getRequestErrorMessage,
  isDirectoryNode,
  isExcelPath,
  isNonTextWorkspaceFile,
  isPlaceholderPath,
  normalizeTreeNodes,
  replaceDirectoryChildren,
  toPathSegments,
} from "./utils";

export interface ProjectPreviewPanelProps {
  width: number;
  block: ProjectBlock;
  onClose: () => void;
}

type PreviewMode = "files" | "app";

const ProjectPreviewPanel: React.FC<ProjectPreviewPanelProps> = ({ width, block, onClose }) => {
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
  const revealedForRef = useRef<string | null>(null);
  const revealingRef = useRef(false);

  const folderSelectedFile = useMemo(
    () => (selectedFilePath ? toPathSegments(selectedFilePath) : undefined),
    [selectedFilePath]
  );

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
        setTreeData(normalizeTreeNodes(filterEmptyDirectories(res.treeData || [])));
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

  const isExcelFile = selectedFilePath ? isExcelPath(selectedFilePath) : false;
  const isNonTextFile = selectedFilePath ? isNonTextWorkspaceFile(selectedFilePath) : false;

  const { refresh: refreshSelectedFile, loading: loadingFile } = useRequest(
    async () => {
      const path = selectedFilePath!;
      const content = await workspaceAPI.getWorkspaceFileText(block.workspaceId, path);
      return { path, content };
    },
    {
      ready: !!selectedFilePath && !isNonTextFile,
      refreshDeps: [block.workspaceId, selectedFilePath, isNonTextFile],
      ...(selectedFilePath && !isNonTextFile
        ? { cacheKey: `workspace-file-content:${block.workspaceId}:${selectedFilePath}` }
        : {}),
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
        setFileError(getRequestErrorMessage(error, "文件内容加载失败"));
      },
    }
  );

  const {
    sheets: excelSheets,
    loading: loadingExcelFile,
    error: excelFileError,
    reload: reloadExcelFile,
  } = useWorkspaceExcelWorkbook(block.workspaceId, selectedFilePath, isExcelFile);

  const { run: runDownloadWorkspaceFile, loading: downloadingWorkspaceFile } = useRequest(
    async (filePath: string) => {
      const buffer = await workspaceAPI.getWorkspaceFileBuffer(block.workspaceId, filePath);
      const blob = new Blob([buffer]);
      const downloadUrl = URL.createObjectURL(blob);
      try {
        await downloadFileByUrl(downloadUrl, filePath.split("/").pop() || "file");
      } finally {
        URL.revokeObjectURL(downloadUrl);
      }
    },
    { manual: true }
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
    revealedForRef.current = null;
    revealingRef.current = false;
    setPreviewMode("files");
    setSelectedFilePath(null);
    setSelectedFile(null);
    setFileError(null);
    setAppPreviewError(null);
    setAppPreviewReloadKey(0);
    refreshTree();
  }, [block.id, refreshTree]);

  useEffect(() => {
    const targetPath = block.selectedFilePath;
    if (!targetPath || loadingTree) {
      return;
    }

    const revealKey = `${block.id}:${targetPath}`;
    if (revealedForRef.current === revealKey || revealingRef.current) {
      return;
    }

    const revealSelectedFile = async () => {
      revealingRef.current = true;
      try {
        const ancestorDirs = getAncestorDirPaths(targetPath);
        for (const dirPath of ancestorDirs) {
          await loadDirTreeIfNeeded(dirPath);
        }
        setExpandedPaths(ancestorDirs);
        setSelectedFilePath(targetPath);
        revealedForRef.current = revealKey;
      } finally {
        revealingRef.current = false;
      }
    };

    void revealSelectedFile();
  }, [block.id, block.selectedFilePath, loadingTree, loadDirTreeIfNeeded]);

  useEffect(() => {
    if (!selectedFilePath) {
      setSelectedFile(null);
      return;
    }
    if (isNonTextFile) {
      setSelectedFile(null);
      setFileError(null);
      return;
    }
    void refreshSelectedFile();
  }, [selectedFilePath, isNonTextFile, refreshSelectedFile]);

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
        if (isExcelPath(filePath)) {
          void reloadExcelFile();
          return;
        }
        if (isNonTextWorkspaceFile(filePath)) {
          return;
        }
        void refreshSelectedFile();
        return;
      }
      setSelectedFilePath(filePath);
    },
    [handleFolderClick, refreshSelectedFile, reloadExcelFile, selectedFilePath, treeData]
  );

  const selectedFileTitle = selectedFilePath?.split("/").pop() || selectedFilePath || "";

  const excelPreview = useMemo(() => {
    if (!selectedFilePath || !isExcelFile) {
      return null;
    }
    return {
      title: selectedFileTitle,
      sheets: excelSheets,
      loading: loadingExcelFile,
      error: excelFileError,
    };
  }, [excelFileError, excelSheets, isExcelFile, loadingExcelFile, selectedFilePath, selectedFileTitle]);

  const binaryFilePreview = useMemo(() => {
    if (!selectedFilePath || !isNonTextFile || isExcelFile) {
      return null;
    }
    return {
      title: selectedFileTitle,
      message: "该文件为二进制格式，暂不支持在线预览，可下载后本地查看。",
      downloading: downloadingWorkspaceFile,
      onDownload: () => {
        runDownloadWorkspaceFile(selectedFilePath);
      },
    };
  }, [
    downloadingWorkspaceFile,
    isExcelFile,
    isNonTextFile,
    runDownloadWorkspaceFile,
    selectedFilePath,
    selectedFileTitle,
  ]);

  const previewNode = (
    <FilePreviewContent
      width={width}
      loadingFile={loadingFile}
      fileError={fileError}
      selectedFile={selectedFile}
      excelPreview={excelPreview}
      binaryFile={binaryFilePreview}
    />
  );

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
              // {
              //   label: <Tooltip title="项目构建完成后才支持运行预览">运行预览</Tooltip>,
              //   value: "app",
              // },
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
            selectedFile={folderSelectedFile}
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
