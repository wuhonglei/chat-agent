"""
多模型 Token 数批量测量脚本

测量 models.yaml 中所有模型对同一文档的 token 计数
"""

import time
from dataclasses import dataclass
from openai import OpenAI


@dataclass
class ModelConfig:
    name: str
    provider: str
    base_url: str
    api_key: str
    model_id: str
    context_limit: int


# 模型配置
MODELS = [
    # DashScope
    ModelConfig(
        "Qwen3.7 Plus",
        "dashscope",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "sk-ws-H.EIDELYL.HvGm.MEUCIQCvqGBkQ6pwFpTnFEAkT3yNiKGp1NfsR9hN565pcgB4wgIgGbuDhb3Sk1LirAb6SJMQy5lNsGRak6bpz1SfXM5F-XY",
        "qwen3.7-plus",
        1000000,
    ),
    ModelConfig(
        "Qwen3.7 Max",
        "dashscope",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "sk-ws-H.RPRIDHY.CFn8.MEUCIEByfkp6hWTloRNYosesLKyFSulCCfcV3zlJWjyNNI1yAiEAqzXJEOs_gf3jhGe0oegjgRKp7MsdvpDt7AjOl-qLFWE",
        "qwen3.7-max",
        1000000,
    ),
    ModelConfig(
        "GLM 5.2",
        "dashscope",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "sk-ws-H.RPRIDHY.CFn8.MEUCIEByfkp6hWTloRNYosesLKyFSulCCfcV3zlJWjyNNI1yAiEAqzXJEOs_gf3jhGe0oegjgRKp7MsdvpDt7AjOl-qLFWE",
        "glm-5.2",
        198000,
    ),
    ModelConfig(
        "Qwen3.5 Flash",
        "dashscope",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "sk-ws-H.RPRIDHY.CFn8.MEUCIEByfkp6hWTloRNYosesLKyFSulCCfcV3zlJWjyNNI1yAiEAqzXJEOs_gf3jhGe0oegjgRKp7MsdvpDt7AjOl-qLFWE",
        "qwen3.5-flash",
        1000000,
    ),
    # DeepSeek
    ModelConfig(
        "DeepSeek V4 Flash",
        "deepseek",
        "https://api.deepseek.com/v1",
        "sk-f8cb83caf1ae4c18929f3d6ca8734414",
        "deepseek-v4-flash",
        1000000,
    ),
    ModelConfig(
        "DeepSeek V4 Pro",
        "deepseek",
        "https://api.deepseek.com/v1",
        "sk-f8cb83caf1ae4c18929f3d6ca8734414",
        "deepseek-v4-pro",
        1000000,
    ),
    # Kimi
    ModelConfig(
        "Kimi K3",
        "kimi",
        "https://api.moonshot.cn/v1",
        "sk-HeW1Te1IcnseuD7BqbpIQLO6rfhwVxMTcyEnFW44oOD6K9mK",
        "kimi-k3",
        1000000,
    ),
    ModelConfig(
        "Kimi K2.6",
        "kimi",
        "https://api.moonshot.cn/v1",
        "sk-HeW1Te1IcnseuD7BqbpIQLO6rfhwVxMTcyEnFW44oOD6K9mK",
        "kimi-k2.6",
        256000,
    ),
]


def measure_model_token(text: str, model: ModelConfig) -> dict:
    """测量单个模型的 token 数"""
    client = OpenAI(api_key=model.api_key, base_url=model.base_url)

    try:
        t0 = time.perf_counter()
        response = client.chat.completions.create(
            model=model.model_id,
            messages=[
                {"role": "system", "content": "你是一个文档分析助手。"},
                {"role": "user", "content": text},
            ],
            max_tokens=10,  # 最小化输出
        )
        t1 = time.perf_counter()

        usage = response.usage
        return {
            "success": True,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "latency_ms": (t1 - t0) * 1000,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "latency_ms": 0,
        }


