import { Input, Switch, Form, ConfigProvider } from "antd";
import classNames from "classnames";
import React from "react";
import styles from "./index.module.css";
import CustomButton from "@/components/CustomButton";
import LogoSvg from "@/assets/svg/DsIcon.svg?react";
import { ChatInputFormValues } from "@/types";

const { TextArea } = Input;

interface ChatInputProps {
  isLoading: boolean;
  isStreaming: boolean;
  className?: string;
  style?: React.CSSProperties;
  onSend: (values: ChatInputFormValues) => void;
}

const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  isLoading,
  isStreaming,
  className,
  style,
}) => {
  const [form] = Form.useForm<ChatInputFormValues>();

  const handleSend = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // 只有按下回车键才发送, 组合键shift+enter不发送
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }

    // 中文输入法下，按下回车键不发送
    if (event.nativeEvent.isComposing) {
      return;
    }

    event.preventDefault();
    const values = form.getFieldsValue();
    if (values.message.trim()) {
      onSend(values);
      form.resetFields(["message"]);
    }
  };

  const handleValuesChange = (changedFields: any, allFields: any) => {
    console.log(changedFields, allFields);
  };

  return (
    <div className={classNames("p-4", className)} style={style}>
      <ConfigProvider theme={{ components: { Form: { itemMarginBottom: 0 } } }}>
        <Form
          form={form}
          layout="vertical"
          onValuesChange={handleValuesChange}
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
              name="thinkMode"
              trigger="onClick"
              initialValue={false}
              valuePropName="active"
            >
              <CustomButton icon={<LogoSvg />}>深度思考</CustomButton>
            </Form.Item>
            <Form.Item
              initialValue={false}
              valuePropName="checked"
              name="useKnowledgeBase"
            >
              <Switch />
            </Form.Item>
          </div>
        </Form>
      </ConfigProvider>
    </div>
  );
};

export default ChatInput;
