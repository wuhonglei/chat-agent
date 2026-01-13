"""安全的 Python 代码执行沙箱"""

import os
import resource
import subprocess
import sys
import tempfile

from RestrictedPython import compile_restricted


class CodeExecutionError(Exception):
    """代码执行错误"""

    pass


class TimeoutError(Exception):
    """执行超时错误"""

    pass


class SandboxExecutor:
    """安全的代码执行沙箱"""

    def __init__(
        self,
        timeout: int = 10,
        cpu_time_limit: int = 5,
        memory_limit_mb: int = 128,
        max_output_length: int = 10000,
        allowed_imports: list[str] | None = None,
    ):
        """
        初始化沙箱执行器

        Args:
            timeout: 执行超时时间（秒）
            cpu_time_limit: CPU 时间限制（秒）
            memory_limit_mb: 内存限制（MB）
            max_output_length: 最大输出长度（字符）
            allowed_imports: 允许导入的模块列表
        """
        self.timeout = timeout
        self.cpu_time_limit = cpu_time_limit
        self.memory_limit_mb = memory_limit_mb
        self.max_output_length = max_output_length
        self.allowed_imports = allowed_imports or []

    def _set_resource_limits(self):
        """设置资源限制"""
        # 设置 CPU 时间限制（软限制和硬限制）
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (self.cpu_time_limit, self.cpu_time_limit))
        except (ValueError, OSError):
            pass  # 在某些系统上可能不支持

        # 设置内存限制
        try:
            memory_limit_bytes = self.memory_limit_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
        except (ValueError, OSError):
            pass  # 在某些系统上可能不支持

        # 设置最大文件大小
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))  # 1MB
        except (ValueError, OSError):
            pass

    def _create_safe_script(self, code: str) -> str:
        """创建安全的执行脚本，包含 RestrictedPython 检查和资源限制"""
        # 使用 RestrictedPython 编译代码以检查安全性
        # compile_restricted 返回 (code, errors, warnings) 元组
        result = compile_restricted(code, "<inline>", "exec")

        # 处理返回值：可能是元组或直接是代码对象
        if isinstance(result, tuple):
            byte_code, errors, warnings = result
            if errors:
                error_msg = "\n".join(errors)
                raise CodeExecutionError(f"代码安全检查失败: {error_msg}")
        else:
            # 如果直接返回代码对象，尝试检查是否有错误属性
            byte_code = result
            if hasattr(byte_code, "errors") and byte_code.errors:
                error_msg = "\n".join(byte_code.errors)
                raise CodeExecutionError(f"代码安全检查失败: {error_msg}")

        # 使用 repr 来安全地嵌入代码
        code_repr = repr(code)

        # 创建包装脚本，在子进程中应用资源限制和模块限制
        wrapper_code = f"""import sys
import resource

# 设置资源限制
try:
    resource.setrlimit(resource.RLIMIT_CPU, ({self.cpu_time_limit}, {self.cpu_time_limit}))
except (ValueError, OSError):
    pass

try:
    memory_limit_bytes = {self.memory_limit_mb} * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
except (ValueError, OSError):
    pass

try:
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
except (ValueError, OSError):
    pass

# 限制可导入的模块
_allowed_modules = {self.allowed_imports!r}
_original_import = __import__

def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name not in _allowed_modules:
        raise ImportError(f"导入 '{{name}}' 被禁止。允许的模块: {{', '.join(_allowed_modules)}}")
    return _original_import(name, globals, locals, fromlist, level)

# 替换 __import__ 函数
import builtins
builtins.__import__ = restricted_import

try:
    # 执行用户代码
    exec({code_repr})
except Exception as e:
    import traceback
    print(f"执行错误: {{e}}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
"""
        return wrapper_code

    def _execute_in_subprocess(self, code: str) -> tuple[str, str]:
        """
        在子进程中执行代码

        Returns:
            (stdout, stderr) 元组
        """
        # 创建安全的执行脚本
        safe_script = self._create_safe_script(code)

        # 创建临时文件用于执行代码
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            script_path = f.name
            try:
                # 写入安全脚本
                f.write(safe_script)
                f.flush()

                # 准备执行环境
                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"

                # 在子进程中执行
                process = subprocess.Popen(
                    [sys.executable, script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                    preexec_fn=self._set_resource_limits if os.name != "nt" else None,
                )

                try:
                    stdout, stderr = process.communicate(timeout=self.timeout)
                    return_code = process.returncode
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise TimeoutError(f"代码执行超时（超过 {self.timeout} 秒）")

                if return_code != 0:
                    error_msg = stderr or f"代码执行失败，返回码: {return_code}"
                    raise CodeExecutionError(error_msg)

                return stdout, stderr

            finally:
                # 清理临时文件
                try:
                    os.unlink(script_path)
                except OSError:
                    pass

    def execute(self, code: str) -> str:
        """
        安全执行 Python 代码

        Args:
            code: 要执行的 Python 代码

        Returns:
            执行结果（stdout 输出）

        Raises:
            CodeExecutionError: 代码执行错误
            TimeoutError: 执行超时
        """
        # 在子进程中执行代码（安全检查在子进程中完成）
        try:
            stdout, stderr = self._execute_in_subprocess(code)
        except TimeoutError:
            raise
        except CodeExecutionError:
            raise
        except Exception as e:
            raise CodeExecutionError(f"执行失败: {str(e)}")

        # 处理输出
        output = stdout.strip()
        if stderr:
            stderr_clean = stderr.strip()
            if stderr_clean:
                output += f"\n[警告] {stderr_clean}"

        # 限制输出长度
        if len(output) > self.max_output_length:
            output = output[: self.max_output_length] + "\n... (输出被截断)"

        return output
