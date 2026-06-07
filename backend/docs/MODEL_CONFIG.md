# 模型配置与解析说明（当前实现）

> 状态：现网实现。本文档以 `app/schemas/config.py`、`app/services/base_service/model_resolver.py`、
> `app/api/models.py`、`app/api/chat.py` 为准。

## 1. 设计目标

模型配置拆成两层：

- `models.providers`：描述供应商、API 地址、API Key，以及该供应商下可调用的模型元数据；
- `models.scenarios`：描述业务场景使用哪个 `provider/model_name`，以及前端可选模型顺序。

这样可以复用同一个供应商的 `base_url` / `api_key`，并让聊天、标题生成、摘要等场景独立换模。

## 2. 配置结构

```yaml
models:
  providers:
    dashscope:
      base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
      api_key: "sk-..."
      models:
        kimi-k2.6:
          name: "Kimi K2.6"
          description: "文本与图片输入模型"
          context_limit: 128000
          capabilities: ["text", "image"]
        deepseek-v4-flash:
          name: "DeepSeek V4 Flash"
          context_limit: 64000
          capabilities: ["text"]

  scenarios:
    text_generation:
      description: "主聊天回复"
      default_model: "dashscope/kimi-k2.6"
      alternatives:
        - "dashscope/deepseek-v4-flash"
    title_generation:
      default_model: "dashscope/deepseek-v4-flash"
    summarization:
      default_model: "dashscope/deepseek-v4-flash"
```

字段约束：

- 模型引用格式固定为 `provider/model_name`，例如 `dashscope/kimi-k2.6`；
- `context_limit` 为必填正整数，会传给 `TokenCalculator` 作为上下文预算；
- `capabilities` 默认为 `["text"]`，包含 `image` 时运行时 `LLMConfig.image_support=true`；
- `providers.*.options` 当前为预留字段，不参与 `ModelResolver` 解析。

当前运行链路会按需读取以下场景：

| 场景 | 使用位置 | 说明 |
|------|----------|------|
| `text_generation` | `/api/chat/stream`、`/api/chat/models` | 主聊天默认模型与前端可选模型列表 |
| `title_generation` | 标题生成服务 | 会话标题生成模型 |
| `summarization` | 摘要相关服务 | 历史压缩/摘要模型 |

缺少被调用的场景或模型引用无法解析时，`ModelResolver` 会抛出错误；聊天入口对用户传入的非法
`model_id` 做降级处理，回退到 `text_generation.default_model`。

## 3. 运行时解析

`ModelResolver` 提供三个核心入口：

- `resolve_model_ref("provider/model")`：解析单个模型引用，生成运行时 `LLMConfig`；
- `resolve_scenario("text_generation")`：读取场景的 `default_model` 并解析；
- `list_text_generation_models()`：返回 `text_generation.default_model + alternatives`，按配置顺序去重。

`GET /api/chat/models` 会调用 `list_text_generation_models()`，返回给前端的字段是脱敏后的展示信息：

```json
[
  {
    "model_id": "dashscope/kimi-k2.6",
    "title": "Kimi K2.6",
    "description": "文本与图片输入模型",
    "image_support": true
  }
]
```

`api_key`、`base_url` 不会返回给前端。接口返回顺序很重要：前端在模型列表加载完成后使用
`models[0]` 作为默认选中项，因此 `text_generation.default_model` 总是排在首位。

## 4. 图片输入约束

聊天请求的 `model_id` 为空或无法解析时会回退到 `text_generation.default_model`。如果请求包含
`ImageBlock`，但解析出的模型 `image_support=false`，`POST /api/chat/stream` 会返回：

```text
400 当前模型不支持图片输入
```

排障时优先检查：

1. 前端传入的 `model_id` 是否是 `provider/model_name`；
2. 对应 `providers.<provider>.models.<model_name>.capabilities` 是否包含 `image`；
3. `text_generation.default_model` 是否支持当前请求需要的能力。

## 5. 与旧配置的差异

- 旧的 `model_map`、`title_model`、`summarizer_model` 口径已不适用于当前实现；
- Embedding 模型仍使用独立的 `embedding_model` 配置，不通过 `ModelResolver`；
- 新增模型时需要同时补充 provider 元数据，并在相应 scenario 中引用，否则不会出现在业务链路中。
