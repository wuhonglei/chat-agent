import { SendSmsResponse } from "@/interfaces";
import { userAPI } from "@/services/user";
import { getRedirectUrl, jumpToLocation, reportError } from "@/utils";
import { SafetyOutlined } from "@ant-design/icons";
import { useCountDown, useLocalStorageState, useRequest } from "ahooks";
import { App, Button, Form, Input, Space } from "antd";
import { isEmpty } from "lodash-es";
import React, { useState } from "react";
import PhoneInput from "./PhoneInput";
import { isVerificationCode, validatePhone, validateVerificationCode } from "./utils";

export interface VerificationCodeFormValues {
  phoneNumber: string;
  verificationCode: string;
}

interface VerifyCodeFormProps {
  onFinish?: (values: VerificationCodeFormValues) => void | Promise<void>;
}

const LAST_LOGIN_PHONE_KEY = "lastLoginPhone";

const VerifyCodeForm: React.FC<VerifyCodeFormProps> = () => {
  const [form] = Form.useForm<VerificationCodeFormValues>();
  const [lastPhone, setLastPhone] = useLocalStorageState<string>(LAST_LOGIN_PHONE_KEY);
  const [targetDate, setTargetDate] = useState<number>();
  const [countdown] = useCountDown({ targetDate });
  const { message } = App.useApp();
  const verificationCode = Form.useWatch("verificationCode", form);

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

  const { run: loginWithVerificationCode, loading: verifySmsCodeLoading } = useRequest(
    userAPI.loginWithVerificationCode,
    {
      manual: true,
      onSuccess: () => {
        const phone = form.getFieldValue("phoneNumber");
        if (phone) setLastPhone(phone);
        message.success("登录成功");
        setTimeout(() => {
          jumpToLocation(getRedirectUrl() || "/chat", true);
        }, 200);
      },
      onError: error => {
        reportError("loginWithVerificationCode failed", { error, smsResponse });
        console.error("登录失败:", error);
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
    if (!smsResponse) {
      message.error("请先发送验证码");
      return;
    }

    loginWithVerificationCode({
      ...(smsResponse as SendSmsResponse),
      verificationCode: (values.verificationCode ?? "").trim(),
    });
  };

  return (
    <Form form={form} className="mt-6" layout="vertical" onFinish={handleSubmit}>
      <Form.Item
        name="phoneNumber"
        initialValue={lastPhone}
        validateTrigger={false}
        rules={[{ validator: (_, value) => validatePhone(value) }]}
      >
        <PhoneInput />
      </Form.Item>
      <Form.Item>
        <Space.Compact className="w-full">
          <Form.Item
            noStyle
            name="verificationCode"
            validateTrigger={false}
            rules={[{ validator: (_, value) => validateVerificationCode(value) }]}
          >
            <Input
              size="large"
              className="flex-1"
              placeholder="请输入验证码"
              prefix={<SafetyOutlined style={{ color: "var(--color-black-quaternary)" }} />}
            />
          </Form.Item>
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
      <div className="text-black-tertiary mb-3">未注册手机号将自动注册，短信签名【开心锦然电商】</div>
      <Form.Item>
        <Button
          block
          size="large"
          type="primary"
          htmlType="submit"
          loading={verifySmsCodeLoading}
          className="h-12 text-base font-medium"
          disabled={isEmpty(smsResponse) || !isVerificationCode(verificationCode)}
        >
          登录
        </Button>
      </Form.Item>
    </Form>
  );
};

export default VerifyCodeForm;
