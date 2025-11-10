# Code Execution MCP Server

安全的 Python 代码执行服务，提供沙箱隔离功能。

## 功能特性

### 多层安全防护

1. **进程隔离**
   - 代码在独立的子进程中执行，与主进程完全隔离
   - 即使代码崩溃也不会影响主服务

2. **资源限制**
   - CPU 时间限制：默认 5 秒
   - 内存限制：默认 128 MB
   - 执行超时：默认 10 秒
   - 文件大小限制：1 MB

3. **模块限制**
   - 只允许导入白名单中的安全模块
   - 默认允许的模块：`math`, `random`, `datetime`, `json`, `collections`, `itertools`, `functools`, `operator`, `string`, `re`, `decimal`, `fractions`, `statistics`

4. **代码安全检查**
   - 使用 RestrictedPython 进行代码安全检查
   - 禁止危险操作（文件系统访问、网络访问等）

5. **输出限制**
   - 限制输出长度，防止资源耗尽
   - 默认最大输出长度：10,000 字符

## 配置

通过环境变量可以配置沙箱参数：

```bash
# 执行超时时间（秒）
CODE_EXEC_EXECUTION_TIMEOUT=10

# CPU 时间限制（秒）
CODE_EXEC_CPU_TIME_LIMIT=5

# 内存限制（MB）
CODE_EXEC_MEMORY_LIMIT_MB=128

# 最大输出长度（字符）
CODE_EXEC_MAX_OUTPUT_LENGTH=10000

# 是否允许文件系统访问（暂未实现）
CODE_EXEC_ALLOW_FILE_ACCESS=false

# 是否允许网络访问（暂未实现）
CODE_EXEC_ALLOW_NETWORK_ACCESS=false
```

## 使用示例

### 基本计算

```python
result = 2 + 2
print(result)
```

### 数据处理

```python
import json
data = {"name": "test", "value": 123}
print(json.dumps(data))
```

### 数学运算

```python
import math
result = math.sqrt(16)
print(result)
```

## 安全限制

以下操作将被禁止：

- 文件系统操作（`open`, `os.system`, `subprocess` 等）
- 网络访问（`socket`, `urllib`, `requests` 等）
- 危险的内置函数（`eval`, `exec`, `compile` 等）
- 导入未在白名单中的模块
- 访问系统资源（环境变量、进程等）

## 注意事项

1. **不完全安全**：虽然有多层防护，但 Python 沙箱无法做到 100% 安全。建议仅用于可信环境。

2. **性能影响**：子进程创建和资源限制会带来一定的性能开销。

3. **平台差异**：资源限制功能在 Windows 上可能不完全支持。

4. **依赖安装**：需要安装 `RestrictedPython` 库：
   ```bash
   uv pip install RestrictedPython
   ```

## 错误处理

- `CodeExecutionError`: 代码执行失败（语法错误、运行时错误等）
- `TimeoutError`: 代码执行超时
- `ImportError`: 尝试导入未允许的模块

## 开发

运行测试服务器：

```bash
uv run -m app.mcp.mcp_servers.code_exec_mcp.server --transport stdio
```

或使用 HTTP 模式：

```bash
uv run -m app.mcp.mcp_servers.code_exec_mcp.server --transport http --port 8003
```

