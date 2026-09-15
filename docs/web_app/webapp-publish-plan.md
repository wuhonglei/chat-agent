# Web 建站产物发布方案（自定义域名访问）

> 目标：Agent 完成 web 建站（build 产物落到 outputs 目录）后，用户可通过自定义域名（子域名优先）访问站点。
> 状态：方案评审完成，尚未实施。落地分 3 期，第 1 期不触碰后端代码。

---

## 一、现状（代码级事实）

| 环节 | 现状 | 源码位置 |
|------|------|----------|
| 建站流程 | React + TS + Vite + shadcn/ui，`pnpm run build` 后 `cp dist/. → outputs/app-dist/`，再调 `present_files` | `/Users/apple/Desktop/code/chat-agent/backend/skills/public/webapp-building/SKILL.md` |
| 产物落盘 | `backend/data/user_data/{user_id}/conversations/{conversation_id}/outputs/app-dist/` | `/Users/apple/Desktop/code/chat-agent/backend/app/vfs/paths.py:60-61` |
| 容器可见性 | backend 把 `./backend/data` 挂到 `/app/data`，产物在宿主机 bind mount 上，任意新容器可只读挂载 | `/Users/apple/Desktop/code/chat-agent/docker-compose.yml:45` |
| 会话内预览 | 把 `index.html` 中 `src|href="/assets/..."` 正则替换成 base64 data URI 后返回 HTML，前端 iframe 渲染 | `/Users/apple/Desktop/code/chat-agent/backend/app/api/user_data.py:126-153` |
| 预览入口候选 | 只有 `workspace/dist/index.html`、`workspace/build/index.html`、`dist/index.html`、`build/index.html`，**不含 `outputs/app-dist/index.html`** | `/Users/apple/Desktop/code/chat-agent/backend/app/api/user_data.py:40-45` |
| 交付物登记 | `present_files` 只接受 `/mnt/user-data/outputs/` 下已存在的**文件**（目录被拒） | `/Users/apple/Desktop/code/chat-agent/backend/app/mcp/mcp_servers/file_mcp/present_files.py:20-38` |
| 前端调用 | `/api/user_data/{user_id}/{conversation_id}/preview-content`、`.../file`、`.../download` | `/Users/apple/Desktop/code/chat-agent/frontend/src/services/workspace.ts:54-101` |
| 反向代理 | 生产入口为 openresty（nginx-proxy-manager），`curl -I https://chat.wuhonglei.cn/` 返回 `server: openresty` + `x-served-by: chat.wuhonglei.cn` | 线上实测 |
| 鉴权形态 | **无 Cookie**，前端持 Bearer token（`app/utils/auth_deps.py:40`） | 同左 |

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

**不要用 `cp -al` 硬链接做快照**：Agent 用 write_file 截断写同一 inode 时会把"已发布版本"一起改掉。用 `cp -r`（或 reflink，注意 ext4 不支持）。

### 2.3 文件服务不放进 backend

FastAPI 的 `StaticFiles` 没有 `sendfile`/gzip/range 优势，且把用户站点流量引到主 API 容器上放大风险。采用 nginx 官方推荐的「应用决定、内核发送」模式：

```
sites-gateway（小服务，只解析 + 鉴权）
    → 返回 X-Accel-Redirect: /__sites/{slug}/{version}/...
nginx 内部 location → alias 到 backend/data/sites（read-only）→ sendfile 吐字节
```

### 2.4 发布域与聊天域隔离

`{slug}.apps.wuhonglei.cn` 与 `chat.wuhonglei.cn` 属同一 registrable domain（同 site）。当前无 Cookie、鉴权走 Bearer，跨 origin 读不到 localStorage，CSRF 也不成立，所以风险低。但一旦将来加 Cookie 鉴权（尤其是域级 `.wuhonglei.cn`），用户上传的 HTML 就能带着 Cookie 打 `/api`。
结论：承诺「永不用 Cookie 鉴权」可以同域；要更干净就换独立 registrable domain（如 `wuhonglei-apps.com`），这是 GitHub Pages / Claude Artifacts 的做法。**默认走同域子域，独立域作为可选项。**

---

## 三、总体架构

