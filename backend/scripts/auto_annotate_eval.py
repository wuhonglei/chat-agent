"""用 LLM 为评估集生成初版标注（ground_truth_points + 打分）。

流程：每条样本分两步
  Step 1: 只看 query → 生成 ground_truth_points
  Step 2: 对比 ground_truth_points 与 answer → 打 correctness_score + completeness_score

用法:
    uv run python scripts/auto_annotate_eval.py
"""

import json
import time
from pathlib import Path

import httpx

# ── 配置 ────────────────────────────────────────────────────────
API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY_ENV = "DASHSCOPE_API_KEY"  # 从环境变量读取
MODEL = "qwen-max"

EVAL_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "eval_set"
    / "v1.0"
    / "eval_samples.json"
)
OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "eval_set"
    / "v1.0"
    / "eval_samples_annotated.json"
)

# 并发控制
BATCH_SIZE = 5
DELAY_BETWEEN_BATCHES = 2  # 秒


def get_api_key() -> str:
    import os

    key = os.environ.get(API_KEY_ENV)
    if not key:
        # 尝试从 .env 读取
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("DASHSCOPE_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        raise RuntimeError(f"未找到 {API_KEY_ENV}，请设置环境变量或写入 backend/.env")
    return key


def call_llm(api_key: str, system: str, user: str) -> str:
    """调用 LLM，返回文本响应。"""
    resp = httpx.post(
        f"{API_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": 1000,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


SYSTEM_STEP1 = """你是一个评估集标注助手。根据用户的问题，列出一个好的回答应该包含的要点。

规则：
- 每个要点一句话，2-5 个要点
- 要点是「该覆盖哪些方面」，不是具体答案
- 输出 JSON 数组格式

示例输入：住三亚海棠湾中午如何吃饭
示例输出：
["用餐地点分类（酒店内/美食街/周边餐厅）", "各方案的价格区间", "营业时间（中午是否营业）", "交通方式或距离", "是否需要预约"]"""

SYSTEM_STEP2 = """你是一个回答质量评估器。根据用户问题、标准要点、模型回答，打两个分。

## 重要规则

1. 如果输入中包含【参考资料/工具返回内容】，这些内容是从知识库、搜索引擎、用户附件中获取的真实数据。模型回答是基于这些参考资料生成的。评分时必须以参考资料为事实依据，不要用你自身的知识判断事实性。
2. 如果参考资料中确认了某个信息（如日期、金额、名称），模型回答中包含该信息就是正确的，不是虚构。
3. 只有当模型回答中的信息既不在参考资料中，也无法从参考资料推导出来时，才能判定为「虚构」。
4. **重要**：逐字核对专有名词，不得基于相似性推断。例如「深圳大学图书馆北馆」和「深圳图书馆北馆」是不同场所，地址不同。

## 评分标准

correctness_score（准确性，1-5）：回答中说的内容是否正确
  5=完全正确 4=基本正确有小瑕疵 3=部分正确有明显错误 2=大部分错误 1=完全错误
  注意：有参考资料时，以参考资料为准判断正确性；无参考资料时，以常识和逻辑判断。

completeness_score（完整性，1-5）：回答是否覆盖了标准要点
  5=覆盖率>=90% 4=覆盖率>=70% 3=覆盖率>=50% 2=覆盖率<50% 1=几乎未覆盖

scene_tag（场景标签）：qa=知识问答 rag=检索回答 tool=工具调用 chat=闲聊创意

输出 JSON：
{"correctness_score": N, "completeness_score": N, "scene_tag": "...", "notes": "扣分原因简述"}"""


def annotate_one(api_key: str, item: dict) -> dict:
    """为一条样本生成标注。"""
    query = item.get("query", "")
    answer = item.get("answer", "")

    # Step 1: 生成 ground_truth_points（不看 answer）
    points_raw = call_llm(api_key, SYSTEM_STEP1, query)
    try:
        # 提取 JSON 数组
        if "[" in points_raw:
            json_str = points_raw[points_raw.index("[") : points_raw.rindex("]") + 1]
            ground_truth_points = json.loads(json_str)
        else:
            ground_truth_points = [
                p.strip() for p in points_raw.strip().split("\n") if p.strip()
            ]
    except (json.JSONDecodeError, ValueError):
        ground_truth_points = [points_raw.strip()]

    # Step 2: 对比打分（如果有 context，传给裁判作为参照）
    context = item.get("context", "")
    context_section = f"\n\n【参考资料/工具返回内容】\n{context}" if context else ""
    score_input = (
        f"【用户问题】{query}\n\n【标准要点】\n"
        + "\n".join(f"- {p}" for p in ground_truth_points)
        + context_section
        + f"\n\n【模型回答】\n{answer[:4000]}"
    )
    score_raw = call_llm(api_key, SYSTEM_STEP2, score_input)
    try:
        if "{" in score_raw:
            json_str = score_raw[score_raw.index("{") : score_raw.rindex("}") + 1]
            scores = json.loads(json_str)
        else:
            scores = {}
    except (json.JSONDecodeError, ValueError):
        scores = {}

    return {
        "ground_truth_points": ground_truth_points,
        "scene_tag": scores.get("scene_tag", ""),
        "correctness_score": scores.get("correctness_score"),
        "completeness_score": scores.get("completeness_score"),
        "notes": scores.get("notes", ""),
        "_auto_annotated": True,
    }


def main():
    api_key = get_api_key()
    items = json.loads(EVAL_PATH.read_text())
    print(f"Loaded {len(items)} eval samples")

    # 断点续传：检查已标注的
    if OUTPUT_PATH.exists():
        existing = json.loads(OUTPUT_PATH.read_text())
        done_ids = {
            e["trace_id"]
            for e in existing
            if e.get("annotation", {}).get("_auto_annotated")
        }
        print(f"Already annotated: {len(done_ids)}")
    else:
        existing = list(items)
        done_ids = set()

    total = len(items)
    annotated = 0
    errors = 0

    for i, item in enumerate(items):
        if item["trace_id"] in done_ids:
            continue

        try:
            annotation = annotate_one(api_key, item)
            item["annotation"] = annotation
            annotated += 1
            print(f"  [{i + 1}/{total}] {item['trace_id'][:12]}... ✓")
        except Exception as e:
            errors += 1
            print(f"  [{i + 1}/{total}] {item['trace_id'][:12]}... ✗ {e}")
            item["annotation"] = {
                "ground_truth_points": [],
                "scene_tag": "",
                "correctness_score": None,
                "completeness_score": None,
                "notes": f"auto-annotate error: {e}",
                "_auto_annotated": False,
            }

        # 每批保存一次（断点续传）
        if annotated % BATCH_SIZE == 0:
            OUTPUT_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2))
            time.sleep(DELAY_BETWEEN_BATCHES)

    # 最终保存
    OUTPUT_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2))
    print(f"\nDone! Annotated: {annotated}, Errors: {errors}")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
