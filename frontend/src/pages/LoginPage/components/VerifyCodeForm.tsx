import { SendSmsResponse } from "@/interfaces";
import { userAPI } from "@/services/user";
import { getRedirectUrl, jumpToLocation } from "@/utils";
import { MobileOutlined, SafetyOutlined } from "@ant-design/icons";
import { useCountDown, useRequest } from "ahooks";
import { App, Button, Form, Input, Select, Space } from "antd";
import React, { useState } from "react";
import { validatePhone, validateVerificationCode } from "../utils";

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
      message.success("短信验证码发送成功");
      setTargetDate(Date.now() + 60 * 1000); // 60秒后重新获取验证码
    },
  });

  const { run: loginWithVerificationCode, loading: verifySmsCodeLoading } =
    useRequest(userAPI.loginWithVerificationCode, {
      manual: true,
      onSuccess: () => {
        message.success("登录成功");
        setTimeout(() => {
          jumpToLocation(getRedirectUrl() || "/chat", true);
        }, 200);
      },
    });

  const handleSendCode = async () => {
    const values = await form.validateFields(["phoneNumber"]);
    const phoneNumberWithCountryCode = `+86 ${values.phoneNumber}`;
    sendSmsCode(phoneNumberWithCountryCode);
    form.resetFields(["verificationCode"]);
  };

  const handleSubmit = async (values: VerificationCodeFormValues) => {
    if (!smsResponse) {
      message.error("请先发送验证码");
      return;
    }

    loginWithVerificationCode({
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
        validateTrigger="blur"
        rules={[{ validator: (_, value) => validateVerificationCode(value) }]}
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
      <div className="text-black-tertiary mb-3">
        <span>未注册的手机号将自动注册.</span>
        <span className="ml-1">短信模板的主体为【腾讯云】</span>
      </div>
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
