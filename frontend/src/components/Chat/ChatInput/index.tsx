import classNames from "classnames";
import React, { useEffect, useRef } from "react";
import { Form, ConfigProvider, FormInstance, Button, GetRef } from "antd";
import { Sender } from "@ant-design/x";
import CustomButton from "@/components/common/CustomButton";
import ThinkModeIcon from "@/assets/svg/ThinkModeIcon.svg?react";
import SquareIcon from "@/assets/svg/SquareIcon.svg?react";
import { ChatInputFormValues } from "@/interfaces";
import ToolsSetting from "./ToolsSetting";
import { names } from "./constant";
import { isInputEnter } from "@/utils";
import { ArrowUpOutlined } from "@ant-design/icons";
import { useButtonState, useFormValuesChange } from "./hooks";
import { isButtonDisabled, isStreamingState } from "./util";
import { useMemoizedFn } from "ahooks";

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
  const senderRef = useRef<GetRef<typeof Sender>>(null);
  const { values, onValuesChange } = useFormValuesChange(form);

  useEffect(() => {
    senderRef.current?.focus();
  }, []);

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
      onStop?.();
      return;
    }

    handleSend();
  });

  return (
    <ConfigProvider theme={{ components: { Form: { itemMarginBottom: 0 } } }}>
      <Form
        form={form}
        layout="horizontal"
        style={style}
        onValuesChange={onValuesChange}
        className={classNames("flex flex-col gap-3", className)}
      >
        <Form.Item className="mr-0" name={names.content}>
          <Sender
            ref={senderRef}
            actions={false}
            onKeyDown={handlePressEnter}
            placeholder="给 DeepSeek 发送消息"
            autoSize={{ minRows: 2, maxRows: 6 }}
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
