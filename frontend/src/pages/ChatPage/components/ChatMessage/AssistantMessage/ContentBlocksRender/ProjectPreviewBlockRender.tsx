import { useBlockPreview } from "@/pages/ChatPage/context/useBlockPreview";
import { Button } from "antd";
import React from "react";
import { useParams } from "react-router-dom";

const VIRTUAL_PATH_PREFIX = "/mnt/user-data/";

function createProjectPreviewBlockId() {
  return `cb_project_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

/** 将 present_files 的虚拟路径转换为会话相对路径（与文件树/文件内容接口一致）。 */
function toWorkspaceRelativePath(virtualPath: string): string {
  if (virtualPath.startsWith(VIRTUAL_PATH_PREFIX)) {
    return virtualPath.slice(VIRTUAL_PATH_PREFIX.length);
  }
  return virtualPath.replace(/^\/+/, "");
}

type Props = {
  filepaths: string[];
};

const ProjectPreviewBlockRender: React.FC<Props> = ({ filepaths }) => {
  const blockPreview = useBlockPreview();
  const params = useParams<{ conversationId: string }>();
  const conversationId = params.conversationId;

  if (!blockPreview || !conversationId) {
    return null;
  }

  const handleOpenPreview = () => {
    const lastFilepath = filepaths.at(-1);
    blockPreview.openPreview({
      id: createProjectPreviewBlockId(),
      type: "project",
      workspaceId: conversationId,
      title: "工作目录预览",
      selectedFilePath: lastFilepath ? toWorkspaceRelativePath(lastFilepath) : undefined,
    });
  };

  return (
    <div>
      <Button
        size="large"
        variant="solid"
        shape="round"
        style={{
          color: "#fff",
          background: "linear-gradient(180deg, #121519 0%, #0e1115 50%, #0a0c10 100%)",
        }}
        onClick={handleOpenPreview}
      >
        预览工作目录
      </Button>
    </div>
  );
};

export default React.memo(ProjectPreviewBlockRender);
