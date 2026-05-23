# DeerFlow 2.0 虚拟路径与安全机制调研报告

## 1. 虚拟路径系统概述

### 1.1 设计目标与核心概念

DeerFlow 2.0 的虚拟路径系统是其沙箱架构的**核心基础设施**，为 Agent 提供了一套与宿主机解耦的统一文件系统视图。Agent 始终看到虚拟路径（`/mnt/user-data/...`），而系统在背后透明地完成虚拟路径到物理路径的转换，从而实现：

- **线程隔离**：不同会话的数据完全隔离
- **安全保护**：防止路径遍历攻击
- **环境一致性**：本地模式和 Docker 模式对 Agent 呈现相同的接口

### 1.2 虚拟路径到物理路径映射总览

| 虚拟路径（Agent 可见） | 物理路径（宿主机） |
|---|---|
| `/mnt/user-data/workspace` | `{base_dir}/users/{user_id}/threads/{thread_id}/user-data/workspace` |
| `/mnt/user-data/uploads` | `{base_dir}/users/{user_id}/threads/{thread_id}/user-data/uploads` |
| `/mnt/user-data/outputs` | `{base_dir}/users/{user_id}/threads/{thread_id}/user-data/outputs` |
| `/mnt/skills` | `deer-flow/skills/`（只读挂载） |
| `/mnt/acp-workspace` | `{base_dir}/users/{user_id}/threads/{thread_id}/acp-workspace` |

---

## 2. 核心组件与源码分析

### 2.1 路径常量定义（`config/paths.py`）

```python
# 虚拟路径前缀常量
VIRTUAL_PATH_PREFIX = "/mnt/user-data"

class Paths:
    """集中管理 DeerFlow 应用数据的目录布局"""
    # 目录结构：
    # {base_dir}/
    # ├── threads/
    # │   └── {thread_id}/
    # │       └── user-data/
    # │           ├── workspace/
    # │           ├── uploads/
    # │           └── outputs/
    # 通过 host_base_dir 支持 Docker DooD 模式
```

### 2.2 路径映射数据结构（`sandbox/local/local_sandbox.py`）

```python
@dataclass(frozen=True)
class PathMapping:
    """容器路径 → 本地路径的映射，支持只读标记"""
    container_path: str   # 容器内路径，如 /mnt/user-data/uploads
    local_path: str       # 宿主机路径
    read_only: bool = False

class ResolvedPath(NamedTuple):
    path: str
    mapping: PathMapping | None
```

**关键方法 `_resolve_path_with_mapping`** — 最长前缀匹配算法：

```python
def _resolve_path_with_mapping(self, path: str) -> ResolvedPath:
    # 1. 遍历所有 PathMapping，按 container_path 长度降序排序
    # 2. 找到最长匹配的容器路径前缀
    # 3. 替换为对应的本地路径
    # 4. 使用 resolved_path.relative_to(local_root) 检查路径逃逸
    #    若路径超出挂载目录范围，抛出 PermissionError
```

**安全检查机制**：

- **路径遍历保护**：拒绝包含 `..` 的路径
- **只读强制**：对标记为 read_only 的映射拒绝写入操作
- **反向解析**：`_reverse_resolve_path` 将本地路径还原为虚拟路径

### 2.3 本地沙箱提供者（`sandbox/local/local_sandbox_provider.py`）

```python
class LocalSandboxProvider(SandboxProvider):
    uses_thread_data_mounts = True  # 标记支持线程级挂载

    def _build_thread_path_mappings(self, thread_id: str) -> list[PathMapping]:
        """构建线程专属路径映射"""
        paths = get_paths()
        user_id = get_effective_user_id()
        paths.ensure_thread_dirs(thread_id, user_id=user_id)  # 确保目录存在

        return [
            # 父目录映射（使 ls /mnt/user-data 正常工作）
            PathMapping("/mnt/user-data", sandbox_user_data_dir, read_only=False),
            # 子目录映射（更长路径优先匹配）
            PathMapping("/mnt/user-data/workspace", sandbox_work_dir),
            PathMapping("/mnt/user-data/uploads", sandbox_uploads_dir),
            PathMapping("/mnt/user-data/outputs", sandbox_outputs_dir),
            PathMapping("/mnt/acp-workspace", acp_workspace_dir),
        ]

    def acquire(self, thread_id: str | None = None) -> str:
        """获取沙箱实例：支持每线程独立沙箱 + LRU 缓存"""
        # thread_id=None → 返回通用单例（兼容旧代码/测试）
        # thread_id="abc" → 返回 local:abc，含线程专属 path_mappings
```

