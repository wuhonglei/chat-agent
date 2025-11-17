import React, { useState, useEffect, useRef } from "react";
import { Form, Input, Button, message, Select, Space } from "antd";
import { MobileOutlined, SafetyOutlined } from "@ant-design/icons";
import { useCountDown } from "ahooks";

export interface VerificationCodeFormValues {
  phone: string;
  code: string;
}

interface VerifyCodeFormProps {
  onFinish?: (values: VerificationCodeFormValues) => void | Promise<void>;
}

const VerifyCodeForm: React.FC<VerifyCodeFormProps> = ({ onFinish }) => {
  const [form] = Form.useForm<VerificationCodeFormValues>();
  const [targetDate, setTargetDate] = useState<number>();
  const [countdown] = useCountDown({ targetDate });

  const handleSendCode = async () => {
    try {
      const values = await form.validateFields(["phone"]);
      setTargetDate(Date.now() + 60 * 1000); // 60秒后重新获取验证码
    } catch (error) {
      console.error("发送验证码失败:", error);
    }
  };

  const handleSubmit = async (values: VerificationCodeFormValues) => {
    await onFinish?.(values);
  };

  return (
    <Form
      form={form}
      className="mt-6"
      layout="vertical"
      onFinish={handleSubmit}
    >
      <Form.Item
        name="phone"
        rules={[
          { required: true, message: "请输入手机号" },
          { pattern: /^1[3-9]\d{9}$/, message: "请输入有效的手机号" },
        ]}
      >
        <Input
          prefix={<MobileOutlined style={{ color: "var(--color-gray-400)" }} />}
          placeholder="请输入手机号"
          size="large"
          addonBefore={
            <Select defaultValue="+86" className="w-20" variant="borderless">
              <Select.Option value="+86">+86</Select.Option>
            </Select>
          }
        />
      </Form.Item>

      <Form.Item
        name="code"
        rules={[{ required: true, message: "请输入验证码" }]}
      >
        <Space.Compact className="w-full">
          <Input
            size="large"
            placeholder="请输入验证码"
            className="flex-1"
            prefix={
              <SafetyOutlined style={{ color: "var(--color-gray-400)" }} />
            }
          />
          <Button
            size="large"
            disabled={countdown > 0}
            onClick={handleSendCode}
            className="min-w-[120px]"
          >
            {countdown > 0 ? `${Math.floor(countdown / 1000)}秒` : "发送验证码"}
          </Button>
        </Space.Compact>
      </Form.Item>

      <Form.Item>
        <Button
          type="primary"
          htmlType="submit"
          size="large"
          block
          className="h-12 text-base font-medium"
        >
          登录
        </Button>
      </Form.Item>
    </Form>
  );
};

export default VerifyCodeForm;
