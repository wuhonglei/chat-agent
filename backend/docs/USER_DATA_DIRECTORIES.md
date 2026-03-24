# 用户数据目录说明：outputs、uploads、workspace

## 概述

每个 DeerFlow 线程（thread）在 `user-data` 下有三个子目录，分别用于不同的用途。Agent 通过虚拟路径 `/mnt/user-data/{uploads,workspace,outputs}` 访问这些目录。

## 三个目录对比

| 目录 | 虚拟路径 | 用途 | 数据来源 |
|------|----------|------|----------|
| **uploads** | `/mnt/user-data/uploads` | 用户上传的输入文件 | 用户通过 API 上传 |
| **workspace** | `/mnt/user-data/workspace` | 工作区/临时文件 | Agent 在任务过程中创建 |
| **outputs** | `/mnt/user-data/outputs` | 最终交付物，可呈现给用户 | Agent 生成并移入 |

## 详细说明

### 1. uploads — 用户上传

- **作用**：存放用户通过界面或 API 上传的文件（PDF、PPT、Excel、Word 等）
- **特点**：
  - 上传后会自动注入到对话上下文的 `<uploaded_files>` 中
  - 支持文档自动转 Markdown（PDF/PPT 等会生成 `*.md`）
  - Agent 使用 `read_file` 读取，路径如 `/mnt/user-data/uploads/xxx.pdf`
- **前端访问**：`/api/conversations/{id}/artifacts/mnt/user-data/uploads/xxx.pdf`

详见 [FILE_UPLOAD.md](FILE_UPLOAD.md) 和 [PATH_EXAMPLES.md](PATH_EXAMPLES.md)。

### 2. workspace — 工作区（临时文件）

- **作用**：Agent 的工作目录，存放临时文件、脚本、中间结果等
- **特点**：
  - Agent 可自由读写，如使用 `bash`、`write_file`、`str_replace` 等工具
  - 适合创建临时脚本、缓存、虚拟环境（如 `.venv`）等
  - 一般不直接呈现给用户
- **建议**：所有临时工作都在 `workspace` 完成，最终成果再复制到 `outputs`

### 3. outputs — 输出目录（可呈现给用户）

- **作用**：存放 Agent 希望呈现给用户的最终交付物
- **特点**：
  - **只有 `outputs` 下的文件才能通过 `present_files` 工具展示到前端**
  - Agent 流程：在 `workspace` 处理 → 复制到 `outputs` → 调用 `present_files`
- **前端访问**：`/api/conversations/{id}/artifacts/mnt/user-data/outputs/xxx.md`

## 推荐工作流

```
用户上传 → uploads（用户输入）
     ↓
Agent 读取 uploads 中的文件
     ↓
Agent 在 workspace 中处理（临时脚本、中间文件等）
     ↓
将最终结果复制到 outputs
     ↓
调用 present_files 工具 → 用户在前端可见
```

## 物理路径结构

实际存储位置（本地模式）：

```
data/conversations/{conversation_id}/user-data/
├── workspace/   # 工作区/临时文件
├── uploads/     # 用户上传
└── outputs/     # 最终交付物
```

虚拟路径映射（见 [ARCHITECTURE.md](ARCHITECTURE.md)）：

| 虚拟路径 | 物理路径 |
|----------|----------|
| `/mnt/user-data/workspace` | `data/conversations/{conversation_id}/user-data/workspace` |
| `/mnt/user-data/uploads` | `data/conversations/{conversation_id}/user-data/uploads` |
| `/mnt/user-data/outputs` | `data/conversations/{conversation_id}/user-data/outputs` |
