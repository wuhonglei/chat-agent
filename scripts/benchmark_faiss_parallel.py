"""
FAISS 语义截断延迟测量脚本 - 串行 vs 并行对比

测量目标:
1. 串行批次处理延迟
2. 并行批次处理延迟 (ThreadPoolExecutor)
3. 延迟对比与加速比
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    """粗略估算 token 数"""
    return len(text) // 2


def _create_faiss_batch(batch, embeddings, max_retries=3):
    """创建单个批次的 FAISS 索引 (带重试)"""
    for attempt in range(max_retries):
        try:
            return FAISS.from_documents(batch, embeddings)
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise


def measure_serial(
    content: str,
    query: str,
    embeddings: DashScopeEmbeddings,
    chunk_size: int = 1024,
    chunk_overlap: int = 200,
    top_k: int = 8,
) -> LatencyResult:
    """串行处理: 逐批次向量化"""

    t0 = time.perf_counter()

    # 1. 切块
    splitter = MarkdownTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = [c.strip() for c in splitter.split_text(content) if c.strip()]
    t1 = time.perf_counter()

    # 2. 向量化 (串行)
    documents = [
        Document(page_content=chunk, metadata={"index": idx})
        for idx, chunk in enumerate(chunks)
    ]

    batch_size = 10
    batches = [documents[i:i + batch_size] for i in range(0, len(documents), batch_size)]

    t2 = time.perf_counter()
    stores = []
    for batch in batches:
        stores.append(_create_faiss_batch(batch, embeddings))
    t3 = time.perf_counter()

    # 3. 合并索引
    vector_store = stores[0]
    for store in stores[1:]:
        vector_store.merge_from(store)

    # 4. 检索
    results = vector_store.similarity_search_with_score(query, k=top_k)
    t4 = time.perf_counter()

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


def measure_parallel(
    content: str,
    query: str,
    embeddings: DashScopeEmbeddings,
    chunk_size: int = 1024,
    chunk_overlap: int = 200,
    top_k: int = 8,
    max_workers: int = 5,
) -> LatencyResult:
    """并行处理: 多线程向量化"""

    t0 = time.perf_counter()

    # 1. 切块
    splitter = MarkdownTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = [c.strip() for c in splitter.split_text(content) if c.strip()]
    t1 = time.perf_counter()

    # 2. 向量化 (并行)
    documents = [
        Document(page_content=chunk, metadata={"index": idx})
        for idx, chunk in enumerate(chunks)
    ]

    batch_size = 10
    batches = [documents[i:i + batch_size] for i in range(0, len(documents), batch_size)]

    t2 = time.perf_counter()
    stores = [None] * len(batches)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有批次
        future_to_idx = {
            executor.submit(_create_faiss_batch, batch, embeddings): idx
            for idx, batch in enumerate(batches)
        }

        # 收集结果
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            stores[idx] = future.result()
    t3 = time.perf_counter()

    # 3. 合并索引
    vector_store = stores[0]
    for store in stores[1:]:
        vector_store.merge_from(store)

    # 4. 检索
    results = vector_store.similarity_search_with_score(query, k=top_k)
    t4 = time.perf_counter()

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


def run_benchmark(label, func, content, query, embeddings, runs=3, **kwargs):
    """运行基准测试"""
    print(f"\n[{label}] 预热中...", end="", flush=True)
    func(content, query, embeddings, **kwargs)
    print(" 完成")

    print(f"[{label}] 测量中 ({runs}次)...", end="", flush=True)
    results = []
    for _ in range(runs):
        results.append(func(content, query, embeddings, **kwargs))
    print(" 完成")

    # 计算平均值
    avg = LatencyResult(
        split_ms=sum(r.split_ms for r in results) / runs,
        embed_ms=sum(r.embed_ms for r in results) / runs,
        search_ms=sum(r.search_ms for r in results) / runs,
        total_ms=sum(r.total_ms for r in results) / runs,
        chunk_count=results[0].chunk_count,
        selected_count=results[0].selected_count,
        original_tokens=results[0].original_tokens,
        selected_tokens=results[0].selected_tokens,
    )
    return avg


def main():
    doc_path = "/Users/apple/Desktop/code/chat-agent/docs/context-management-comparison.md"
    with open(doc_path, encoding="utf-8") as f:
        content = f.read()

    query = "chat-agent 项目的优化点"

    embeddings = DashScopeEmbeddings(
        model="text-embedding-v4",
        dashscope_api_key="sk-ws-H.RPRIDIR.Ja2p.MEUCIG6Df1l-ou4U2TMyY_wpnzDgjdrhZrWUS49_zhxMd6-rAiEAypxrRkaawlp3mPrm_4QDWmo5Oh0ZnVF4NKhr2Cgh5jc",
    )

    print("=" * 70)
    print("FAISS 语义截断延迟测量 - 串行 vs 并行")
    print("=" * 70)
    print(f"文档: {doc_path}")
    print(f"文档大小: {len(content)} 字符")
    print(f"Query: {query}")
    print("=" * 70)

    # 测试配置
    configs = [
        {"chunk_size": 1000, "overlap": 200, "top_k": 8, "label": "生产默认 (1000)"},
        {"chunk_size": 1024, "overlap": 200, "top_k": 8, "label": "用户指定 (1024)"},
        {"chunk_size": 2000, "overlap": 200, "top_k": 8, "label": "大块 (2000)"},
    ]

    all_results = []

    for cfg in configs:
        print(f"\n{'='*70}")
        print(f"配置: {cfg['label']}, chunk_size={cfg['chunk_size']}, overlap={cfg['overlap']}, top_k={cfg['top_k']}")
        print("=" * 70)

        # 串行测试
        serial = run_benchmark(
            "串行", measure_serial, content, query, embeddings,
            chunk_size=cfg["chunk_size"], chunk_overlap=cfg["overlap"], top_k=cfg["top_k"]
        )

        # 并行测试 (不同线程数)
        parallel_results = {}
        for workers in [2, 3, 5]:
            parallel = run_benchmark(
                f"并行 (workers={workers})", measure_parallel, content, query, embeddings,
                chunk_size=cfg["chunk_size"], chunk_overlap=cfg["overlap"], top_k=cfg["top_k"],
                max_workers=workers
            )
            parallel_results[workers] = parallel

        all_results.append({
            "config": cfg,
            "serial": serial,
            "parallel": parallel_results,
        })

    # 汇总对比
    print("\n" + "=" * 70)
    print("汇总对比")
    print("=" * 70)

    for item in all_results:
        cfg = item["config"]
        serial = item["serial"]

        print(f"\n配置: {cfg['label']}")
        print(f"  切块数: {serial.chunk_count}, 批次数: {(serial.chunk_count + 9) // 10}")
        print(f"  压缩率: {serial.selected_tokens}/{serial.original_tokens} = {serial.selected_tokens/serial.original_tokens*100:.1f}%")
        print()
        print(f"  {'模式':<20} {'总延迟(ms)':<12} {'向量化(ms)':<12} {'检索(ms)':<10} {'加速比':<8}")
        print(f"  {'-'*60}")

        # 串行
        print(f"  {'串行':<20} {serial.total_ms:<12.1f} {serial.embed_ms:<12.1f} {serial.search_ms:<10.1f} {'1.00x':<8}")

        # 并行
        for workers, parallel in item["parallel"].items():
            speedup = serial.total_ms / parallel.total_ms
            print(f"  {'并行 (workers=' + str(workers) + ')':<20} {parallel.total_ms:<12.1f} {parallel.embed_ms:<12.1f} {parallel.search_ms:<10.1f} {speedup:<8.2f}x")

    # 最佳配置推荐
    print("\n" + "=" * 70)
    print("最佳配置推荐")
    print("=" * 70)

    best_speedup = 0
    best_config = None
    best_workers = None

    for item in all_results:
        for workers, parallel in item["parallel"].items():
            speedup = item["serial"].total_ms / parallel.total_ms
            if speedup > best_speedup:
                best_speedup = speedup
                best_config = item["config"]
                best_workers = workers

    print(f"配置: {best_config['label']}")
    print(f"并行度: {best_workers} workers")
    print(f"加速比: {best_speedup:.2f}x")

    # 找到该配置的详细数据
    for item in all_results:
        if item["config"] == best_config:
            serial = item["serial"]
            parallel = item["parallel"][best_workers]
            print(f"串行延迟: {serial.total_ms:.1f}ms")
            print(f"并行延迟: {parallel.total_ms:.1f}ms")
            print(f"节省时间: {serial.total_ms - parallel.total_ms:.1f}ms")
            break


if __name__ == "__main__":
    main()
