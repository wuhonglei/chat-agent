import { Input, Form, ConfigProvider } from "antd";
import classNames from "classnames";
import React from "react";
import styles from "./index.module.css";
import CustomButton from "@/components/CustomButton";
import LogoSvg from "@/assets/svg/DsIcon.svg?react";
import { ChatInputFormValues } from "@/types";
import { GlobalOutlined } from "@ant-design/icons";
import { names } from "./constant";

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
    <div className={classNames("p-4", className)} style={style}>
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
              name={names.deepThink}
              trigger="onClick"
              initialValue={false}
              valuePropName="active"
            >
              <CustomButton
                size="small"
                icon={<LogoSvg />}
                tooltip="先思考后回答, 解决推理问题"
              >
                深度思考
              </CustomButton>
            </Form.Item>
            <Form.Item
              trigger="onClick"
              initialValue={false}
              valuePropName="active"
              name={names.webSearch}
            >
              <CustomButton
                size="small"
                icon={<GlobalOutlined />}
                tooltip="按需搜索网页"
              >
                联网搜索
              </CustomButton>
            </Form.Item>
          </div>
        </Form>
      </ConfigProvider>
    </div>
  );
};

export default ChatInput;
