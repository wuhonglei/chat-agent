# Phase 0 实施计划：命令执行沙箱隔离 + 用户目录虚拟映射

> 对应 Roadmap：#4 命令执行沙箱隔离（P0）+ #5 用户目录虚拟映射（P1）
> 目标：守住安全底线，解除路径耦合

---

## 一、现状分析

### 1.1 命令执行风险

`run_bash` 工具直接使用 `subprocess.run(shell=True)` 在宿主机执行，安全防护仅依赖字符串匹配黑名单（`agent_skills_mcp/config.py:15-38`），可被 `echo hello && rm -rf /` 等 shell 组合语法绕过。

### 1.2 路径暴露风险

- 前端 `WorkspaceTreeNode.fullPath` 直接暴露服务器物理路径
- API 响应中 `path` 字段为物理路径（如 `/Users/.../data/user_data/...`）
- 上传文件路径 `/api/file/preview/{user_id}/{storage_key}` 暴露 user_id 和存储结构

### 1.3 已有基础

| 安全机制 | 位置 | 说明 |
|---------|------|------|
| 路径遍历防护 | `utils.py:53-71` `_resolve_under_root` | 拒绝绝对路径、`..`、禁止目录段 |
| workspace 参数注入防护 | `tool_executor.py:231-247` | LLM 无法伪造 user_id/workspace_id |
| 写入配额限制 | `utils.py:98-109` | 2GB workspace 上限 |
| Piston 远程沙箱 | `code_exec_mcp/server.py` | 代码执行已隔离 |
| 系统提示词约束 | `system_prompt.py:50` | 限制文件操作范围 |

### 1.4 工具名对照（改造前 → 改造后）

| 当前名称 | 新名称 | MCP 归属 | 变更类型 |
|---------|--------|---------|---------|
| `read_project_file` | `read_file` | file-mcp | 重命名 |
| `write_workspace_file` | `write_file` | file-mcp | 重命名 |
| `edit_workspace_file` | `edit_file` | file-mcp | 重命名 |
| `load_skill` | `load_skill` | file-mcp | 保留 |
| — | `search_files` | file-mcp | **新增** |
| `run_bash` | `shell` | shell-mcp | 重命名 |
| `execute_code` | `ipython` | code-exec-mcp | 重命名 |
| `list_project_files` | — | — | **移除** |
| `delete_workspace_file` | — | — | **移除** |
| `clear_workspace` | — | — | **移除** |

---

## 二、总体架构

### 2.1 拆分为 2 个 MCP 服务

```
backend/app/mcp/mcp_servers/
├── file_mcp/                           # MCP 1: 文件操作 + 搜索 + 技能加载
│   ├── server.py                       # FastMCP("File MCP Service")
│   ├── utils.py                        # 路径解析、配额校验
│   ├── config.py                       # 文件相关配置
│   └── test_server.py
│
├── shell_mcp/                          # MCP 2: 沙箱命令执行
│   ├── server.py                       # FastMCP("Shell MCP Service")
│   ├── policy.py                       # 命令策略引擎（AST 级解析）
│   ├── executor.py                     # SandboxExecutor 委托
│   ├── audit.py                        # 审计日志
│   ├── config.py                       # 沙箱配置
│   └── test_server.py
│
├── code_exec_mcp/                      # 保留（Piston 远程代码执行）
├── tavily_mcp/                         # 保留
├── weather_mcp/                        # 保留
└── time_mcp/                           # 保留
```

### 2.2 新增模块

```
backend/app/
├── sandbox/                            # 沙箱执行引擎
│   ├── __init__.py
│   ├── executor.py                     # SandboxExecutor 抽象基类
│   ├── docker_executor.py              # Docker 容器沙箱实现
│   ├── local_executor.py               # 本地执行（开发模式 fallback）
│   └── config.py                       # 沙箱全局配置
│
├── vfs/                                # 虚拟文件系统
│   ├── __init__.py
│   ├── mapper.py                       # VirtualPathMapper 核心映射
│   ├── resolver.py                     # 路径解析 + 安全校验
│   ├── uploads_provider.py             # /uploads/ 虚拟文件列表
│   └── config.py                       # 虚拟路径配置
```

### 2.3 工具层结构（对齐 kimi 命名）

每个工具独立为一个文件，按 MCP 服务归属放置：

```
backend/app/mcp/mcp_servers/
├── file_mcp/
│   ├── server.py                       # FastMCP("File MCP Service") 注册入口
│   ├── base.py                         # ToolBase 抽象基类
│   ├── schemas.py                      # JSON Schema 定义（对齐 kimi 格式）
│   ├── read_file.py                    # read_file 工具
│   ├── write_file.py                   # write_file 工具
│   ├── edit_file.py                    # edit_file 工具
│   ├── search_files.py                 # search_files 工具
│   ├── load_skill.py                   # load_skill 工具
│   ├── utils.py                        # 路径解析、配额校验
│   ├── config.py                       # 文件相关配置
│   └── test_server.py                  # 测试
│
├── shell_mcp/
│   ├── server.py                       # FastMCP("Shell MCP Service") 注册入口
│   ├── base.py                         # ToolBase 抽象基类（可复用或共享）
│   ├── schemas.py                      # shell JSON Schema 定义
│   ├── shell.py                        # shell 工具
│   ├── policy.py                       # 命令策略引擎（AST 级解析）
│   ├── executor.py                     # SandboxExecutor 委托
│   ├── audit.py                        # 审计日志
│   ├── config.py                       # 沙箱配置
│   └── test_server.py                  # 测试
```

