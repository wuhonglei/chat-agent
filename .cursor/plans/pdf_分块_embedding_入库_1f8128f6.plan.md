---
name: PDF 分块 Embedding 入库
overview: 在 `save_chat_pdf` 成功落盘并生成 Markdown 之后，使用 **`settings.kb_file_rag`** 中的 `chunk_size` / `chunk_overlap` 与 `MarkdownTextSplitter` 分块，经 `EmbeddingService`（DashScope）批量向量化，将结果写入新表 `kb_file_chunk_embeddings`（pgvector），并在 Alembic 中维护结构。**无向量或入库失败则接口失败（HTTP 异常），不视为上传成功。**
todos:
  - id: config-kb-file-rag
    content: 在 schemas/config.py 定义 KbFileRagConfig；在 core/config.py Settings 顶层增加 kb_file_rag 字段并 import
    status: completed
  - id: model-migration
    content: 新增 KbFileChunkEmbedding SQLModel（表 kb_file_chunk_embeddings：id/user_id/file_id/chunk_idx/chunk_content/embedding_vector/created_at/metadata JSON）+ Alembic 迁移（pgvector vector(1024)、索引、唯一约束）
    status: completed
  - id: indexing-service
    content: 实现 kb_file_chunk_embedding_service：读文本、MarkdownTextSplitter（参数来自 settings.kb_file_rag）、EmbeddingService、Session 内 delete+insert
    status: completed
  - id: wire-save-chat-pdf
    content: 在 save_chat_pdf 成功路径（含去重返回）调用 indexing；无向量或入库失败则抛 HTTP 异常，上传视为失败
    status: completed
  - id: tests
    content: 补充测试或手动验证迁移与入库行数
    status: completed
isProject: false
---

# PDF 分块 Embedding 入库方案

## 现状与约定

- [`chat_pdf_service.py`](backend/app/services/base_service/chat_pdf_service.py)：`save_chat_pdf` 以内容 SHA-256（`content_hash`）命名文件；`PdfBlock.id` 即为该哈希，可作为 **`file_id`** 与磁盘上的 `{hash}.md` 一一对应。
- 向量化已有封装：[`embedding_service.py`](backend/app/services/base_service/embedding_service.py) 使用 `DashScopeEmbeddings`，提供 `aembed_documents(texts)`，与工具侧一致。
- **上传文件分块（独立于工具结果压缩配置）**：与 [`context_compactor.py`](backend/app/utils/context_compactor.py) 同样使用 `MarkdownTextSplitter`，但 **`chunk_size` / `chunk_overlap` 来自应用配置顶层字段 `kb_file_rag`**（见下），**不**读取 `settings.chat_context.tool_result_compression`。
- **`kb_file_rag` 配置（实现时）**：在 [`backend/app/schemas/config.py`](backend/app/schemas/config.py) 新增 **`KbFileRagConfig`**（`BaseModel`），字段例如：`chunk_size: int = 1000`（字符）、`chunk_overlap: int = 200`。在 [`backend/app/core/config.py`](backend/app/core/config.py) 的 **`Settings`** 上增加顶层字段 **`kb_file_rag: KbFileRagConfig`**，`Field(default_factory=KbFileRagConfig, description="知识库上传文件分块与 RAG 相关配置")`，并从 `app.schemas.config` 引入 `KbFileRagConfig`。环境变量覆盖与其它嵌套配置一致，例如 **`KB_FILE_RAG__CHUNK_SIZE`**、**`KB_FILE_RAG__CHUNK_OVERLAP`**（`env_nested_delimiter="__"` 已存在）。`kb_file_chunk_embedding_service` 内使用 **`settings.kb_file_rag.chunk_size`** 等实例化 `MarkdownTextSplitter`。
- 向量列维度与历史迁移一致：**1024**（见 [`EmbeddingModelConfig.embedding_dimension`](backend/app/schemas/config.py) 及各 migration 中的 `EMBEDDING_DIMENSION = 1024`）；**不再单独建 `embedding_size` 列**，维度由 `vector(1024)` 类型体现；若需在业务上记录模型名或维度，写入 **`metadata`**（见数据表设计）。

## 数据表设计

