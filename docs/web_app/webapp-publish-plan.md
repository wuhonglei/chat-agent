# Web 建站产物发布（自定义域名访问）

> 目标：Agent 完成 web 建站（产物落到 `outputs`）后，用户可通过 `{slug}.apps.wuhonglei.cn` 访问站点。
> 状态：**第 1–3 期代码已落地**（`#358`–`#366`）。下文「现网实现摘要」以源码为准；其后各节保留设计理由，不再当待办清单。
> 线上 DNS / 通配证书 / NPM 属部署前置，本仓库无法从源码证明证书已签发。

---

## 现网实现摘要

核对：`backend/app/services/site_publish_service.py`、`backend/app/api/sites.py`、`backend/app/mcp/mcp_servers/file_mcp/publish_site.py`、`deploy/sites/nginx.conf`、`frontend/src/pages/ChatPage/components/BlockPreviewPanel/ProjectPreview/`。

### 意图

发布的是 **outputs 快照**，不是会话可写目录。nginx 只认 `data/sites/{slug}/current` 软链：有链就能打开，摘链立刻 404。静态流量不进 backend、不查 Postgres/Redis。

### 发布入口

| 入口 | 路径 / 工具 | slug | source 默认 |
|------|-------------|------|-------------|
| MCP（Agent） | `file_publish_site`（bare `publish_site`） | **禁止传入**；`allow_requested_slug=False` | `/mnt/user-data/outputs/app-dist`；目录不存在则回退 `outputs/`（须有 `index.html`） |
| REST | `POST /api/sites/` | 可传自定义 slug（仅前端）；非法 400、占用 409，**不静默改名** | 同上；前端按树优先 `app-dist`，否则 `outputs` |
| 再发布 | `POST /api/sites/{slug}/republish` | 路径中的 slug | 可改 source / visibility |
| 列表 | `GET /api/sites/me` | — | 当前用户全部站点（含已下线）；**不是** Agent 查重 API |
| 下线 | `DELETE /api/sites/{slug}` | — | 写 `unpublished_at` **并摘 `current`** |

同一 `conversation_id` 一站：已有行（含已下线）则复用 slug、`version+1`。删会话会先 `purge_for_conversation`（摘链 + `rmtree data/sites/{slug}` + 删行），再删 conversation（`conversation_id` 有 FK）。

### source 约束

- 必须落在 `/mnt/user-data/outputs/` 下，经 `PathResolver` 转物理路径；`is_relative_to` 防遍历。
- 目录或 `index.html` / `index.htm` 文件均可；文件会取其父目录。
- 目录内必须有 `index.html`。
- 快照只拷普通文件：跳过 `.` 开头目录/文件，**不跟随符号链接**（避免硬链接污染，也避免链出 outputs）。

### slug 与配额（`SitesConfig` 默认）

- 服务端生成：会话标题 ASCII slugify → 过短 / 保留字则 `site-{nanoid(6)}`；冲突 `{base}-2`…，超长或超过 20 次后缀则再回退 nanoid。
- 合法：`^[a-z0-9-]{3,40}$`。保留字：`www` / `api` / `admin` / `chat` / `static` / `apps` / `mail` / `ftp`。
- `public_base_domain` 默认 `apps.wuhonglei.cn` → URL `https://{slug}.apps.wuhonglei.cn`
- 单站快照 ≤ **50MB**（413）；每用户同时上线 ≤ **20** 站（413，只计 `unpublished_at IS NULL`）
- 默认 TTL **30** 天；再发布会重置 `expires_at`。`expire_interval_seconds` 默认 3600；`0` 关闭。lifespan 里 `run_site_expire_loop` 到期只摘链 + 写 `unpublished_at`，**不删版本目录**。

`visibility` 仅 `unlisted` | `public`。nginx **不读**该字段，两者现网同等可访问；`public` 留给以后的索引策略。`private_signed` **未实现**。

### 静态网关 `sites`

- 镜像：`deploy/sites/`（官方 nginx，无 Python gateway）
- compose：`8080:80`，**只读**挂 `./backend/data/sites`（不要挂整个 `backend/data`）
- `server_name "~^(?<slug>[a-z0-9-]{3,40})\.apps\.wuhonglei\.cn$"`（量词必须加引号；nginx 1.31 会把裸 `{` 当块起始）
- 对不上正则 / 无 Host → `default_server` **404**。探活用 `pidof nginx`，不要要求 HTTP 200。
- `/assets/` 长期缓存且缺失不回退 HTML；`index.html` `no-cache`；其它路径 SPA `try_files`；`.` 开头路径 **404 不是 403**；`.svg` 加 `CSP: default-src 'none'`
- `deploy.sh` 已纳入 `sites`；零停机等 60s，最终健康检查看容器内 `pidof nginx`

