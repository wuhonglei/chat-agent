import SquareIcon from "@/assets/svg/SquareIcon.svg?react";
import ThinkModeIcon from "@/assets/svg/ThinkModeIcon.svg?react";
import CustomButton from "@/components/common/CustomButton";
import { ChatInputConfig } from "@/interfaces";
import { ArrowUpOutlined, PaperClipOutlined } from "@ant-design/icons";
import { Button, Divider, Form } from "antd";
import React from "react";
import { ButtonState, names } from "../constant";
import { isButtonDisabled, isStreamingState } from "../util";
import ToolsSetting from "./ToolsSetting";

export interface ChatInputFooterProps {
  onOpenAttachmentPicker: () => void;
  values: ChatInputConfig;
  buttonState: ButtonState;
  onPrimaryClick: () => void;
}

const ChatInputFooter: React.FC<ChatInputFooterProps> = ({
  onOpenAttachmentPicker,
  values,
  buttonState,
  onPrimaryClick,
}) => {
  return (
    <div className="flex items-center gap-2 justify-between">
      <div className="flex items-center gap-2">
        <Form.Item hidden name={names.mcpAutoMode}>
          <span />
        </Form.Item>
        <Form.Item hidden name={names.sourceConfig}>
          <span />
        </Form.Item>
        <Button
          type="text"
          aria-label="文件上传"
          style={{ fontSize: 16 }}
          icon={<PaperClipOutlined />}
          onClick={onOpenAttachmentPicker}
        />
        <Divider orientation="vertical" style={{ margin: 0 }} />
        <Form.Item trigger="onClick" initialValue={false} valuePropName="active" name={names.thinkMode}>
          <CustomButton bordered={false} size="middle" icon={<ThinkModeIcon />} tooltip="先思考后回答, 解决推理问题">
            深度思考
          </CustomButton>
        </Form.Item>
        <ToolsSetting values={values} />
      </div>
      <div className="flex items-center gap-2">
        <Button
          size="middle"
          shape="round"
          type="primary"
          icon={isStreamingState(buttonState) ? <SquareIcon /> : <ArrowUpOutlined />}
          onClick={onPrimaryClick}
          disabled={isButtonDisabled(buttonState)}
        />
      </div>
    </div>
  );
};

export default React.memo(ChatInputFooter);
