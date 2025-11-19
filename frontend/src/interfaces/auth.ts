export interface SendSmsResponse {
  verificationId: string;
  expiresIn: number;
  isUser: boolean;
}

export interface VerifySmsRequest extends SendSmsResponse {
  verificationCode: string;
}