**缓存策略**：使用 `OrderedDict` 实现 LRU 缓存，默认上限 256 个线程沙箱实例。

### 2.4 Docker 沙箱提供者（`community/aio_sandbox/aio_sandbox_provider.py`）

Docker 模式通过**卷挂载**实现相同虚拟路径契约：

```python
def _get_thread_mounts(self, thread_id: str) -> list[tuple[str, str, bool]]:
    """Docker 卷挂载配置：(host_path, container_path, read_only)"""
    paths.ensure_thread_dirs(thread_id, user_id=user_id)
    return [
        (host_work_dir,      "/mnt/user-data/workspace", False),
        (host_uploads_dir,   "/mnt/user-data/uploads",   False),
        (host_outputs_dir,   "/mnt/user-data/outputs",   False),
        (host_acp_workspace, "/mnt/acp-workspace",       True),   # 只读
    ]

def _get_skills_mount(self) -> tuple[str, str, bool] | None:
    """技能目录挂载（只读）"""
    return (host_skills_path, "/mnt/skills", True)
```

### 2.5 沙箱中间件（`sandbox/middleware.py`）

```python
class SandboxMiddleware(AgentMiddleware):
    """沙箱生命周期管理"""
    def __init__(self, lazy_init: bool = True):
        # lazy_init=True: 首次工具调用时才获取沙箱（性能优化）
        # lazy_init=False: 在 before_agent 阶段立即获取

    def _acquire_sandbox(self, thread_id: str) -> str:
        # 同一线程内的多次 Agent 调用复用同一沙箱
        # 不在每次调用后释放，避免重复创建开销
```

---

## 3. 两种实现模式对比

| 特性 | LocalSandboxProvider | AioSandboxProvider |
|---|---|---|
| **隔离级别** | 进程级（逻辑隔离） | 容器级（Docker 命名空间） |
| **路径转换方式** | Python 代码动态解析 | Docker 卷挂载 |
| **启动速度** | 即时 | 5-10 秒冷启动 |
| **适用场景** | 开发调试 | 生产环境 |
| **bash 支持** | 默认禁用（安全考虑） | 容器内完整 Shell |
| **路径契约** | 代码层维护 | 内核层维护 |

---

## 4. `read_file` 工具远程执行机制

### 4.1 执行链路对比

| 环节 | LocalSandboxProvider（本地模式） | AioSandboxProvider（远程/Docker 模式） |
|------|----------------------------------|----------------------------------------|
| **文件读取方式** | 直接操作宿主机文件系统（Python `open()`） | 通过 HTTP API 调用容器内文件服务 |
| **路径转换** | 代码层 `_resolve_path_with_mapping()` | 内核层 Docker Volume Mount |
| **是否启动容器** | 否 | 是（per-thread 容器） |
| **沙箱隔离** | 逻辑隔离（路径前缀匹配） | 容器命名空间隔离 |

### 4.2 AIO 模式下 `read_file` 的具体实现

**`AioSandbox.read_file()`**（`community/aio_sandbox/aio_sandbox.py`）：

```python
def read_file(self, path: str) -> str:
    """Read the content of a file in the sandbox."""
    try:
        result = self._client.file.read_file(file=path)
        return result.data.content if result.data else ""
    except Exception as e:
        logger.error(f"Failed to read file in sandbox: {e}")
        return f"Error: {e}"
```

关键点：

- **`self._client`** 是 `agent_sandbox`（agent-infra/sandbox）库的客户端
- 通过 **HTTP API** 向容器内的 sandbox 服务端点发送请求
- **不是**通过 `docker exec` 执行 shell 命令来读取文件
- 传入的 `path` 已经是虚拟路径（如 `/mnt/user-data/workspace/file.txt`），因为通过 volume mount 映射到了容器内

