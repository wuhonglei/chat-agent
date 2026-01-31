import SiteLogo from "@/components/common/SiteLogo";
import SiteTitle from "@/components/common/SiteTitle";
import { useIsSmallScreen } from "@/hooks";
import React from "react";
import VerifyCodeForm from "./components/VerifyCodeForm";
import WeChatLoginForm from "./components/WeChatLogin";

const LoginPage: React.FC = () => {
  const isSmallScreen = useIsSmallScreen();

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-4 pb-16 gap-8">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <SiteLogo size={44} />
        <SiteTitle level={3} />
      </div>
      {/* Login Card */}
      <div className="w-full max-w-4xl bg-white rounded-2xl shadow-lg p-8 md:p-10">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="md:pr-6 md:border-r border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900 mb-6">验证码登录</h2>
            <VerifyCodeForm />
          </div>
          {!isSmallScreen && (
            <div className="md:pl-6 flex flex-col items-center justify-center">
              <h2 className="text-lg font-semibold text-gray-900 mb-6">微信登录</h2>
              <WeChatLoginForm />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
