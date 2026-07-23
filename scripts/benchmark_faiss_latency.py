"""
FAISS 语义截断延迟测量脚本

测量目标:
1. Markdown 切块延迟
2. 向量化 + FAISS 索引构建延迟
3. 语义检索延迟
4. 总体延迟

配置参数:
- chunk_size: 1024
- overlap: 200
- splitter: MarkdownTextSplitter
- top-k: 8
- embedding: DashScope text-embedding-v4
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
    embeddings = DashScopeEmbeddings(
        model="text-embedding-v4",
        dashscope_api_key="sk-ws-H.RPRIDIR.Ja2p.MEUCIG6Df1l-ou4U2TMyY_wpnzDgjdrhZrWUS49_zhxMd6-rAiEAypxrRkaawlp3mPrm_4QDWmo5Oh0ZnVF4NKhr2Cgh5jc",
    )
    documents = [
        Document(page_content=chunk, metadata={"index": idx})
        for idx, chunk in enumerate(chunks)
    ]
    t2 = time.perf_counter()

    # DashScope 限制每次最多 20 个文档，需要分批处理
    batch_size = 10  # DashScope 限制
    if len(documents) <= batch_size:
        vector_store = FAISS.from_documents(documents, embeddings)
    else:
        # 第一批创建索引
        vector_store = FAISS.from_documents(documents[:batch_size], embeddings)
        # 后续批次合并
        for i in range(batch_size, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            batch_store = FAISS.from_documents(batch, embeddings)
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

    print("=" * 60)
    print("FAISS 语义截断延迟测量")
    print("=" * 60)
    print(f"文档: {doc_path}")
    print(f"文档大小: {len(content)} 字符")
    print(f"Query: {query}")
    print(f"chunk_size: 1024, overlap: 200, top_k: 8")
    print("=" * 60)

    # 预热
    print("\n[预热] 首次调用 (含模型加载)...")
    warmup = measure_faiss_latency(content, query)
    print(f"  预热耗时: {warmup.total_ms:.1f}ms")

    # 正式测量 (3 次取平均)
    print("\n[正式测量] 3 次调用取平均...")
    results = []
    for i in range(3):
        r = measure_faiss_latency(content, query)
        results.append(r)
        print(f"  第 {i+1} 次: {r.total_ms:.1f}ms (split:{r.split_ms:.1f} embed:{r.embed_ms:.1f} search:{r.search_ms:.1f})")

    # 计算平均值
    avg = LatencyResult(
        split_ms=sum(r.split_ms for r in results) / 3,
        embed_ms=sum(r.embed_ms for r in results) / 3,
        search_ms=sum(r.search_ms for r in results) / 3,
        total_ms=sum(r.total_ms for r in results) / 3,
        chunk_count=results[0].chunk_count,
        selected_count=results[0].selected_count,
        original_tokens=results[0].original_tokens,
        selected_tokens=results[0].selected_tokens,
    )

    print("\n" + "=" * 60)
    print("测量结果 (平均)")
    print("=" * 60)
    print(f"切块数量: {avg.chunk_count}")
    print(f"检索命中: {avg.selected_count} chunks")
    print(f"原始 token: ~{avg.original_tokens}")
    print(f"筛选后 token: ~{avg.selected_tokens}")
    print(f"压缩率: {avg.selected_tokens/avg.original_tokens*100:.1f}%")
    print("-" * 60)
    print(f"Markdown 切块:   {avg.split_ms:>8.2f}ms  ({avg.split_ms/avg.total_ms*100:.1f}%)")
    print(f"向量化+索引构建: {avg.embed_ms:>8.2f}ms  ({avg.embed_ms/avg.total_ms*100:.1f}%)")
    print(f"语义检索:        {avg.search_ms:>8.2f}ms  ({avg.search_ms/avg.total_ms*100:.1f}%)")
    print(f"-" * 60)
    print(f"总延迟:          {avg.total_ms:>8.2f}ms")
    print("=" * 60)

    # 评估影响
    print("\n[评估]")
    if avg.total_ms < 100:
        print("✓ 延迟极低 (<100ms)，对用户体验几乎无影响")
    elif avg.total_ms < 500:
        print("✓ 延迟较低 (<500ms)，用户可感知但可接受")
    elif avg.total_ms < 1000:
        print("⚠ 延迟中等 (500ms-1s)，可能影响流式体验")
    else:
        print("✗ 延迟较高 (>1s)，建议优化或考虑异步处理")

    # 主要瓶颈分析
    max_stage = max(
        ("切块", avg.split_ms),
        ("向量化", avg.embed_ms),
        ("检索", avg.search_ms),
        key=lambda x: x[1],
    )
    print(f"主要瓶颈: {max_stage[0]} ({max_stage[1]:.1f}ms, {max_stage[1]/avg.total_ms*100:.1f}%)")


if __name__ == "__main__":
    main()
