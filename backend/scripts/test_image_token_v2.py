"""反推 DashScope API 实际使用的图片 token 计算参数。

策略：已知 actual_tokens=2522, 原始尺寸=3526x2240,
反推 max_pixels 候选值，再多张图片交叉验证。

用法:
    python scripts/test_image_token_v2.py
"""

import base64
import math
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

API_KEY = "sk-ws-H.EMPHEII.y3Lp.MEUCIQCbfrMW3zW6qAODnFtK9Coe9FMR_cPnXRCNjkkSMGzdaQIgVEnBrrXYGsC8CXkDJUSp4jKYa4_CXJ3ovyuCCHjqO2I"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen3.7-plus"
PATCH_SIZE = 28


def estimate_qwen(width: int, height: int, max_pixels: int) -> int:
    """Qwen VL token 估算：缩放到 max_pixels 以内，对齐后计算 patch 数。"""
    total = width * height
    if total > max_pixels:
        scale = math.sqrt(max_pixels / total)
    else:
        scale = 1.0
    new_w = max((int(width * scale) // PATCH_SIZE) * PATCH_SIZE, PATCH_SIZE)
    new_h = max((int(height * scale) // PATCH_SIZE) * PATCH_SIZE, PATCH_SIZE)
    return (new_w // PATCH_SIZE) * (new_h // PATCH_SIZE)


def get_image_tokens(image_path: Path) -> tuple[int, int, int, int]:
    """调用 API 获取图片 token 数。返回 (image_tokens, prompt_tokens, baseline_tokens, completion_tokens)。"""
    img = Image.open(image_path)
    w, h = img.size
    img.close()

    suffix = image_path.suffix.lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    mime = mime_map.get(suffix, "image/png")
    raw = image_path.read_bytes()
    b64 = base64.b64encode(raw).decode()
    data_url = f"data:{mime};base64,{b64}"

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    # 含图片
    payload_img = {
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": data_url}},
            {"type": "text", "text": "描述这张图片。"},
        ]}],
        "max_tokens": 50,
    }
    resp = httpx.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload_img, timeout=120)
    resp.raise_for_status()
    usage_img = resp.json()["usage"]

    # 纯文本基线
    payload_txt = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "描述这张图片。"}],
        "max_tokens": 50,
    }
    resp2 = httpx.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload_txt, timeout=60)
    resp2.raise_for_status()
    baseline = resp2.json()["usage"]["prompt_tokens"]

    image_tokens = usage_img["prompt_tokens"] - baseline
    return image_tokens, usage_img["prompt_tokens"], baseline, usage_img["completion_tokens"]


def create_test_image(width: int, height: int) -> Path:
    """创建纯色测试图片。"""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    path = Path(f"/tmp/test_{width}x{height}.png")
    img.save(path)
    return path


def main():
    print("=" * 70)
    print("反推 DashScope API 图片 token 计算参数")
    print("=" * 70)

    # 测试用例：(路径或尺寸, 描述)
    test_cases = [
        ("real", Path("/Users/apple/Desktop/iShot_2026-07-23_15.17.35.png"), "真实截图 3526x2240"),
        ("gen", (1024, 1024), "生成图 1024x1024"),
        ("gen", (2048, 1536), "生成图 2048x1536"),
        ("gen", (512, 512), "生成图 512x512"),
    ]

    results = []

    for kind, src, desc in test_cases:
        if kind == "real":
            path = src
            img = Image.open(path)
            w, h = img.size
            img.close()
        else:
            w, h = src
            path = create_test_image(w, h)

        print(f"\n测试: {desc} ({w}x{h}, {w*h:,} px)")
        try:
            image_tokens, prompt_t, base_t, comp_t = get_image_tokens(path)
            print(f"  API: prompt={prompt_t}, baseline={base_t}, image={image_tokens}, completion={comp_t}")
            results.append((w, h, image_tokens))
        except Exception as e:
            print(f"  ❌ API 调用失败: {e}")
            continue

    # 反推 max_pixels
    print("\n" + "=" * 70)
    print("反推分析")
    print("=" * 70)

    # 常见的 Qwen max_pixels 候选值
    candidates = [
        256 * 28 * 28,    # 200,704    (min_pixels default)
        512 * 28 * 28,    # 401,408
        768 * 28 * 28,    # 602,112
        1024 * 28 * 28,   # 802,816
        1280 * 28 * 28,   # 1,003,520  (max_pixels default)
        1536 * 28 * 28,   # 1,204,224
        2048 * 28 * 28,   # 1,605,632
        2560 * 28 * 28,   # 2,007,040
        3072 * 28 * 28,   # 2,408,448
        3584 * 28 * 28,   # 2,809,856
        4096 * 28 * 28,   # 3,211,264
        5120 * 28 * 28,   # 4,014,080
    ]

    print(f"\n{'max_pixels':>12}  {'tokens格':>8}", end="")
    for w, h, actual in results:
        print(f"  {'实际':>6} {'估算':>6} {'差':>6}", end="")
    print()

    best_mp = None
    best_total_err = float("inf")

    for mp in candidates:
        label = f"{mp:>12,}"
        # 找对应的 grid 数
        grid_label = ""
        # 检查是否是某个 N*28*28 的形式
        n = mp / (28 * 28)
        if n == int(n):
            grid_label = f"{int(n)}*28²"

        print(f"{label}  {grid_label:>8}", end="")

        total_err = 0
        for w, h, actual in results:
            est = estimate_qwen(w, h, mp)
            err = actual - est
            total_err += abs(err)
            print(f"  {actual:>6} {est:>6} {err:>+6}", end="")

        if total_err < best_total_err:
            best_total_err = total_err
            best_mp = mp
        print()

    print(f"\n最佳匹配 max_pixels = {best_mp:,} ({best_mp // (28*28)} * 28²)")
    print(f"总绝对误差: {best_total_err}")

    # 用最佳参数重新计算所有
    print(f"\n{'='*70}")
    print(f"最终对比 (max_pixels = {best_mp:,})")
    print(f"{'='*70}")
    print(f"{'图片':<30} {'尺寸':>12} {'实际token':>10} {'估算token':>10} {'误差':>8}")
    print(f"{'-'*30} {'-'*12} {'-'*10} {'-'*10} {'-'*8}")

    for w, h, actual in results:
        est = estimate_qwen(w, h, best_mp)
        diff = actual - est
        pct = (diff / actual * 100) if actual else 0
        name = f"{w}x{h}"
        print(f"{name:<30} {w*h:>12,} {actual:>10} {est:>10} {diff:>+7d} ({pct:>+.1f}%)")


if __name__ == "__main__":
    main()
