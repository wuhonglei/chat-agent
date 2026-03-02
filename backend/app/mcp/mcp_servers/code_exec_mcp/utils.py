from .models import CodeExecResponse


def format_results(response: CodeExecResponse) -> str:
    """将代码执行结果格式化为可读字符串"""
    parts = [f"语言: {response.language} {response.version}"]

    if response.compile:
        parts.append("\n--- 编译阶段 ---")
        if response.compile.stdout:
            parts.append(f"编译输出:\n{response.compile.stdout}")
        if response.compile.stderr:
            parts.append(f"编译错误:\n{response.compile.stderr}")
        if response.compile.code is not None:
            parts.append(f"编译退出码: {response.compile.code}")

    parts.append("\n--- 运行阶段 ---")
    if response.run.stdout:
        parts.append(f"标准输出:\n{response.run.stdout}")
    if response.run.stderr:
        parts.append(f"标准错误:\n{response.run.stderr}")
    if response.run.code is not None:
        parts.append(f"退出码: {response.run.code}")
    if response.run.signal:
        parts.append(f"终止信号: {response.run.signal}")

    if not response.run.stdout and not response.run.stderr:
        parts.append("（无输出）")

    return "\n".join(parts)
