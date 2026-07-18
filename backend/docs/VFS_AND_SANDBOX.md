# VFS 与沙箱执行手册（当前实现）

## 1. 适用范围

本文档说明 Agent 模式下的会话文件系统、虚拟路径映射、`file` / `shell`
MCP 工具和沙箱执行后端。它面向维护后端、MCP 工具或 Agent 文件能力的开发者。

对应源码：

- 路径布局：`app/vfs/paths.py`
- 虚拟路径解析与权限：`app/vfs/resolver.py`、`app/vfs/mapper.py`
- File MCP：`app/mcp/mcp_servers/file_mcp/`
- Shell MCP：`app/mcp/mcp_servers/shell_mcp/`
- 沙箱执行器：`app/sandbox/`
- 配置：`app/schemas/config.py` 的 `MCPConfig`、`SandboxConfig`

## 2. 磁盘目录与虚拟路径

用户数据统一放在 `backend/data/user_data/{user_id}/` 下。会话级数据按
`conversation_id` 隔离：

```text
backend/data/user_data/{user_id}/
├── skills/                         # 用户自定义 skills
└── conversations/{conversation_id}/
    ├── workspace/                  # Agent 可读写工作区
    ├── uploads/                    # 用户上传文件，只读挂载给 Agent
    └── outputs/                    # Agent 最终产物，可读写
```

Agent 和 MCP 工具不应暴露磁盘路径，应使用虚拟路径：

| 虚拟路径前缀 | 磁盘位置 | 权限 | 典型用途 |
|---|---|---|---|
| `/mnt/user-data/workspace/` | `conversations/{conversation_id}/workspace/` | 读写 | 中间文件、代码草稿、临时分析 |
| `/mnt/user-data/uploads/` | `conversations/{conversation_id}/uploads/` | 只读 | 读取用户上传的 PDF、表格、文本等 |
| `/mnt/user-data/outputs/` | `conversations/{conversation_id}/outputs/` | 读写 | 需要交付给用户的最终文件 |
| `/mnt/skills/custom/` | `data/user_data/{user_id}/skills/` | 读写 | 用户自定义 skill |
| `/mnt/skills/public/` | `backend/skills/public/` | 只读 | 内置公共 skill |
| `/mnt/skills/` | `backend/skills/` | 只读 | skills 根目录兜底映射 |

`PathResolver` 会拒绝绝对路径逃逸、`..`、`.git`、`.ssh`、`.aws`、
`.cursor`、`__pycache__` 和 `.env` 等敏感路径片段。`VirtualPathMapper`
负责将返回值中的磁盘路径替换回虚拟路径，避免把宿主机目录暴露给前端或 LLM。

## 3. File MCP 工具

默认 `agent_mode > 0` 时会向 LLM 暴露 `file` server；普通对话模式默认不暴露。
工具名在 LLM 侧带 server 前缀，例如 `file_read_file`。

| 工具 | 行为 | 关键约束 |
|---|---|---|
| `read_file` | 读取虚拟路径文件，支持 `offset`/`limit` 分页 | 只能读已存在文件；返回内容会按系统读取上限截断 |
| `write_file` | 写入或追加文件 | 只能写 `/workspace/`、`/outputs/`、`/skills/custom/`；单次内容默认最多 100000 字符 |
| `edit_file` | 精确字符串替换 | 默认要求 `old_string` 唯一；多处替换需显式 `replace_all=true` |
| `search_files` | 用 ripgrep 搜索内容或文件名 | 默认搜索当前会话 `workspace`；返回路径会转换为虚拟路径 |
| `present_files` | 将产物标记为可展示给用户 | 只接受 `/mnt/user-data/outputs/` 下已存在的文件 |

写入 `workspace` 或 `outputs` 会走工作区配额检查；当前总量上限定义在
`app/utils/workspace.py`（`MAX_WORKSPACE_BYTES = 2000 * 1024 * 1024`）。
`skills/custom` 用于持久化用户 skill，不计入会话 workspace 配额。

### 示例

```json
{
  "file_path": "/mnt/user-data/workspace/analysis/result.md",
  "content": "# 分析结果\n..."
}
```

完成最终交付时先写到 outputs，再调用 `present_files`：

```json
{
  "filepaths": ["/mnt/user-data/outputs/report.md"]
}
```

## 4. Shell MCP 与沙箱后端