---

## 三、Track A：命令执行沙箱隔离（#4）

### A1. SandboxExecutor 抽象层

**文件**：`backend/app/sandbox/executor.py`

```python
class SandboxExecutor(ABC):
    @abstractmethod
    async def execute(self, request: ExecutionRequest) -> ExecutionResult: ...

    @abstractmethod
    async def setup(self, workspace_path: Path) -> None: ...

    @abstractmethod
    async def cleanup(self) -> None: ...

@dataclass
class ExecutionRequest:
    command: str
    cwd: str                              # 虚拟路径，由 mapper 解析
    timeout: int = 600000                 # ms，对齐 kimi max 600000
    env: dict[str, str] | None = None
    description: str = ""                 # 命令用途描述（对齐 kimi shell.md）

@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    return_code: int
    timed_out: bool
    blocked: bool
    block_reason: str | None
    duration_ms: int
    output_truncated: bool
```

关键设计（对齐 kimi shell.md）：
- 非持久化：每次调用创建新进程/容器，无状态残留
- 输出截断：STDOUT+STDERR 合并，上限 50000 字符
- 超时硬限：最大 600000ms（10 分钟）
- `description` 字段：LLM 必须说明命令用途，便于审计

### A2. Docker 沙箱后端

**文件**：`backend/app/sandbox/docker_executor.py`

容器配置（对齐 kimi capability dropping + 资源限制）：

| 配置项 | 值 | 对应 kimi 实践 |
|--------|-----|----------------|
| `--network=none` | 网络隔离 | kimi: namespace 级网络阻断 |
| `--cpus=1` | CPU 限制 | kimi: 2 cores |
| `--memory=512m` | 内存限制 | kimi: 4GB（MVP 先保守） |
| `--pids-limit=100` | 进程数限制 | 防 fork bomb |
| `--read-only` | 只读根文件系统 | kimi: /app, /bin, /lib 只读 |
| `--user=1000:1000` | 非 root 执行 | kimi: Non-root execution |
| `--cap-drop=ALL` | 丢弃所有 capabilities | kimi: SYS_PTRACE, SYS_ADMIN, NET_RAW dropped |
| `--security-opt=no-new-privileges` | 禁止提权 | kimi 标准实践 |

挂载点：
```
/mnt/user-data/workspace:/mnt/user-data/workspace:rw
/mnt/user-data/uploads:/mnt/user-data/uploads:ro
/mnt/user-data/outputs:/mnt/user-data/outputs:rw
uploads:/uploads:ro                      # 上传文件（只读）
```

### A3. 命令策略引擎

**文件**：`backend/app/shell_mcp/policy.py`

替代现有字符串匹配（`agent_skills_mcp/config.py:15-38`），升级为三层策略：

```
Layer 1: bashlex AST 解析
  - 解析 shell AST，检测命令链（&&, ||, ;, |）中的危险节点
  - 检测子 shell、进程替换、eval
  - 解析失败 → 默认拒绝

Layer 2: 命令白名单
  - 基础工具: ls, cat, grep, find, head, tail, wc, sort, cp, mv, mkdir, touch
  - 开发工具: node, npm, npx, python, pip, git (受限子命令)
  - 构建工具: make, cargo, go, pnpm, yarn
  - 禁止: sudo, su, mount, umount, iptables, dd, mkfs

Layer 3: 参数/路径约束
  - rm -rf / → 拒绝
  - curl|bash, wget|sh → 拒绝
  - 路径参数必须在 workspace 或 uploads 虚拟路径下
```

### A4. 审计日志

**文件**：`backend/app/shell_mcp/audit.py`

```python
@dataclass
class SandboxAuditEntry:
    timestamp: datetime
    user_id: str
    workspace_id: str
    command: str
    description: str                      # LLM 提供的命令描述
    decision: str                         # "allowed" | "blocked"
    block_reason: str | None
    return_code: int | None
    duration_ms: int | None
    container_id: str | None
    output_size: int
```

通过 loguru JSON 格式输出，后续对接 Prometheus（Phase 2）。

### A5. 本地执行器（开发模式）

**文件**：`backend/app/sandbox/local_executor.py`

- 用于 Docker 不可用的开发环境
- 仍通过策略引擎过滤
- 使用 `subprocess.run()` + `preexec_fn=os.setsid` 做进程组管理
- 通过配置 `SANDBOX__BACKEND=local` 切换

