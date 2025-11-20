export interface SendSmsResponse {
  verificationId: string;
  expiresIn: number;
  isUser: boolean;
  phoneNumber: string;
}

export interface VerifySmsRequest extends SendSmsResponse {
  verificationCode: string;
}