`shell` server 只在 Agent 模式默认暴露。每个 `(user_id, conversation_id)` 会懒创建
一个会话级 `ShellExecutor`，工作目录固定为当前会话 workspace。

### 4.1 配置

`SandboxConfig` 当前默认：

| 配置 | 默认值 | 说明 |
|---|---:|---|
| `SANDBOX__BACKEND` | `local` | `local` 或 `docker` |
| `SANDBOX__TIMEOUT` | `600000` | 单次命令最大超时，毫秒 |
| `SANDBOX__NETWORK_ENABLED` | `false` | Docker 后端是否允许网络 |
| `SANDBOX__OUTPUT_LIMIT` | `50000` | executor 层输出截断上限 |

Shell MCP 自身还限制命令长度和输出展示：

- 默认超时：30000 ms
- 最大超时：600000 ms
- 最大命令长度：10000 字符
- 最大展示输出：50000 字符

### 4.2 local 后端

`local` 后端在宿主机以会话 workspace 为 `cwd` 执行命令。执行前会：

1. 校验命令中的绝对路径，要求文件访问落在 `/mnt/user-data/...` 或
   `/mnt/skills/...` 等允许前缀；
2. 将虚拟路径替换成宿主机物理路径；
3. 执行后把 stdout/stderr 中的物理路径再替换回虚拟路径。

因此开发和排障时，即使实际运行在本机，也应让 Agent 使用虚拟路径。例如：

```bash
python /mnt/user-data/workspace/scripts/analyze.py /mnt/user-data/uploads/data.csv
```

不要让 Agent 直接引用 `backend/data/user_data/...` 的物理路径。

### 4.3 docker 后端

`docker` 后端会启动一次性容器执行命令，并绑定挂载：

- workspace：读写挂载到 `/mnt/user-data/workspace`
- uploads：只读挂载到 `/mnt/user-data/uploads`
- outputs：读写挂载到 `/mnt/user-data/outputs`
- custom skills：读写挂载到 `/mnt/skills/custom`
- public skills：只读挂载到 `/mnt/skills/public`

容器默认禁用网络，丢弃 Linux capabilities，启用 `no-new-privileges`，并设置 CPU、
内存、PID 和 `/tmp` tmpfs 限制。若配置为 `docker` 但 Docker daemon 不可用，
请求会直接失败并提示启动 Docker 或改用 `SANDBOX__BACKEND=local`，不会自动回退。

## 5. 命令审计与常见阻断

Shell MCP 会先执行命令审计：

- 高风险命令会阻断，例如递归删除根目录、`dd if=`、`mkfs`、读取
  `/etc/shadow`、管道执行远程脚本、写入系统目录、`LD_PRELOAD`、`/dev/tcp/` 等；
- 中风险命令会执行但追加警告，例如 `chmod 777`、`pip install`、
  `apt install`、`sudo`、修改 `PATH`。

local 后端还会阻断常见路径逃逸：

- `cd /tmp`、`cd ~`、`cd $VAR` 等不在 `/mnt/user-data` 下的工作目录切换；
- `file://...` URL；
- 包含 `..` 的路径；
- 对 `/` 等根路径的 `cat`、`ls`、`rm`、`cp`、`mv`、`grep`、`find` 等操作。

排障时优先检查：

1. 命令是否带 `description`（必填，5-10 个词的用途说明）；
2. 路径是否使用虚拟前缀；
3. `agent_mode` 是否大于 0，否则默认不会暴露 `file`/`shell`；
4. Docker 后端是否能连接 daemon；
5. 产物是否写入 `/mnt/user-data/outputs/` 后再调用 `present_files`。

## 6. 与附件 RAG 的关系

用户上传文件先进入 `uploads/`。普通对话模式会按附件类型走聊天附件链路和
RAG 上下文注入；Agent 模式则把上传文件作为 `/mnt/user-data/uploads/...`
虚拟路径提供给工具使用，文件读取、转换和产物生成由 Agent 通过 `file`/`shell`
工具完成。

这意味着：

- 需要让 LLM 直接操作文件时，应使用 Agent 模式；
- 需要给用户展示最终结果时，应写入 `outputs/` 并调用 `present_files`；
- 不要把 `uploads/` 当作可写工作目录，派生文件应写到 `workspace/` 或 `outputs/`。