### 前端 ProjectPreview

实现：`frontend/src/services/sites.ts`、`ProjectPreview/index.tsx`、`sitePaths.ts`、`htmlPreview.ts`。

- 打开面板时 `GET /api/sites/me`，按 `block.workspaceId`（即 conversation id）匹配。
- 存在 `outputs/app-dist`、`outputs/index.html`、已发布记录、或当前选中可发布路径时，显示「文件 / 运行」与发布工具栏。
- 发布弹窗可填自定义 slug（预览 `https://{slug}.apps.wuhonglei.cn`）；400/409 展示在表单上，不改名。
- 已上线：复制链接、重新发布、下线。运行预览 iframe 走站点公网 URL（`getPublishedHtmlPreviewUrl`），不再做 base64 内联。
- 未发布 HTML：行数 ≥ 50 时默认 `srcDoc` 预览，否则源码。

### 迁移与排障

- 表：`published_sites`（PK `slug`，`conversation_id` UNIQUE）。迁移 `j3k4l5m6n7o8_add_published_sites`。
- 下线后公网仍 200：只改了 DB、没摘 `current`。
- MCP 报 source 不存在：先确认 `outputs/app-dist/index.html` 或 `outputs/index.html` 已落盘，且调用的是 `publish_site` 而不是自己拼域名。
- 超长 Host 命中 default_server：验收时边界内 slug 必须真有 `current`，否则「404」可能只是目录不存在。
- Vercel claimable skill **已删除**（`eede1bac`）。陈旧 mem0 记忆用 `backend/scripts/archive_stale_skill_memories.py`（默认 dry-run）归档；不要改冻结评测集 `eval_set/v1.0/`。

---

## 一、方案起草时的代码事实（历史对照）


| 环节     | 现状                                                                                                                                    | 源码位置                                                                                               |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| 建站流程   | React + TS + Vite + shadcn/ui，`pnpm run build` 后 `cp dist/. → outputs/app-dist/`，再调 `present_files`                                   | `/Users/apple/Desktop/code/chat-agent/backend/skills/public/webapp-building/SKILL.md`              |
| 产物落盘   | `backend/data/user_data/{user_id}/conversations/{conversation_id}/outputs/app-dist/`                                                  | `/Users/apple/Desktop/code/chat-agent/backend/app/vfs/paths.py:60-61`                              |
| 容器可见性  | backend 把 `./backend/data` 挂到 `/app/data`，产物在宿主机 bind mount 上，任意新容器可只读挂载                                                              | `/Users/apple/Desktop/code/chat-agent/docker-compose.yml:45`                                       |
| 会话内预览  | 把 `index.html` 中 `src                                                                                                                 | href="/assets/..."` 正则替换成 base64 data URI 后返回 HTML，前端 iframe 渲染                                    |
| 预览入口候选 | 只有 `workspace/dist/index.html`、`workspace/build/index.html`、`dist/index.html`、`build/index.html`，**不含** `outputs/app-dist/index.html` | `/Users/apple/Desktop/code/chat-agent/backend/app/api/user_data.py:40-45`                          |
| 交付物登记  | `present_files` 只接受 `/mnt/user-data/outputs/` 下已存在的**文件**（目录被拒）                                                                       | `/Users/apple/Desktop/code/chat-agent/backend/app/mcp/mcp_servers/file_mcp/present_files.py:20-38` |
| 前端调用   | `/api/user_data/{user_id}/{conversation_id}/preview-content`、`.../file`、`.../download`                                                | `/Users/apple/Desktop/code/chat-agent/frontend/src/services/workspace.ts:54-101`                   |
| 反向代理   | 生产入口为 openresty（nginx-proxy-manager），`curl -I https://chat.wuhonglei.cn/` 返回 `server: openresty` + `x-served-by: chat.wuhonglei.cn`   | 线上实测                                                                                               |
| 鉴权形态   | **无 Cookie**，前端持 Bearer token（`app/utils/auth_deps.py:40`）                                                                            | 同左                                                                                                 |


现状带来的三个缺口：

