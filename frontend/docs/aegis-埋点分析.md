# Aegis 埋点上报分析报告

## 一、项目现状

项目已集成 aegis SDK，当前配置：
- ✅ 已配置基础监控（接口测速、静态资源测速、SPA页面跳转）
- ✅ 已配置用户ID关联（通过 `authHeader.updateAegisConfig()` 设置 uin）
- ✅ 已配置自定义返回码处理

## 二、建议增加的埋点分类

### 1. 用户行为埋点（自定义事件）

#### 1.1 登录相关
| 埋点位置 | 事件名称 | 事件参数 | 优先级 |
|---------|---------|---------|--------|
| `src/pages/LoginPage/components/VerifyCodeForm.tsx` | `send_verification_code` | `{ phone_number: string }` | 高 |
| `src/pages/LoginPage/components/VerifyCodeForm.tsx` | `login_success` | `{ phone_number: string, method: 'verification_code' }` | 高 |
| `src/pages/LoginPage/components/VerifyCodeForm.tsx` | `login_failed` | `{ phone_number: string, error: string }` | 高 |

#### 1.2 对话管理
| 埋点位置 | 事件名称 | 事件参数 | 优先级 |
|---------|---------|---------|--------|
| `src/components/Layout/MainLayout.tsx` | `create_conversation` | `{ conversation_id: string }` | 高 |
| `src/components/Layout/MainLayout.tsx` | `delete_conversation` | `{ conversation_id: string }` | 高 |
| `src/components/Layout/MainLayout.tsx` | `rename_conversation` | `{ conversation_id: string, old_title: string, new_title: string }` | 中 |
| `src/components/Layout/MainLayout.tsx` | `switch_conversation` | `{ from_id: string, to_id: string }` | 中 |
| `src/components/Layout/hooks.tsx` | `click_conversation_menu` | `{ conversation_id: string, action: 'rename' | 'delete' }` | 低 |

#### 1.3 消息操作
| 埋点位置 | 事件名称 | 事件参数 | 优先级 |
|---------|---------|---------|--------|
| `src/hooks/chat.ts` (sendMessage) | `send_message` | `{ conversation_id: string, has_think_mode: boolean, has_mcp_tools: boolean, message_length: number }` | 高 |
| `src/hooks/chat.ts` (reSendMessage) | `resend_message` | `{ conversation_id: string, message_index: number }` | 中 |
| `src/hooks/chat.ts` (abortMessage) | `abort_message` | `{ conversation_id: string, message_id: string }` | 中 |
| `src/pages/ChatPage/index.tsx` (handleEditMessage) | `edit_message` | `{ conversation_id: string, message_index: number }` | 中 |

#### 1.4 工具和功能使用
| 埋点位置 | 事件名称 | 事件参数 | 优先级 |
|---------|---------|---------|--------|
| `src/pages/ChatPage/components/ChatInput/index.tsx` | `toggle_think_mode` | `{ enabled: boolean }` | 中 |
| `src/pages/ChatPage/components/ChatInput/ToolsSetting.tsx` | `toggle_mcp_auto_mode` | `{ enabled: boolean }` | 中 |
| `src/pages/ChatPage/components/ChatInput/ToolsSetting.tsx` | `select_mcp_server` | `{ server_id: string, server_name: string }` | 中 |
| `src/hooks/chat.ts` (tool_call handler) | `tool_call_start` | `{ conversation_id: string, tool_name: string }` | 中 |
| `src/hooks/chat.ts` (tool_call handler) | `tool_call_done` | `{ conversation_id: string, tool_name: string, duration: number }` | 中 |
| `src/hooks/chat.ts` (reasoning handler) | `reasoning_start` | `{ conversation_id: string }` | 中 |
| `src/hooks/chat.ts` (reasoning handler) | `reasoning_done` | `{ conversation_id: string, duration: number }` | 中 |

#### 1.5 页面交互
| 埋点位置 | 事件名称 | 事件参数 | 优先级 |
|---------|---------|---------|--------|
| `src/components/Layout/MainLayout.tsx` | `toggle_sidebar` | `{ collapsed: boolean }` | 低 |
| `src/pages/ChatPage/components/ChatMessage/components/AssistantOperation.tsx` | `copy_message` | `{ conversation_id: string, message_id: string }` | 中 |
| `src/pages/ChatPage/components/ChatMessage/components/AssistantOperation.tsx` | `regenerate_response` | `{ conversation_id: string, message_id: string }` | 中 |

