"""
文档 Token 数测量脚本

测量方法:
1. tiktoken (cl100k_base) - OpenAI 标准
2. qwen3.7-plus API response usage - 实际模型计数
"""

import json
import time

import tiktoken
from openai import OpenAI


def count_tokens_tiktoken(text: str, encoding_name: str = "cl100k_base") -> int:
    """使用 tiktoken 计算 token 数"""
    encoding = tiktoken.get_encoding(encoding_name)
    tokens = encoding.encode(text)
    return len(tokens)


def count_tokens_qwen(text: str, api_key: str, api_base: str) -> dict:
    """使用 qwen3.7-plus API 计算 token 数"""
    client = OpenAI(api_key=api_key, base_url=api_base)

    # 发送一个简单的请求，让模型返回 token 统计
    response = client.chat.completions.create(
        model="qwen3.7-plus",
        messages=[
            {"role": "user", "content": f"请统计以下文档的字数和行数，只返回数字:\n\n{text[:100]}..."}
        ],
        max_tokens=50,
    )

    # 获取 usage 信息
    usage = response.usage
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }


def count_tokens_qwen_full_context(text: str, api_key: str, api_base: str) -> dict:
    """使用 qwen3.7-plus API 计算完整文档的 token 数"""
    client = OpenAI(api_key=api_key, base_url=api_base)

    # 将完整文档作为 prompt 发送
    response = client.chat.completions.create(
        model="qwen3.7-plus",
        messages=[
            {"role": "system", "content": "你是一个文档分析助手。"},
            {"role": "user", "content": text}
        ],
        max_tokens=10,  # 最小化输出 token
    )

    usage = response.usage
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }


def main():
    doc_path = "/Users/apple/Desktop/code/chat-agent/docs/context-management-comparison.md"

    # 读取文档
    with open(doc_path, encoding="utf-8") as f:
        content = f.read()

    print("=" * 60)
    print("文档 Token 数测量")
    print("=" * 60)
    print(f"文件: {doc_path}")
    print(f"文件大小: {len(content.encode('utf-8'))} bytes ({len(content.encode('utf-8'))/1024:.1f} KB)")
    print(f"字符数: {len(content)}")
    print(f"行数: {content.count(chr(10)) + 1}")
    print("=" * 60)

    # 1. tiktoken 测量
    print("\n[1] tiktoken (cl100k_base)")
    print("-" * 40)
    t0 = time.perf_counter()
    tiktoken_count = count_tokens_tiktoken(content)
    t1 = time.perf_counter()
    print(f"Token 数: {tiktoken_count}")
    print(f"耗时: {(t1-t0)*1000:.2f}ms")
    print(f"字符/token 比: {len(content)/tiktoken_count:.2f}")

    # 2. qwen3.7-plus 测量
    print("\n[2] qwen3.7-plus API")
    print("-" * 40)

    # 使用 DashScope API
    api_key = "sk-ws-H.RPRIDIR.Ja2p.MEUCIG6Df1l-ou4U2TMyY_wpnzDgjdrhZrWUS49_zhxMd6-rAiEAypxrRkaawlp3mPrm_4QDWmo5Oh0ZnVF4NKhr2Cgh5jc"
    api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    try:
        t0 = time.perf_counter()
        qwen_result = count_tokens_qwen_full_context(content, api_key, api_base)
        t1 = time.perf_counter()

        print(f"Prompt Tokens: {qwen_result['prompt_tokens']}")
        print(f"Completion Tokens: {qwen_result['completion_tokens']}")
        print(f"Total Tokens: {qwen_result['total_tokens']}")
        print(f"耗时: {(t1-t0)*1000:.2f}ms")
        print(f"字符/token 比: {len(content)/qwen_result['prompt_tokens']:.2f}")
    except Exception as e:
        print(f"API 调用失败: {e}")
        qwen_result = None

    # 3. 对比分析
    print("\n" + "=" * 60)
    print("对比分析")
    print("=" * 60)

    if qwen_result:
        print(f"{'方法':<20} {'Token 数':<12} {'字符/token':<10}")
        print("-" * 42)
        print(f"{'tiktoken':<20} {tiktoken_count:<12} {len(content)/tiktoken_count:<10.2f}")
        print(f"{'qwen3.7-plus':<20} {qwen_result['prompt_tokens']:<12} {len(content)/qwen_result['prompt_tokens']:<10.2f}")

        diff = abs(tiktoken_count - qwen_result['prompt_tokens'])
        diff_pct = diff / tiktoken_count * 100
        print(f"\n差异: {diff} tokens ({diff_pct:.1f}%)")

        if diff_pct < 10:
            print("✓ 两种方法结果接近")
        elif diff_pct < 20:
            print("⚠ 两种方法有差异，可能是 tokenization 策略不同")
        else:
            print("✗ 两种方法差异较大，需要进一步分析")

    # 4. 分段统计
    print("\n" + "=" * 60)
    print("分段统计 (按章节)")
    print("=" * 60)

    sections = content.split("\n## ")
    print(f"{'章节':<30} {'字符数':<10} {'tiktoken':<10}")
    print("-" * 50)

    for i, section in enumerate(sections[:10]):  # 最多显示 10 个章节
        title = section.split("\n")[0][:25] + "..." if len(section.split("\n")[0]) > 25 else section.split("\n")[0]
        section_tokens = count_tokens_tiktoken(section)
        print(f"{title:<30} {len(section):<10} {section_tokens:<10}")


if __name__ == "__main__":
    main()