1. **只能会话内看，不能给外部链接。** 预览是后端拼 HTML + base64 内联，没有公网 URL。
2. **内联方案本身是残的。** 只重写 `src|href` 且只认 `/assets/` 前缀 —— 引用 `/logo.png`、a 标签跳转、字体、多页站点全部失效。
3. **入口候选漏了 outputs。** 既然交付物在 `outputs/app-dist/`，预览逻辑却只看 `workspace/dist`，属于既存缺口。

---



## 二、关键决策与理由



### 2.1 用子域名，不用路径前缀

Vite 默认 `base='/'`，产物里全是 `/assets/index-xxx.js` 这类绝对路径。挂到 `/p/{slug}/` 下要么在每个站构建时改 `base`（模板 `init-webapp.sh` 得加参数、且每站不同），要么在 nginx 做一遍 rewrite。子域名天然从根路径提供服务，产物零改动。
技术依据而不是审美偏好 —— 这是选子域名的核心原因。

### 2.2 发布的是快照，不是 outputs 目录

`outputs/` 是同会话可写区，Agent 下一轮 debug 就会覆盖。发布要求不可变：

```
backend/data/sites/{slug}/{version}/        # 每次发布新建目录
backend/data/sites/{slug}/current -> 1/     # 原子切换（ln -sfn）
```

**不要用** `cp -al` **硬链接做快照**：Agent 用 write_file 截断写同一 inode 时会把"已发布版本"一起改掉。用 `cp -r`（或 reflink，注意 ext4 不支持）。

### 2.3 文件服务不放进 backend，也不再套一层 gateway

FastAPI 的 `StaticFiles` 没有 `sendfile`/gzip/range 优势，且把用户站点流量引到主 API 容器上放大风险。用户 HTML 也不要进现有 `frontend` nginx（那是 `chat.wuhonglei.cn` 的 server）。

默认可见性是 `unlisted`（知道 URL 就能打开）。发布已切 `current` 软链，下线摘掉这条链。对这种站点，**「注册表里有没有」≈「`data/sites/{slug}/current` 在不在」**，每请求再查 DB/Redis 只是多一跳。`X-Accel-Redirect` 的价值是「应用先鉴权、内核再 sendfile」；应用若只确认目录存在，鉴权这步可以省掉。

因此第 1 / 2 期只要一个 **纯 nginx 容器** `sites`：

```
NPM（TLS，Host 保留）
    → sites nginx
         server_name 正则抽出 slug
         root /app/data/sites/$slug/current
         try_files SPA 回退；sendfile + gzip 吐字节
```

不要把 root 直接配进 NPM GUI：配置不进 git，还要把 `data/sites` 挂进 NPM 容器。`private_signed` HMAC 以后用 nginx `auth_request` 打 backend 一个小接口，仍不必单独起 Python gateway。



### 2.4 发布域与聊天域隔离

`{slug}.apps.wuhonglei.cn` 与 `chat.wuhonglei.cn` 属同一 registrable domain（同 site）。当前无 Cookie、鉴权走 Bearer，跨 origin 读不到 localStorage，CSRF 也不成立，所以风险低。但一旦将来加 Cookie 鉴权（尤其是域级 `.wuhonglei.cn`），用户上传的 HTML 就能带着 Cookie 打 `/api`。
结论：承诺「永不用 Cookie 鉴权」可以同域；要更干净就换独立 registrable domain（如 `wuhonglei-apps.com`），这是 GitHub Pages / Claude Artifacts 的做法。**默认走同域子域，独立域作为可选项。**

### 2.5 slug 由服务端生成，不让模型填

公开 URL 一旦进 DNS，就不该依赖模型即兴起名。把字符集、保留字、`GET /api/sites/me` 写进 skill 防不住幻觉，而且这条查重路径本身是错的：

- Agent 只有 MCP 工具，调不到 REST `/api/sites/me`。
- `/me` 只返回当前用户站点，`slug` 却是全站主键，看不到别人的占用。
- 409 会再烧掉一轮工具调用，模型改名后仍可能撞车或踩保留字。

稳定身份是 `(user_id, conversation_id)`，不是 DNS label。因此：

- **MCP** `publish_site` **入参不含** `slug`（schema 层硬约束；可选字段模型仍会编）。
- **同一 conversation 复用已有 slug**，重复发布只升 `version`。
- **新站由服务端生成并在事务内保证全局唯一**；冲突时内部加后缀，不把 409 抛给模型。
- **自定义 slug 只走 REST**，给第 3 期前端「自定义链接」；用户在对话里口头指定域名作为后续增强，第 2 期不做。

---



## 三、总体架构

