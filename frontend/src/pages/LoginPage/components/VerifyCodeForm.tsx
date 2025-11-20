import React, { useState } from "react";
import { Form, Input, Button, Select, Space } from "antd";
import { MobileOutlined, SafetyOutlined } from "@ant-design/icons";
import { useCountDown } from "ahooks";
import { validatePhone } from "../utils";
import { useRequest } from "ahooks";
import { userAPI } from "@/services/user";
import { App } from "antd";
import { SendSmsResponse } from "@/interfaces";
import { getRedirectUrl, jumpToLocation } from "@/utils";

export interface VerificationCodeFormValues {
  phoneNumber: string;
  verificationCode: string;
}

interface VerifyCodeFormProps {
  onFinish?: (values: VerificationCodeFormValues) => void | Promise<void>;
}

const VerifyCodeForm: React.FC<VerifyCodeFormProps> = () => {
  const [form] = Form.useForm<VerificationCodeFormValues>();
  const [targetDate, setTargetDate] = useState<number>();
  const [countdown] = useCountDown({ targetDate });
  const { message } = App.useApp();

  const {
    run: sendSmsCode,
    loading: sendSmsCodeLoading,
    data: smsResponse,
  } = useRequest(userAPI.sendVerificationCode, {
    manual: true,
    onSuccess: () => {
      message.success("发送验证码成功");
      setTargetDate(Date.now() + 60 * 1000); // 60秒后重新获取验证码
    },
  });

  const { run: verifySmsCode, loading: verifySmsCodeLoading } = useRequest(
    userAPI.verifyVerificationCode,
    {
      manual: true,
      onSuccess: () => {
        message.success("登录成功");
        setTimeout(() => {
          jumpToLocation(getRedirectUrl() || "/chat", true);
        }, 200);
      },
    }
  );

  const handleSendCode = async () => {
    const values = await form.validateFields(["phoneNumber"]);
    const phoneNumberWithCountryCode = `+86 ${values.phoneNumber}`;
    sendSmsCode(phoneNumberWithCountryCode);
    form.resetFields(["verificationCode"]);
  };

  const handleSubmit = async (values: VerificationCodeFormValues) => {
    verifySmsCode({
      ...(smsResponse as SendSmsResponse),
      verificationCode: values.verificationCode,
    });
  };

  return (
    <Form
      form={form}
      className="mt-6"
      layout="vertical"
      onFinish={handleSubmit}
    >
      <Form.Item
        name="phoneNumber"
        rules={[{ validator: (_, value) => validatePhone(value) }]}
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
        name="verificationCode"
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
            onClick={handleSendCode}
            className="min-w-[120px]"
            disabled={countdown > 0 || sendSmsCodeLoading}
          >
            {countdown > 0 ? `${Math.floor(countdown / 1000)}秒` : "发送验证码"}
          </Button>
        </Space.Compact>
      </Form.Item>

      <Form.Item>
        <Button
          block
          size="large"
          type="primary"
          htmlType="submit"
          loading={verifySmsCodeLoading}
          className="h-12 text-base font-medium"
        >
          登录
        </Button>
      </Form.Item>
    </Form>
  );
};

export default VerifyCodeForm;