### 4.3 容器启动时的 Volume Mount 配置

**挂载构建**（`aio_sandbox_provider.py`）：

```python
def _get_thread_mounts(self, thread_id: str) -> list[tuple[str, str, bool]]:
    """Docker 卷挂载配置：(host_path, container_path, read_only)"""
    paths.ensure_thread_dirs(thread_id, user_id=user_id)
    return [
        (host_work_dir,    "/mnt/user-data/workspace", False),
        (host_uploads_dir, "/mnt/user-data/uploads",   False),
        (host_outputs_dir, "/mnt/user-data/outputs",   False),
        (host_acp_workspace, "/mnt/acp-workspace",     True),  # 只读
    ]
```

**挂载格式化**（`local_backend.py`）：

```python
def _format_container_mount(runtime, host_path, container_path, read_only):
    """生成 Docker --mount 参数"""
    if runtime == "docker":
        mount_spec = f"type=bind,src={host_path},dst={container_path}"
        if read_only:
            mount_spec += ",readonly"
        return ["--mount", mount_spec]
```

容器启动命令示例：

```bash
docker run \
  --mount type=bind,src=/host/data/workspace,dst=/mnt/user-data/workspace \
  --mount type=bind,src=/host/data/uploads,dst=/mnt/user-data/uploads \
  --mount type=bind,src=/host/data/outputs,dst=/mnt/user-data/outputs \
  --mount type=bind,src=/host/skills,dst=/mnt/skills,readonly \
  -p 127.0.0.1:xxxxx:8080 \
  enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:latest
```

### 4.4 远程后端（K8s 模式）

**`RemoteSandboxBackend`**（`remote_backend.py`）：

- 通过 **provisioner 服务**（:8002）在 k3s 中动态创建 Pod + NodePort Service
- 数据持久化通过 **PVC（PersistentVolumeClaim）** 实现
- 文件读取同样通过 HTTP API 调用容器内的 sandbox 服务
- 架构：`AioSandbox → HTTP → provisioner → K8s API → sandbox Pod`

---

## 5. Docker 容器启动时机与调用链

### 5.1 启动命令由谁执行

`docker run` **不是**直接由 `ensure_sandbox_initialized` 执行，而是通过**多层调用链路**最终触发：

```
ensure_sandbox_initialized(runtime)          [tools.py]
    ↓
provider = get_sandbox_provider()            [sandbox_provider.py]
    ↓
sandbox_id = provider.acquire(thread_id)     [aio_sandbox_provider.py]
    ↓
返回缓存？→ 是 → 复用现有容器
    ↓ 否
backend.start(port=..., mounts=...)           [local_backend.py]
    ↓
docker run ...
```

### 5.2 详细拆解

**`ensure_sandbox_initialized` — 入口层**：

```python
# tools.py
def ensure_sandbox_initialized(runtime: Runtime):
    """Ensure the sandbox is ready for tool execution."""
    provider = get_sandbox_provider()
    sandbox_id = provider.acquire(runtime.context.get("thread_id"))
```

这里只是**获取沙箱提供者**并调用 `acquire()`，本身不包含任何 Docker 命令。

**`AioSandboxProvider.acquire` — 提供者层**：

```python
# aio_sandbox_provider.py
class AioSandboxProvider(SandboxProvider):
    def acquire(self, thread_id: str | None = None) -> str:
        # LRU 缓存检查
        if thread_id in self._sandbox_cache:
            return self._sandbox_cache[thread_id]

        # 缓存未命中 → 创建新容器
        port = self._allocate_port()
        mounts = self._get_thread_mounts(thread_id)
        self._backend.start(port=port, mounts=mounts)  # ← 触发 docker run
        self._sandbox_cache[thread_id] = f"localhost:{port}"
        return self._sandbox_cache[thread_id]
```

`acquire()` 负责**缓存管理**和**端口分配**，实际容器启动委托给 `backend.start()`。

**`LocalSandboxBackend._start_container` — 执行层**：

