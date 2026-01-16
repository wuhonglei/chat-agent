import { WeChatLoginStatus } from "@/constants";
import { authHeader } from "@/constants/authHeader";
import { userAPI } from "@/services/user";
import { getRedirectUrl, jumpToLocation } from "@/utils";
import { ReloadOutlined } from "@ant-design/icons";
import { useRequest } from "ahooks";
import { App, Button, Image, Spin, Typography } from "antd";
import React, { useEffect, useState } from "react";

const { Text } = Typography;

const WeChatLoginForm: React.FC = () => {
  const { message } = App.useApp();
  const [ticket, setTicket] = useState<string>("");
  const [qrCodeUrl, setQrCodeUrl] = useState<string>("");
  const [status, setStatus] = useState<WeChatLoginStatus>(
    WeChatLoginStatus.Waiting
  );

  // 初始化微信登录，获取二维码
  const {
    run: initLogin,
    loading: initLoading,
    refresh: refreshQrCode,
  } = useRequest(userAPI.initWeChatLogin, {
    manual: true,
    onSuccess: data => {
      setQrCodeUrl(data.qrCodeUrl);
      setTicket(data.ticket);
      setStatus(WeChatLoginStatus.Waiting);
    },
    onError: error => {
      message.error("获取二维码失败，请重试");
      console.error("初始化微信登录失败:", error);
    },
  });

  // 轮询检查登录状态
  const {
    run: checkStatus,
    cancel: cancelPolling,
    refresh: refreshCheck,
  } = useRequest(
    () => {
      if (!ticket) {
        return Promise.reject(new Error("ticket 不存在"));
      }
      return userAPI.checkWeChatLoginStatus(ticket);
    },
    {
      manual: true,
      pollingInterval: 2000, // 每 2 秒轮询一次
      pollingWhenHidden: false, // 页面隐藏时停止轮询
      ready: !!ticket, // 只有当 ticket 存在时才开始轮询
      onSuccess: data => {
        setStatus(data.status);

        if (data.status === WeChatLoginStatus.Confirmed && data.token) {
          // 登录成功
          cancelPolling();
          authHeader.setAuthorizationHeader(data.token);
          message.success("登录成功");
          setTimeout(() => {
            jumpToLocation(getRedirectUrl() || "/chat", true);
          }, 200);
        } else if (data.status === WeChatLoginStatus.Expired) {
          // 二维码过期
          cancelPolling();
          message.warning("二维码已过期，请刷新后重试");
        } else if (data.status === WeChatLoginStatus.Scanned) {
          // 已扫码，等待确认
          message.info("请在手机上确认登录");
        }
      },
      onError: error => {
        console.error("检查登录状态失败:", error);
        // 网络错误时不停止轮询，继续尝试
      },
    }
  );

  // 组件挂载时初始化
  useEffect(() => {
    initLogin();
    return () => {
      cancelPolling();
    };
  }, []);

  // 当 ticket 变化时开始轮询
  useEffect(() => {
    if (ticket && status === WeChatLoginStatus.Waiting) {
      // 使用 refresh 来触发轮询
      refreshCheck();
    }
  }, [ticket, status]);

  // 刷新二维码
  const handleRefresh = () => {
    cancelPolling();
    setTicket("");
    setQrCodeUrl("");
    setStatus(WeChatLoginStatus.Waiting);
    refreshQrCode();
  };

  const getStatusText = () => {
    switch (status) {
      case WeChatLoginStatus.Waiting:
        return "请使用微信扫码登录";
      case WeChatLoginStatus.Scanned:
        return "扫码成功，请在手机上确认登录";
      case WeChatLoginStatus.Confirmed:
        return "登录成功，正在跳转...";
      case WeChatLoginStatus.Expired:
        return "二维码已过期，请点击刷新";
      default:
        return "请使用微信扫码登录";
    }
  };

  return (
    <div className="mt-6 flex flex-col items-center">
      {initLoading ? (
        <div className="flex flex-col items-center justify-center py-12">
          <Spin size="large" />
          <Text className="mt-4 text-black-tertiary">正在加载二维码...</Text>
        </div>
      ) : (
        <>
          {qrCodeUrl ? (
            <div className="flex flex-col items-center">
              <div className="relative mb-4">
                <Image
                  src={qrCodeUrl}
                  alt="微信登录二维码"
                  width={240}
                  height={240}
                  preview={false}
                  className="border border-gray-200 rounded-lg"
                />
                {status === WeChatLoginStatus.Expired && (
                  <div className="absolute inset-0 bg-black bg-opacity-50 rounded-lg flex items-center justify-center">
                    <Text className="text-white text-center px-4">
                      二维码已过期
                    </Text>
                  </div>
                )}
              </div>
              <Text className="mb-4 text-center text-black-tertiary">
                {getStatusText()}
              </Text>
              {(status === WeChatLoginStatus.Expired ||
                status === WeChatLoginStatus.Waiting) && (
                <Button
                  icon={<ReloadOutlined />}
                  onClick={handleRefresh}
                  type="default"
                >
                  刷新二维码
                </Button>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center py-12">
              <Text className="mb-4 text-black-tertiary">
                二维码加载失败，请重试
              </Text>
              <Button onClick={handleRefresh} type="primary">
                重新加载
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default WeChatLoginForm;
