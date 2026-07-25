"""测试图片 token 估算公式 vs API 实际消耗。
同时用两种公式对比：项目当前公式 vs Qwen VL 公式。

用法:
    python scripts/test_image_token.py
"""

import base64
import math
import sys
from pathlib import Path

import httpx
from PIL import Image

# ── 配置 ──────────────────────────────────────────────
IMAGE_PATH = Path("/Users/apple/Desktop/iShot_2026-07-23_15.17.35.png")
API_KEY = "sk-ws-H.EMPHEII.y3Lp.MEUCIQCbfrMW3zW6qAODnFtK9Coe9FMR_cPnXRCNjkkSMGzdaQIgVEnBrrXYGsC8CXkDJUSp4jKYa4_CXJ3ovyuCCHjqO2I"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen3.7-plus"

# ── 公式参数 ──────────────────────────────────────────
# 项目当前公式 (GPT-4V style)
GPT4V_PATCH_SIZE = 28
GPT4V_FIXED_OVERHEAD = 2

# Qwen VL 公式
QWEN_PATCH_SIZE = 28          # patch_size * merge_size = 14 * 2
QWEN_MIN_TOKENS = 4           # min visual tokens per image
QWEN_MAX_TOKENS = 16384       # max visual tokens per image
QWEN_MIN_PIXELS = 256 * 28 * 28   # 200,704
QWEN_MAX_PIXELS = 1280 * 28 * 28  # 1,003,520


# ── 1. 项目当前公式 (GPT-4V) ────────────────────────────
def estimate_gpt4v(width: int, height: int) -> int:
    """ceil(h/28) * ceil(w/28) + 2"""
    return (
        math.ceil(height / GPT4V_PATCH_SIZE)
        * math.ceil(width / GPT4V_PATCH_SIZE)
        + GPT4V_FIXED_OVERHEAD
    )


# ── 2. Qwen VL 公式 ─────────────────────────────────────
def estimate_qwen_vl(width: int, height: int) -> int:
    """
    Qwen VL 图片 token 计算逻辑：
    1. 将图片缩放，使总像素数在 [min_pixels, max_pixels] 范围内
    2. 宽高对齐到 patch_size 的整数倍
    3. tokens = (w_aligned / patch_size) * (h_aligned / patch_size)
    """
    # 计算缩放因子，使总像素在范围内
    total_pixels = width * height
    if total_pixels > QWEN_MAX_PIXELS:
        scale = math.sqrt(QWEN_MAX_PIXELS / total_pixels)
    elif total_pixels < QWEN_MIN_PIXELS:
        scale = math.sqrt(QWEN_MIN_PIXELS / total_pixels)
    else:
        scale = 1.0

    # 缩放后对齐到 patch_size 整数倍
    new_w = int(width * scale)
    new_h = int(height * scale)
    # 向下取整到 patch_size 的倍数
    new_w = (new_w // QWEN_PATCH_SIZE) * QWEN_PATCH_SIZE
    new_h = (new_h // QWEN_PATCH_SIZE) * QWEN_PATCH_SIZE
    # 确保至少有一个 patch
    new_w = max(new_w, QWEN_PATCH_SIZE)
    new_h = max(new_h, QWEN_PATCH_SIZE)

    tokens = (new_w // QWEN_PATCH_SIZE) * (new_h // QWEN_PATCH_SIZE)
    tokens = max(QWEN_MIN_TOKENS, min(tokens, QWEN_MAX_TOKENS))
    return tokens


# ── 3. 读取图片并编码 ────────────────────────────────────
def make_data_url(image_path: Path) -> tuple[str, int, int]:
    img = Image.open(image_path)
    width, height = img.size
    img.close()

    suffix = image_path.suffix.lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".webp": "image/webp", ".gif": "image/gif"}
    mime = mime_map.get(suffix, "image/png")

    raw = image_path.read_bytes()
    b64 = base64.b64encode(raw).decode()
    data_url = f"data:{mime};base64,{b64}"
    return data_url, width, height


# ── 4. 调用 API ─────────────────────────────────────────
def call_api(data_url: str) -> dict:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": "请用一句话描述这张图片的内容。"},
                ],
            }
        ],
        "max_tokens": 100,
    }
    resp = httpx.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["usage"]


