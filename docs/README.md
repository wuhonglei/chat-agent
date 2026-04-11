# 项目文档索引

本文档用于统一导航仓库内的业务/设计文档，避免与代码实现脱节。

## 如何使用本索引

- `现网实现`：与当前代码结构和接口保持一致，可直接按文档操作。
- `规划方案`：用于设计讨论，未必已经全部实现。
- `历史文档`：保留背景信息，不作为当前实现依据。

## 根目录文档（`/docs`）

### 现网实现

- `requirements.md`：当前版本需求范围与功能边界
- `认证流程.md`：短信/微信登录与 JWT 鉴权流程
- `会话管理.md`：会话与消息的接口和数据流
- `conversation-management-requirements.md`：会话管理需求（按现网接口整理）
- `图表可视化展示.md`：图表渲染相关说明
- `nginx-cache-analysis.md`：Nginx 缓存分析

### 规划方案

- `messages表字段精简计划.md`：消息表字段优化计划

## 后端文档（`/backend/docs`）

### 现网实现

- `logging_guide.md`：结构化日志使用指南
- `type_checking_guide.md`：类型检查说明
- `用户管理.md`：用户模块说明
- `COMPONENT_TOOLS_PRD.md`：组件工具接入说明（已对齐当前字段）
- `MCP_CONFIG_ANALYSIS.md`：MCP 配置与加载机制说明（按当前 `mcp_client`）
- `RETRIEVAL_SYSTEM.md`：当前检索链路说明（基于 MCP 工具与会话流）

### 规划方案

- `RETRIEVAL_PRD.md`：检索能力 PRD
- `目录结构优化建议.md`：目录结构优化建议

### 历史文档

- `USER_DATA_DIRECTORIES.md`：外部项目目录约定说明（本项目当前未使用）
- `confluence.md`：Confluence 相关历史设计
- `install_postgresql_mac.md` / `install_postgresql_centos.md`：环境安装参考
- `生成非对称密钥.md`：密钥生成脚本说明

## 前端文档（`/frontend/docs`）

### 现网实现

- `conversation.md`：会话路由、流式 `content_blocks`、图片附件上传/预览与排障说明
- `component-tools-implementation.md`：组件工具前端实现
- `schema-generation.md` / `schema-for-backend-usage.md`：组件 schema 生成与后端使用
- `conversion_cache.md`、`scroll-properties-explanation.md`、`aegis-埋点分析.md`

### 历史文档

- `vite-preview-cjs-esm-interop-memory.md`：历史排障记录（命令已按 Vite+ 更新）
- `知识点.md`、`项目依赖与Cursor-Agent-Skills分析.md`：知识沉淀/分析类文档

## 主入口文档

- 根项目说明：`/README.md`
- 后端说明：`/backend/README.md`
- 前端说明：`/frontend/README.md`