```
                    *.apps.wuhonglei.cn
                            │  DNS 泛解析
                            ▼
              NPM / openresty（通配 server_name + 通配证书）
                            │  proxy_pass（Host 保留）
                            ▼
                    sites:8080（纯 nginx，无 gateway）
        ┌─────────────────────────────────────────────┐
        │ 1. server_name 正则 → slug（非法 Host → 404） │
        │ 2. root = /app/data/sites/$slug/current     │
        │ 3. try_files SPA 回退；无 current → 404      │
        │ 4. sendfile + gzip 吐字节                    │
        └─────────────────────────────────────────────┘
                        ▲
                        │ 只读挂载（仅 sites，不挂 user_data）
        backend/data/sites/{slug}/current -> {version}/
                        ▲
                        │ 复制 + ln -sfn
        backend/data/user_data/{uid}/conversations/{cid}/outputs/app-dist/
```

对外是否可访问由 **`current` 软链** 表达，不经过 backend、不查 Redis。每个页面的静态请求因此不打 Postgres。

发布触发链：

```
Agent: pnpm build → cp dist/. outputs/app-dist/
     → publish_site（source + visibility，无 slug）
     → 校验 outputs 路径
     → 解析 slug：本 conversation 已有站点则复用，否则服务端生成并保证全局唯一
     → cp -r 快照到 data/sites/{slug}/{v}/
     → 写 published_sites 行 → ln -sfn 切 current
     → 返回 https://{slug}.apps.wuhonglei.cn
```

下线：写 `unpublished_at` **并摘掉 `current`**，nginx 立刻 404（不必等缓存 TTL）。版本目录可留着便于回滚，由 TTL/配额任务稍后清。

---



## 四、数据模型与接口契约



### 4.1 新表 `published_sites`

模型文件：`/Users/apple/Desktop/code/chat-agent/backend/app/models/published_site.py`
迁移：`/Users/apple/Desktop/code/chat-agent/backend/alembic/versions/{rev}_add_published_sites.py`（命名沿用现有风格）

```sql
slug            varchar(64)  PRIMARY KEY      -- DNS label 合法字符：小写字母/数字/连字符
user_id         varchar(36)  NOT NULL
conversation_id varchar(36)  NOT NULL UNIQUE  -- 一会话一站；重复发布升 version，不换 slug
message_id      varchar(36)  NULL              -- 溯源：哪条消息触发的发布
site_root       text         NOT NULL          -- 快照绝对路径，服务端生成，永不接受用户输入
version         int          NOT NULL DEFAULT 1
entry           varchar(128) NOT NULL DEFAULT 'index.html'
visibility      varchar(16)  NOT NULL DEFAULT 'unlisted'   -- public|unlisted|private_signed
size_bytes      bigint       NOT NULL DEFAULT 0
expires_at      timestamptz  NULL
created_at      timestamptz  NOT NULL
updated_at      timestamptz  NOT NULL
unpublished_at  timestamptz  NULL
```

`site_root` 由发布服务根据 slug 生成，**永不接受调用方传入的路径**（防止发布接口把快照写到 `user_data/`）。公网读取不走这列：nginx 只认 `data/sites/{slug}/current`，关口是 **Host 正则 + 独立 root**。
下线写 `unpublished_at` 并摘掉 `current`；再发布仍复用该行的 slug，URL 保持稳定。

### 4.2 API（`/api/sites`）

新增路由文件：`/Users/apple/Desktop/code/chat-agent/backend/app/api/sites.py`，在 `/Users/apple/Desktop/code/chat-agent/backend/app/main.py:149` 附近注册（`prefix="/api/sites"`）。


| 方法     | 路径                            | 说明                                                                                                                                                              |
| ------ | ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| POST   | `/api/sites`                  | 发布：`{conversation_id, source: "/mnt/user-data/outputs/app-dist", slug?, visibility?}`。`slug` 仅前端自定义链接时传入；省略则服务端生成。本 conversation 已有站点时忽略传入 slug，复用原值并 republish |
| POST   | `/api/sites/{slug}/republish` | 重新发布（version+1，切 current）                                                                                                                                       |
| GET    | `/api/sites/me`               | 当前用户站点列表（给前端展示，**不是** Agent 查重入口）                                                                                                                               |
| DELETE | `/api/sites/{slug}`           | 下线（写 `unpublished_at` + 摘掉 `current` 软链，nginx 立刻 404）                                                                                                           |


请求/响应示例（发布）：

