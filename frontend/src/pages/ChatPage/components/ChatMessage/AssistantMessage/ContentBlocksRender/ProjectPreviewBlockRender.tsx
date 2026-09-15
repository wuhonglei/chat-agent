import {
  isHtmlPath,
  toWorkspaceRelativePath,
} from "@/pages/ChatPage/components/BlockPreviewPanel/ProjectPreview/utils";
import { useBlockPreview } from "@/pages/ChatPage/context/useBlockPreview";
import { Button } from "antd";
import { findLast } from "lodash-es";
import React from "react";
import { useParams } from "react-router-dom";

function createProjectPreviewBlockId() {
  return `cb_project_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
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
    const preferredFilepath = findLast(filepaths, isHtmlPath) ?? filepaths.at(-1);
    blockPreview.openPreview({
      id: createProjectPreviewBlockId(),
      type: "project",
      workspaceId: conversationId,
      title: "工作目录预览",
      selectedFilePath: preferredFilepath ? toWorkspaceRelativePath(preferredFilepath) : undefined,
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
