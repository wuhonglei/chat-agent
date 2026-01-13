import asyncio
import time


async def fetch_data(task_id: int, delay: float) -> str:
    """模拟异步获取数据的函数"""
    print(f"任务 {task_id} 开始执行，延迟 {delay} 秒")
    await asyncio.sleep(delay)
    result = f"任务 {task_id} 完成，获取到数据"
    print(result)
    return result


async def simple_gather_example():
    """简单的 asyncio.gather 示例"""
    print("=== 简单 asyncio.gather 示例 ===")

    # 创建多个异步任务
    tasks = [
        fetch_data(1, 1.0),
        fetch_data(2, 2.0),
        fetch_data(3, 1.5),
        fetch_data(4, 0.5),
    ]

    start_time = time.time()

    # 使用 asyncio.gather 并发执行所有任务
    results = await asyncio.gather(*tasks)

    end_time = time.time()

    print(f"\n所有任务完成，总耗时: {end_time - start_time:.2f} 秒")
    print("所有结果:")
    for i, result in enumerate(results, 1):
        print(f"  结果 {i}: {result}")


async def gather_with_return_exceptions_example():
    """演示 return_exceptions=True 的用法"""
    print("\n=== asyncio.gather 异常处理示例 ===")

    async def failing_task(task_id: int) -> str:
        await asyncio.sleep(0.5)
        if task_id == 2:
            raise ValueError(f"任务 {task_id} 故意抛出异常")
        return f"任务 {task_id} 成功完成"

    # 创建包含会失败的任务
    tasks = [
        failing_task(1),
        failing_task(2),  # 这个任务会失败
        failing_task(3),
    ]

    try:
        # 使用 return_exceptions=True，异常会被包含在结果中而不是抛出
        results = await asyncio.gather(*tasks, return_exceptions=True)

        print("处理结果:")
        for i, result in enumerate(results, 1):
            if isinstance(result, Exception):
                print(f"  任务 {i} 失败: {result}")
            else:
                print(f"  任务 {i} 成功: {result}")

    except Exception as e:
        print(f"捕获到异常: {e}")


async def gather_without_return_exceptions_example():
    """演示不使用 return_exceptions 时的异常处理"""
    print("\n=== 不使用 return_exceptions 的异常处理示例 ===")

    async def failing_task(task_id: int) -> str:
        await asyncio.sleep(0.5)
        if task_id == 2:
            raise ValueError(f"任务 {task_id} 故意抛出异常")
        return f"任务 {task_id} 成功完成"

    # 创建包含会失败的任务
    tasks = [
        failing_task(1),
        failing_task(2),  # 这个任务会失败
        failing_task(3),
    ]

    try:
        # 不使用 return_exceptions=True，异常会直接抛出
        results = await asyncio.gather(*tasks)
        print("所有任务都成功完成")

    except Exception as e:
        print(f"捕获到异常: {e}")
        print("当有任务失败时，整个 gather 操作会停止")


async def gather_with_partial_results_example():
    """演示 gather 的部分结果处理"""
    print("\n=== 部分结果处理示例 ===")

    async def variable_task(task_id: int, delay: float) -> str:
        print(f"任务 {task_id} 开始，延迟 {delay} 秒")
        await asyncio.sleep(delay)
        return f"任务 {task_id} 完成"

    # 创建不同延迟的任务
    tasks = [
        variable_task(1, 0.5),
        variable_task(2, 1.0),
        variable_task(3, 2.0),
        variable_task(4, 0.3),
    ]

    start_time = time.time()

    # 并发执行所有任务
    results = await asyncio.gather(*tasks)

    end_time = time.time()

    print(f"所有任务完成，总耗时: {end_time - start_time:.2f} 秒")
    print("结果按原始顺序返回:")
    for result in results:
        print(f"  {result}")


async def main():
    """主函数，运行所有示例"""
    print("asyncio.gather 示例集合\n")

    # 运行所有示例
    await simple_gather_example()
    await gather_with_return_exceptions_example()
    await gather_without_return_exceptions_example()
    await gather_with_partial_results_example()

    print("\n=== 所有示例运行完成 ===")


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
