import React from "react";
import { Form, Input, Button } from "antd";
import { LockOutlined, MailOutlined } from "@ant-design/icons";

export interface PasswordFormValues {
  account: string;
  password: string;
}

interface PasswordFormProps {
  onFinish?: (values: PasswordFormValues) => void | Promise<void>;
}

const PasswordForm: React.FC<PasswordFormProps> = ({ onFinish }) => {
  const [form] = Form.useForm<PasswordFormValues>();

  // 验证账号格式（手机号或邮箱）
  const validateAccount = (_: unknown, value: string) => {
    if (!value) {
      return Promise.reject(new Error("请输入手机号或邮箱"));
    }
    const phoneRegex = /^1[3-9]\d{9}$/;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (phoneRegex.test(value) || emailRegex.test(value)) {
      return Promise.resolve();
    }
    return Promise.reject(new Error("请输入有效的手机号或邮箱地址"));
  };

  // 密码登录
  const handleSubmit = async (values: PasswordFormValues) => {
    if (onFinish) {
      await onFinish(values);
    }
  };

  return (
    <Form
      form={form}
      layout="vertical"
      className="mt-6"
      onFinish={handleSubmit}
    >
      <Form.Item name="account" rules={[{ validator: validateAccount }]}>
        <Input
          prefix={<MailOutlined style={{ color: "var(--color-gray-400)" }} />}
          placeholder="请输入手机号或邮箱"
          size="large"
        />
      </Form.Item>

      <Form.Item
        name="password"
        rules={[
          { required: true, message: "请输入密码" },
          { min: 6, message: "密码至少6位" },
        ]}
      >
        <Input.Password
          prefix={<LockOutlined style={{ color: "var(--color-gray-400)" }} />}
          placeholder="请输入密码"
          size="large"
        />
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

export default PasswordForm;
