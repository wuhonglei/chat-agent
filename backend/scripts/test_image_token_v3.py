"""最终版：测试图片 token 估算公式 vs API 实际消耗。

对比三种公式：
1. 项目当前公式 (GPT-4V): ceil(h/28) * ceil(w/28) + 2
2. Qwen VL (14x14 patch): ceil(h/14) * ceil(w/14) + ~20 (含固定前缀)
3. 拟合公式: 基于实际数据反推

用法:
    python scripts/test_image_token_v3.py
"""

import base64
import math
from pathlib import Path

import httpx
from PIL import Image

API_KEY = "sk-ws-H.EMPHEII.y3Lp.MEUCIQCbfrMW3zW6qAODnFtK9Coe9FMR_cPnXRCNjkkSMGzdaQIgVEnBrrXYGsC8CXkDJUSp4jKYa4_CXJ3ovyuCCHjqO2I"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen3.7-plus"


def call_api_with_image(image_path: Path, prompt: str = "描述这张图片。") -> dict:
    """调用 API 返回完整 usage。"""
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    img = Image.open(image_path)
    w, h = img.size
    img.close()
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    data_url = f"data:{mime};base64,{b64}"

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": data_url}},
            {"type": "text", "text": prompt},
        ]}],
        "max_tokens": 50,
    }
    resp = httpx.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["usage"]


def call_api_text_only(prompt: str = "描述这张图片。") -> int:
    """纯文本基线。"""
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 50}
    resp = httpx.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["usage"]["prompt_tokens"]


def create_test_image(width: int, height: int, color=(100, 150, 200)) -> Path:
    img = Image.new("RGB", (width, height), color)
    path = Path(f"/tmp/test_{width}x{height}.png")
    img.save(path)
    return path


def get_actual_image_tokens(image_path: Path) -> int:
    usage = call_api_with_image(image_path)
    baseline = call_api_text_only()
    return usage["prompt_tokens"] - baseline


# ── 公式定义 ──────────────────────────────────────────

def formula_gpt4v(w: int, h: int) -> int:
    """项目当前公式: ceil(h/28)*ceil(w/28) + 2"""
    return math.ceil(h / 28) * math.ceil(w / 28) + 2


def formula_qwen_raw(w: int, h: int) -> int:
    """Qwen3-VL 原始 (不缩放): ceil(h/14)*ceil(w/14)"""
    return math.ceil(h / 14) * math.ceil(w / 14)


def formula_qwen_with_resize(w: int, h: int, min_edge: int = 448, max_edge: int = 2048) -> int:
    """Qwen3-VL 带缩放 (最短边>=448, 最长边<=2048):"""
    if min(h, w) < min_edge:
        scale = min_edge / min(h, w)
        w, h = int(w * scale), int(h * scale)
    if max(h, w) > max_edge:
        scale = max_edge / max(h, w)
        w, h = int(w * scale), int(h * scale)
    # 对齐到 14 的倍数
    w = (w // 14) * 14
    h = (h // 14) * 14
    return (w // 14) * (h // 14) + 20  # +20 for fixed visual prefix/suffix


def formula_pixel_budget(w: int, h: int, max_pixels: int = 2_007_040) -> int:
    """基于总像素预算缩放 + 28x28 patch + 2 overhead。"""
    total = w * h
    if total > max_pixels:
        scale = math.sqrt(max_pixels / total)
        w, h = int(w * scale), int(h * scale)
    w = (w // 28) * 28
    h = (h // 28) * 28
    w = max(w, 28)
    h = max(h, 28)
    return (w // 28) * (h // 28) + 2


# ── 主流程 ────────────────────────────────────────────

def main():
    # 获取纯文本基线
    print("获取纯文本基线 ...")
    baseline = call_api_text_only()
    print(f"纯文本基线 prompt_tokens: {baseline}")

    # 测试用例
    test_cases = [
        (Path("/Users/apple/Desktop/iShot_2026-07-23_15.17.35.png"), "真实截图 3526x2240"),
        (create_test_image(1024, 1024), "纯色图 1024x1024"),
        (create_test_image(2048, 1536), "纯色图 2048x1536"),
        (create_test_image(512, 512), "纯色图 512x512"),
        (create_test_image(4096, 2160), "纯色图 4096x2160"),
        (create_test_image(256, 256), "纯色图 256x256"),
    ]

    results = []
    for path, desc in test_cases:
        img = Image.open(path)
        w, h = img.size
        img.close()
        print(f"\n测试: {desc} ({w}x{h}, {w*h:,} px) ...")
        try:
            usage = call_api_with_image(path)
            actual = usage["prompt_tokens"] - baseline
            print(f"  实际图片 token: {actual}")
            results.append((path.name, w, h, actual))
        except Exception as e:
            print(f"  ❌ 失败: {e}")

    # 对比表格
    formulas = [
        ("GPT-4V (当前)", formula_gpt4v),
        ("Qwen 14x14 原始", formula_qwen_raw),
        ("Qwen 14x14+缩放", formula_qwen_with_resize),
        ("像素预算 28x28", formula_pixel_budget),
    ]

    print("\n" + "=" * 90)
    print("各公式对比")
    print("=" * 90)

    # 表头
    header = f"{'图片':<25} {'尺寸':>12} {'实际':>6}"
    for name, _ in formulas:
        header += f" {name:>14}"
    print(header)
    print("-" * 90)

    # 每种公式的总误差
    total_errors = {name: 0 for name, _ in formulas}

    for name, w, h, actual in results:
        row = f"{name:<25} {w:>5}x{h:<5} {actual:>6}"
        best_est = None
        best_err = float("inf")
        for fname, fn in formulas:
            est = fn(w, h)
            err = abs(actual - est)
            total_errors[fname] += err
            if err < best_err:
                best_err = err
                best_est = est
            row += f" {est:>14}"
        print(row)

    print("-" * 90)
    summary = f"{'总绝对误差':<25} {'':>12} {'':>6}"
    best_formula = min(total_errors, key=total_errors.get)
    for fname, _ in formulas:
        e = total_errors[fname]
        flag = " ✅" if fname == best_formula else ""
        summary += f" {e:>14}{flag}"
    print(summary)

    # 每张图最佳公式
    print("\n" + "=" * 90)
    print("每张图最接近的公式")
    print("=" * 90)
    for name, w, h, actual in results:
        best_name = None
        best_err = float("inf")
        for fname, fn in formulas:
            est = fn(w, h)
            err = abs(actual - est)
            if err < best_err:
                best_err = err
                best_name = fname
        pct = best_err / actual * 100 if actual else 0
        flag = "✅" if pct < 10 else ("⚠️" if pct < 30 else "❌")
        print(f"  {name:<25} → {best_name:<18} 差 {best_err} tokens ({pct:.1f}%) {flag}")

    # 结论
    print("\n" + "=" * 90)
    print("结论")
    print("=" * 90)
    print(f"  最佳匹配公式: {best_formula} (总绝对误差 {total_errors[best_formula]})")
    print(f"  项目当前公式: GPT-4V (总绝对误差 {total_errors['GPT-4V (当前)']})")


if __name__ == "__main__":
    main()
