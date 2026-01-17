import { userAPI } from "@/services/user";
import { getRedirectUrl, jumpToLocation, toLoginPage } from "@/utils/location";
import { useRequest } from "ahooks";
import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

const LoginCallback = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { run: weChatLoginCallback } = useRequest(userAPI.weChatLoginCallback, {
    manual: true,
    onSuccess: () => {
      jumpToLocation(getRedirectUrl() || "/chat", true);
    },
    onError: error => {
      console.error("登录失败:", error);
      toLoginPage(getRedirectUrl());
    },
  });

  useEffect(() => {
    const handleCallback = async () => {
      const params = new URLSearchParams(location.search);
      const code = params.get("code") || "";
      const state = params.get("state") || "";
      const replaceUri = params.get("replace_uri") || "";

      const isProd = import.meta.env.PROD;
      if (isProd && Number(replaceUri)) {
        const newUrl = new URL(window.location.href);
        newUrl.host = "localhost:3000";
        newUrl.protocol = "http";
        // 移除 replace_uri 参数
        newUrl.searchParams.delete("replace_uri");
        jumpToLocation(newUrl.toString(), true);
      }

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
