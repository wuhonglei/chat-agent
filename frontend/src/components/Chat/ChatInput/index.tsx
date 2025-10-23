import { Input, Form, ConfigProvider, FormInstance, Button } from "antd";
import classNames from "classnames";
import React from "react";
import styles from "./css/index.module.css";
import CustomButton from "@/components/common/CustomButton";
import ThinkModeIcon from "@/assets/svg/ThinkModeIcon.svg?react";
import SquareIcon from "@/assets/svg/SquareIcon.svg?react";
import { ChatInputFormValues } from "@/interfaces";
import ToolsSetting from "./ToolsSetting";
import { names } from "./constant";
import { isInputEnter } from "@/utils";
import { ArrowUpOutlined } from "@ant-design/icons";
import { useButtonState } from "./hooks";
import { isButtonDisabled, isStreamingState } from "./util";
import { useMemoizedFn } from "ahooks";

const { TextArea } = Input;

interface ChatInputProps {
  isLoading: boolean;
  isStreaming: boolean;
  className?: string;
  style?: React.CSSProperties;
  onSend: (values: ChatInputFormValues) => void;
  onStop: () => void;
  form: FormInstance<ChatInputFormValues>;
}

const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  onStop,
  isLoading,
  isStreaming,
  className,
  style,
  form,
}) => {
  const message = Form.useWatch(names.message, form);
  const buttonState = useButtonState(message, isStreaming);
  const handleSend = useMemoizedFn(() => {
    const values = form.getFieldsValue();
    const message = (values.message || "").trim();
    if (message) {
      onSend({
        ...values,
        message: message,
      });
      form.resetFields([names.message]);
    }
  });

  const handlePressEnter = useMemoizedFn(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (!isInputEnter(event)) {
        return;
      }
      event.preventDefault(); // 阻止默认行为, 避免产生新行
      handleSend();
    }
  );

  const handleBtnClick = useMemoizedFn(() => {
    // 停止流式传输
    if (isStreamingState(buttonState)) {
      onStop();
      return;
    }

    handleSend();
  });

  return (
    <ConfigProvider theme={{ components: { Form: { itemMarginBottom: 0 } } }}>
      <Form
        form={form}
        layout="horizontal"
        className={classNames(
          "flex flex-col gap-3 bg-white",
          styles["input-container"],
          className
        )}
        style={style}
      >
        <Form.Item
          className="mr-0"
          name={names.message}
          initialValue={undefined}
        >
          <TextArea
            autoFocus
            autoSize={{ minRows: 2.5 }}
            placeholder="给 DeepSeek 发送消息"
            onPressEnter={handlePressEnter}
            className={classNames(styles.input)}
          />
        </Form.Item>
        <div className="flex items-center gap-2 justify-between">
          {/* 左侧 */}
          <div className="flex items-center gap-2">
            <Form.Item
              trigger="onClick"
              initialValue={false}
              valuePropName="active"
              name={names.thinkMode}
            >
              <CustomButton
                size="middle"
                icon={<ThinkModeIcon />}
                tooltip="先思考后回答, 解决推理问题"
              >
                深度思考
              </CustomButton>
            </Form.Item>
            {/* 工具设置 */}
            <ToolsSetting />
          </div>
          {/* 右侧 */}
          <div className="flex items-center gap-2">
            <Button
              size="middle"
              shape="round"
              type="primary"
              icon={
                isStreamingState(buttonState) ? (
                  <SquareIcon />
                ) : (
                  <ArrowUpOutlined />
                )
              }
              onClick={handleBtnClick}
              disabled={isButtonDisabled(buttonState)}
            />
          </div>
        </div>
      </Form>
    </ConfigProvider>
  );
};

export default React.memo(ChatInput);
