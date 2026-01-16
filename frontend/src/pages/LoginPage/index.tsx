import SiteLogo from "@/components/common/SiteLogo";
import SiteTitle from "@/components/common/SiteTitle";
import type { TabsProps } from "antd";
import { Tabs } from "antd";
import React, { useState } from "react";
import VerifyCodeForm from "./components/VerifyCodeForm";
import WeChatLoginForm from "./components/WeChatLogin";

const LoginPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>("wechat");

  const tabItems: TabsProps["items"] = [
    {
      key: "verification",
      label: "验证码登录",
      children: <VerifyCodeForm />,
    },
    {
      key: "wechat",
      label: "微信登录",
      children: <WeChatLoginForm />,
    },
  ];

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-4 pb-16 gap-8">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <SiteLogo size={44} />
        <SiteTitle level={3} />
      </div>
      {/* Login Card */}
      <div className="w-full max-w-md bg-white rounded-lg shadow-lg p-8">
        <Tabs
          size="large"
          items={tabItems}
          activeKey={activeTab}
          onChange={setActiveTab}
          classNames={{
            item: "font-medium",
          }}
        />
      </div>
    </div>
  );
};

export default LoginPage;
