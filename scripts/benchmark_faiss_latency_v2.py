"""
FAISS 语义截断延迟测量脚本 - 完整对比版

测量目标:
1. 不同 chunk_size 下的延迟
2. 生产配置 vs 用户指定配置
3. 瓶颈分析
"""

import time
from dataclasses import dataclass

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownTextSplitter


@dataclass
class LatencyResult:
    split_ms: float
    embed_ms: float
    search_ms: float
    total_ms: float
    chunk_count: int
    selected_count: int
    original_tokens: int
    selected_tokens: int


def count_tokens_approx(text: str) -> int:
    """粗略估算 token 数 (中文约 2 字符/token)"""
    return len(text) // 2


def measure_faiss_latency(
    content: str,
    query: str,
    embeddings: DashScopeEmbeddings,
    chunk_size: int = 1024,
    chunk_overlap: int = 200,
    top_k: int = 8,
) -> LatencyResult:
    """测量 FAISS 语义截断全链路延迟"""

    # 1. Markdown 切块
    t0 = time.perf_counter()
    splitter = MarkdownTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = [c.strip() for c in splitter.split_text(content) if c.strip()]
    t1 = time.perf_counter()

    # 2. 向量化 + FAISS 索引构建
    documents = [
        Document(page_content=chunk, metadata={"index": idx})
        for idx, chunk in enumerate(chunks)
    ]
    t2 = time.perf_counter()

    # DashScope 限制每次最多 10 个文档，需要分批处理
    batch_size = 10
    max_retries = 3
    vector_store = None

    def _create_with_retry(docs):
        for attempt in range(max_retries):
            try:
                return FAISS.from_documents(docs, embeddings)
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise

    if len(documents) <= batch_size:
        vector_store = _create_with_retry(documents)
    else:
        vector_store = _create_with_retry(documents[:batch_size])
        for i in range(batch_size, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            batch_store = _create_with_retry(batch)
            vector_store.merge_from(batch_store)
    t3 = time.perf_counter()

    # 3. 语义检索
    results = vector_store.similarity_search_with_score(query, k=top_k)
    t4 = time.perf_counter()

    # 4. 统计
    original_tokens = count_tokens_approx(content)
    selected_text = "\n\n".join(doc.page_content for doc, _ in results)
    selected_tokens = count_tokens_approx(selected_text)

    return LatencyResult(
        split_ms=(t1 - t0) * 1000,
        embed_ms=(t3 - t2) * 1000,
        search_ms=(t4 - t3) * 1000,
        total_ms=(t4 - t0) * 1000,
        chunk_count=len(chunks),
        selected_count=len(results),
        original_tokens=original_tokens,
        selected_tokens=selected_tokens,
    )


def main():
    # 读取文档
    doc_path = "/Users/apple/Desktop/code/chat-agent/docs/context-management-comparison.md"
    with open(doc_path, encoding="utf-8") as f:
        content = f.read()

    query = "chat-agent 项目的优化点"

    # 共享 Embedding 实例 (避免重复初始化)
    embeddings = DashScopeEmbeddings(
        model="text-embedding-v4",
        dashscope_api_key="sk-ws-H.RPRIDIR.Ja2p.MEUCIG6Df1l-ou4U2TMyY_wpnzDgjdrhZrWUS49_zhxMd6-rAiEAypxrRkaawlp3mPrm_4QDWmo5Oh0ZnVF4NKhr2Cgh5jc",
    )

    print("=" * 70)
    print("FAISS 语义截断延迟测量 - 配置对比")
    print("=" * 70)
    print(f"文档: {doc_path}")
    print(f"文档大小: {len(content)} 字符")
    print(f"Query: {query}")
    print("=" * 70)

    # 测试配置
    configs = [
        {"name": "生产默认", "chunk_size": 1000, "overlap": 200, "top_k": 8},
        {"name": "用户指定", "chunk_size": 1024, "overlap": 200, "top_k": 8},
        {"name": "大块", "chunk_size": 2000, "overlap": 200, "top_k": 8},
    ]

    results_summary = []

    for cfg in configs:
        print(f"\n[配置: {cfg['name']}] chunk_size={cfg['chunk_size']}, overlap={cfg['overlap']}, top_k={cfg['top_k']}")

        # 预热
        print("  预热中...", end="", flush=True)
        measure_faiss_latency(content, query, embeddings, cfg["chunk_size"], cfg["overlap"], cfg["top_k"])
        print(" 完成")

        # 正式测量 (3 次取平均)
        print("  测量中...", end="", flush=True)
        measurements = []
        for _ in range(3):
            r = measure_faiss_latency(content, query, embeddings, cfg["chunk_size"], cfg["overlap"], cfg["top_k"])
            measurements.append(r)
        print(" 完成")

        # 计算平均值
        avg = LatencyResult(
            split_ms=sum(r.split_ms for r in measurements) / 3,
            embed_ms=sum(r.embed_ms for r in measurements) / 3,
            search_ms=sum(r.search_ms for r in measurements) / 3,
            total_ms=sum(r.total_ms for r in measurements) / 3,
            chunk_count=measurements[0].chunk_count,
            selected_count=measurements[0].selected_count,
            original_tokens=measurements[0].original_tokens,
            selected_tokens=measurements[0].selected_tokens,
        )

        results_summary.append({
            "name": cfg["name"],
            "config": cfg,
            "result": avg,
        })

        print(f"  结果: {avg.total_ms:.1f}ms (split:{avg.split_ms:.1f} embed:{avg.embed_ms:.1f} search:{avg.search_ms:.1f})")
        print(f"  切块: {avg.chunk_count}, 命中: {avg.selected_count}, 压缩率: {avg.selected_tokens/avg.original_tokens*100:.1f}%")

    # 汇总对比
    print("\n" + "=" * 70)
    print("汇总对比")
    print("=" * 70)
    print(f"{'配置':<10} {'chunk_size':<12} {'切块数':<8} {'总延迟(ms)':<12} {'向量化(ms)':<12} {'检索(ms)':<10} {'压缩率':<8}")
    print("-" * 70)

    for item in results_summary:
        cfg = item["config"]
        r = item["result"]
        print(f"{item['name']:<10} {cfg['chunk_size']:<12} {r.chunk_count:<8} {r.total_ms:<12.1f} {r.embed_ms:<12.1f} {r.search_ms:<10.1f} {r.selected_tokens/r.original_tokens*100:<8.1f}%")

    print("=" * 70)

    # 瓶颈分析
    print("\n[瓶颈分析]")
    best = min(results_summary, key=lambda x: x["result"].total_ms)
    print(f"最快配置: {best['name']} ({best['result'].total_ms:.1f}ms)")
    print(f"主要瓶颈: 向量化 ({best['result'].embed_ms:.1f}ms, {best['result'].embed_ms/best['result'].total_ms*100:.1f}%)")

    print("\n[优化建议]")
    print("1. 向量化是主要瓶颈 (90%+)，考虑:")
    print("   - 使用本地 Embedding 模型 (如 BAAI/bge-m3)")
    print("   - 批量请求优化 (减少 API 调用次数)")
    print("   - 异步处理 (不阻塞主流程)")
    print("2. FAISS 检索延迟可接受 (~300ms)")
    print("3. Markdown 切块延迟可忽略 (<1ms)")


if __name__ == "__main__":
    main()