```python
# local_backend.py
class LocalSandboxBackend:
    def start(self, port: int, mounts: list[tuple[str, str, bool]]):
        cmd = ["docker", "run", "-d", "--rm"]
        for host_path, container_path, read_only in mounts:
            cmd.extend(self._format_container_mount("docker", host_path, container_path, read_only))
        cmd.extend(["-p", f"127.0.0.1:{port}:8080", self._image])
        subprocess.run(cmd, check=True)
```

**docker run 实际在这里执行**。

### 5.3 容器启动时机总结

| 阶段 | 触发条件 | 执行者 |
|------|---------|--------|
| `ensure_sandbox_initialized` | 工具首次调用时 | 工具层，调用 provider |
| `provider.acquire` | 缓存未命中时 | AioSandboxProvider，分配端口 |
| `backend.start` | acquire 请求新容器时 | LocalSandboxBackend，执行 docker run |

**关键点**：

- **不是每次 `read_file` 都启动容器**。容器启动后会被 LRU 缓存，同一线程的后续工具调用直接复用。
- **默认 LRU 上限为 3 个容器**。超出限制时，最久未使用的容器被 `docker stop` 释放。
- **空闲超时**（默认 600 秒）后，后台清理线程会自动释放闲置容器。
- **`ensure_sandbox_initialized` 在每个工具函数开头被调用**，但由于缓存存在，实际启动 docker 的频率很低。

---

## 6. `read_file` 源码深度分析

### 6.1 工具入口：`read_file_tool`（`tools.py`）

这是 Agent 直接调用的 LangChain 工具函数，负责路径校验、虚拟路径解析，最终委托给底层 `sandbox.read_file()`。

```python
@tool("read_file", parse_docstring=True)
def read_file_tool(
    runtime: Runtime,
    description: str,
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    try:
        # 1. 获取/初始化沙箱
        sandbox = ensure_sandbox_initialized(runtime)
        ensure_thread_directories_exist(runtime)
        requested_path = path

        # 2. 本地模式特有的路径处理
        if is_local_sandbox(runtime):
            thread_data = get_thread_data(runtime)
            validate_local_tool_path(path, thread_data, read_only=True)

            # 分三种路径类型分别解析
            if _is_skills_path(path):
                path = _resolve_skills_path(path)           # /mnt/skills → host skills dir
            elif _is_acp_workspace_path(path):
                path = _resolve_acp_workspace_path(path, ...)  # /mnt/acp-workspace → host acp dir
            elif not _is_custom_mount_path(path):
                path = _resolve_and_validate_user_data_path(path, thread_data)  # /mnt/user-data/* → thread dir
            # Custom mount paths 由 LocalSandbox._resolve_path() 处理

        # 3. 调用底层沙箱 read_file
        content = sandbox.read_file(path)

        # 4. 后处理
        if not content:
            return "(empty)"
        if start_line is not None and end_line is not None:
            content = "\n".join(content.splitlines()[start_line - 1 : end_line])
        return _truncate_read_file_output(content, max_chars)
    except ...
```

**本地模式路径解析逻辑**：

| 路径类型 | 解析函数 | 说明 |
|----------|----------|------|
| `/mnt/skills/*` | `_resolve_skills_path()` | 只读，映射到 host skills 目录 |
| `/mnt/acp-workspace/*` | `_resolve_acp_workspace_path()` | 只读，ACP 工作区 |
| `/mnt/user-data/*` | `_resolve_and_validate_user_data_path()` | 线程隔离目录 |
| 自定义 mount | `LocalSandbox._resolve_path()` | 由最长前缀匹配处理 |

### 6.2 本地模式实现：`LocalSandbox.read_file`（`local/local_sandbox.py`）

直接操作宿主机文件系统，通过 `_resolve_path` 将虚拟路径转为物理路径。

```python
def read_file(self, path: str) -> str:
    # 虚拟路径 → 本地物理路径（最长前缀匹配）
    resolved_path = self._resolve_path(path)
    try:
        with open(resolved_path, encoding="utf-8") as f:
            content = f.read()

        # 关键设计：仅对 Agent 写入的文件做反向路径解析
        # 用户上传文件、外部工具输出不会被静默改写（PR #1935）
        if resolved_path in self._agent_written_paths:
            content = self._reverse_resolve_paths_in_output(content)

        return content
    except OSError as e:
        # 用原始虚拟路径重新抛出异常，隐藏内部物理路径
        raise type(e)(e.errno, e.strerror, path) from None
```