---

## 四、Track B：用户目录虚拟映射（#5）

### B1. 虚拟路径规范

| 虚拟路径 | 物理路径 | 权限 | 说明 |
|---------|---------|------|------|
| `/mnt/user-data/workspace/` | `data/user_data/{uid}/conversations/{conv}/workspace/` | 读写 | 当前会话工作区 |
| `/mnt/user-data/uploads/` | `data/user_data/{uid}/conversations/{conv}/uploads/` | 只读 | 当前会话上传（含 `derived/`） |
| `/mnt/user-data/outputs/` | `data/user_data/{uid}/conversations/{conv}/outputs/` | 读写 | 最终交付物目录 |
| `/mnt/skills/` | `app/agent_skills/skills/` | 只读 | Agent 技能文档 |
| `/skills/` | `app/agent_skills/skills/` | 只读 | 技能目录 |

### B2. VirtualPathMapper

**文件**：`backend/app/vfs/mapper.py`

```python
class VirtualPathMapper:
    """双向映射：虚拟路径 <-> 物理路径"""

    def to_virtual(self, physical: Path, ctx: MappingContext) -> str:
        """物理路径 → 虚拟路径（API 响应用）"""

    def to_physical(self, virtual: str, ctx: MappingContext) -> Path:
        """虚拟路径 → 物理路径（实际操作用）"""

    def resolve_permission(self, virtual: str) -> PathPermission:
        """返回路径的权限级别（read_only / read_write）"""

    def sanitize_response(self, data: Any, ctx: MappingContext) -> Any:
        """递归清理响应数据中的物理路径"""
```

MappingContext：
```python
@dataclass
class MappingContext:
    user_id: str
    workspace_id: str                     # = conversation_id
    db: AsyncSession                      # 用于 /uploads/ 查询
```

### B3. /uploads/ 虚拟文件提供者

**文件**：`backend/app/vfs/uploads_provider.py`

基于 `conversation_attachments` 表提供 `/uploads/` 虚拟文件列表。

查询逻辑：
```sql
SELECT af.display_name, af.storage_key, af.mime, af.size, af.kind
FROM conversation_attachments ca
JOIN attachment_files af ON ca.attachment_file_id = af.id
WHERE ca.conversation_id = :workspace_id AND ca.user_id = :user_id
ORDER BY ca.created_at ASC
```

同名文件处理（追加序号）：
```
conversation_attachments 按 created_at ASC 遍历：
  report.pdf → report.pdf
  report.pdf → report(1).pdf
  report.pdf → report(2).pdf
```

安全约束：
- 只能访问当前会话 `conversation_attachments` 中已挂载的文件
- `display_name` 校验：拒绝 `/`、`..`、`\`、空字节、控制字符
- 只读权限，不允许通过虚拟路径写入/删除

### B4. 路径解析与安全校验

**文件**：`backend/app/vfs/resolver.py`

```python
class PathResolver:
    FORBIDDEN_SEGMENTS = {".git", ".ssh", ".aws", ".cursor", "__pycache__", ".env"}

    def resolve(self, virtual_path: str, ctx: MappingContext,
                permission: PathPermission) -> Path:
        # 1. 解析虚拟前缀 → 确定根目录
        # 2. 拼接物理根 + 相对路径
        # 3. .resolve() 规范化
        # 4. 安全校验：
        #    - 拒绝绝对路径
        #    - 拒绝 .. 遍历
        #    - 拒绝禁止目录段
        #    - 确认解析后仍在根目录下
        #    - 符号链接逃逸检测
        # 5. 权限校验（read_only 路径不允许写操作）
```

---

## 五、工具层改造（对齐 kimi）

### 5.1 工具 JSON Schema

对齐 kimi `ok-computer.json` 格式，定义在 `backend/app/tools/schemas.py`：

```python
READ_FILE_SCHEMA = {
    "name": "read_file",
    "description": "Reads a file from the workspace filesystem.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The virtual path to the file to read (e.g. /workspace/src/main.py, /uploads/report.pdf)"
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-based index)",
                "minimum": 1
            },
            "limit": {
                "type": "integer",
                "description": "Number of lines to read (useful for long files)",
                "minimum": 1,
                "maximum": 1000
            }
        },
        "required": ["file_path"]
    }
}

WRITE_FILE_SCHEMA = {
    "name": "write_file",
    "description": "Writes a file to the workspace filesystem.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The virtual path to the file to write (must be under /workspace/)"
            },
            "content": {
                "type": "string",
                "description": "The content to write to the file, maxlength is 100000"
            },
            "append": {
                "type": "boolean",
                "description": "Whether to append to the file instead of overwriting it"
            }
        },
        "required": ["file_path", "content"]
    }
}

EDIT_FILE_SCHEMA = {
    "name": "edit_file",
    "description": "Performs exact string replacements in files.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The virtual path to the file to modify"
            },
            "old_string": {
                "type": "string",
                "description": "The text to replace"
            },
            "new_string": {
                "type": "string",
                "description": "The text to replace it with (must be different from old_string)"
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences of old_string (default: false)"
            }
        },
        "required": ["file_path", "old_string", "new_string"]
    }
}

