"""
MarkdownTextSplitter vs MarkdownHeaderTextSplitter 对比演示

核心差异：
- MarkdownTextSplitter     → 按 chunk_size 递归切分，markdown 感知的分隔符优先级
- MarkdownHeaderTextSplitter → 按标题结构切分，每个 chunk 对应一个章节，标题转为 metadata
"""

import json
from pathlib import Path
from langchain_text_splitters import MarkdownTextSplitter, MarkdownHeaderTextSplitter

# 输出目录
OUTPUT_DIR = Path(__file__).parent / "splitter_output"

# ──────────────────────────────────────────────
# 1. 加载测试文件
# ──────────────────────────────────────────────
files = {
    "复习计划.md": Path("/Users/apple/Desktop/code/web-recruit/interview_experience/复习计划.md").read_text(encoding="utf-8"),
    "高频考点分析.md": Path("/Users/apple/Desktop/code/web-recruit/interview_experience/高频考点分析.md").read_text(encoding="utf-8"),
}

# ──────────────────────────────────────────────
# 2. MarkdownTextSplitter（递归切分，按 chunk_size）
# ──────────────────────────────────────────────
splitter_recursive = MarkdownTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
)

# ──────────────────────────────────────────────
# 3. MarkdownHeaderTextSplitter（按标题结构切分）
# ──────────────────────────────────────────────
headers_to_split_on = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]
splitter_header = MarkdownHeaderTextSplitter(
    headers_to_split_on=headers_to_split_on,
    strip_headers=False,   # 保留标题在正文中，方便对比
)

# ──────────────────────────────────────────────
# 4. 对比输出
# ──────────────────────────────────────────────
SEPARATOR = "=" * 70


def save_chunks(chunks, out_path: Path, splitter_name: str, strip_headers: bool = True):
    """将切分结果保存为可读的 markdown 文件"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {splitter_name} 切分结果\n", f"共 {len(chunks)} 个 chunk\n\n"]
    for i, doc in enumerate(chunks):
        content = doc.page_content
        meta = doc.metadata
        lines.append(f"---\n\n## Chunk {i+1} (len={len(content)})\n\n")
        if meta:
            lines.append(f"**metadata**: `{json.dumps(meta, ensure_ascii=False)}`\n\n")
        lines.append(f"```\n{content}\n```\n\n")
    out_path.write_text("".join(lines), encoding="utf-8")
    print(f"  💾 已保存: {out_path}")


for fname, text in files.items():
    print(SEPARATOR)
    print(f"📄 文件: {fname}")
    print(f"   原文长度: {len(text)} 字符")
    print(SEPARATOR)

    # --- 方法 A: MarkdownTextSplitter ---
    # split_text → list[str]；create_documents → list[Document]
    chunks_recursive = splitter_recursive.create_documents([text])
    stem = Path(fname).stem
    print(f"\n【A】MarkdownTextSplitter (chunk_size=500, overlap=50)")
    print(f"    切分结果: {len(chunks_recursive)} 个 chunk\n")
    save_chunks(chunks_recursive, OUTPUT_DIR / stem / "A_recursive_splitter.md", "MarkdownTextSplitter")
    for i, doc in enumerate(chunks_recursive):
        content = doc.page_content
        print(f"  --- chunk {i+1} (len={len(content)}) ---")
        # 只打印前 200 字符，避免刷屏
        preview = content[:200].replace("\n", "\n    ")
        print(f"    {preview}{'...' if len(content) > 200 else ''}")
        print()

    # --- 方法 B: MarkdownHeaderTextSplitter ---
    chunks_header = splitter_header.split_text(text)
    print(f"\n【B】MarkdownHeaderTextSplitter (strip_headers=False)")
    print(f"    切分结果: {len(chunks_header)} 个 chunk\n")
    save_chunks(chunks_header, OUTPUT_DIR / stem / "B_header_splitter.md", "MarkdownHeaderTextSplitter")
    for i, doc in enumerate(chunks_header):
        content = doc.page_content
        meta = doc.metadata
        print(f"  --- chunk {i+1} (len={len(content)}) ---")
        print(f"    metadata: {json.dumps(meta, ensure_ascii=False)}")
        preview = content[:200].replace("\n", "\n    ")
        print(f"    {preview}{'...' if len(content) > 200 else ''}")
        print()

    print()

# ──────────────────────────────────────────────
# 5. 差异总结
# ──────────────────────────────────────────────
print(SEPARATOR)
print("📊 差异总结")
print(SEPARATOR)
print("""
┌─────────────────────┬──────────────────────────────┬──────────────────────────────┐
│                     │  MarkdownTextSplitter        │  MarkdownHeaderTextSplitter  │
├─────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 切分依据            │ chunk_size (字符数)           │ 标题层级结构                 │
│ 继承关系            │ RecursiveCharacterTextSplitter│ 独立实现，不继承递归切分器    │
│ 分隔符优先级        │ \\\\n#{1,6} > \\\\n\\\\n > … > 空格│ 仅识别 # / ## / ### 等标题行 │
│ chunk 大小          │ 受 chunk_size 控制            │ 由内容自然决定（可能很大）    │
│ metadata            │ 无（纯文本）                 │ 标题文本写入 metadata dict    │
│ chunk_overlap       │ ✅ 支持                      │ ❌ 不支持                    │
│ 适用场景            │ RAG 向量检索（需固定长度）    │ 知识库索引（需保留层级语义）  │
│ 标题处理            │ 标题保留在正文中              │ strip_headers=True 时剥离     │
│ 代码块保护          │ ✅ 递归切分器会感知            │ ✅ 识别 ``` 围栏              │
└─────────────────────┴──────────────────────────────┴──────────────────────────────┘

选型建议：
  • 纯 RAG 场景 → MarkdownTextSplitter（控制 chunk 大小，embedding 效果稳定）
  • 知识库/文档站 → MarkdownHeaderTextSplitter（保留文档结构，metadata 可用于过滤）
  • 生产级方案 → 两者组合：先 Header 切分保留结构，再对超长 chunk 做 Recursive 二次切分
""")
