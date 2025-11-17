import React, { useState } from "react";
import { Tabs, Typography, App } from "antd";
import type { TabsProps } from "antd";
import styles from "./index.module.css";
import VerifyCodeForm, {
  VerificationCodeFormValues,
} from "./components/VerifyCodeForm";
import PasswordForm, { PasswordFormValues } from "./components/PasswordForm";
import { WEB_TITLE } from "@/constants";

const { Title } = Typography;

const LoginPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>("verification");
  const { message } = App.useApp();

  // 验证码登录
  const handleVerificationLogin = async (
    values: VerificationCodeFormValues
  ) => {
    try {
      // TODO: 调用登录接口
      console.log("验证码登录:", values);
      message.success("登录成功");
    } catch (error) {
      console.error("登录失败:", error);
      message.error("登录失败，请检查验证码");
    }
  };

  // 密码登录
  const handlePasswordLogin = async (values: PasswordFormValues) => {
    try {
      // TODO: 调用登录接口
      console.log("密码登录:", values);
      message.success("登录成功");
    } catch (error) {
      console.error("登录失败:", error);
      message.error("登录失败，请检查账号和密码");
    }
  };

  const tabItems: TabsProps["items"] = [
    {
      key: "verification",
      label: "验证码登录",
      children: <VerifyCodeForm onFinish={handleVerificationLogin} />,
    },
    {
      key: "password",
      label: "密码登录",
      children: <PasswordForm onFinish={handlePasswordLogin} />,
    },
  ];

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-4 gap-8">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <img alt="logo" width={44} height={44} src="/logo.png" />
        <Title level={3} style={{ marginBottom: 0 }}>
          {WEB_TITLE}
        </Title>
      </div>
      {/* Login Card */}
      <div className="w-full max-w-md bg-white rounded-lg shadow-lg p-8">
        <Tabs
          items={tabItems}
          activeKey={activeTab}
          onChange={setActiveTab}
          className={styles.loginTabs}
        />
      </div>
    </div>
  );
};

export default LoginPage;
