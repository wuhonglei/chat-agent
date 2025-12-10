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