```
                    *.apps.wuhonglei.cn
                            │  DNS 泛解析
                            ▼
              NPM / openresty（通配 server_name + 通配证书）
                            │  proxy_pass（Host 保留）
                            ▼
                    sites-gateway:8080
        ┌─────────────────────────────────────────────┐
        │ 1. Host → slug（去后缀）                    │
        │ 2. Redis/DB 查注册表（TTL 60s）             │
        │ 3. 可见性校验（public / unlisted / signed） │
        │ 4. 定位文件；SPA 路由回退 entry             │
        │ 5. 返回 X-Accel-Redirect（不吐字节）        │
        └───────────────┬─────────────────────────────┘
                        │ 内部 location /__sites/
                        ▼
              nginx（含于同一容器）
              root: /app/data/sites（ro，sendfile+gzip）
                        ▲
                        │ 只读挂载
        backend/data/sites/{slug}/{version}/  ← 发布时快照
                        ▲
                        │ 复制
        backend/data/user_data/{uid}/conversations/{cid}/outputs/app-dist/
```

发布触发链：

```
Agent: pnpm build → cp dist/. outputs/app-dist/
     → publish_site（新 MCP 工具）
     → 校验 outputs 路径 → cp -r 快照到 data/sites/{slug}/{v}/
     → 写 published_sites 行 → 切 current 软链 → 失效 Redis
     → 返回 https://{slug}.apps.wuhonglei.cn
```

---

## 四、数据模型与接口契约

### 4.1 新表 `published_sites`

模型文件：`/Users/apple/Desktop/code/chat-agent/backend/app/models/published_site.py`
迁移：`/Users/apple/Desktop/code/chat-agent/backend/alembic/versions/{rev}_add_published_sites.py`（命名沿用现有风格）

```sql
slug            varchar(64)  PRIMARY KEY      -- DNS label 合法字符：小写字母/数字/连字符
user_id         varchar(36)  NOT NULL
conversation_id varchar(36)  NOT NULL
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

**`site_root` 必须由服务端从 slug 查表得到，绝不接受调用方传入的路径** —— 这是防跨用户越权的唯一关口。

### 4.2 API（`/api/sites`）

新增路由文件：`/Users/apple/Desktop/code/chat-agent/backend/app/api/sites.py`，在 `/Users/apple/Desktop/code/chat-agent/backend/app/main.py:149` 附近注册（`prefix="/api/sites"`）。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sites` | 发布：`{conversation_id, source: "/mnt/user-data/outputs/app-dist", slug?, visibility?}` |
| POST | `/api/sites/{slug}/republish` | 重新发布（version+1，切 current） |
| GET | `/api/sites/me` | 当前用户站点列表 |
| DELETE | `/api/sites/{slug}` | 下线（写 `unpublished_at` + 失效缓存） |

请求/响应示例（发布）：

```json
// POST /api/sites
{"conversation_id": "2c004935-9cfb-4889-9df1-c2ebd8e1b52b",
 "source": "/mnt/user-data/outputs/app-dist",
 "slug": "resume-site",
 "visibility": "unlisted"}

// 200
{"code": 0, "msg": "发布成功",
 "data": {"slug": "resume-site", "version": 3, "url": "https://resume-site.apps.wuhonglei.cn",
          "visibility": "unlisted", "size_bytes": 1048576, "expires_at": null}}
```

错误：slug 非法 → 400；slug 被占 → 409；source 不存在或非 outputs 下 → 400；超配额 → 413。

### 4.3 发布 MCP 工具 `publish_site`

位置：`/Users/apple/Desktop/code/chat-agent/backend/app/mcp/mcp_servers/file_mcp/publish_site.py`（按 `present_files.py` 的 `ToolBase` 写法），在 `file_mcp/server.py` 注册。

```json
// 入参
{"source": "/mnt/user-data/outputs/app-dist", "slug": "resume-site", "visibility": "unlisted"}

// 返回（ToolResult.structured_content）
{"slug": "resume-site", "version": 3, "url": "https://resume-site.apps.wuhonglei.cn",
 "entry": "index.html", "file_count": 14, "size_bytes": 1048576}
```

用显式工具而不是「present_files 时自动发布」：发布产生公开资源，要让 LLM 显式调用并向用户报 URL，避免用户没要求就把产物挂上公网。

---

## 五、发布链路改动清单

1. **`webapp-building` skill 加 Step C**
   `/Users/apple/Desktop/code/chat-agent/backend/skills/public/webapp-building/SKILL.md`
   在 Step B（present_files）之后补：调 `publish_site`，并写清 slug 规则（小写字母/数字/连字符，3-40 字符；保留字 `www`/`api`/`admin`/`chat`/`static`；先查 `GET /api/sites/me` 避免冲突）。

2. **后端服务** `backend/app/services/site_publish_service.py`
   - 路径校验：复用 `present_files.py:20-38` 的「虚拟路径前缀 + `resolve_virtual_path`」套路，只接受 `/mnt/user-data/outputs/` 下已存在目录。
   - 快照：`cp -r` 到 `data/sites/{slug}/{version}/`，随后 `ln -sfn` 切 current。
   - 事务与幂等：先落目录再写库；同一 conversation 重复发布走 republish（version+1），保留旧版本便于回滚。

