import { WeChatLoginInitResponse } from "@/interfaces";
import { userAPI } from "@/services/user";
import { useRequest } from "ahooks";
import { App, Spin, Typography } from "antd";
import classNames from "classnames";
import React, { useEffect, useRef, useState } from "react";
import { initWxQrCode } from "../../utils";
import styles from "./index.module.css";

const { Text } = Typography;

const QR_CODE_CONTAINER_ID = "wx-login-qrcode-container";

const WeChatLoginForm: React.FC = () => {
  const { message } = App.useApp();
  const [loginData, setLoginData] = useState<WeChatLoginInitResponse | null>(
    null
  );
  const containerRef = useRef<HTMLDivElement>(null);

  // 初始化微信登录，获取二维码
  const { run: initLogin, loading: initLoading } = useRequest(
    (oldState?: string) => userAPI.initWeChatLogin(oldState),
    {
      manual: true,
      onSuccess: data => {
        setLoginData(data);

        try {
          initWxQrCode(QR_CODE_CONTAINER_ID, data);
        } catch (error) {
          console.error("初始化微信二维码失败:", error);
          message.error("二维码加载失败，请重试");
        }
      },
      onError: error => {
        message.error("获取二维码失败，请重试");
        console.error("初始化微信登录失败:", error);
      },
    }
  );

  // 组件挂载时初始化
  useEffect(() => {
    initLogin();
  }, []);

  return (
    <div className="mt-4 flex flex-col items-center">
      <div className="flex flex-col items-center">
        <div className="relative">
          {/* 容器始终存在，确保初始化时可以访问 */}
          <div
            ref={containerRef}
            id={QR_CODE_CONTAINER_ID}
            className={classNames(
              "flex items-center justify-center",
              styles["wx-container"]
            )}
          />
          {initLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-90 rounded-lg">
              <div className="flex flex-col items-center">
                <Spin size="large" />
                <Text className="mt-4 text-black-tertiary text-sm">
                  正在加载二维码...
                </Text>
              </div>
            </div>
          )}
          {!loginData && !initLoading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <Text className="text-black-tertiary text-center px-4">
                二维码加载失败，请重试
              </Text>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default WeChatLoginForm;
