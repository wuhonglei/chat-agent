import axios, { AxiosResponse, InternalAxiosRequestConfig } from "axios";

import { isPlainObject } from "lodash-es";
import snakecaseKeys from "snakecase-keys";
import camelcaseKeys from "camelcase-keys";
import { getMessageInstance } from "../utils/message";

// Create axios instance
const apiClient = axios.create({
  baseURL: "/api",
  timeout: 60000,
  headers: {
    "Content-Type": "application/json",
  },
});

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
    // Add token or other auth headers here if needed
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// Response interceptor - Convert all response data to camelCase
apiClient.interceptors.response.use(
  (response: AxiosResponse<{ data: any; code: number; msg: string }>) => {
    const { code, msg, data: responseData } = response.data;
    if (code !== 0) {
      const message = getMessageInstance();
      message.error(msg);
      // 当前 conversation 不存在
      if (code === 404) {
        location.replace("/chat");
      }

      return Promise.reject(response.data);
    }

    let data = responseData;
    // Convert response data to camelCase
    if (isPlainObject(data) && !(data instanceof Blob)) {
      data = camelcaseKeys(data, { deep: true });
    }
    return data;
  },
  error => {
    if (error.response) {
      // Convert error response to camelCase
      if (isPlainObject(error.response.data)) {
        error.response.data = camelcaseKeys(error.response.data, {
          deep: true,
        });
      }
      console.error("API Error:", error.response.data);
    } else if (error.request) {
      console.error("Network Error:", error.request);
    } else {
      console.error("Error:", error.message);
    }
    return Promise.reject(error);
  }
);

export { apiClient };
