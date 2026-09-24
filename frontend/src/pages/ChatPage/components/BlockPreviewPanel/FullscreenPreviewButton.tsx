import { emitPreviewFullscreen, EventType, getPreviewFullscreen, useEmitter } from "@/events";
import { FullscreenExitOutlined, FullscreenOutlined } from "@ant-design/icons";
import { Button, Tooltip } from "antd";
import React, { useState } from "react";

const FullscreenPreviewButton: React.FC = () => {
  const [fullscreen, setFullscreen] = useState(getPreviewFullscreen);

  useEmitter(EventType.ChangePreviewFullscreen, setFullscreen);

  const title = fullscreen ? "退出全屏预览" : "全屏预览";

  return (
    <Tooltip title={title}>
      <Button
        type="text"
        aria-label={title}
        icon={fullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
        onClick={() => emitPreviewFullscreen(!fullscreen)}
      />
    </Tooltip>
  );
};

export default React.memo(FullscreenPreviewButton);
