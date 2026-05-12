import axios, { AxiosResponse, InternalAxiosRequestConfig } from "axios";

import { authHeader } from "@/constants";
import {
  getAnonymousUserId,
  getClientId,
  getRedirectUrl,
  getUUID,
  isConversationNotFound,
  isInLoginPage,
  isUnAuthorized,
  isUserDetailApi,
  jumpToLocation,
  redirectToLogin,
  reportError,
  toChatPage,
} from "@/utils";
import camelcaseKeys from "camelcase-keys";
import { isObject, isPlainObject, isString, pick } from "lodash-es";
import snakecaseKeys from "snakecase-keys";
import { getMessageInstance } from "../utils/message";

// Create axios instance
const apiClient = axios.create({
  baseURL: "/api",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

export function addRequestHeaders<T extends Record<string, string>>(headers: T): T {
  const newHeaders = {
    ...headers,
    Authorization: authHeader.getAuthorizationHeader(),
    "X-Request-ID": getUUID(),
    "X-Client-ID": getClientId(),
  } as Record<string, string>;

  // 如果用户未登录，则添加匿名 ID
  if (!authHeader.getUserId()) {
    newHeaders["X-Anonymous-User-ID"] = getAnonymousUserId();
  }

  return newHeaders as T;
}

/**
 * 从 headers 中提取 X-Request-ID 和 X-Client-ID
 * 兼容 AxiosHeaders 和普通对象
 */
function extractRequestHeaders(headers: unknown): Record<string, string> | undefined {
  return pick(headers, ["X-Request-ID", "X-Client-ID", "X-Anonymous-User-ID"]);
}

// Request interceptor - Convert all request data to snake_case
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Convert request data to snake_case
    if (isPlainObject(config.data) && !(config.data instanceof FormData)) {
      config.data = snakecaseKeys(config.data, { deep: true });
    }
    // Convert params to snake_case
    if (isPlainObject(config.params)) {
      config.params = snakecaseKeys(config.params, { deep: true });
    }
    config.headers = addRequestHeaders(config.headers);
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// Response interceptor - Convert all response data to camelCase
apiClient.interceptors.response.use(
  // oxlint-disable-next-line @typescript-eslint/no-explicit-any
  (response: AxiosResponse<{ data: any; code: number; msg: string }>) => {
    const { code, msg, data: responseData } = response.data;
    // 如果响应头部中有 x-secret-token-info 则更新
    const newSecretTokenInfo = response.headers["x-secret-token-info"];
    if (newSecretTokenInfo) {
      authHeader.setAuthorizationHeader(newSecretTokenInfo);
    }

    if (code !== 0) {
      const message = getMessageInstance();
      message.error(msg);
      // 上报API错误
      reportError("API Error", {
        code,
        msg,
        url: response.config.url,
        method: response.config.method,
        ...extractRequestHeaders(response.config.headers),
      });
      // 当前 conversation 不存在
      if (isConversationNotFound(code, response.config.url)) {
        toChatPage(undefined);
      }

      return Promise.reject(response.data);
    } else if (isInLoginPage() && isUserDetailApi(response.config.url)) {
      // 如果当前在 login 页面，且用户已经登录成功，则跳转至 chat 页面
      const redirectUrl = getRedirectUrl() || "/chat";
      jumpToLocation(redirectUrl, true);
    }

    let data = responseData;
    // Convert response data to camelCase
    if (isObject(data) && !(data instanceof Blob)) {
      data = camelcaseKeys(data, { deep: true });
    }
    return data;
  },
  error => {
    if (error.response) {
      // 如果响应状态码为 401，则跳转至登录页面
      if (isUnAuthorized(error.response.status)) {
        redirectToLogin(location.pathname);
        return Promise.reject(error);
      }

      // 上报API网络错误
      reportError("API Network Error", {
        status: error.response.status,
        url: error.config?.url,
        method: error.config?.method,
        ...extractRequestHeaders(error.config?.headers),
      });

      // Convert error response to camelCase
      if (isObject(error.response.data)) {
        error.response.data = camelcaseKeys(error.response.data, {
          deep: true,
        });

        const msg = error.response.data.msg;
        if (msg && isString(msg)) {
          const message = getMessageInstance();
          message.error(msg);
        }
      }
      console.error("API Error:", error.response.data);
    } else if (error.request) {
      // 上报API请求错误
      reportError("API Request Error", {
        url: error.config?.url,
        ...extractRequestHeaders(error.config?.headers),
      });
      console.error("Network Error:", error.request);
    } else {
      console.error("Error:", error.message);
    }
    return Promise.reject(error);
  }
);

export { apiClient };
