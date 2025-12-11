import { debounce } from "lodash-es";
import { Component, ErrorInfo, ReactNode } from "react";
import CodeHighlighter from "./CodeHighlighter";

interface Props {
  children: ReactNode;
  fallbackCode?: string;
  fallbackLang?: string;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error?: Error;
}

/**
 * 组件错误边界，用于捕获组件渲染时的错误
 * 当组件内部执行出错时，降级为代码高亮展示
 */
class ComponentErrorBoundary extends Component<Props, State> {
  private resetErrorDebounced = debounce(this.resetError, 1000);

  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  private resetError() {
    this.setState({ hasError: false, error: undefined });
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // 记录错误信息
    console.warn("组件渲染错误，降级为代码展示:", error, errorInfo);

    // 调用外部错误处理函数
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  componentDidUpdate(prevProps: Props) {
    // 当 fallbackCode 变化时，重置错误状态，允许重新尝试渲染
    // 这样可以处理 JSON 从非法变为合法的情况
    const codeChanged = prevProps.fallbackCode !== this.props.fallbackCode;
    if (this.state.hasError && codeChanged) {
      this.resetErrorDebounced();
    }
  }

  render() {
    if (this.state.hasError) {
      // 降级为代码高亮展示
      if (this.props.fallbackCode) {
        return (
          <CodeHighlighter lang={this.props.fallbackLang || "json"}>
            {this.props.fallbackCode}
          </CodeHighlighter>
        );
      }
      // 如果没有提供降级代码，显示错误信息
      return (
        <div style={{ padding: "12px", color: "#ff4d4f", fontSize: "14px" }}>
          组件渲染出错，请检查数据格式
        </div>
      );
    }

    return this.props.children;
  }
}

export default ComponentErrorBoundary;
