/// <reference types="vite/client" />
/// <reference types="vite-plugin-svgr/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
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
 */
declare namespace aegis {
  interface Params {
    name: string; // "XXX请求成功"; 必填
    ext1?: string | number; // "额外参数1"
    ext2?: string | number; // "额外参数2"
    ext3?: string | number; // "额外参数3"
  }
  function reportEvent(params: Params): void;
}
