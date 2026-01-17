import { userAPI } from "@/services/user";
import { getRedirectUrl, jumpToLocation, toLoginPage } from "@/utils/location";
import { useRequest } from "ahooks";
import { App } from "antd";
import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

const LoginCallback = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { message } = App.useApp();
  const { run: weChatLoginCallback } = useRequest(userAPI.weChatLoginCallback, {
    manual: true,
    onSuccess: () => {
      message.success("登录成功");
      jumpToLocation(getRedirectUrl() || "/chat", true);
    },
    onError: error => {
      console.error("登录失败:", error);
      message.error("登录失败，请重试");
      toLoginPage(getRedirectUrl());
    },
  });

  useEffect(() => {
    const handleCallback = async () => {
      const params = new URLSearchParams(location.search);
      const code = params.get("code") || "";
      const state = params.get("state") || "";
      weChatLoginCallback({
        code,
        state,
      });
    };

    handleCallback();
  }, [location, navigate, weChatLoginCallback]);

  return <div className="callback-container"></div>;
};

export default LoginCallback;