**核心依赖 `_resolve_path`**：

```python
def _resolve_path(self, path: str) -> str:
    return self._resolve_path_with_mapping(path).path

def _resolve_path_with_mapping(self, path: str) -> ResolvedPath:
    # 最长前缀匹配：按 container_path 长度降序排序
    mapping_match = self._find_path_mapping(path_str)
    if mapping_match is None:
        return ResolvedPath(path_str, None)  # 无匹配，原样返回

    mapping, relative = mapping_match
    local_root = Path(mapping.local_path).resolve()
    resolved_path = (local_root / relative).resolve()

    # 安全检查：防止路径逃逸出挂载目录
    try:
        resolved_path.relative_to(local_root)
    except ValueError:
        raise PermissionError("Access denied: path escapes mounted directory")

    return ResolvedPath(str(resolved_path), mapping)
```

### 6.3 Docker 模式实现：`AioSandbox.read_file`（`community/aio_sandbox/aio_sandbox.py`）

通过 HTTP API 调用容器内的 sandbox 文件服务，传入的 `path` 保持虚拟路径不变（因为 volume mount 已在容器内完成映射）。

```python
def read_file(self, path: str) -> str:
    """Read the content of a file in the sandbox.

    Args:
        path: The absolute path of the file to read.
              使用虚拟路径，如 /mnt/user-data/workspace/file.txt

    Returns:
        The content of the file.
    """
    try:
        # self._client 是 agent_sandbox (agent-infra/sandbox) 的 HTTP 客户端
        result = self._client.file.read_file(file=path)
        return result.data.content if result.data else ""
    except Exception as e:
        logger.error(f"Failed to read file in sandbox: {e}")
        return f"Error: {e}"
```

### 6.4 两种模式对比总结

| 维度 | LocalSandbox | AioSandbox |
|------|-------------|------------|
| **文件读取方式** | `open(resolved_path)` 直接打开 | HTTP API `client.file.read_file()` |
| **路径转换时机** | 工具层 + sandbox 层双重解析 | 仅在工具层解析；容器内通过 volume mount |
| **路径隔离机制** | Python 代码最长前缀匹配 | Docker `--mount` 内核级隔离 |
| **反向解析** | 仅 Agent 写入文件做反向解析 | 无（由容器服务处理） |
| **错误处理** | 用虚拟路径重新抛出异常 | 返回 `"Error: ..."` 字符串 |
| **并发安全** | 无特殊处理 | 通过 `threading.Lock` 串行化 |

**调用链路**：

```
Agent → read_file_tool(tools.py)
       ├── 本地模式: validate_local_tool_path() → _resolve_*_path()
       │             → LocalSandbox.read_file() → _resolve_path() → open()
       │
       └── Docker模式: ensure_sandbox_initialized() → AioSandbox.read_file()
                       → HTTP API → 容器内 volume mount → 读取文件
```

---

## 7. 安全机制

### 7.1 安全策略：`security.py`

```python
LOCAL_HOST_BASH_DISABLED_MESSAGE = (
    "Host bash execution is disabled for LocalSandboxProvider because it is not a secure "
    "sandbox boundary. Switch to AioSandboxProvider for isolated bash access, or set "
    "sandbox.allow_host_bash: true only in a fully trusted local environment."
)

def is_host_bash_allowed(config=None) -> bool:
    """Return whether host bash execution is explicitly allowed."""
    if config is None:
        config = get_app_config()

    sandbox_cfg = getattr(config, "sandbox", None)
    if sandbox_cfg is None:
        return False
    if not uses_local_sandbox_provider(config):
        return True   # Docker 模式下，bash 在容器内执行，天然安全
    return bool(getattr(sandbox_cfg, "allow_host_bash", False))  # 本地默认禁用
```

**三级安全策略**：

