import { WeChatLoginStatus } from "@/constants";

export interface SendSmsResponse {
  verificationId: string;
  expiresIn: number;
  isUser: boolean;
  phoneNumber: string;
}

export interface VerifySmsRequest extends SendSmsResponse {
  verificationCode: string;
}

export interface JwtPayload {
  access_token: string;
  exp: number;
  expires_in: number;
  iat: number;
  refresh_token: string;
  sub: string;
  token_type: string;
  user_id: string;
}

export interface WeChatLoginInitResponse {
  authorizeUrl: string; // 微信网页授权 URL，包含二维码扫码链接
  state: string; // 状态码，用于轮询检查登录状态和防 CSRF 攻击
  expireSeconds: number; // 过期时间（秒）
  appid: string; // 微信开放平台 AppID
  redirectUri: string; // 授权回调地址
}

export interface WeChatLoginCheckResponse {
  status: WeChatLoginStatus;
  userInfo?: {
    id: string;
    name: string;
    avatar?: string;
    phone: string;
  };
  token?: string; // 登录成功后的 token
  message?: string; // 状态描述信息
}