```json
// POST /api/sites（Agent / 默认：不传 slug）
{"conversation_id": "2c004935-9cfb-4889-9df1-c2ebd8e1b52b",
 "source": "/mnt/user-data/outputs/app-dist",
 "visibility": "unlisted"}

// POST /api/sites（第 3 期前端自定义链接）
{"conversation_id": "2c004935-9cfb-4889-9df1-c2ebd8e1b52b",
 "source": "/mnt/user-data/outputs/app-dist",
 "slug": "resume-site",
 "visibility": "unlisted"}

// 200
{"code": 0, "msg": "发布成功",
 "data": {"slug": "resume-site", "version": 1, "url": "https://resume-site.apps.wuhonglei.cn",
          "visibility": "unlisted", "size_bytes": 1048576, "expires_at": null}}
```

错误：调用方传入的 slug 非法 → 400；传入 slug 被其他站点占用 → 409（不自动改名，避免用户拿到非所要的 URL）；source 不存在或非 outputs 下 → 400；超配额 → 413。服务端自动生成路径遇占用则内部加后缀，不返回 409。

### 4.3 发布 MCP 工具 `publish_site`

位置：`/Users/apple/Desktop/code/chat-agent/backend/app/mcp/mcp_servers/file_mcp/publish_site.py`（按 `present_files.py` 的 `ToolBase` 写法），在 `file_mcp/server.py` 注册。

```json
// 入参（无 slug）
{"source": "/mnt/user-data/outputs/app-dist", "visibility": "unlisted"}

// 返回（ToolResult.structured_content）
{"slug": "resume-site", "version": 1, "url": "https://resume-site.apps.wuhonglei.cn",
 "entry": "index.html", "file_count": 14, "size_bytes": 1048576}
```

用显式工具而不是「present_files 时自动发布」：发布产生公开资源，要让 LLM 显式调用并向用户报 URL，避免用户没要求就把产物挂上公网。
工具描述写清：不要猜测或传入 slug；把返回的 `url` 原样告知用户，不要自行拼接域名。

### 4.4 slug 生成规则（只在服务端）

实现位置：`site_publish_service.py`，不写进 skill。

1. 本 `conversation_id` 已有行（含已下线）→ 复用其 `slug`，走 republish / 重新上线。
2. 否则用会话标题 slugify：小写 ASCII、数字、连字符，压缩连续 `-`，截断到 3–40 字符。
3. 标题为空、纯中文/非 ASCII 导致结果过短、或命中保留字 → 回退 `site-{nanoid(6)}`。
4. 保留字（不可作 DNS label）：`www` / `api` / `admin` / `chat` / `static` / `apps` / `mail` / `ftp`。
5. 与已有主键冲突：`{base}-2`、`{base}-3`…；加后缀后仍冲突或超长则改用 `site-{nanoid(6)}`。查重与插入在同一事务内完成，避免 TOCTOU。

---



## 五、发布链路改动清单

1. `webapp-building` **skill 加 Step C**
  `/Users/apple/Desktop/code/chat-agent/backend/skills/public/webapp-building/SKILL.md`
   在 Step B（`present_files`）之后补行为约定，**不写 DNS/slug 手册**：
  - 仅当用户明确要求公开访问 / 外部分享时调用 `publish_site`（`source` 固定为 `/mnt/user-data/outputs/app-dist`）。
  - 不要传 `slug`，不要调用 `/api/sites/me`，不要自行拼接 `{slug}.apps.wuhonglei.cn`。
  - 把工具返回的 `url` 原样告诉用户；不要为了换 slug 重试。
2. **后端服务** `backend/app/services/site_publish_service.py`
  - 路径校验：复用 `present_files.py:20-38` 的「虚拟路径前缀 + `resolve_virtual_path`」套路，只接受 `/mnt/user-data/outputs/` 下已存在目录。
  - slug：按 4.4 生成或复用；MCP 路径永不读调用方传入的 slug。
  - 快照：`cp -r` 到 `data/sites/{slug}/{version}/`，随后 `ln -sfn` 切 current（nginx 只读这条软链）。
  - 事务与幂等：先落目录再写库；同一 conversation 重复发布走 republish（version+1），保留旧版本便于回滚。
  - 下线必须摘 `current`，不能只改 DB（否则 nginx 仍会对外服务）。