SEARCH_FILES_SCHEMA = {
    "name": "search_files",
    "description": "Search file contents or find files by name. Use this instead of grep/rg/find/ls in terminal. Ripgrep-backed, faster than shell equivalents.\n\nContent search (target='content'): Regex search inside files. Output modes: full matches with line numbers, file paths only, or match counts.\n\nFile search (target='files'): Find files by glob pattern (e.g., '*.py', '*config*'). Also use this instead of ls — results sorted by modification time.",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern for content search, or glob pattern (e.g., '*.py') for file search"
            },
            "target": {
                "type": "string",
                "enum": ["content", "files"],
                "description": "'content' searches inside file contents, 'files' searches for files by name",
                "default": "content"
            },
            "path": {
                "type": "string",
                "description": "Directory or file to search in (default: current working directory)",
                "default": "."
            },
            "file_glob": {
                "type": "string",
                "description": "Filter files by pattern in grep mode (e.g., '*.py' to only search Python files)"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 50)",
                "default": 50
            },
            "offset": {
                "type": "integer",
                "description": "Skip first N results for pagination (default: 0)",
                "default": 0
            },
            "output_mode": {
                "type": "string",
                "enum": ["content", "files_only", "count"],
                "description": "Output format for grep mode: 'content' shows matching lines with line numbers, 'files_only' lists file paths, 'count' shows match counts per file",
                "default": "content"
            },
            "context": {
                "type": "integer",
                "description": "Number of context lines before and after each match (grep mode only)",
                "default": 0
            }
        },
        "required": ["pattern"]
    }
}

