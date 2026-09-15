import { EventType, useEmitter } from "@/events";
import type { ProjectBlock } from "@/interfaces/contentBlock";
import type { PublishedSite, WorkspaceTreeNode } from "@/services";
import { sitesAPI, workspaceAPI } from "@/services";
import { downloadFileByUrl } from "@/utils/file";
import { getMessageInstance } from "@/utils/message";
import {
  CloseOutlined,
  CloudUploadOutlined,
  CopyOutlined,
  DisconnectOutlined,
  DownloadOutlined,
  ExportOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { Folder } from "@ant-design/x";
import { useRequest } from "ahooks";
import { Alert, Button, Form, Input, Modal, Segmented, Space, Spin, Tooltip } from "antd";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { SelectedFile } from "./FilePreviewContent";
import FilePreviewContent from "./FilePreviewContent";
import { PROJECT_PREVIEW_DIRECTORY_ICONS } from "./file_icons";
import { getPublishedHtmlPreviewUrl } from "./htmlPreview";
import { useWorkspaceExcelWorkbook, useWorkspaceImagePreview } from "./hooks";
import {
  SITE_OUTPUTS_DIR,
  filterEmptyDirectories,
  findNodeByPath,
  getAncestorDirPaths,
  getLanguageFromPath,
  getRequestErrorMessage,
  isDirectoryNode,
  isExcelPath,
  isImagePath,
  isNonTextWorkspaceFile,
  isPlaceholderPath,
  isPublishableSitePath,
  normalizeTreeNodes,
  outputsTreeHasAppDist,
  outputsTreeHasIndexHtml,
  replaceDirectoryChildren,
  resolvePublishSource,
  toPathSegments,
} from "./utils";

export interface ProjectPreviewPanelProps {
  width: number;
  block: ProjectBlock;
  onClose: () => void;
}

type PreviewMode = "files" | "app";

const SLUG_PATTERN = /^[a-z0-9-]{3,40}$/;

interface SlugInputProps {
  id?: string;
  value?: string;
  onChange?: React.ChangeEventHandler<HTMLInputElement>;
  status?: "" | "error" | "warning";
}

const SlugInput: React.FC<SlugInputProps> = ({ id, value, onChange, status }) => (
  <Space.Compact block>
    <Space.Addon>https://</Space.Addon>
    <Input
      id={id}
      className="flex-1"
      placeholder="resume-site"
      value={value}
      onChange={onChange}
      status={status}
    />
    <Space.Addon>.apps.wuhonglei.cn</Space.Addon>
  </Space.Compact>
);

function isLiveSite(site: PublishedSite | null): site is PublishedSite {
  return site != null && site.unpublishedAt == null;
}

const ProjectPreviewPanel: React.FC<ProjectPreviewPanelProps> = ({ width, block, onClose }) => {
  const [previewMode, setPreviewMode] = useState<PreviewMode>("files");
  const [publishOpen, setPublishOpen] = useState(false);
  const [publishForm] = Form.useForm<{ slug?: string }>();

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
    [selectedFilePath],
  );

  const { run: runLoadRootTree, loading: loadingTree } = useRequest(
    async () => {
      return await workspaceAPI.getWorkspaceFileTree(block.workspaceId, { path: "", depth: 1 });
    },
    {
      refreshDeps: [block.workspaceId],
      onBefore: () => {
        setTreeError(null);
      },
      onSuccess: (res) => {
        setTreeData(normalizeTreeNodes(filterEmptyDirectories(res.treeData || [])));
        setLoadedDirPaths(new Set([""]));
      },
      onError: (error) => {
        setTreeError(error instanceof Error ? error.message : "文件树加载失败");
      },
    },
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
      onError: (error) => {
        setTreeError(error instanceof Error ? error.message : "子目录加载失败");
      },
      onSuccess: (res, params) => {
        const dirPath = params[0] || "";
        setTreeData((prev) =>
          replaceDirectoryChildren(prev, dirPath, normalizeTreeNodes(res.treeData || [], dirPath)),
        );
        setLoadedDirPaths((prev) => {
          const next = new Set(prev);
          next.add(dirPath);
          return next;
        });
      },
    },
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
    [loadedDirPaths, runLoadDirTree],
  );

  const isExcelFile = selectedFilePath ? isExcelPath(selectedFilePath) : false;
  const isImageFile = selectedFilePath ? isImagePath(selectedFilePath) : false;
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
      onSuccess: (res) => {
        setSelectedFile({
          path: res.path,
          title: res.path.split("/").pop() || res.path,
          content: res.content || "",
          language: getLanguageFromPath(res.path),
        });
      },
      onError: (error) => {
        setFileError(getRequestErrorMessage(error, "文件内容加载失败"));
      },
    },
  );

  const {
    sheets: excelSheets,
    loading: loadingExcelFile,
    error: excelFileError,
    reload: reloadExcelFile,
  } = useWorkspaceExcelWorkbook(block.workspaceId, selectedFilePath, isExcelFile);

  const {
    url: imagePreviewUrl,
    loading: loadingImageFile,
    error: imageFileError,
    reload: reloadImageFile,
  } = useWorkspaceImagePreview(block.workspaceId, selectedFilePath, isImageFile);

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
    { manual: true },
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
      onError: (error) => {
        setTreeError(error instanceof Error ? error.message : "下载失败，请稍后重试");
      },
    },
  );

  const {
    data: conversationSite,
    loading: loadingSite,
    refresh: refreshSite,
  } = useRequest(
    async () => {
      const sites = await sitesAPI.listMine();
      return sites.find((item) => item.conversationId === block.workspaceId) ?? null;
    },
    {
      refreshDeps: [block.workspaceId],
    },
  );
  const liveSite = isLiveSite(conversationSite ?? null) ? conversationSite : null;
  const unpublishedSite =
    conversationSite != null && conversationSite.unpublishedAt != null ? conversationSite : null;

  const hasOutputsDir = treeData.some((node) => (node.fullPath || node.path) === SITE_OUTPUTS_DIR);
  const { data: outputsLayout, refresh: refreshOutputsLayout } = useRequest(
    async () => {
      const res = await workspaceAPI.getWorkspaceFileTree(block.workspaceId, {
        path: SITE_OUTPUTS_DIR,
        depth: 1,
      });
      const nodes = res.treeData || [];
      return {
        hasAppDist: outputsTreeHasAppDist(nodes),
        hasOutputsIndex: outputsTreeHasIndexHtml(nodes),
      };
    },
    {
      ready: hasOutputsDir,
      refreshDeps: [block.workspaceId, hasOutputsDir],
    },
  );
  const hasAppDistDir = outputsLayout?.hasAppDist === true;
  const hasOutputsIndexHtml = outputsLayout?.hasOutputsIndex === true;
  const publishSource = resolvePublishSource({
    hasAppDist: hasAppDistDir,
    hasOutputsIndex: hasOutputsIndexHtml,
  });
  const showSiteUi =
    conversationSite != null ||
    hasAppDistDir ||
    hasOutputsIndexHtml ||
    isPublishableSitePath(block.selectedFilePath);
  const activePreviewMode: PreviewMode = showSiteUi ? previewMode : "files";

  const { run: runPublish, loading: publishing } = useRequest(
    async (slug?: string) => {
      return await sitesAPI.publish({
        conversationId: block.workspaceId,
        source: publishSource,
        slug,
      });
    },
    {
      manual: true,
      onSuccess: (site) => {
        setPublishOpen(false);
        publishForm.resetFields();
        void refreshSite();
        getMessageInstance().success(`已发布：${site.url}`);
        setPreviewMode("app");
      },
      onError: (error) => {
        const msg = getRequestErrorMessage(error, "发布失败");
        publishForm.setFields([{ name: "slug", errors: [msg] }]);
      },
    },
  );

  const { run: runRepublish, loading: republishing } = useRequest(
    async (slug: string) => {
      return await sitesAPI.republish(slug, { source: publishSource });
    },
    {
      manual: true,
      onSuccess: (site) => {
        void refreshSite();
        setAppPreviewReloadKey((prev) => prev + 1);
        getMessageInstance().success(`已重新发布：${site.url}`);
      },
    },
  );

  const { run: runUnpublish, loading: unpublishing } = useRequest(
    async (slug: string) => {
      return await sitesAPI.unpublish(slug);
    },
    {
      manual: true,
      onSuccess: () => {
        void refreshSite();
        getMessageInstance().success("站点已下线");
      },
    },
  );
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

  useEmitter(EventType.WorkspaceTreeRefresh, (payload) => {
    if (payload.workspaceId === block.workspaceId) {
      refreshTree();
      refreshOutputsLayout();
    }
  });

  const handleExpandedPathsChange = useCallback(
    (paths: string[]) => {
      setExpandedPaths(paths);
      for (const path of paths) {
        void loadDirTreeIfNeeded(path);
      }
    },
    [loadDirTreeIfNeeded],
  );

  const handleFolderClick = useCallback(
    async (folderPath: string) => {
      setFileError(null);
      const alreadyExpanded = expandedPaths.includes(folderPath);
      if (alreadyExpanded) {
        setExpandedPaths((prev) => prev.filter((path) => path !== folderPath));
        return;
      }

      try {
        await loadDirTreeIfNeeded(folderPath);
      } catch {
        return;
      }
      setExpandedPaths((prev) => (prev.includes(folderPath) ? prev : [...prev, folderPath]));
    },
    [expandedPaths, loadDirTreeIfNeeded],
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
        if (isImagePath(filePath)) {
          void reloadImageFile();
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
    [
      handleFolderClick,
      refreshSelectedFile,
      reloadExcelFile,
      reloadImageFile,
      selectedFilePath,
      treeData,
    ],
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
  }, [
    excelFileError,
    excelSheets,
    isExcelFile,
    loadingExcelFile,
    selectedFilePath,
    selectedFileTitle,
  ]);

  const imagePreview = useMemo(() => {
    if (!selectedFilePath || !isImageFile) {
      return null;
    }
    return {
      title: selectedFileTitle,
      url: imagePreviewUrl,
      loading: loadingImageFile,
      error: imageFileError,
    };
  }, [
    imageFileError,
    imagePreviewUrl,
    isImageFile,
    loadingImageFile,
    selectedFilePath,
    selectedFileTitle,
  ]);

  const binaryFilePreview = useMemo(() => {
    if (!selectedFilePath || !isNonTextFile || isExcelFile || isImageFile) {
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
    isImageFile,
    isNonTextFile,
    runDownloadWorkspaceFile,
    selectedFilePath,
    selectedFileTitle,
  ]);

  const textSelectedFile =
    selectedFilePath && !isNonTextFile && selectedFile?.path === selectedFilePath
      ? selectedFile
      : null;
  const textFileError = selectedFilePath && !isNonTextFile ? fileError : null;
  const publishedHtmlPreviewUrl = getPublishedHtmlPreviewUrl(selectedFilePath, liveSite?.url);

  const previewNode = (
    <FilePreviewContent
      width={width}
      loadingFile={loadingFile}
      fileError={textFileError}
      selectedFile={textSelectedFile}
      excelPreview={excelPreview}
      imagePreview={imagePreview}
      binaryFile={binaryFilePreview}
      publishedPreviewUrl={publishedHtmlPreviewUrl}
    />
  );

  const handleOpenPublish = useCallback(() => {
    if (unpublishedSite) {
      runPublish();
      return;
    }
    publishForm.resetFields();
    setPublishOpen(true);
  }, [publishForm, runPublish, unpublishedSite]);

  const appPreviewNode = useMemo(() => {
    if (appPreviewError) {
      return (
        <div className="p-3">
          <Alert type="error" showIcon message={appPreviewError} />
        </div>
      );
    }
    if (loadingSite) {
      return (
        <div className="h-full w-full flex items-center justify-center">
          <Spin />
        </div>
      );
    }
    if (!liveSite) {
      return (
        <div className="h-full min-h-0 flex flex-col items-center justify-center gap-3 p-6 text-center">
          <Alert
            type="info"
            showIcon
            message="发布后可通过域名预览"
            description="把当前会话的静态站点（outputs/app-dist 或 outputs/index.html）发布到子域名后，多页路由、图片和字体才能正常加载。"
          />
          <Button type="primary" icon={<CloudUploadOutlined />} onClick={handleOpenPublish}>
            {unpublishedSite ? "重新上线" : "发布站点"}
          </Button>
        </div>
      );
    }
    const previewUrl = `${liveSite.url}${liveSite.url.includes("?") ? "&" : "?"}t=${appPreviewReloadKey}`;
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
            setAppPreviewError("运行预览加载失败，请确认站点是否仍在线");
          }}
          className="h-full min-h-0 w-full flex-1 border-0"
        />
      </div>
    );
  }, [
    appPreviewError,
    appPreviewReloadKey,
    handleOpenPublish,
    liveSite,
    loadingSite,
    unpublishedSite,
  ]);

  const handleRefresh = useCallback(() => {
    if (activePreviewMode === "app") {
      setAppPreviewError(null);
      setAppPreviewReloadKey((prev) => prev + 1);
      void refreshSite();
      return;
    }
    refreshTree();
    refreshOutputsLayout();
  }, [activePreviewMode, refreshOutputsLayout, refreshSite, refreshTree]);

  const handleOpenAppPreviewInNewPage = useCallback(() => {
    if (!liveSite) {
      return;
    }
    window.open(liveSite.url, "_blank", "noopener,noreferrer");
  }, [liveSite]);

  const handleCopySiteUrl = useCallback(async () => {
    if (!liveSite) {
      return;
    }
    await navigator.clipboard.writeText(liveSite.url);
    getMessageInstance().success("链接已复制");
  }, [liveSite]);

  const handleConfirmPublish = useCallback(async () => {
    const values = await publishForm.validateFields();
    const slug = values.slug?.trim();
    runPublish(slug || undefined);
  }, [publishForm, runPublish]);

  const handleUnpublish = useCallback(() => {
    if (!liveSite) {
      return;
    }
    Modal.confirm({
      title: "下线该站点？",
      content: "下线后公网链接立即 404，同会话再次发布会复用原 slug。",
      okText: "下线",
      okButtonProps: { danger: true },
      onOk: () => runUnpublish(liveSite.slug),
    });
  }, [liveSite, runUnpublish]);

  const handleDownloadWorkspaceZip = useCallback(() => {
    setTreeError(null);
    runDownloadWorkspaceZip();
  }, [runDownloadWorkspaceZip]);

  const siteBusy = publishing || republishing || unpublishing || loadingSite;

  return (
    <section className="h-full min-h-0 flex flex-col border-l border-(--ant-color-border-secondary) bg-(--ant-color-bg-layout)">
      <header className="flex h-15 shrink-0 items-center justify-between gap-2 border-b border-(--ant-color-border-secondary) bg-(--ant-color-bg-container) px-3">
        <div className="min-w-0 flex items-center gap-2">
          {showSiteUi ? (
            <Segmented<PreviewMode>
              size="small"
              value={activePreviewMode}
              onChange={setPreviewMode}
              options={[
                { label: "文件预览", value: "files" },
                { label: "运行预览", value: "app" },
              ]}
            />
          ) : null}
        </div>
        <div className="flex items-center gap-1">
          {showSiteUi ? (
            liveSite ? (
              <>
                <Tooltip title="复制公网链接">
                  <Button
                    type="text"
                    icon={<CopyOutlined />}
                    onClick={() => void handleCopySiteUrl()}
                  />
                </Tooltip>
                <Tooltip title="重新发布当前产物">
                  <Button
                    type="text"
                    icon={<CloudUploadOutlined />}
                    loading={republishing}
                    disabled={siteBusy}
                    onClick={() => runRepublish(liveSite.slug)}
                  />
                </Tooltip>
                <Tooltip title="下线">
                  <Button
                    type="text"
                    danger
                    icon={<DisconnectOutlined />}
                    loading={unpublishing}
                    disabled={siteBusy}
                    onClick={handleUnpublish}
                  />
                </Tooltip>
              </>
            ) : (
              <Tooltip title={unpublishedSite ? "重新上线" : "发布到域名"}>
                <Button
                  type="text"
                  icon={<CloudUploadOutlined />}
                  loading={publishing}
                  disabled={siteBusy}
                  onClick={handleOpenPublish}
                />
              </Tooltip>
            )
          ) : null}
          {activePreviewMode === "files" ? (
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
          {activePreviewMode === "app" && liveSite ? (
            <Tooltip title="在新页面打开">
              <Button
                type="text"
                icon={<ExportOutlined />}
                onClick={handleOpenAppPreviewInNewPage}
              />
            </Tooltip>
          ) : null}
          <Button
            type="text"
            onClick={handleRefresh}
            icon={<ReloadOutlined />}
            loading={activePreviewMode === "app" ? loadingSite : loadingTree}
          />
          <Button type="text" onClick={onClose} icon={<CloseOutlined />} />
        </div>
      </header>
      <div className="flex-1 min-h-0 overflow-hidden">
        {activePreviewMode === "app" ? (
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
            onFileClick={(filePath) => {
              handleFileClick(filePath);
            }}
            onFolderClick={(folderPath) => {
              void handleFolderClick(folderPath);
            }}
            previewRender={previewNode}
            directoryIcons={PROJECT_PREVIEW_DIRECTORY_ICONS}
          />
        )}
      </div>
      <Modal
        centered
        open={publishOpen}
        title="发布站点"
        okText="发布"
        confirmLoading={publishing}
        onCancel={() => setPublishOpen(false)}
        onOk={() => void handleConfirmPublish()}
      >
        <p className="mb-3 text-(--ant-color-text-secondary)">
          将当前会话的静态站点（<code>outputs/app-dist</code> 或 <code>outputs/index.html</code>
          ）发布到子域名。留空 slug 则由服务端生成。
        </p>
        <Form form={publishForm} layout="vertical">
          <Form.Item
            name="slug"
            label="自定义链接（可选）"
            extra="3–40 位小写字母、数字和连字符，例如 resume-site"
            rules={[
              {
                validator: async (_, value: string | undefined) => {
                  const slug = value?.trim();
                  if (!slug) {
                    return;
                  }
                  if (!SLUG_PATTERN.test(slug)) {
                    throw new Error("slug 仅允许 3–40 位小写字母、数字和连字符");
                  }
                },
              },
            ]}
          >
            <SlugInput />
          </Form.Item>
        </Form>
      </Modal>
    </section>
  );
};

export default React.memo(ProjectPreviewPanel);
