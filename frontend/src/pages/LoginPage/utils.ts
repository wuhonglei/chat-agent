import { trim } from "lodash-es";

export function isPhone(value: string): boolean {
  return /^1[3-9]\d{9}$/.test(value);
}

export function isEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

export function isVerificationCode(value: string): boolean {
  return /^[0-9]{6}$/.test(value);
}

export function validatePhone(value: string): Promise<void | any> {
  const trimmedValue = trim(value);
  if (!trimmedValue) {
    return Promise.reject(new Error("请输入手机号"));
  }
  if (isPhone(trimmedValue)) {
    return Promise.resolve();
  }

  return Promise.reject(new Error("请输入有效的手机号"));
}

export function validateAccount(value: string): Promise<void | any> {
  const trimmedValue = trim(value);
  if (!trimmedValue) {
    return Promise.reject(new Error("请输入手机号或邮箱"));
  }

  if (isPhone(trimmedValue) || isEmail(trimmedValue)) {
    return Promise.resolve();
  }
  return Promise.reject(new Error("请输入有效的手机号或邮箱地址"));
}

export function validateVerificationCode(value: string): Promise<void | any> {
  const trimmedValue = trim(value);
  if (!trimmedValue) {
    return Promise.reject(new Error("请输入验证码"));
  }
  if (isVerificationCode(trimmedValue)) {
    return Promise.resolve();
  }
  return Promise.reject(new Error("请输入有效的验证码"));
}
