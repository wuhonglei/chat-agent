import { useBlockPreview } from "@/pages/ChatPage/context/BlockPreviewContext";
import { Button } from "antd";
import React from "react";
import { useParams } from "react-router-dom";

function createProjectPreviewBlockId() {
  return `cb_project_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

const ProjectPreviewBlockRender: React.FC = () => {
  const blockPreview = useBlockPreview();
  const params = useParams<{ conversationId: string }>();
  const conversationId = params.conversationId;

  if (!blockPreview || !conversationId) {
    return null;
  }

  return (
    <div>
      <Button
        size="small"
        onClick={() =>
          blockPreview.openPreview({
            id: createProjectPreviewBlockId(),
            type: "project",
            workspaceId: conversationId,
            title: "项目结构预览",
          })
        }
      >
        打开项目结构预览
      </Button>
    </div>
  );
};

export default React.memo(ProjectPreviewBlockRender);