### 2. 性能埋点

#### 2.1 消息流式传输性能
| 埋点位置 | 指标名称 | 说明 | 优先级 |
|---------|---------|------|--------|
| `src/hooks/chat.ts` (sendMessage) | `message_stream_duration` | 从发送到完成的总耗时 | 高 |
| `src/hooks/chat.ts` (done handler) | `message_first_token_time` | 首字时间（从发送到收到第一个token） | 高 |
| `src/hooks/chat.ts` (content handler) | `message_token_count` | 消息token数量（估算） | 中 |

#### 2.2 工具调用性能
| 埋点位置 | 指标名称 | 说明 | 优先级 |
|---------|---------|------|--------|
| `src/hooks/chat.ts` (tool_call handler) | `tool_call_duration` | 工具调用耗时 | 高 |
| `src/hooks/chat.ts` (reasoning handler) | `reasoning_duration` | 思考过程耗时 | 高 |

#### 2.3 页面加载性能
| 埋点位置 | 指标名称 | 说明 | 优先级 |
|---------|---------|------|--------|
| `src/App.tsx` (init) | `app_init_duration` | 应用初始化耗时 | 中 |
| `src/hooks/chat.ts` (useCachedRequest) | `message_load_duration` | 消息加载耗时 | 中 |
| `src/hooks/chat.ts` (useCachedRequest) | `cache_hit_rate` | IndexedDB缓存命中率 | 低 |

### 3. 错误埋点

#### 3.1 API错误（已有部分，建议增强）
| 埋点位置 | 错误类型 | 说明 | 优先级 |
|---------|---------|------|--------|
| `src/services/base.ts` (response interceptor) | `api_error` | API返回错误码 | 高 |
| `src/services/base.ts` (error interceptor) | `api_network_error` | 网络错误 | 高 |
| `src/services/base.ts` (error interceptor) | `api_timeout_error` | 请求超时 | 高 |

#### 3.2 流式传输错误
| 埋点位置 | 错误类型 | 说明 | 优先级 |
|---------|---------|------|--------|
| `src/services/chat.ts` (onerror) | `stream_error` | 流式传输错误 | 高 |
| `src/services/chat.ts` (onmessage parse error) | `stream_parse_error` | 消息解析错误 | 中 |
| `src/hooks/chat.ts` (error handler) | `stream_message_error` | 流消息错误 | 高 |

#### 3.3 业务错误
| 埋点位置 | 错误类型 | 说明 | 优先级 |
|---------|---------|------|--------|
| `src/hooks/chat.ts` (sendMessage catch) | `send_message_error` | 发送消息失败 | 高 |
| `src/store/middleware/dbMiddleware.ts` | `indexeddb_error` | IndexedDB操作失败 | 中 |
| `src/App.tsx` (init catch) | `app_init_error` | 应用初始化失败 | 高 |

### 4. 业务指标埋点

#### 4.1 用户活跃度
| 埋点位置 | 指标名称 | 说明 | 优先级 |
|---------|---------|------|--------|
| `src/pages/ChatPage/index.tsx` | `chat_page_view` | 聊天页面访问 | 中 |
| `src/pages/WelcomePage/index.tsx` | `welcome_page_view` | 欢迎页面访问 | 低 |
| `src/hooks/chat.ts` (sendMessage) | `daily_message_count` | 每日消息数 | 中 |

#### 4.2 功能使用率
| 埋点位置 | 指标名称 | 说明 | 优先级 |
|---------|---------|------|--------|
| `src/hooks/chat.ts` (sendMessage) | `think_mode_usage_rate` | 深度思考模式使用率 | 中 |
| `src/hooks/chat.ts` (sendMessage) | `mcp_tools_usage_rate` | MCP工具使用率 | 中 |
| `src/hooks/chat.ts` (tool_call handler) | `tool_usage_distribution` | 各工具使用分布 | 中 |

## 三、实现建议

### 3.1 创建埋点工具函数

