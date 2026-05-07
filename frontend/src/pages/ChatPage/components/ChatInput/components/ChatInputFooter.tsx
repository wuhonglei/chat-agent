import SquareIcon from "@/assets/svg/SquareIcon.svg?react";
import ThinkModeIcon from "@/assets/svg/ThinkModeIcon.svg?react";
import CustomButton from "@/components/common/CustomButton";
import { useIsSmallScreen } from "@/hooks";
import { ChatInputConfig } from "@/interfaces";
import { useAppSelector } from "@/store/hooks";
import { ArrowUpOutlined, PaperClipOutlined } from "@ant-design/icons";
import { Button, Divider, Form, Select, Tooltip } from "antd";
import React from "react";
import { ButtonState, names } from "../constant";
import { isStreamingState } from "../util";
import ToolsSetting from "./ToolsSetting";
import { CHAT_ATTACHMENT_TOOLTIP, isButtonDisabled } from "./utils";

export interface ChatInputFooterProps {
  onOpenAttachmentPicker: () => void;
  values: ChatInputConfig;
  buttonState: ButtonState;
  onPrimaryClick: () => void;
  hasImageAttachment: boolean;
}

const ChatInputFooter: React.FC<ChatInputFooterProps> = ({
  onOpenAttachmentPicker,
  values,
  buttonState,
  onPrimaryClick,
  hasImageAttachment,
}) => {
  const isSmallScreen = useIsSmallScreen();
  const { models, loaded } = useAppSelector(state => state.models);

  const options = models.map(item => ({
    value: item.modelName,
    label: item.modelName,
    disabled: hasImageAttachment && !item.imageSupport,
  }));

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
            size="middle"
            icon={<ThinkModeIcon />}
            tooltip={isSmallScreen ? undefined : "先思考后回答, 解决推理问题"}
          >
            深度思考
          </CustomButton>
        </Form.Item>
        <ToolsSetting values={values} />
      </div>
      <div className="flex items-center gap-2">
        <Form.Item name={names.modelName}>
          <Select
            size="middle"
            options={options}
            loading={!loaded}
            style={{ minWidth: 160 }}
            disabled={!loaded || options.length === 0}
          />
        </Form.Item>
        <Button
          size="middle"
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
