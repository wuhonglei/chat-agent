import { ErrorInfo, ReactNode } from "react";
import { ErrorBoundary } from "react-error-boundary";

interface Props {
  children: ReactNode;
  fallback?: ReactNode | ((error: Error) => ReactNode);
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

/**
 * Fallback 组件：当组件渲染出错时，显示错误信息或自定义 fallback
 */
function ComponentFallback({
  error,
  fallback,
}: {
  error: Error;
  fallback?: ReactNode | ((error: Error) => ReactNode);
}) {
  // 如果有自定义 fallback，优先使用
  if (fallback) {
    return typeof fallback === "function" ? fallback(error) : fallback;
  }

  // 默认错误信息
  return (
    <div style={{ padding: "12px", color: "#ff4d4f", fontSize: "14px" }}>
      组件渲染出错，请检查数据格式
      {error.message && (
        <div style={{ marginTop: "8px", fontSize: "12px", opacity: 0.7 }}>
          {error.message}
        </div>
      )}
    </div>
  );
}

/**
 * 组件错误边界，用于捕获组件渲染时的错误
 * 当组件内部执行出错时，显示错误信息或自定义 fallback
 */
function ComponentErrorBoundary({ children, fallback, onError }: Props) {
  return (
    <ErrorBoundary
      fallbackRender={({ error }) => (
        <ComponentFallback error={error} fallback={fallback} />
      )}
      onError={(error, errorInfo) => {
        // 记录错误信息
        console.warn("组件渲染错误:", error, errorInfo);

        // 调用外部错误处理函数
        if (onError) {
          onError(error, errorInfo);
        }
      }}
    >
      {children}
    </ErrorBoundary>
  );
}

export default ComponentErrorBoundary;
