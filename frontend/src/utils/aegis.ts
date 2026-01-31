/**
 * Aegis 埋点工具函数
 * 用于统一管理前端埋点上报
 */

import { get } from "lodash-es";

/**
 * 上报自定义事件
 * @param name 事件名称
 * @param params 事件参数（会被序列化为JSON）
 */
export function reportEvent(
  name: string,
  params?: Record<string, unknown>
): void {
  try {
    if (typeof aegis !== "undefined" && aegis) {
      aegis.reportEvent({
        name,
        ext1: JSON.stringify(params || {}),
      });
    }
  } catch (error) {
    // 埋点失败不应影响业务功能
    console.warn("Failed to report event:", error);
  }
}

/**
 * 上报性能指标
 * @param name 性能指标名称
 * @param duration 耗时（毫秒）
 * @param params 额外参数
 */
export function reportSpeed(
  name: string,
  duration: number,
  params?: Record<string, unknown>
): void {
  try {
    if (typeof aegis !== "undefined" && aegis) {
      aegis.reportTime({
        name,
        duration,
        ext1: JSON.stringify(params || {}),
      });
    }
  } catch (error) {
    console.warn("Failed to report speed:", error);
  }
}

/**
 * 上报错误
 * @param error 错误对象或错误消息
 * @param params 额外参数
 */
export function reportError(
  error: string,
  params?: Record<string, unknown>
): void {
  try {
    if (typeof aegis !== "undefined" && aegis) {
      const stack = get(params, "error.stack");
      const errorInfo = { msg: error, stack, ...params };
      aegis.error(errorInfo);
    }
  } catch (e) {
    console.warn("Failed to report error:", e);
  }
}

/**
 * 上报页面访问（PV）
 * @param pageName 页面名称
 * @param params 额外参数
 */
export function reportPageView(
  pageName: string,
  params?: Record<string, unknown>
): void {
  try {
    if (typeof aegis !== "undefined" && aegis) {
      aegis.reportEvent({
        name: "page_view",
        ext1: JSON.stringify({
          page: pageName,
          ...params,
        }),
      });
    }
  } catch (error) {
    console.warn("Failed to report page view:", error);
  }
}
