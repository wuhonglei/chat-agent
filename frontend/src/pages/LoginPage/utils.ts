import { WeChatLoginInitResponse } from "@/interfaces";
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

export function validatePhone(value: string): Promise<void> {
  const trimmedValue = trim(value);
  if (!trimmedValue) {
    return Promise.reject(new Error("请输入手机号"));
  }
  if (isPhone(trimmedValue)) {
    return Promise.resolve();
  }

  return Promise.reject(new Error("请输入有效的手机号"));
}

export function validateAccount(value: string): Promise<void> {
  const trimmedValue = trim(value);
  if (!trimmedValue) {
    return Promise.reject(new Error("请输入手机号或邮箱"));
  }

  if (isPhone(trimmedValue) || isEmail(trimmedValue)) {
    return Promise.resolve();
  }
  return Promise.reject(new Error("请输入有效的手机号或邮箱地址"));
}

export function validateVerificationCode(value: string): Promise<void> {
  const trimmedValue = trim(value);
  if (!trimmedValue) {
    return Promise.reject(new Error("请输入验证码"));
  }
  if (isVerificationCode(trimmedValue)) {
    return Promise.resolve();
  }
  return Promise.reject(new Error("请输入有效的验证码"));
}

/**
 * 微信 WxLogin SDK 类型定义
 */
declare global {
  interface Window {
    WxLogin: new (options: WxLoginOptions) => void;
  }
}

/**
 * 微信登录配置选项
 */
export interface WxLoginOptions {
  self_redirect?: boolean; // 是否自动跳转（false：扫码成功后不自动跳转，通过回调处理；true：自动跳转到redirect_uri）
  id: string; // 二维码挂载容器的ID
  appid: string; // 微信开放平台AppID（网站应用）
  scope: string; // 授权作用域，固定值 'snsapi_login'
  redirect_uri: string; // 授权回调地址（需URLEncode）
  state: string; // 随机状态值，用于防止CSRF攻击
  style?: "black" | "white"; // 二维码样式
  href?: string; // 自定义二维码样式的CSS链接（可选，需满足微信跨域要求）
  stylelite?: number; // 二维码样式 lite
  onReady?: (isReady: boolean) => void; // 二维码准备就绪回调
}

/**
 * 初始化微信扫码二维码（使用微信官方 WxLogin SDK）
 * @param containerId 二维码挂载容器的ID
 * @param data 微信登录初始化数据
 * @param options 其他可选配置
 */
export function initWxQrCode(
  containerId: string,
  data: WeChatLoginInitResponse
): void {
  if (!window.WxLogin) {
    throw new Error("微信登录SDK未加载，请先调用 loadWxLoginSDK()");
  }

  const container = document.getElementById(containerId);
  if (!container) {
    throw new Error(`找不到ID为 "${containerId}" 的容器元素`);
  }

  // 清空容器（避免重复初始化）
  container.innerHTML = "";

  // 配置微信登录参数
  const wxLoginOptions: WxLoginOptions = {
    self_redirect: false, // 不自动跳转，通过回调处理
    id: containerId,
    appid: data.appid,
    scope: "snsapi_login", // 固定值
    redirect_uri: encodeURIComponent(data.redirectUri),
    state: data.state,
    style: "black", // 默认黑色样式
    href: "", // 自定义样式, stylelite 为 1 时，href 无效
    stylelite: 1,
    onReady: (isReady: boolean) => {
      console.log("QR code ready:", isReady);
    },
  };

  // 初始化微信扫码组件
  new window.WxLogin(wxLoginOptions);
}

/**
 * 获取微信官方二维码显示 URL（已废弃，推荐使用 initWxQrCode）
 * @deprecated 请使用 initWxQrCode 函数配合微信官方 WxLogin SDK
 */
export function getWeChatQrCodeUrl(authorizeUrl: string): string {
  if (!authorizeUrl) return "";
  return authorizeUrl;
}

/**
 * 生成微信官方二维码 iframe 嵌入代码（已废弃，推荐使用 initWxQrCode）
 * @deprecated 请使用 initWxQrCode 函数配合微信官方 WxLogin SDK
 */
export function getWeChatQrCodeIframe(authorizeUrl: string): string {
  if (!authorizeUrl) return "";
  return `<iframe src="${authorizeUrl}" width="300" height="300" frameborder="0" scrolling="no"></iframe>`;
}
