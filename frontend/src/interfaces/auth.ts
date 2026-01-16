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
  qrCodeUrl: string; // 二维码图片 URL
  ticket: string; // 二维码 ticket，用于轮询检查状态
  expiresIn: number; // 过期时间（秒）
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
