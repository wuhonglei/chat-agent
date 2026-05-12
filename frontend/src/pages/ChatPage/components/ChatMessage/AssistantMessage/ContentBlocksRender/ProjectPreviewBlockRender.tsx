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
        size="large"
        variant="solid"
        shape="round"
        style={{
          color: "#fff",
          background: "linear-gradient(180deg, #121519 0%, #0e1115 50%, #0a0c10 100%)",
        }}
        onClick={() =>
          blockPreview.openPreview({
            id: createProjectPreviewBlockId(),
            type: "project",
            workspaceId: conversationId,
            title: "项目结构预览",
          })
        }
      >
        预览项目结构
      </Button>
    </div>
  );
};

export default React.memo(ProjectPreviewBlockRender);