建议在 `src/utils/` 目录下创建 `aegis.ts` 文件，封装埋点方法：

```typescript
// src/utils/aegis.ts
/**
 * Aegis 埋点工具函数
 */

/**
 * 上报自定义事件
 */
export function reportEvent(
  name: string,
  params?: Record<string, any>
): void {
  if (typeof aegis !== "undefined" && aegis) {
    aegis.reportEvent({
      name,
      ext1: JSON.stringify(params || {}),
    });
  }
}

/**
 * 上报性能指标
 */
export function reportSpeed(
  name: string,
  duration: number,
  params?: Record<string, any>
): void {
  if (typeof aegis !== "undefined" && aegis) {
    aegis.reportSpeed({
      name,
      duration,
      ext1: JSON.stringify(params || {}),
    });
  }
}

/**
 * 上报错误
 */
export function reportError(
  error: Error | string,
  params?: Record<string, any>
): void {
  if (typeof aegis !== "undefined" && aegis) {
    const errorInfo =
      error instanceof Error
        ? {
            msg: error.message,
            stack: error.stack,
            ...params,
          }
        : { msg: error, ...params };

    aegis.error(errorInfo);
  }
}
```

### 3.2 优先级实施建议

**第一阶段（高优先级）**：
1. 登录相关埋点
2. 消息发送埋点
3. API错误埋点增强
4. 流式传输错误埋点
5. 消息流式传输性能埋点

**第二阶段（中优先级）**：
1. 对话管理埋点
2. 工具调用相关埋点
3. 消息操作埋点（重发、中止、编辑）
4. 工具调用性能埋点

**第三阶段（低优先级）**：
1. 页面交互埋点
2. 缓存相关埋点
3. 功能使用率统计

### 3.3 注意事项

1. **隐私保护**：避免上报敏感信息（如消息内容、用户手机号等）
2. **性能影响**：埋点不应影响主业务流程性能
3. **错误处理**：埋点失败不应影响业务功能
4. **数据量控制**：避免高频埋点导致数据量过大
5. **环境区分**：开发环境可以降低埋点频率或禁用部分埋点

## 四、示例代码

### 示例1：消息发送埋点

```typescript
// src/hooks/chat.ts
import { reportEvent, reportSpeed } from "@/utils/aegis";

const sendMessage = useMemoizedFn(
  async (
    values: ChatInputFormValues,
    options?: SendMessageOptions
  ): Promise<void> => {
    const startTime = Date.now();

    // 埋点：发送消息
    reportEvent("send_message", {
      conversation_id: conversationId,
      has_think_mode: values.thinkMode || false,
      has_mcp_tools: !isEmpty(values.sourceConfig),
      message_length: values.content?.length || 0,
    });

    try {
      // ... 原有逻辑

      // 在 done handler 中上报性能
      done: data => {
        const duration = Date.now() - startTime;
        reportSpeed("message_stream_duration", duration, {
          conversation_id: conversationId,
        });
        // ... 原有逻辑
      },
    } catch (error) {
      reportError(error as Error, {
        event: "send_message",
        conversation_id: conversationId,
      });
      // ... 原有错误处理
    }
  }
);
```

### 示例2：API错误埋点增强

```typescript
// src/services/base.ts
import { reportError } from "@/utils/aegis";

apiClient.interceptors.response.use(
  (response) => {
    // ... 原有逻辑
    if (code !== 0) {
      // 上报API错误
      reportError(`API Error: ${msg}`, {
        code,
        url: response.config.url,
        method: response.config.method,
      });
      // ... 原有逻辑
    }
  },
  (error) => {
    if (error.response) {
      reportError("API Network Error", {
        status: error.response.status,
        url: error.config?.url,
        method: error.config?.method,
      });
    } else if (error.request) {
      reportError("API Request Error", {
        url: error.config?.url,
      });
    }
    // ... 原有逻辑
  }
);
```

## 五、总结

建议优先实施高优先级的埋点，这些埋点能够：
1. 监控核心业务流程（登录、消息发送）
2. 及时发现和定位错误
3. 了解性能瓶颈
4. 分析用户行为模式

通过系统化的埋点，可以更好地：
- 监控应用健康状态
- 优化用户体验
- 分析功能使用情况
- 快速定位和解决问题