| 沙盒模式 | bash 工具 | bash SubAgent | 安全级别 |
|-|-|-|-|
| **LocalSandbox + allow_host_bash=false** | 禁止 | 禁止 | 最高 |
| **LocalSandbox + allow_host_bash=true** | 允许 | 允许 | 中等（信任环境） |
| **AioSandbox** | 容器内执行 | 容器内执行 | 高（容器隔离） |

### 7.2 本地模式的安全限制

1. **路径遍历防护**：`_resolve_path_with_mapping` 使用 `resolved_path.relative_to(local_root)` 确保解析后的路径不逃逸出挂载目录
2. **只读强制写入拒绝**：对只读映射写入时抛出 `OSError(errno.EROFS, ...)`
3. **输出路径脱敏**：`_reverse_resolve_paths_in_output` 将命令输出中的物理路径替换为虚拟路径
4. **保留前缀冲突检测**：自定义挂载不允许与 `/mnt/user-data`、`/mnt/acp-workspace` 冲突
5. **Thread ID 验证**：正则 `^[A-Za-z0_\-]+$` 防止路径注入

### 7.3 远程容器模式的安全依赖

AioSandbox（远程/Docker 模式）在 DeerFlow 代码层面对 shell 命令内容**不做任何过滤或审计**。命令被原样通过 HTTP API 转发给底层容器执行，安全完全依赖于 **Docker 容器隔离机制**。

**三个层面的隔离机制**：

| 安全层面 | 机制 | 由谁控制 |
|---------|------|---------|
| **容器 Namespace 隔离** | 独立的 PID、Network、Mount、UTS namespace | Docker 引擎 |
| **Volume Mount 边界** | 只有显式挂载的目录才能在容器内访问 | `aio_sandbox_provider.py` |
| **容器镜像安全配置** | seccomp、capabilities、AppArmor/SELinux | 底层 `agent-infra/sandbox` 镜像 |

### 7.4 CVE-2026-34430：已知漏洞与修复

**CVE-2026-34430** 是 DeerFlow 中一个已知的 sandbox escape 漏洞：

- **问题**：LocalSandbox 在公共 API 边界未维护 `/mnt/user-data/...` 契约，调用者需要自行处理路径转换
- **攻击方式**：通过 `cd ..`、相对路径等绕过应用层 regex 校验，在宿主机上执行任意命令
- **影响范围**：仅影响 **LocalSandboxProvider**，**不影响 AioSandboxProvider**
- **修复方案**（commit `92c7a20`）：
  - `LocalSandboxProvider.acquire(thread_id)` 现在返回带有完整线程级 path_mappings 的 `LocalSandbox`
  - `tools.py` 中保留了 `replace_virtual_path()` 作为**纵深防御层**
  - 兼容旧代码：`acquire()` / `acquire(None)` 仍返回传统单例

---

## 8. 演进与架构总结

### 8.1 多层架构设计

DeerFlow 的虚拟路径实现采用了**多层架构设计**：

- **抽象层**：`Sandbox` ABC 定义统一接口
- **映射层**：`PathMapping` + 最长前缀匹配实现路径转换
- **隔离层**：线程级目录 + 用户级目录（支持多用户隔离）
- **执行层**：Local/Docker 两种提供者保持对 Agent 的接口一致性

### 8.2 总结

这种设计使得 Agent 代码完全无需关心底层是本地运行还是 Docker 运行，只需要使用统一的 `/mnt/user-data/...` 路径即可安全地操作文件。对于生产环境，**强烈建议使用 AioSandboxProvider（Docker 模式）**，它提供了真正的容器级隔离，相比本地模式具有更高的安全性。

| 问题 | 答案 |
|------|------|
| `read_file` 在远程模式下是否走 Docker？ | **是**，文件读取发生在容器内 |
| 是通过 `docker exec` 吗？ | **否**，通过容器内 sandbox 服务的 **HTTP API** |
| 路径是虚拟路径还是物理路径？ | Agent 传入虚拟路径（`/mnt/user-data/...`），容器内通过 **volume mount** 映射到物理路径 |
| 与本地模式的核心区别？ | 本地模式是代码层路径解析后直接 `open()`；远程模式是 HTTP API + 容器 volume mount |
| 远程模式 shell 有安全限制吗？ | **代码层面无限制**，安全完全依赖 **Docker 容器隔离** |