表名：**`kb_file_chunk_embeddings`**（`kb` = 知识库语义：按上传文件分块入库；后续若增加 TXT 等纯文本上传，可复用同一张表；**`metadata`** 中约定 `source_kind`、`text_format`、`file_name`、分块前全文 token 数、`original_size_bytes`、`processed_size_bytes` 等，页码、章节等也可放其中，无需首版加列）。

| 列 | 说明 |
|----|------|
| `id` | 主键 UUID（与项目其他表一致，使用 `gen_uuid`） |
| `user_id` | 字符串，建议 `VARCHAR(36)`，可选 `ForeignKey("users.id")` 与用户表对齐 |
| `file_id` | 上传内容哈希标识（当前 PDF 流程为 `PdfBlock.id` / `content_hash`，SHA-256 十六进制 64 字符；其他类型上传沿用同一「内容命名」规则即可） |
| `chunk_idx` | 整数，从 0 递增，与分块顺序一致 |
| `chunk_content` | `Text`，分块正文 |
| `embedding_vector` | `pgvector`：`vector(1024)`，与 [`o1p2q3r4s5t6_remove_message_embedding_columns.py`](backend/alembic/versions/o1p2q3r4s5t6_remove_message_embedding_columns.py) 等迁移一致 |
| `created_at` | `timestamptz`，默认 `now()`，入库时间 |
| `metadata` | `JSON`（或 SQLAlchemy `JSON`），可空或默认 `{}`。**建议字段**：`embedding_model`（如 `settings.embedding_model.model_name`）、可选 `embedding_dimension`（与向量维度一致，便于导出/排查）；**`source_kind`**：用户上传的原始来源类型（如 PDF 上传为 `"pdf"`，纯文本上传为 `"text"` 等，与「切块前的业务来源」一致）；**`text_format`**：实际参与分块的正文形态（如 PDF 经转换后按 Markdown 字符串切块为 `"markdown"`，直接上传 TXT 按纯文本切块为 `"plain"` 等）；**`file_name`**：用户上传时的展示文件名（与附件侧展示名一致，如 PDF 流程可与 `PdfBlock.name` / `sanitize_upload_display_name` 结果对齐）；**`source_token_count`**：与「`file_id` 对应、在分块之前」对**全文**的 token 计数。PDF 流程下为 **转换后的 Markdown 全文**（与参与 `MarkdownTextSplitter` 的字符串一致）的 token 数，而非原始 PDF 字节或 `.md` 文件字节数。计数建议使用 [`TokenCalculator`](backend/app/utils/token.py)，`model_name` 与 `settings.embedding_model.model_name` 一致（与 [`context_compactor.py`](backend/app/utils/context_compactor.py) 口径对齐），便于与 embedding / 上下文预算对比；**`original_size_bytes`**：原始上传文件字节数（PDF 流程为 **`.pdf` 文件大小**，与 `save_chat_pdf` 成功时的 `pdf_size` 一致）；**`processed_size_bytes`**：与「分块前」用于索引的文本对应的落盘或处理结果大小（PDF 流程为转换后的 **`.md` 文件字节数**，与 `markdown_size` 一致；纯文本直传场景可与源文件或读入后的 UTF-8 字节数对齐）。同一 `file_id` 下各 chunk 的 `metadata` 中上述字段取值相同，属冗余存储、便于单行检索展示。**可扩展**：页码、章节标题等 |

**索引与约束**

- 复合索引：`(user_id, file_id)`，便于按用户+文件删除/查询。
- **唯一约束**：`(user_id, file_id, chunk_idx)`，防止重复插入。
- 当前需求仅为「入库」；若后续要做相似度检索，可再增加向量索引（如 HNSW），本次可不做以免过度设计。

## 处理流程（接在保存成功之后）

```mermaid
flowchart LR
  savePdf[save_chat_pdf 落盘+转 MD]
  readMd[读取 md_path 文本]
  split[MarkdownTextSplitter 分块]
  embed[EmbeddingService.aembed_documents]
  dbTx[删除旧行后批量插入]
  savePdf --> readMd --> split --> embed --> dbTx
```