3. **前端（第 3 期）**
  - `/Users/apple/Desktop/code/chat-agent/frontend/src/pages/ChatPage/components/BlockPreviewPanel/ProjectPreview/index.tsx` 加「发布 / 复制链接 / 下线」入口，调用风格对齐 `frontend/src/services/workspace.ts`。
  - 发布表单可让用户填写自定义 slug，走 `POST /api/sites` 的 `slug?`；非法或被占时展示 400/409，**不要**静默改名。
  - 预览改走 `iframe src=https://{slug}.apps.wuhonglei.cn/`，替换 base64 内联路径。
  - 顺带修 `/Users/apple/Desktop/code/chat-agent/backend/app/api/user_data.py:40-45`，把 `outputs/app-dist/index.html` 加入预览入口候选。

---



## 六、服务层落地



### 6.1 新容器 `sites`（纯 nginx，无 gateway.py）

目录：`/Users/apple/Desktop/code/chat-agent/deploy/sites/`（`Dockerfile`、`nginx.conf`）

官方 `nginx:alpine` 即可，不要再放 FastAPI/Go。职责：

- `default_server` 对不上正则的 Host 一律 404，绝不 fallback 到某个站。
- `server_name ~^(?<slug>[a-z0-9-]{3,40})\.apps\.wuhonglei\.cn$;`
- `root /app/data/sites/$slug/current;`（软链不存在 → 404）
- `try_files $uri $uri/ /index.html;`（SPA 刷新不 404）
- `sendfile on; gzip on; autoindex off;`
- `/assets/`（Vite hash）→ `Cache-Control: public, max-age=31536000, immutable`；`index.html` → `no-cache`
- 拒绝 `.` 开头路径（**返回 404 而不是 403**：403 等于确认文件存在，对外网关统一用 404 不暴露存在性）；`.svg` 单独加 `Content-Security-Policy: default-src 'none'`

体积挂载 **只挂 `backend/data/sites`**，不要挂整个 `backend/data`（里面有 `user_data`）。

`/Users/apple/Desktop/code/chat-agent/docker-compose.yml` 新增：

```yaml
sites:
  build:
    context: ./deploy/sites
    dockerfile: Dockerfile
  container_name: chat-agent-sites
  # NPM 在另一台机器（10.0.0.6），必须把端口发布到宿主机；容器内仍是 80。
  # 宿主机安全组需放行「TCP 8080 / 来源 10.0.0.6」——未放行时是静默丢包，
  # NPM 侧表现为请求挂死而不是 502（实测踩过）。
  ports:
    - "8080:80"
  volumes:
    - ./backend/data/sites:/app/data/sites:ro
  networks:
    - chat-agent-network
  restart: unless-stopped
  healthcheck:
    test: ["CMD-SHELL", "pidof nginx || exit 1"]
    interval: 15s
    timeout: 3s
    retries: 3
```

无 Host 的探活会打到 `default_server`（404），不要用「必须 200」的 HTTP check。同时把 `sites` 纳入 `/Users/apple/Desktop/code/chat-agent/deploy.sh` 的服务范围与健康检查（脚本按服务名分范围，漏了会部署不到）。

不要把这层配进 NPM Advanced 当静态 root，也不要复用 `frontend/nginx.conf`。

### 6.2 DNS + TLS + NPM

1. **DNS**：DNSPod（`NS` 为 `bread/rabbit.dnspod.net`）加 `*.apps` A 记录指向服务器。DNSPod 支持泛解析。
2. **证书**：Let's Encrypt 泛域名必须 DNS-01 验证，DNSPod 需要 API Token。两种可行路径：
  - 宿主机 `acme.sh` + `dns_dp` 签发 `*.apps.wuhonglei.cn`，导入 NPM；
  - NPM 的 DNS challenge 插件（需自备 DNSPod 校验脚本）。
3. **NPM**：新建 Proxy Host
  - Domain：`*.apps.wuhonglei.cn`
  - Forward：`sites:8080`
  - 启用 HSTS；Advanced 追加 `add_header X-Robots-Tag noindex;`
  - 可选：`Content-Security-Policy: sandbox allow-scripts allow-same-origin allow-forms`（会让页面成 opaque origin，站内 localStorage 失效，先不开）

---



## 七、安全与治理