def call_api_text_only() -> int:
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "请用一句话描述这张图片的内容。"}],
        "max_tokens": 100,
    }
    resp = httpx.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["usage"]["prompt_tokens"]


# ── 5. 主流程 ────────────────────────────────────────────
def main():
    data_url, width, height = make_data_url(IMAGE_PATH)
    file_size_kb = IMAGE_PATH.stat().st_size / 1024

    print("=" * 65)
    print(f"图片:  {IMAGE_PATH.name}")
    print(f"尺寸:  {width} x {height} ({width * height:,} px)")
    print(f"大小:  {file_size_kb:.1f} KB")
    print("=" * 65)

    # 公式估算
    gpt4v_est = estimate_gpt4v(width, height)
    qwen_est = estimate_qwen_vl(width, height)

    # Qwen 缩放细节
    total_pixels = width * height
    if total_pixels > QWEN_MAX_PIXELS:
        scale = math.sqrt(QWEN_MAX_PIXELS / total_pixels)
    elif total_pixels < QWEN_MIN_PIXELS:
        scale = math.sqrt(QWEN_MIN_PIXELS / total_pixels)
    else:
        scale = 1.0
    new_w = max((int(width * scale) // QWEN_PATCH_SIZE) * QWEN_PATCH_SIZE, QWEN_PATCH_SIZE)
    new_h = max((int(height * scale) // QWEN_PATCH_SIZE) * QWEN_PATCH_SIZE, QWEN_PATCH_SIZE)

    print(f"\n项目公式 (GPT-4V):")
    print(f"  公式:  ceil({height}/28) * ceil({width}/28) + 2")
    print(f"       = {math.ceil(height/28)} * {math.ceil(width/28)} + 2")
    print(f"  估算:  {gpt4v_est} tokens")

    print(f"\nQwen VL 公式:")
    print(f"  缩放:  scale = sqrt({QWEN_MAX_PIXELS:,}/{total_pixels:,}) = {scale:.6f}")
    print(f"       {width}x{height} → {int(width*scale)}x{int(height*scale)} → 对齐 {new_w}x{new_h}")
    print(f"  公式:  ({new_w}/28) * ({new_h}/28) = {new_w//28} * {new_h//28}")
    print(f"  估算:  {qwen_est} tokens")

    # API 调用
    print(f"\n正在调用 {MODEL} API ...")
    usage = call_api(data_url)
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)

    print("正在获取纯文本基线 ...")
    baseline_prompt = call_api_text_only()

    image_tokens_actual = prompt_tokens - baseline_prompt

    print()
    print("=" * 65)
    print("结果对比")
    print("=" * 65)
    print(f"  API prompt_tokens (含图片):   {prompt_tokens}")
    print(f"  API prompt_tokens (纯文本):   {baseline_prompt}")
    print(f"  推算图片实际 token:           {image_tokens_actual}")
    print()
    print(f"  {'公式':<18} {'估算':>8} {'实际':>8} {'差值':>8} {'误差%':>8}")
    print(f"  {'-'*18} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

    for name, est in [("GPT-4V (当前)", gpt4v_est), ("Qwen VL", qwen_est)]:
        diff = image_tokens_actual - est
        pct = (diff / est * 100) if est else 0
        flag = "✅" if abs(pct) < 15 else ("⚠️" if abs(pct) < 30 else "❌")
        print(f"  {name:<18} {est:>8} {image_tokens_actual:>8} {diff:>+8} {pct:>+7.1f}% {flag}")

    print()
    best = min(
        [("GPT-4V", gpt4v_est), ("Qwen VL", qwen_est)],
        key=lambda x: abs(image_tokens_actual - x[1]),
    )
    print(f"  最接近实际的公式: {best[0]} (差 {abs(image_tokens_actual - best[1])} tokens)")


if __name__ == "__main__":
    main()