3. **前端（第 3 期）**
   - `/Users/apple/Desktop/code/chat-agent/frontend/src/pages/ChatPage/components/BlockPreviewPanel/ProjectPreview/index.tsx` 加「发布 / 复制链接 / 下线」入口，调用风格对齐 `frontend/src/services/workspace.ts`。
   - 预览改走 `iframe src=https://{slug}.apps.wuhonglei.cn/`，替换 base64 内联路径。
   - 顺带修 `/Users/apple/Desktop/code/chat-agent/backend/app/api/user_data.py:40-45`，把 `outputs/app-dist/index.html` 加入预览入口候选。

---

## 六、服务层落地

### 6.1 新容器 `sites`

目录：`/Users/apple/Desktop/code/chat-agent/deploy/sites/`（`Dockerfile`、`gateway.py`、`nginx.conf`、`entrypoint.sh`）

- 约 100-150 行 FastAPI（或 Go），职责只有 5 步：解析 Host → 查注册表 → 可见性校验 → 定位文件/SPA 回退 → 返回 `X-Accel-Redirect`。
- 内部 nginx：`location ^~ /__sites/ { internal; alias /app/data/sites/; }`，配 `sendfile on; gzip on;`。
- 缓存头：`/assets/*`（带 hash）→ `Cache-Control: public, max-age=31536000, immutable`；`index.html` → `no-cache`。
- 未命中 → 404 定制页；`autoindex off`；拒绝 `.` 开头文件的访问。

`/Users/apple/Desktop/code/chat-agent/docker-compose.yml` 新增：

```yaml
sites:
  build:
    context: ./deploy/sites
    dockerfile: Dockerfile
  container_name: chat-agent-sites
  volumes:
    - ./backend/data:/app/data:ro
  networks:
    - chat-agent-network
  restart: unless-stopped
  # 不对外暴露端口，仅由 NPM 经内网访问
```

同时把 `sites` 纳入 `/Users/apple/Desktop/code/chat-agent/deploy.sh` 的服务范围与健康检查（脚本按服务名分范围，漏了会部署不到）。

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

| 项 | 要求 |
|----|------|
| 跨用户越权 | `site_root` 只从库取；Host 解析失败直接 404，绝不拼用户输入成路径 |
| 目录遍历 | 内部 location 限定 `/app/data/sites`；拒绝 `.` 开头文件；`autoindex off` |
| 隔离 | 用户 HTML 与聊天域同 site，故**永不用 Cookie 鉴权**；如需 Cookie，改用独立 registrable domain |
| 内容类型 | `Content-Type` 只按扩展名推断，不信用户；`.svg` 单独加 `CSP: default-src 'none'` |
| 私密站 | `private_signed` 用 HMAC 签名 URL（`?k=HMAC(slug,exp)`），不做服务端会话 |
| 资源治理 | 单用户站数上限、单站体积上限、默认 TTL（如 30 天，可续期）、一键下线、`noindex` |
| 滥用 | 用户内容挂自有域名存在钓鱼/品牌风险，上线即带 TTL + 下线接口 + 巡查手段 |

---

## 八、分期与验收

### 第 1 期（约 2-3 天）：链路先通，不碰后端代码

- [ ] DNSPod 泛解析 + 通配证书 + NPM Proxy Host 就位
- [ ] `deploy/sites/` 容器（gateway + nginx）落地，手工把现有 `outputs/app-dist` 拷进 `data/sites/{slug}/1/` 验证
- [ ] 验收：`curl -I https://{slug}.apps.wuhonglei.cn/` 返回 200、`content-type: text/html`、assets 命中 long-cache；刷新子路由不 404（SPA 回退生效）；证书链有效（不是 NPM 自签回落）

### 第 2 期（约 2-3 天）：发布闭环，Agent 能交付公网 URL

- [ ] `published_sites` 表 + 迁移 + `/api/sites` 四个接口
- [ ] `publish_site` MCP 工具 + `file_mcp/server.py` 注册
- [ ] `webapp-building` skill 加 Step C
- [ ] 验收：agent 在对话里完成建站后调用 `publish_site`，用户拿到可访问 URL；重复发布 version+1 且旧版本仍在；`DELETE` 后立刻 404，`include_merged` 语义不涉及（那是 mem0）

### 第 3 期（约 2 天）：前端体验与既有缺口

