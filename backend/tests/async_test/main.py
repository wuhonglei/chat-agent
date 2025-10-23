import asyncio
import time


async def test_async_simple():
    """不使用 await，直接返回普通值"""
    print("test_async_simple")
    return 1


async def test_async_with_await():
    """使用 await 等待异步操作"""
    print("test_async_with_await - 开始")
    await asyncio.sleep(1)  # 模拟异步操作
    print("test_async_with_await - 结束")
    return 2


async def test_async_mixed():
    """混合使用：有些地方用 await，有些地方不用"""
    print("test_async_mixed - 开始")

    # 不使用 await，直接计算
    result1 = 10 + 20

    # 使用 await 等待异步操作
    await asyncio.sleep(0.5)

    # 不使用 await，直接返回
    return result1


async def main():
    print("=== 测试不同的 async 函数模式 ===")

    # 1. 不使用 await 的函数
    result1 = await test_async_simple()
    print(f"结果1: {result1}")

    # 2. 使用 await 的函数
    result2 = await test_async_with_await()
    print(f"结果2: {result2}")

    # 3. 混合使用的函数
    result3 = await test_async_mixed()
    print(f"结果3: {result3}")


if __name__ == "__main__":
    asyncio.run(main())
