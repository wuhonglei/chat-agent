import React, { useState } from "react";
import { Tabs, Typography } from "antd";
import type { TabsProps } from "antd";
import styles from "./index.module.css";
import VerifyCodeForm from "./components/VerifyCodeForm";
import { WEB_TITLE } from "@/constants";

const { Title } = Typography;

const LoginPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>("verification");

  const tabItems: TabsProps["items"] = [
    {
      key: "verification",
      label: "验证码登录",
      children: <VerifyCodeForm />,
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
