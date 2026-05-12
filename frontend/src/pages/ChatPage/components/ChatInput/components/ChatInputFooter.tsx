import SquareIcon from "@/assets/svg/SquareIcon.svg?react";
import ThinkModeIcon from "@/assets/svg/ThinkModeIcon.svg?react";
import WebSiteIcon from "@/assets/svg/WebSiteIcon.svg?react";
import CustomButton from "@/components/common/CustomButton";
import { useIsSmallScreen } from "@/hooks";
import { ChatInputConfig } from "@/interfaces";
import { ArrowUpOutlined, PaperClipOutlined } from "@ant-design/icons";
import { Button, Divider, Form, Tooltip } from "antd";
import { SizeType } from "antd/es/config-provider/SizeContext";
import React from "react";
import { ButtonState, names } from "../constant";
import { isStreamingState } from "../util";
import ModelSelect from "./ModelSelect";
import ToolsSetting from "./ToolsSetting";
import { CHAT_ATTACHMENT_TOOLTIP, isButtonDisabled } from "./utils";

export interface ChatInputFooterProps {
  onOpenAttachmentPicker: () => void;
  values: ChatInputConfig;
  buttonState: ButtonState;
  onPrimaryClick: () => void;
  hasImageContext: boolean;
}

const ChatInputFooter: React.FC<ChatInputFooterProps> = ({
  onOpenAttachmentPicker,
  values,
  buttonState,
  onPrimaryClick,
  hasImageContext,
}) => {
  const isSmallScreen = useIsSmallScreen();
  const size = (isSmallScreen ? "small" : "middle") as SizeType;

  return (
    <div className="flex items-center gap-2 justify-between">
      <div className="flex items-center gap-2">
        <Form.Item hidden name={names.mcpAutoMode}>
          <span />
        </Form.Item>
        <Form.Item hidden name={names.sourceConfig}>
          <span />
        </Form.Item>
        <Tooltip title={isSmallScreen ? undefined : CHAT_ATTACHMENT_TOOLTIP}>
          <Button
            type="text"
            size={size}
            aria-label="文件上传"
            style={{ fontSize: 16 }}
            icon={<PaperClipOutlined />}
            onClick={onOpenAttachmentPicker}
          />
        </Tooltip>
        <Divider orientation="vertical" style={{ margin: 0 }} />
        <Form.Item trigger="onClick" initialValue={false} valuePropName="active" name={names.thinkMode}>
          <CustomButton
            bordered={false}
            size={size}
            icon={<ThinkModeIcon />}
            tooltip={isSmallScreen ? undefined : "先思考后回答, 解决推理问题"}
          >
            {isSmallScreen ? "" : "深度思考"}
          </CustomButton>
        </Form.Item>
        <ToolsSetting values={values} size={size} websiteBuildMode={Boolean(values.websiteBuildMode)} />
        <Form.Item trigger="onClick" initialValue={false} valuePropName="active" name={names.websiteBuildMode}>
          <CustomButton
            size={size}
            bordered={false}
            icon={<WebSiteIcon />}
            tooltip={isSmallScreen ? undefined : "启用 Agent Skills 网站构建模式"}
          >
            {isSmallScreen ? "" : "网站构建"}
          </CustomButton>
        </Form.Item>
      </div>
      <div className="flex items-center gap-2">
        <ModelSelect size={size} hasImageContext={hasImageContext} />
        <Button
          size={size}
          shape="round"
          type="primary"
          onClick={onPrimaryClick}
          disabled={isButtonDisabled(buttonState)}
          icon={isStreamingState(buttonState) ? <SquareIcon /> : <ArrowUpOutlined />}
        />
      </div>
    </div>
  );
};

export default React.memo(ChatInputFooter);