def main():
    doc_path = (
        "/Users/apple/Desktop/code/chat-agent/docs/context-management-comparison.md"
    )

    # 读取文档
    with open(doc_path, encoding="utf-8") as f:
        content = f.read()

    print("=" * 80)
    print("多模型 Token 数批量测量")
    print("=" * 80)
    print(f"文件: {doc_path}")
    print(
        f"文件大小: {len(content.encode('utf-8'))} bytes ({len(content.encode('utf-8')) / 1024:.1f} KB)"
    )
    print(f"字符数: {len(content)}")
    print("=" * 80)

    # 测量 tiktoken 作为基准
    import tiktoken

    encoding = tiktoken.get_encoding("cl100k_base")
    tiktoken_count = len(encoding.encode(content))
    print(f"\n基准 (tiktoken cl100k_base): {tiktoken_count} tokens")

    # 批量测量
    print("\n" + "=" * 80)
    print("模型测量结果")
    print("=" * 80)

    results = []
    for model in MODELS:
        print(f"\n[{model.name}] ({model.provider}/{model.model_id})")
        print("-" * 60)

        result = measure_model_token(content, model)
        results.append({"model": model, "result": result})

        if result["success"]:
            print(f"  Prompt Tokens:    {result['prompt_tokens']:,}")
            print(f"  Completion Tokens: {result['completion_tokens']:,}")
            print(f"  Total Tokens:     {result['total_tokens']:,}")
            print(f"  耗时:             {result['latency_ms']:.0f}ms")
            print(f"  字符/token 比:    {len(content) / result['prompt_tokens']:.2f}")
        else:
            print(f"  ❌ 失败: {result['error']}")

    # 汇总对比
    print("\n" + "=" * 80)
    print("汇总对比")
    print("=" * 80)

    # 表头
    print(
        f"{'模型':<25} {'Provider':<12} {'Prompt Tokens':<15} {'与tiktoken差异':<15} {'耗时(ms)':<10}"
    )
    print("-" * 77)

    # tiktoken 基准行
    print(
        f"{'tiktoken (基准)':<25} {'local':<12} {tiktoken_count:<15} {'-':<15} {'<1':<10}"
    )

    # 各模型结果
    for item in results:
        model = item["model"]
        result = item["result"]

        if result["success"]:
            diff = result["prompt_tokens"] - tiktoken_count
            diff_pct = diff / tiktoken_count * 100
            diff_str = f"{diff:+d} ({diff_pct:+.1f}%)"
            print(
                f"{model.name:<25} {model.provider:<12} {result['prompt_tokens']:<15,} {diff_str:<15} {result['latency_ms']:<10.0f}"
            )
        else:
            print(
                f"{model.name:<25} {model.provider:<12} {'失败':<15} {'-':<15} {'-':<10}"
            )

    # 统计分析
    print("\n" + "=" * 80)
    print("统计分析")
    print("=" * 80)

    successful = [item for item in results if item["result"]["success"]]
    if successful:
        prompt_tokens = [item["result"]["prompt_tokens"] for item in successful]
        avg_tokens = sum(prompt_tokens) / len(prompt_tokens)
        min_tokens = min(prompt_tokens)
        max_tokens = max(prompt_tokens)

        print(f"成功测量: {len(successful)}/{len(results)} 模型")
        print(f"平均 Prompt Tokens: {avg_tokens:,.0f}")
        print(f"最小 Prompt Tokens: {min_tokens:,}")
        print(f"最大 Prompt Tokens: {max_tokens:,}")
        print(
            f"极差: {max_tokens - min_tokens:,} ({(max_tokens - min_tokens) / avg_tokens * 100:.1f}%)"
        )

        # 找出最接近 tiktoken 的模型
        closest = min(
            successful, key=lambda x: abs(x["result"]["prompt_tokens"] - tiktoken_count)
        )
        print(f"\n最接近 tiktoken 的模型: {closest['model'].name}")
        print(
            f"  差异: {abs(closest['result']['prompt_tokens'] - tiktoken_count):,} tokens"
        )


if __name__ == "__main__":
    main()
