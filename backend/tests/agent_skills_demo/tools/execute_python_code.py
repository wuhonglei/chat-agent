"""执行 Python 代码工具，通过 subprocess 在临时文件中执行"""

import os
import subprocess
import sys
import tempfile
import uuid

from ._common import DEMO_ROOT


def execute_python_code(code: str, timeout: float = 300) -> str:
    """在临时文件中执行 Python 代码，捕获标准输出、标准错误和返回码。

    使用 print() 输出结果。执行完成后临时文件会自动删除。

    Args:
        code: 要执行的 Python 代码
        timeout: 最大执行时间（秒），默认 300

    Returns:
        包含 returncode、stdout、stderr 的响应字符串
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file = os.path.join(temp_dir, f"tmp_{uuid.uuid4().hex}.py")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(code)

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        try:
            result = subprocess.run(
                [sys.executable, "-u", temp_file],
                capture_output=True,
                timeout=timeout,
                env=env,
                encoding="utf-8",
                errors="replace",
                cwd=DEMO_ROOT,
            )
            returncode = result.returncode
            stdout_str = result.stdout or ""
            stderr_str = result.stderr or ""

        except subprocess.TimeoutExpired:
            returncode = -1
            stdout_str = ""
            stderr_str = f"TimeoutError: 代码执行超过超时限制 {timeout} 秒。"

    return (
        f"<returncode>{returncode}</returncode>"
        f"<stdout>{stdout_str}</stdout>"
        f"<stderr>{stderr_str}</stderr>"
    )


TOOL_DEF: dict[str, object] = {
    "type": "function",
    "function": {
        "name": "execute_python_code",
        "description": "执行 Python 代码。将代码写入临时文件并通过 subprocess 执行，使用 print() 输出结果。支持 timeout 参数限制执行时间。",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python 代码",
                },
            },
            "required": ["code"],
        },
    },
}