| 项     | 要求                                                                      |
| ----- | ----------------------------------------------------------------------- |
| 跨用户越权 | nginx 只挂 `data/sites`；slug 由 `^[a-z0-9-]{3,40}$` 捕获，对不上直接 404。发布接口的 `site_root` 仍由服务端生成，不接受调用方路径 |
| 目录遍历  | `root` 钉在 `/app/data/sites/$slug/current`；拒绝 `.` 开头文件（404，非 403）；`autoindex off`   |
| 隔离    | 用户 HTML 与聊天域同 site，故**永不用 Cookie 鉴权**；如需 Cookie，改用独立 registrable domain。站点流量不进 backend、不进 frontend nginx |
| 内容类型  | `Content-Type` 只按扩展名推断，不信用户；`.svg` 单独加 `CSP: default-src 'none'`        |
| 私密站   | 第 1 / 2 期不做。以后 `private_signed` 用 HMAC 签名 URL（`?k=HMAC(slug,exp)`）+ nginx `auth_request` 打 backend，仍不必单独 gateway |
| 下线    | 必须摘 `current`；只写 `unpublished_at` 的话 nginx 会继续提供服务                     |
| 资源治理  | 单用户站数上限、单站体积上限、默认 TTL（如 30 天，可续期）、一键下线、`noindex`                        |
| 滥用    | 用户内容挂自有域名存在钓鱼/品牌风险，上线即带 TTL + 下线接口 + 巡查手段                               |


---



## 八、分期与验收



### 第 1 期：链路先通

- [x] `deploy/sites/` 纯 nginx 容器 + compose `sites:8080` + `deploy.sh` 健康检查（`pidof nginx`）
- [ ] DNSPod 泛解析 + 通配证书 + NPM Proxy Host（**线上前置，不在本仓库**；部署后需 `curl -I` 校验证书链）

### 第 2 期：发布闭环

- [x] `published_sites` 表 + 迁移 `j3k4l5m6n7o8` + `/api/sites` 四个接口
- [x] `publish_site` MCP（schema **无** `slug`）+ `webapp-building` Step C
- [x] slug 服务端生成 / 保留字 / 冲突加后缀；删会话同步 purge
- [x] 单页 HTML：`source` 可为 `outputs` 或 `outputs/index.html`，缺省 `app-dist` 不存在时回退

### 第 3 期：前端体验

- [x] ProjectPreview 发布 / 复制 / 下线；自定义 slug 走 REST，409 明示
- [x] 已发布站点 iframe 直连公网 URL（不再 base64 内联）
- [x] 会话预览改为文件系统扫描（`user_data.py` 不再维护硬编码入口候选列表）

---



## 九、坑清单（按踩中概率排序）

1. **软链切换非原子**：必须新版本目录写完后 `ln -sfn`，否则中间态 404。
2. **只挂 `data/sites`，不要挂整个 `backend/data`**：`user_data` 路径含 `user_id`，Host 解析一旦写错就是跨用户泄露。nginx `root` 钉在 `$slug/current`。
3. **不要把站点静态配进 `frontend/nginx.conf` 或 NPM Advanced**：前者和聊天域混 server，后者配置不进 git。
4. **下线必须摘 `current`**：只写 `unpublished_at` 时 nginx 仍会对外服务，没有 Redis TTL 可等。
5. **硬链接快照会被就地改写**（见 2.2），会静默污染"已发布版本"。
6. **通配证书签发失败时 NPM 回落到自签**，浏览器告警。部署后必须 `curl -I` 校验证书链。
7. **SPA 刷新 404**：无扩展名且文件不存在时回退 entry，返回 200 而不是 404。
8. `.svg` **内嵌 XSS**：单独设 `CSP: default-src 'none'`。
9. **Content-Type 靠扩展名**，别信用户声明的类型。
10. **deploy.sh 服务范围**：新容器不加进脚本，部署时会漏。
11. **快照与 outputs 双份占用磁盘**：`size_bytes` 入表，配额按快照计；下线时同时清理目录。
12. **不要把 slug 规则写进 SKILL.md**，也不要给 MCP 工具加可选 `slug` 字段——模型会填。查重、保留字、加后缀全部留在服务端。
13. `GET /api/sites/me` **不能当冲突检查**：只含当前用户站点，防不了全局主键冲突，且 Agent 调不到这条 REST。
14. **nginx `server_name` 正则里的量词必须加引号**：`{3,40}` 裸写会被配置解析器当成块起始符而报语法错误，正确写法是 `server_name "~^(?<slug>[a-z0-9-]{3,40})\.apps\.wuhonglei\.cn$";`。改用字符展开（`[a-z0-9][a-z0-9-][a-z0-9-]*`）会**悄悄丢掉上界**（下界也变成 2），且验收时「超长 slug 404」会被「目录不存在」掩盖成假通过——要证明边界必须让边界内的 slug 有真实站点目录、断言 200。
15. **nginx 会先把 Host 转小写再匹配 `server_name`**：大写域名会命中，`AB.apps…` 不是「非法 Host」。真正非法的用例是含 `_` / `.` / `-` 开头这类，断言 404。

