/**
 * 类型声明：@tailwindcss/vite 使用 .d.mts 导出，
 * 部分 TS/IDE 在 moduleResolution: "bundler" 下无法解析，在此补充声明。
 */
import type { Plugin } from "vite";

declare module "@tailwindcss/vite" {
  export type PluginOptions = {
    optimize?: boolean | { minify?: boolean };
  };
  function tailwindcss(opts?: PluginOptions): Plugin[];
  export default tailwindcss;
}
