"""安全的 Python 代码执行沙箱"""

import os
import resource
import subprocess
import sys
import tempfile


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
        allow_file_access: bool = False,
        allowed_paths: list[str] | None = None,
        allow_network_access: bool = False,
    ):
        """
        初始化沙箱执行器

        Args:
            timeout: 执行超时时间（秒）
            cpu_time_limit: CPU 时间限制（秒）
            memory_limit_mb: 内存限制（MB）
            max_output_length: 最大输出长度（字符）
            allowed_imports: 允许导入的模块列表
            allow_file_access: 是否允许文件系统访问
            allowed_paths: 允许访问的文件路径列表
            allow_network_access: 是否允许网络访问
        """
        self.timeout = timeout
        self.cpu_time_limit = cpu_time_limit
        self.memory_limit_mb = memory_limit_mb
        self.max_output_length = max_output_length
        self.allowed_imports = allowed_imports or []
        self.allow_file_access = allow_file_access
        self.allowed_paths = allowed_paths or []
        self.allow_network_access = allow_network_access

    def _set_resource_limits(self) -> None:
        """设置资源限制"""
        # 设置 CPU 时间限制（软限制和硬限制）
        try:
            resource.setrlimit(
                resource.RLIMIT_CPU, (self.cpu_time_limit, self.cpu_time_limit)
            )
        except (ValueError, OSError):
            pass  # 在某些系统上可能不支持

        # 设置内存限制
        try:
            memory_limit_bytes = self.memory_limit_mb * 1024 * 1024
            resource.setrlimit(
                resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes)
            )
        except (ValueError, OSError):
            pass  # 在某些系统上可能不支持

        # 设置最大文件大小
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))  # 1MB
        except (ValueError, OSError):
            pass

    def _create_safe_script(self, code: str) -> str:
        """创建安全的执行脚本，包含 RestrictedPython 检查和资源限制"""
        # 使用 repr 来安全地嵌入代码
        code_repr = repr(code)

        # 创建包装脚本，在子进程中应用资源限制和模块限制
        wrapper_code = f"""import sys
import resource
import os
import traceback
import warnings
warnings.filterwarnings("ignore", message=".*Prints, but never reads.*printed.*", category=SyntaxWarning)
from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Guards import guarded_iter_unpack_sequence

# 提供 RestrictedPython 所需的 guard：print、属性/下标访问、迭代
class _StdoutPrintCollector:
    def __init__(self, _getattr_=None):
        self._getattr_ = _getattr_
        self._parts = []
    def write(self, text):
        sys.stdout.write(text)
        self._parts.append(text)
    def __call__(self):
        return "".join(self._parts)
    def _call_print(self, *objects, **kwargs):
        if kwargs.get("file", None) is None:
            kwargs["file"] = self
        else:
            self._getattr_(kwargs["file"], "write")
        print(*objects, **kwargs)

_exec_globals = safe_globals.copy()
_exec_globals["_print_"] = _StdoutPrintCollector
_exec_globals["_getattr_"] = getattr
_exec_globals["_getitem_"] = lambda obj, key: obj[key]
_exec_globals["_getiter_"] = iter
_exec_globals["_iter_unpack_sequence_"] = guarded_iter_unpack_sequence

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
_allow_network_access = {self.allow_network_access!r}

_network_blocked = {{"socket"}}

def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
    if not _allow_network_access and (name in _network_blocked or name.startswith("socket.")):
        raise ImportError("网络访问被禁止")
    if not any(name == allowed or name.startswith(allowed + ".") for allowed in _allowed_modules):
        raise ImportError(f"导入 '{{name}}' 被禁止。允许的模块: {{', '.join(_allowed_modules)}}")
    return _original_import(name, globals, locals, fromlist, level)

# 替换 __import__ 函数
import builtins
builtins.__import__ = restricted_import

_allow_file_access = {self.allow_file_access!r}
_allowed_paths = {self.allowed_paths!r}
_original_open = builtins.open

def _normalize_path(path):
    return os.path.realpath(os.path.expanduser(path))

def restricted_open(file, *args, **kwargs):
    if not _allow_file_access:
        raise PermissionError("文件系统访问被禁止")
    if not _allowed_paths:
        raise PermissionError("未配置允许的文件路径")
    target_path = _normalize_path(file)
    for allowed in _allowed_paths:
        allowed_path = _normalize_path(allowed)
        if target_path == allowed_path or target_path.startswith(allowed_path + os.sep):
            return _original_open(file, *args, **kwargs)
    raise PermissionError("访问路径不在允许列表中")

builtins.open = restricted_open

class _LimitedWriter:
    def __init__(self, stream, max_len):
        self.stream = stream
        self.max_len = max_len
        self.written = 0

    def write(self, data):
        if not data:
            return 0
        if self.written >= self.max_len:
            return len(data)
        remaining = self.max_len - self.written
        chunk = data[:remaining]
        self.stream.write(chunk)
        self.stream.flush()
        self.written += len(chunk)
        return len(data)

    def flush(self):
        self.stream.flush()

sys.stdout = _LimitedWriter(sys.stdout, {self.max_output_length})
sys.stderr = _LimitedWriter(sys.stderr, {self.max_output_length})

try:
    # 执行用户代码（RestrictedPython）
    compiled = compile_restricted({code_repr}, "<inline>", "exec")
    if isinstance(compiled, tuple):
        byte_code, errors, _warnings = compiled
        if errors:
            raise SyntaxError("\\n".join(errors))
    else:
        byte_code = compiled
    exec(byte_code, _exec_globals, _exec_globals)
except Exception as e:
    print(f"执行错误: {{e}}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
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