- [ ] ProjectPreview 加发布/复制链接/下线入口
- [ ] 预览改 iframe 直连，替换 base64 内联
- [ ] `user_data.py:40-45` 补 `outputs/app-dist/index.html` 入口候选
- [ ] 验收：多页站点、相对路径图片、字体在预览面板里全部可用（当前必坏）

---

## 九、坑清单（按踩中概率排序）

1. **软链切换非原子**：必须新版本目录写完后 `ln -sfn`，否则中间态 404。
2. **别把 `data/user_data` 整个挂成 nginx 静态 root**：路径含 `user_id`，Host 解析一旦写错就是跨用户泄露。快照根独立为 `data/sites/`。
3. **硬链接快照会被就地改写**（见 2.2），会静默污染"已发布版本"。
4. **通配证书签发失败时 NPM 回落到自签**，浏览器告警。部署后必须 `curl -I` 校验证书链。
5. **SPA 刷新 404**：无扩展名且文件不存在时回退 entry，返回 200 而不是 404。
6. **`.svg` 内嵌 XSS**：单独设 `CSP: default-src 'none'`。
7. **Content-Type 靠扩展名**，别信用户声明的类型。
8. **deploy.sh 服务范围**：新容器不加进脚本，部署时会漏。
9. **快照与 outputs 双份占用磁盘**：`size_bytes` 入表，配额按快照计；下线时同时清理目录。

---

## 十、待决项

| # | 问题 | 选项 | 倾向 |
|---|------|------|------|
| 1 | 发布域 | `*.apps.wuhonglei.cn`（省事） / 独立 registrable domain（隔离干净） | 先用子域，Cookie 方案出现前不换 |
| 2 | 默认可见性 | `public` / `unlisted` | `unlisted`（不 index，URL 已知可访问） |
| 3 | 治理策略 | 永久公开 / TTL + 配额 | 至少要有 TTL 与一键下线 |

---

## 附录 A：相关既有变更

- **`backend/skills/public/vercel-deploy-claimable` 已删除**（commit `eede1bac`，删除前内容可用 `git show eede1bac^:backend/skills/public/vercel-deploy-claimable/scripts/deploy.sh` 查）。
  理由：上游 claimable deploy 接口已废弃（`POST https://claude-skills-deploy.vercel.com/api/deploy` 现返回「请改用 Vercel CLI」的说明，不再返回 `previewUrl`），脚本在删除前 `deploy.sh:232` 处 `grep -o '"previewUrl":"[^"]*"'` 必然取空并 `exit 1`（第 236 行）；且 `SKILL.md:23` 指向的 `/mnt/skills/custom/vercel-deploy/scripts/deploy.sh` 与实际位置（`skills/public/vercel-deploy-claimable/`）不符，照文档执行必然 No such file。
  能力缺口：Vercel 能托管需要服务端运行时的应用（Next.js SSR、API routes），本方案只托管静态产物。当前 skill 模板产出为 Vite SPA 静态站，主链路不受影响；若将来要交付 SSR/带后端应用，需另设运行时档位。
- **mem0 线上库仍有断言该 skill 存在的记忆**，会在「网页设计 skill 推荐」类提问时被召回。清理脚本：`/Users/apple/Desktop/code/chat-agent/backend/scripts/archive_stale_skill_memories.py`（默认 dry-run）。
- **评测语料 `backend/data/eval_set/v1.0/` 保持不变**：`eval_samples*.json` 是历史 trace 快照，`answer` 字段挂着裁判对原文的评分，`memories[].memory` 是当时 mem0 的返回原文；回改会让分数与文本脱钩，且 `calibration_report.json` 表明 v1.0 是冻结基线。需要干净语料应切 v1.1 重采样。

## 附录 B：源码索引

- 产物路径解析：`/Users/apple/Desktop/code/chat-agent/backend/app/vfs/paths.py`
- 虚拟路径权限：`/Users/apple/Desktop/code/chat-agent/backend/app/vfs/resolver.py`
- 会话内预览（含 base64 内联）：`/Users/apple/Desktop/code/chat-agent/backend/app/api/user_data.py`
- 交付物登记：`/Users/apple/Desktop/code/chat-agent/backend/app/mcp/mcp_servers/file_mcp/present_files.py`
- 前端容器内 nginx（`/api` 反代规则）：`/Users/apple/Desktop/code/chat-agent/frontend/nginx.conf`
- 编排与部署：`/Users/apple/Desktop/code/chat-agent/docker-compose.yml`、`/Users/apple/Desktop/code/chat-agent/deploy.sh`
- VFS 与沙箱运维手册：`/Users/apple/Desktop/code/chat-agent/backend/docs/VFS_AND_SANDBOX.md`
