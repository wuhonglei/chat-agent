import { Input, Form, ConfigProvider, FormInstance } from "antd";
import classNames from "classnames";
import React from "react";
import styles from "./index.module.css";
import CustomButton from "@/components/common/CustomButton";
import ThinkModeIcon from "@/assets/svg/ThinkModeIcon.svg?react";
import { ChatInputFormValues } from "@/types";
import ToolsSetting from "./ToolsSetting";
import { names } from "./constant";
import { isInputEnter } from "@/utils";

const { TextArea } = Input;

interface ChatInputProps {
  isLoading: boolean;
  isStreaming: boolean;
  className?: string;
  style?: React.CSSProperties;
  onSend: (values: ChatInputFormValues) => void;
  form: FormInstance<ChatInputFormValues>;
}

const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  isLoading,
  isStreaming,
  className,
  style,
  form,
}) => {
  const handleSend = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (!isInputEnter(event)) {
      return;
    }

    event.preventDefault(); // 阻止默认行为, 避免产生新行
    const values = form.getFieldsValue();
    const { message } = values;
    if (message.trim()) {
      onSend({
        ...values,
        message: message.trim(),
      });
      form.resetFields(["message"]);
    }
  };

  return (
    <div className={classNames("pb-4", className)} style={style}>
      <ConfigProvider theme={{ components: { Form: { itemMarginBottom: 0 } } }}>
        <Form
          form={form}
          layout="vertical"
          className={classNames(
            "flex flex-col gap-3",
            styles["input-container"]
          )}
        >
          <Form.Item name="message" initialValue={undefined}>
            <TextArea
              autoFocus
              placeholder="发消息"
              onPressEnter={handleSend}
              className={classNames(styles.input)}
              autoSize={{ minRows: 2, maxRows: 4 }}
            />
          </Form.Item>
          <div className="flex items-center gap-2">
            <Form.Item
              trigger="onClick"
              initialValue={false}
              valuePropName="active"
              name={names.thinkMode}
            >
              <CustomButton
                size="small"
                icon={<ThinkModeIcon />}
                tooltip="先思考后回答, 解决推理问题"
              >
                深度思考
              </CustomButton>
            </Form.Item>
            <ToolsSetting />
          </div>
        </Form>
      </ConfigProvider>
    </div>
  );
};

export default React.memo(ChatInput);
