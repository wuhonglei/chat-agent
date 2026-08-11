import { authHeader } from "@/constants";
import { useAppSelector } from "@/store/hooks";
import { toLoginPage } from "@/utils/location";
import { Spin } from "antd";
import React, { ReactNode, useEffect } from "react";
import { Navigate } from "react-router-dom";

interface RequireAdminProps {
  children: ReactNode;
}

/** 仅 admin 可访问；未登录跳登录，非 admin 回聊天页 */
const RequireAdmin: React.FC<RequireAdminProps> = ({ children }) => {
  const userDetail = useAppSelector((state) => state.user.userDetail);
  const hasToken = Boolean(authHeader.getJwtPayload()?.user_id || authHeader.getUserId());

  useEffect(() => {
    if (!hasToken) {
      toLoginPage(location.pathname);
    }
  }, [hasToken]);

  if (!hasToken) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spin description="跳转登录..." />
      </div>
    );
  }

  if (!userDetail) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spin description="加载用户信息..." />
      </div>
    );
  }

  if (userDetail.role !== "admin") {
    return <Navigate to="/chat" replace />;
  }

  return <>{children}</>;
};

export default RequireAdmin;
