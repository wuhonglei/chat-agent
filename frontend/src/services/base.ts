import axios, {
  AxiosInstance,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from "axios";

import { isPlainObject } from "lodash-es";
import snakecaseKeys from "snakecase-keys";
import camelcaseKeys from "camelcase-keys";

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
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
  (response: AxiosResponse) => {
    // Convert response data to camelCase
    if (isPlainObject(response.data) && !(response.data instanceof Blob)) {
      response.data = camelcaseKeys(response.data, { deep: true });
    }
    return response;
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