1. 在 **`md_path` 存在且可读**、且已得到最终 `content_hash` / `file_id` 之后触发（包括「去重直接返回」分支：此时 MD 已在磁盘上，同样应索引，避免仅新写入才入库）。
2. 读取 Markdown 全文，`strip` 后若为空则**视为失败**（无分块、无向量，与「无向量视为失败」一致），在 `save_chat_pdf` 侧返回错误响应。
3. `MarkdownTextSplitter(chunk_size=settings.kb_file_rag.chunk_size, chunk_overlap=settings.kb_file_rag.chunk_overlap)`，过滤空块，得到 `chunk_idx` 与 `chunk_content`。
4. 调用 `EmbeddingService().aembed_documents(chunks)`；若返回空或长度与块数不一致，**视为失败**，不向 DB 写入半套 chunk，并在 `save_chat_pdf` 中抛 HTTP 异常。
5. **同一事务**：`DELETE` 该 `user_id` + `file_id` 下所有行，再 `INSERT` 新行（全量替换，支持同一用户重复上传、模型维度变更、修复历史失败数据）。

## 代码落点

| 位置 | 工作 |
|------|------|
| 新模型 [`backend/app/models/kb_file_chunk_embedding_db.py`](backend/app/models/kb_file_chunk_embedding_db.py) | SQLModel 类名如 `KbFileChunkEmbeddingDb`，`__tablename__ = "kb_file_chunk_embeddings"`；列含 `created_at`、`metadata`（`JSON`）；`embedding_vector` 使用 `pgvector.sqlalchemy.Vector`，维度常量 **1024** 与迁移一致 |
| [`backend/app/models/__init__.py`](backend/app/models/__init__.py) | `import` 新模型，确保 `create_db_and_tables` 能注册 |
| [`backend/app/schemas/config.py`](backend/app/schemas/config.py) + [`backend/app/core/config.py`](backend/app/core/config.py) | 定义 `KbFileRagConfig` 与 `Settings.kb_file_rag`（见现状与约定） |
| 新服务模块（建议）[`backend/app/services/base_service/kb_file_chunk_embedding_service.py`](backend/app/services/base_service/kb_file_chunk_embedding_service.py) | 通用入口如 `async def index_uploaded_text_chunks(...)`（参数含 `user_id`、`file_id`、文本或 `Path`）：`to_thread` 跑 splitter（**`settings.kb_file_rag`**）、embedding、写入 `metadata`（含 `embedding_model`、`source_kind`、`text_format`、`file_name`、`source_token_count`、`original_size_bytes`、`processed_size_bytes` 等）、DB 事务；`save_chat_pdf` 仅作为首批调用方传入 MD 路径 |
| [`chat_pdf_service.py`](backend/app/services/base_service/chat_pdf_service.py) | 在两处 `return _build_pdf_block(...)` **之前** `await index_...`；**无向量、向量条数不匹配、DB 失败或空全文**时抛 `HTTPException`（如 502），上传接口整体失败（见失败策略） |
| 新 Alembic revision | `down_revision = "v2w3x4y5z6a7"`（当前链头），`CREATE TABLE` + 索引 + 唯一约束 |

**会话管理**：上传 API [`backend/app/api/file.py`](backend/app/api/file.py) 当前未注入 DB；建议在 `kb_file_chunk_embedding_service` 内使用 `Session(engine)` 短事务（与项目其他不经过 `get_db` 的用法兼容），避免为附件上传整条链路增加 `Depends(get_db)`。

## 失败策略（已定）

- **无向量即失败**：`aembed_documents` 返回空、与 chunk 条数不一致、全文 strip 后无可分块内容、或 `kb_file_chunk_embeddings` 写入事务失败时，均在 `save_chat_pdf`（或索引服务向上抛出）中 **`HTTPException`**，上传接口返回错误（建议 **502** 或 **503**，与现有「PDF 转 Markdown 失败」同为 502 时可统一文案）。客户端应视为本次上传未成功。
- **副作用说明**：PDF/Markdown 可能已落盘；不强制回滚磁盘文件（与当前去重/内容哈希命名策略一致），仅接口层失败。可打 `logger.error` 便于排查与后续清理任务。

## 测试建议

- 单元测试或轻量集成：mock `EmbeddingService.aembed_documents` 返回固定维度向量，断言 `DELETE` + `INSERT` 后行数与 chunk 数一致。
- 迁移：`alembic upgrade head` 在本地 Postgres（已启用 `vector` 扩展）上验证。
