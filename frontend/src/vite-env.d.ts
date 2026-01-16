/// <reference types="vite/client" />
/// <reference types="vite-plugin-svgr/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_WECHAT_APPID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// 声明 gtag 函数的类型定义
declare function gtag(
  type: "event",
  customEventName: string,
  fieldObject: {
    event_category?: string;
    event_label?: number | string;
    debug_mode?: boolean;
    value: number | string;
  }
): void;

/**
 * 腾讯云监控团队提供的前端监控 aegis 类型定义
 * 文档: https://www.npmjs.com/package/aegis-web-sdk
 * 通过 CDN 引入的全局变量，使用 aegis-web-sdk 包的类型定义
 */
import type Aegis from "aegis-web-sdk";

declare global {
  // 声明全局变量 aegis，类型为 Aegis 实例
  // eslint-disable-next-line no-var
  var aegis: Aegis | undefined;
}
