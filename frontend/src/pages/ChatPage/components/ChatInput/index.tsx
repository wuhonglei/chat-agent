import SquareIcon from "@/assets/svg/SquareIcon.svg?react";
import ThinkModeIcon from "@/assets/svg/ThinkModeIcon.svg?react";
import CustomButton from "@/components/common/CustomButton";
import { ChatInputFormValues } from "@/interfaces";
import { isInputEnter } from "@/utils";
import { ArrowUpOutlined } from "@ant-design/icons";
import { Sender } from "@ant-design/x";
import { useMemoizedFn } from "ahooks";
import { Button, ConfigProvider, Form, FormInstance } from "antd";
import classNames from "classnames";
import React from "react";
import ToolsSetting from "./ToolsSetting";
import { names } from "./constant";
import styles from "./css/index.module.css";
import { useButtonState, useFormValuesChange } from "./hooks";
import { isButtonDisabled, isStreamingState } from "./util";

interface ChatInputProps {
  isStreaming?: boolean;
  className?: string;
  style?: React.CSSProperties;
  onSend: (values: ChatInputFormValues) => void;
  onStop?: () => void;
  form: FormInstance<ChatInputFormValues>;
}

const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  onStop,
  isStreaming,
  className,
  style,
  form,
}) => {
  const content = Form.useWatch(names.content, form);
  const buttonState = useButtonState(content, isStreaming);
  const { values, onValuesChange } = useFormValuesChange(form);

  const handleSend = useMemoizedFn(() => {
    const values = form.getFieldsValue();
    const content = (values.content || "").trim();
    if (content) {
      onSend({
        ...values,
        content,
      });
      form.resetFields([names.content]);
    }
  });

  const handlePressEnter = useMemoizedFn(
    (event: React.KeyboardEvent<Element>) => {
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
      onStop?.();
      return;
    }

    handleSend();
  });

  return (
    <ConfigProvider theme={{ components: { Form: { itemMarginBottom: 0 } } }}>
      <Form
        form={form}
        style={style}
        layout="horizontal"
        onValuesChange={onValuesChange}
        className={classNames("flex flex-col gap-3", className)}
      >
        <Form.Item name={names.content}>
          <Sender
            suffix={false}
            onKeyDown={handlePressEnter}
            className={styles.container}
            placeholder="给 DeepSeek 发送消息"
            autoSize={{ minRows: 2, maxRows: 6 }}
            style={{ borderColor: "#d9d9d9", boxShadow: "none" }}
            footer={() => {
              return (
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
                    <Form.Item hidden name={names.mcpAutoMode}>
                      <span />
                    </Form.Item>
                    <Form.Item hidden name={names.sourceConfig}>
                      <span />
                    </Form.Item>
                    <ToolsSetting values={values} />
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
              );
            }}
          />
        </Form.Item>
      </Form>
    </ConfigProvider>
  );
};

export default React.memo(ChatInput);