SHELL_SCHEMA = {
    "name": "shell",
    "description": "Execute shell commands in a sandboxed environment with proper security measures.",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute."
            },
            "description": {
                "type": "string",
                "description": "Clear, concise summary (5-10 words) of what this command does."
            },
            "timeout": {
                "type": "integer",
                "description": "Optional timeout for command execution (in milliseconds, max: 600000)",
                "minimum": 1,
                "maximum": 600000
            }
        },
        "required": ["command", "description"]
    }
}
```

### 5.2 关键行为对齐 kimi

| 行为 | kimi 规范 | 当前实现 | 改造内容 |
|------|----------|---------|---------|
| `read_file` 分页 | `offset`(1-based) + `limit`(max 1000) | 无分页 | 新增 offset/limit 参数 |
| `read_file` 输出 | 行号前缀 + 截断 | 无行号 | 添加行号前缀 |
| `write_file` 追加 | `append` 参数 | 无 | 新增 append 参数 |
| `write_file` 大小 | maxlength 100000 | 2GB workspace 配额 | 单次写入限制 100000 字符 |
| `edit_file` 替换全部 | `replace_all` 参数 | 已有 | 保持 |
| `edit_file` 安全 | read-before-edit | 无 | 新增 read-before-edit 校验 |
| `shell` description | 必填 | 无 | 新增必填 description 参数 |
| `shell` 超时 | max 600000ms | max 300000ms | 提升到 600000ms |
| `shell` 输出截断 | 10000 字符 | 无截断 | 新增 50000 字符截断 |
| 路径参数名 | `file_path` | `path` | 统一为 `file_path` |
| 工具名 | `read_file` / `write_file` / `edit_file` / `shell` | `read_project_file` 等 | 统一重命名 |
| `search_files` 范围 | 内容搜索 + 文件搜索双模式 | 无此工具 | 新增，target=content 搜索内容，target=files 搜索文件名 |
| `search_files` 输出 | content/files_only/count 三种模式 | — | 基于 ripgrep，支持分页（limit/offset）和上下文（context） |

### 5.3 路径白名单（对齐 kimi Allowed/Forbidden Paths）

```
Read-Write:  /workspace/*
Read-Only:   /uploads/*, /skills/*
Forbidden:   物理路径、其他虚拟路径前缀
```

### 5.4 安全机制（对齐 kimi）

| 机制 | kimi 参考 | 实现 |
|------|----------|------|
| Read-Before-Write | write_file.md Safety | 覆盖写入前检查文件是否已读取 |
| Read-Before-Edit | edit_file.md Safety | edit_file 必须先 read_file |
| Uniqueness Check | edit_file.md | old_string 必须唯一（除非 replace_all） |
| Identical String Check | edit_file.md | old_string != new_string |
| Output Truncation | shell.md 10000 chars | 50000 字符截断 |
| Content Size Limit | write_file.md maxlength | 单次写入 100000 字符 |

### 5.5 search_files 工具设计

**功能**：搜索文件内容或按文件名查找文件。替代 LLM 在 shell 中使用 grep/rg/find/ls。基于 ripgrep，比 shell 等价命令更快。

**两种搜索模式**：

| 模式 | target 值 | 说明 |
|------|----------|------|
| 内容搜索 | `content` | 正则搜索文件内容，支持行号/路径/计数三种输出 |
| 文件搜索 | `files` | 按 glob 模式查找文件名，替代 ls，按修改时间排序 |

**参数说明**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `pattern` | string | 是 | — | 内容搜索用正则，文件搜索用 glob（如 `*.py`） |
| `target` | string | 否 | `content` | `content` 搜索文件内容，`files` 搜索文件名 |
| `path` | string | 否 | `.` | 搜索范围的虚拟路径，默认当前工作目录 |
| `file_glob` | string | 否 | — | 内容搜索时的文件过滤（如 `*.py`） |
| `limit` | integer | 否 | 50 | 最大返回结果数 |
| `offset` | integer | 否 | 0 | 跳过前 N 条结果（分页） |
| `output_mode` | string | 否 | `content` | 输出格式：`content`（匹配行+行号）、`files_only`（仅文件路径）、`count`（每文件匹配数） |
| `context` | integer | 否 | 0 | 匹配行前后的上下文行数（仅内容搜索） |

**实现方案**：

```python
# backend/app/mcp/mcp_servers/file_mcp/search_files.py
class SearchFilesTool(ToolBase):
    name = "search_files"
    description = SEARCH_FILES_SCHEMA["description"]
    parameters = SEARCH_FILES_SCHEMA

    async def execute(self, arguments: dict, ctx: ToolContext) -> ToolResult:
        pattern = arguments["pattern"]
        target = arguments.get("target", "content")
        virtual_path = arguments.get("path", ".")
        file_glob = arguments.get("file_glob")
        limit = arguments.get("limit", 50)
        offset = arguments.get("offset", 0)
        output_mode = arguments.get("output_mode", "content")
        context = arguments.get("context", 0)

        # 1. 虚拟路径解析 → 物理目录
        physical_dir = ctx.mapper.to_physical(virtual_path, ctx.mapping_context)

        # 2. 根据 target 分发
        if target == "files":
            # 文件搜索：find / glob 模式
            # rg --files --glob pattern physical_dir
        else:
            # 内容搜索：ripgrep
            # rg --line-number --no-heading --color=never
            #   [--glob=file_glob]
            #   [--context=N]
            #   [--offset=N --max-count=limit]
            #   [--output_mode=files_only|count]
            #   pattern physical_dir

        # 3. 物理路径替换为虚拟路径（sanitize）

        # 4. 输出截断 50000 字符
```

**安全约束**：
- 搜索范围限定在虚拟路径白名单内（`/workspace/`、`/skills/`）
- 不支持搜索 `/uploads/`（文件内容通过 RAG 索引，不直接搜索）
- 正则表达式编译失败时返回明确错误
- 结果中所有物理路径替换为虚拟路径
- 输出上限 50000 字符（对齐 shell 输出截断）

**依赖**：宿主机需安装 `ripgrep`（`rg` 命令），或回退到 Python `re` + `pathlib` 遍历。

**输出示例**：

`output_mode=content`（默认）：
```
/workspace/src/main.py:15:from app.core.config import settings
/workspace/src/main.py:42:    settings.app.debug = True
/workspace/src/utils/helper.py:8:def get_config():
```

`output_mode=content, context=2`：
```
/workspace/src/main.py:13-  import os
/workspace/src/main.py:14-
/workspace/src/main.py:15:from app.core.config import settings
/workspace/src/main.py:16-
/workspace/src/main.py:17-  class App:
```

`output_mode=files_only`：
```
/workspace/src/main.py
/workspace/src/utils/helper.py
/workspace/src/config/settings.py
```

`output_mode=count`：
```
/workspace/src/main.py:5
/workspace/src/utils/helper.py:2
/workspace/src/config/settings.py:12
```

`target=files, pattern="*.py"`：
```
/workspace/src/main.py
/workspace/src/utils/helper.py
/workspace/src/config/settings.py
/workspace/tests/test_main.py
```

---

## 六、MCP 注册变更

### 6.1 mcp_registry.py

```python
from app.mcp.mcp_servers.file_mcp.server import mcp as file_mcp
from app.mcp.mcp_servers.shell_mcp.server import mcp as shell_mcp

_servers = {
    "time-mcp": time_mcp,
    "context7-mcp": ...,
    "weather-mcp": weather_mcp,
    "tavily-mcp": tavily_mcp,
    "code-exec-mcp": code_exec_mcp,
    "file-mcp": file_mcp,               # 新增（替代 agent-skills-mcp）
    "shell-mcp": shell_mcp,             # 新增
}
```

### 6.2 tool_executor.py

`_inject_workspace_args_for_agent_skills()` 需要同步更新：
- 工具名列表更新为 `file-mcp` + `shell-mcp` 的工具
- `user_id` / `workspace_id` 注入逻辑保持不变

---

## 七、前端改造

### 7.1 工具名同步

| 文件 | 改造内容 |
|------|---------|
| `ToolResult/hooks.ts:27` | `read_project_file` → `read_file` |
| `ContentBlocksRender/viewModel.ts:11` | `write_workspace_file` → `write_file` |
| `ToolArguments/hooks.tsx` | 工具名映射更新 |
| `ProjectPreviewBlockRender.tsx` | `write_workspace_file` → `write_file` |

### 7.2 路径模型变更

```typescript
// 改造前
interface WorkspaceTreeNode {
    title: string;
    path: string;          // 相对路径
    fullPath?: string;     // 物理绝对路径（暴露风险）
    ...
}

// 改造后
interface WorkspaceTreeNode {
    title: string;
    path: string;          // 虚拟路径（/workspace/xxx, /uploads/xxx）
    nodeType: "dir" | "file";
    hasChildren?: boolean;
    isLeaf?: boolean;
    key?: string;
    children?: WorkspaceTreeNode[];
    // 移除 fullPath
}
```

### 7.3 前端文件改造清单

| 文件 | 改造内容 |
|------|---------|
| `ProjectPreview/utils.ts` | `toDisplayPath()` 基于虚拟路径截取；移除 `fullPath` |
| `ProjectPreview/index.tsx` | 移除 `fullPath` 使用，统一用 `path`（虚拟路径） |
| `services/workspace.ts` | `WorkspaceTreeNode` 移除 `fullPath` 字段 |
| `ToolResult/hooks.ts` | 文件路径语言检测适配虚拟路径扩展名 |

---

## 八、后端 API 改造（可暂缓）

> **暂缓说明**：此部分为展示层优化，不影响安全隔离核心目标。MCP 工具层已保障 LLM 只接触虚拟路径，前端 API 改造可独立迭代。建议在 Week 4 或后续阶段实施。

### 8.1 workspace API（`api/workspace.py`）

| 端点 | 改造内容 |
|------|---------|
| `GET /{id}/files` | 返回虚拟路径；注入 /uploads/ 虚拟目录节点 |
| `GET /{id}/file-content` | 接收虚拟路径，mapper 解析后读取 |
| `GET /{id}/download` | 内部使用物理路径，ZIP 中文件名使用虚拟路径 |
| `GET /{uid}/{wid}/preview-content` | 内部使用物理路径（不暴露） |

### 8.2 file API（`api/file.py`）

| 端点 | 改造内容 |
|------|---------|
| `POST /file/upload` | 上传逻辑不变，返回路径改为虚拟路径 |
| `GET /file/preview/{uid}/{sk}` | 保持不变（内部 API） |

### 8.3 响应数据清洗

所有返回给前端的 JSON 数据，通过 `VirtualPathMapper.sanitize_response()` 递归替换物理路径为虚拟路径。

---

## 九、删除项清理

### 9.1 移除的工具函数

从 `agent_skills_mcp/server.py`（迁移至 `file_mcp/server.py` 时不再包含）：
- `list_project_files()` — 整个函数删除
- `delete_workspace_file()` — 整个函数删除
- `clear_workspace()` — 整个函数删除
- `_resolve_readonly_root()` — 仅被 `list_project_files` 和 `read_project_file` 使用，`read_file` 改用 mapper 后可删除

### 9.2 移除的工具函数（utils.py）

- `format_usage()` — 仅被删除的工具使用
- `workspace_usage()` — 仅被 `format_usage` 和 `ensure_write_quota` 使用，`ensure_write_quota` 改为直接计算

### 9.3 移除的配置（config.py）

- `DANGEROUS_BASH_PATTERNS` — 移至 `shell_mcp/policy.py`（升级为 AST 级策略）

### 9.4 前端清理

- `PROJECT_PREVIEW_TOOLS` 中 `write_workspace_file` → `write_file`

---

## 十、配置变更

### 10.1 沙箱配置

```bash
# backend/.env 或 Nacos
SANDBOX__ENABLED=true
SANDBOX__BACKEND=docker                  # docker | local
SANDBOX__IMAGE=ubuntu:22.04
SANDBOX__CPU_LIMIT=1.0
SANDBOX__MEMORY_LIMIT=512m
SANDBOX__PID_LIMIT=100
SANDBOX__TIMEOUT=600000                  # ms，对齐 kimi
SANDBOX__NETWORK_ENABLED=false
SANDBOX__CONTAINER_POOL_SIZE=5
SANDBOX__OUTPUT_LIMIT=50000              # 输出截断字符数
```

### 10.2 虚拟路径配置

```bash
VFS__ENABLED=true
VFS__WORKSPACE_PREFIX=/workspace/
VFS__UPLOADS_PREFIX=/uploads/
VFS__SKILLS_PREFIX=/skills/
VFS__MAX_FILE_SIZE_MB=100                # 单文件大小限制
VFS__MAX_LINE_LENGTH=2000                # 单行截断长度
VFS__WRITE_MAX_CHARS=100000              # 单次写入字符限制（对齐 kimi）
```

---

## 十一、依赖新增

| 依赖 | 用途 | 安装方式 |
|------|------|---------|
| `docker` | Docker Python SDK | `pip install docker` |
| `bashlex` | Shell AST 解析 | `pip install bashlex` |
| `ripgrep` | search_files 底层搜索引擎 | `brew install ripgrep` / `apt install ripgrep` |

---

## 十二、分周计划

```
Week 1: 基础架构搭建
├── 创建 sandbox/ 模块（SandboxExecutor 抽象 + DockerExecutor 原型）
├── 创建 vfs/ 模块（VirtualPathMapper + PathResolver + UploadsProvider）
├── 创建 tools/ 模块（ToolBase + schemas.py）
├── 拆分 MCP 服务（file_mcp/ + shell_mcp/ 目录结构）
└── 移除 list_project_files、delete_workspace_file、clear_workspace

Week 2: 核心逻辑实现
├── Docker 沙箱后端完整实现（资源限制、挂载、capability dropping）
├── 命令策略引擎（bashlex AST 解析 + 白名单）
├── file-mcp 5 个工具实现（对齐 kimi Schema + 行为）
└── shell-mcp shell 工具实现（对接 SandboxExecutor）

Week 3: 前端适配 + 安全加固
├── 前端工具名同步（read_file、write_file、edit_file、shell）
├── 审计日志实现
├── 安全测试用例集（路径遍历、符号链接、编码绕过、命令注入）
└── 安全测试集 100% 通过

Week 4: 集成测试 + 灰度
├── 端到端集成测试
├── 性能基准测试（沙箱延迟 < 500ms）
├── 灰度开关实现（按用户 ID 百分比放量）
└── 回归测试（MCP 工具调用、文件操作、命令执行）

后续迭代（可暂缓）
├── 后端 API 路径改造（workspace API、file API 返回虚拟路径）
├── 前端路径模型变更（移除 fullPath，使用虚拟路径）
└── 回归测试（文件上传/下载、项目预览、workspace ZIP）
```

---

## 十三、里程碑与验收

| 里程碑 | 时间 | 验收标准 |
|--------|------|---------|
| **M1** | Week 1 末 | sandbox/ + vfs/ + tools/ 模块骨架就绪；MCP 拆分完成；3 个废弃工具已移除 |
| **M2** | Week 2 末 | Docker 沙箱可执行简单命令；策略引擎覆盖 90%+ 危险命令变体；5 个 file-mcp 工具 + 1 个 shell-mcp 工具功能完整；API 响应无物理路径泄漏 |
| **M3** | Week 3 末 | 前端适配完成；审计日志上线；安全测试集 100% 通过 |
| **M4** | Week 4 末 | 集成测试通过；灰度开关就绪；性能基准测试完成 |

---

## 十四、验收标准（对应 Roadmap）

### #4 命令执行沙箱隔离

- [ ] 危险命令、越权访问均可拦截
- [ ] 非授权路径访问拦截率 100%
- [ ] 合法操作主流程可用性 >= 99%

### #5 用户目录虚拟映射

- [ ] 前后端不再出现真实物理路径
- [ ] 路径遍历攻击测试 100% 拦截
- [ ] 文件工具调用成功率不低于改造前基线
- [ ] /uploads/ 可正确列出当前会话上传文件
- [ ] 同名文件追加序号处理
- [ ] 跨会话文件访问被拒绝

---

## 十五、暂缓项决策记录

### 15.1 todo_read / todo_write 工具 — 暂不引入

**来源**：kimi OK Computer 模式的 `mshtools-todo_read`、`mshtools-todo_write`

**功能**：会话级任务列表管理，存储在 `.todo.jsonl`，跨轮次追踪多步任务进度。

**决策**：Phase 0 不引入

**理由**：
- 适用场景为复杂多步编码任务（OK Computer 模式），当前项目为对话式 AI + MCP 工具调用，非编码 Agent
- 对话历史本身已提供上下文连续性，LLM 可通过对话记录追踪进度
- 引入成本：需新增存储层（session-scoped JSONL）、2 个 MCP 工具、前端 todo 展示组件

**引入时机**：Phase 3（Agent Skills 技能扩展）时按需评估，当 Agent 扩展为编码模式或单次对话工具调用次数显著增加（10+ 次）时考虑引入。

### 15.2 后端 API 路径改造 — 可暂缓

**详见**：第八节（后端 API 改造）

**决策**：展示层优化不影响安全隔离核心目标，MCP 工具层已保障 LLM 只接触虚拟路径。建议在 Week 4 或后续阶段实施。

---

## 十六、风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| Docker 引入后命令延迟增加 | 用户体验 | 预热容器池；local 模式保留为 fallback |
| 虚拟路径改造影响面广 | 回归风险 | 先改 MCP 层，再改 API 层，最后改前端；每层独立验收 |
| bashlex 解析复杂命令失败 | 策略引擎覆盖率 | 解析失败时默认拒绝 + 告警，人工补充规则 |
| 工具名变更影响 LLM 调用 | 兼容性 | 更新 system prompt 中的工具引用；灰度验证 |
| /uploads/ 同名文件序号逻辑复杂 | 正确性 | 单元测试覆盖多场景（0/1/2/3 个同名文件） |

---

## 十七、文件变更总览

### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/sandbox/__init__.py` | 沙箱模块 |
| `backend/app/sandbox/executor.py` | SandboxExecutor 抽象基类 |
| `backend/app/sandbox/docker_executor.py` | Docker 沙箱实现 |
| `backend/app/sandbox/local_executor.py` | 本地执行器（开发模式） |
| `backend/app/sandbox/config.py` | 沙箱全局配置 |
| `backend/app/vfs/__init__.py` | 虚拟文件系统模块 |
| `backend/app/vfs/mapper.py` | VirtualPathMapper |
| `backend/app/vfs/resolver.py` | PathResolver |
| `backend/app/vfs/uploads_provider.py` | UploadsProvider |
| `backend/app/vfs/config.py` | 虚拟路径配置 |
| `backend/app/mcp/mcp_servers/file_mcp/__init__.py` | file-mcp 模块 |
| `backend/app/mcp/mcp_servers/file_mcp/server.py` | file-mcp 服务注册入口 |
| `backend/app/mcp/mcp_servers/file_mcp/base.py` | ToolBase 抽象基类 |
| `backend/app/mcp/mcp_servers/file_mcp/schemas.py` | JSON Schema 定义 |
| `backend/app/mcp/mcp_servers/file_mcp/read_file.py` | read_file 工具 |
| `backend/app/mcp/mcp_servers/file_mcp/write_file.py` | write_file 工具 |
| `backend/app/mcp/mcp_servers/file_mcp/edit_file.py` | edit_file 工具 |
| `backend/app/mcp/mcp_servers/file_mcp/search_files.py` | search_files 工具 |
| `backend/app/mcp/mcp_servers/file_mcp/load_skill.py` | load_skill 工具 |
| `backend/app/mcp/mcp_servers/file_mcp/utils.py` | 路径解析、配额校验 |
| `backend/app/mcp/mcp_servers/file_mcp/config.py` | 文件相关配置 |
| `backend/app/mcp/mcp_servers/file_mcp/test_server.py` | 文件工具测试 |
| `backend/app/mcp/mcp_servers/shell_mcp/__init__.py` | shell-mcp 模块 |
| `backend/app/mcp/mcp_servers/shell_mcp/server.py` | shell-mcp 服务注册入口 |
| `backend/app/mcp/mcp_servers/shell_mcp/base.py` | ToolBase 抽象基类 |
| `backend/app/mcp/mcp_servers/shell_mcp/schemas.py` | shell JSON Schema 定义 |
| `backend/app/mcp/mcp_servers/shell_mcp/shell.py` | shell 工具 |
| `backend/app/mcp/mcp_servers/shell_mcp/policy.py` | 命令策略引擎 |
| `backend/app/mcp/mcp_servers/shell_mcp/executor.py` | SandboxExecutor 委托 |
| `backend/app/mcp/mcp_servers/shell_mcp/audit.py` | 审计日志 |
| `backend/app/mcp/mcp_servers/shell_mcp/config.py` | 沙箱配置 |
| `backend/app/mcp/mcp_servers/shell_mcp/test_server.py` | shell 工具测试 |

### 修改文件

| 文件 | 改造内容 |
|------|---------|
| `backend/app/mcp/mcp_registry.py` | 注册 file-mcp + shell-mcp，移除 agent-skills-mcp |
| `backend/app/agents/tool_executor.py` | 工具名列表更新，注入逻辑适配两个 MCP |
| `backend/app/mcp/mcp_tool_gateway.py` | 工具 schema 清洗适配新工具名 |
| `backend/app/prompts/system_prompt.py` | 更新工具引用和路径说明 |
| `backend/app/api/workspace.py` | API 响应使用虚拟路径（**可暂缓**） |
| `backend/app/api/file.py` | 上传返回路径改为虚拟路径（**可暂缓**） |
| `backend/pyproject.toml` | 新增 docker、bashlex 依赖 |
| `frontend/src/pages/.../ToolResult/hooks.ts` | `read_project_file` → `read_file` |
| `frontend/src/pages/.../viewModel.ts` | `write_workspace_file` → `write_file` |
| `frontend/src/pages/.../ProjectPreview/utils.ts` | 移除 fullPath，使用虚拟路径（**可暂缓**） |
| `frontend/src/pages/.../ProjectPreview/index.tsx` | 移除 fullPath 使用（**可暂缓**） |
| `frontend/src/services/workspace.ts` | WorkspaceTreeNode 移除 fullPath（**可暂缓**） |

### 删除文件

| 文件 | 说明 |
|------|------|
| `backend/app/mcp/mcp_servers/agent_skills_mcp/` | 整个目录废弃，功能迁移至 file_mcp/ + shell_mcp/ |