---



## 十、待决项


| #   | 问题          | 选项                                                      | 倾向                            |
| --- | ----------- | ------------------------------------------------------- | ----------------------------- |
| 1   | 发布域         | `*.apps.wuhonglei.cn`（省事） / 独立 registrable domain（隔离干净） | 先用子域，Cookie 方案出现前不换           |
| 2   | 默认可见性       | `public` / `unlisted`                                   | `unlisted`（不 index，URL 已知可访问） |
| 3   | 治理策略        | 永久公开 / TTL + 配额                                         | 至少要有 TTL 与一键下线                |
| 4   | 对话内自定义 slug | 第 2 期 MCP 不接收 / 第 3 期仅前端 REST / 以后 MCP 可选覆盖             | 第 2 期不接收；自定义名只走前端             |
| 5   | 私密站          | 不做 / nginx `auth_request` + HMAC / 独立 gateway                 | 第 1 / 2 期不做；需要时用 `auth_request`  |


---



## 附录 A：相关既有变更

- `backend/skills/public/vercel-deploy-claimable` **已删除**（commit `eede1bac`，删除前内容可用 `git show eede1bac^:backend/skills/public/vercel-deploy-claimable/scripts/deploy.sh` 查）。
理由：上游 claimable deploy 接口已废弃（`POST https://claude-skills-deploy.vercel.com/api/deploy` 现返回「请改用 Vercel CLI」的说明，不再返回 `previewUrl`），脚本在删除前 `deploy.sh:232` 处 `grep -o '"previewUrl":"[^"]*"'` 必然取空并 `exit 1`（第 236 行）；且 `SKILL.md:23` 指向的 `/mnt/skills/custom/vercel-deploy/scripts/deploy.sh` 与实际位置（`skills/public/vercel-deploy-claimable/`）不符，照文档执行必然 No such file。
能力缺口：Vercel 能托管需要服务端运行时的应用（Next.js SSR、API routes），本方案只托管静态产物。当前 skill 模板产出为 Vite SPA 静态站，主链路不受影响；若将来要交付 SSR/带后端应用，需另设运行时档位。
- **mem0 线上库仍有断言该 skill 存在的记忆**，会在「网页设计 skill 推荐」类提问时被召回。清理脚本：`/Users/apple/Desktop/code/chat-agent/backend/scripts/archive_stale_skill_memories.py`（默认 dry-run）。
- **评测语料** `backend/data/eval_set/v1.0/` **保持不变**：`eval_samples*.json` 是历史 trace 快照，`answer` 字段挂着裁判对原文的评分，`memories[].memory` 是当时 mem0 的返回原文；回改会让分数与文本脱钩，且 `calibration_report.json` 表明 v1.0 是冻结基线。需要干净语料应切 v1.1 重采样。



## 附录 B：源码索引

- 产物路径解析：`/Users/apple/Desktop/code/chat-agent/backend/app/vfs/paths.py`
- 虚拟路径权限：`/Users/apple/Desktop/code/chat-agent/backend/app/vfs/resolver.py`
- 会话内预览（含 base64 内联）：`/Users/apple/Desktop/code/chat-agent/backend/app/api/user_data.py`
- 交付物登记：`/Users/apple/Desktop/code/chat-agent/backend/app/mcp/mcp_servers/file_mcp/present_files.py`
- 前端容器内 nginx（`/api` 反代规则）：`/Users/apple/Desktop/code/chat-agent/frontend/nginx.conf`
- 站点静态出口：`deploy/sites/`（`Dockerfile`、`nginx.conf`）
- 发布服务 / REST / MCP：`backend/app/services/site_publish_service.py`、`backend/app/api/sites.py`、`backend/app/mcp/mcp_servers/file_mcp/publish_site.py`
- 过期巡检：`backend/app/services/site_expire_loop.py`（`app/main.py` lifespan）
- 前端：`frontend/src/services/sites.ts`、`frontend/src/pages/ChatPage/components/BlockPreviewPanel/ProjectPreview/`
- 编排与部署：`/Users/apple/Desktop/code/chat-agent/docker-compose.yml`、`/Users/apple/Desktop/code/chat-agent/deploy.sh`
- VFS 与沙箱运维手册：`/Users/apple/Desktop/code/chat-agent/backend/docs/VFS_AND_SANDBOX.md`

