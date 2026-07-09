# MinerU 文档解析接口文档

MinerU 提供两种文档解析 API，满足不同场景需求：

- 🎯 **精准解析 API** — 需填写token（API管理页面自定创建），支持单文件/批量、表格/公式/多格式输出
- ⚡ **Agent 轻量解析 API** — 免登录，IP 限频防滥用，专为 AI Agent 工作流设计

## 模式对比

| 对比维度 | 🎯 精准解析 API | ⚡ Agent 轻量解析 API |
|---------|---------------|---------------------|
| 是否需要 Token | ✅ 需要 | ❌ 无需（IP 限频） |
| 接口地址 | `/api/v4/extract/task` 或 `/api/v4/file-urls/batch` | `/api/v1/agent/parse/url` 或 `/api/v1/agent/parse/file` |
| 模型版本 | `pipeline`（默认）/ `vlm`(推荐) / `MinerU-HTML` | 固定 pipeline 轻量模型 |
| 文件大小限制 | ≤ 200MB | ≤ 10MB |
| 页数限制 | ≤ 200 页 | ≤ 20 页 |
| 批量支持 | ✅ 支持（≤ 200 个） | ❌ 单文件 |
| 输出格式 | Zip包，其中包含Markdown、JSON，且可导出为docx/html/latex | 仅 Markdown（CDN 链接） |
| 调用方式 | 异步（提交 → 轮询） | 异步（提交 → 轮询） |

---

## 🎯 精准解析 API

> 需填写token（API管理页面自定创建），支持 pipeline / vlm / MinerU-HTML 三种模型，单文件和批量均支持。

### 概述

MinerU 的精准解析 API 专为需要高精度、深层次结构化提取的复杂文档设计。它能够智能识别并处理各类复杂版式、多模态内容（如表格、数学公式、图表、图片、多栏布局等），将文档内容转化为高质量的结构化数据。

**核心特性：**

- **极致精度**：提供行业领先的解析准确性，尤其擅长处理非标准和复杂文档
- **深度结构化**：不仅仅是文本提取，更能深度理解文档的版面和语义，输出包含丰富层级关系的结构化数据
- **多模态支持**：全面支持文本、表格、图片、公式等多种内容类型的精准识别与提取
- **复杂版式适应**：有效应对扫描件、排版混乱、水印干扰等复杂文档场景

**文件限制：**

| 限制项 | 限制值 |
|-------|-------|
| 文件大小上限 | 200 MB |
| 文件页数上限 | 200 页 |
| 支持文件类型 | PDF、图片（png/jpg/jpeg/jp2/webp/gif/bmp）、Doc、Docx、Ppt、PPTx、Xls、Xlsx |

---

## 1.单个文件解析

### 创建解析任务

#### 接口说明

适用于通过 API 创建解析任务的场景，用户需在 Header 中填写 Token（可在 API 管理页面自定创建）。 **注意：**

- 单个文件大小不能超过 200MB,文件页数不超出 200 页
- 每个账号每天享有 1000 页最高优先级解析额度，超过 1000 页的部分优先级降低
- 因网络限制，github、aws 等国外 URL 会请求超时
- 该接口不支持文件直接上传
- header头中需要包含 Authorization 字段，格式为 Bearer + 空格 + Token

#### Python 请求示例（适用于pdf、doc、ppt、excel、图片文件）：

```python
import requests

token = "API管理页面自定创建的token"

url = "https://mineru.net/api/v4/extract/task"

header = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

data = {
    "url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf",
    "model_version": "vlm"
}

res = requests.post(url, headers=header, json=data)

print(res.status_code)
print(res.json())
print(res.json()["data"])
```

#### Python 请求示例（适用于html文件）：

```python
import requests

token = "API管理页面自定创建的token"

url = "https://mineru.net/api/v4/extract/task"

header = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

data = {
    "url": "https://****",
    "model_version": "MinerU-HTML"
}

res = requests.post(url, headers=header, json=data)

print(res.status_code)
print(res.json())
print(res.json()["data"])
```

#### CURL 请求示例（适用于pdf、doc、ppt、excel、图片文件）：

```bash
curl --location --request POST 'https://mineru.net/api/v4/extract/task' \
--header 'Authorization: Bearer ***' \
--header 'Content-Type: application/json' \
--header 'Accept: */*' \
--data-raw '{
    "url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf",
    "model_version": "vlm"
}'
```

#### CURL 请求示例（适用于html文件）：

```bash
curl --location --request POST 'https://mineru.net/api/v4/extract/task' \
--header 'Authorization: Bearer ***' \
--header 'Content-Type: application/json' \
--header 'Accept: */*' \
--data-raw '{
    "url": "https://****",
    "model_version": "MinerU-HTML"
}'
```

#### 请求体参数说明

| 参数 | 类型 | 是否必选 | 示例 | 描述 |
|------|------|---------|------|------|
| url | string | 是 | `https://cdn-mineru.openxlab.org.cn/demo/example.pdf` | 文件 URL，支持.pdf、.doc、.docx、.ppt、.pptx、.xls、.xlsx、图片（png/jpg/jpeg/jp2/webp/gif/bmp）、.html多种格式 |
| is_ocr | bool | 否 | `false` | 是否启动 ocr 功能，默认 false，仅对pipeline、vlm模型有效 |
| enable_formula | bool | 否 | `true` | 是否开启公式识别，默认 true，仅对pipeline、vlm模型有效。特别注意的是：对于vlm模型，这个参数指只会影响行内公式的解析 |
| enable_table | bool | 否 | `true` | 是否开启表格识别，默认 true，仅对pipeline、vlm模型有效 |
| language | string | 否 | `ch` | 指定文档语言，默认 `ch`。可选值见 `language 取值参考`。仅对 pipeline、vlm 模型有效 |
| data_id | string | 否 | `abc**` | 解析对象对应的数据 ID。由大小写英文字母、数字、下划线（_）、短划线（-）、英文句号（.）组成，不超过 128 个字符，可以用于唯一标识您的业务数据。 |
| callback | string | 否 | `http://127.0.0.1/callback` | 解析结果回调通知您的 URL，支持使用 HTTP 和 HTTPS 协议的地址。该字段为空时，您必须定时轮询解析结果。callback 接口必须支持 POST 方法、UTF-8 编码、Content-Type: application/json。callback 推送格式如下：<br>**checksum**：字符串格式，由用户 uid + seed + content 拼成字符串，通过 SHA256 算法生成。用户 UID，可在个人中心查询。为防篡改，您可以在获取到推送结果时，按上述算法重新生成 checksum 并与推送的 checksum 进行比对。<br>**content**：JSON 字符串格式，请自行解析反转成 JSON 对象。关于 content 结果的示例，请参见任务查询结果的返回示例，对应任务查询结果的 data 部分。<br>**说明**:您的服务端 callback 接口收到 Mineru 解析服务推送的结果后，如果返回的 HTTP 状态码为 200，则表示接收成功，其他的 HTTP 状态码均视为接收失败。接收失败时，mineru 会按一定策略重试推送。 |
| seed | string | 否 | `abc**` | 随机字符串，该值用于回调通知请求中的签名。由英文字母、数字、下划线（_）组成，不超过 64 个字符，由您自定义。用于在接收到内容安全的回调通知时校验请求由 Mineru 解析服务发起。<br>**说明：**当使用 callback 时，该字段必须提供。 |
| extra_formats | [string] | 否 | `["docx","html"]` | markdown、json为默认导出格式，无须设置，该参数仅支持docx、html、latex三种格式中的一个或多个。对源文件为html的文件无效。 |
| page_ranges | string | 否 | `1-200` | 指定页码范围，格式为逗号分隔的字符串。例如：`"2,4-6"`：表示选取第2页、第4页至第6页（包含4和6，结果为 [2,4,5,6]）；`"2--2"`：表示从第2页一直选取到倒数第二页（其中"-2"代表倒数第二页），结果为 [2, 5, 6]；`"1-3,7-9,15-"`：表示选取第1至3页、第7至9页以及第15页直到最后一页。 |
| model_version | string | 否 | `vlm` | mineru模型版本，三个选项:pipeline、vlm、MinerU-HTML，默认pipeline。如果解析的是HTML文件，model_version需明确指定为MinerU-HTML，如果解析的是PDF等非HTML文件，建议使用vlm模型以获得更好的解析效果 |
| no_cache | bool | 否 | `false` | 是否绕过缓存，默认 false。我们的 API 服务器会将 URL 内容缓存一段时间，设置为 true 可忽略缓存结果，从 URL 获取最新内容。 |
| cache_tolerance | int | 否 | `900` | 缓存容忍时间（秒），默认 900（15分钟）。 可容忍的 URL 内容缓存有效时间，超出该时间的缓存不会被使用。当no_cache为false时有效 |

#### 响应参数说明

| 参数 | 类型 | 示例 | 说明 |
|------|------|------|------|
| code | int | `0` | 接口状态码，成功：0 |
| msg | string | `ok` | 接口处理信息，成功："ok" |
| trace_id | string | `c876cd60b202f2396de1f9e39a1b0172` | 请求 ID |
| data.task_id | string | `a90e6ab6-44f3-4554-b459-b62fe4c6b436` | 提取任务 id，可用于查询任务结果 |

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "task_id": "a90e6ab6-44f3-4554-b4***"
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

### 获取任务结果

#### 接口说明

通过 task_id 查询提取任务目前的进度，任务处理完成后，接口会响应对应的提取详情。

#### Python 请求示例

```python
import requests

token = "API管理页面自定创建的token"
task_id = "上一步创建任务返回的task_id"

url = f"https://mineru.net/api/v4/extract/task/{task_id}"

header = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

res = requests.get(url, headers=header)

print(res.status_code)
print(res.json())
print(res.json()["data"])
```

#### 响应参数说明

| 参数 | 类型 | 示例 | 说明 |
|------|------|------|------|
| code | int | `0` | 接口状态码，成功：0 |
| msg | string | `ok` | 接口处理信息，成功："ok" |
| trace_id | string | `c876cd60b202f2396de1f9e39a1b0172` | 请求 ID |
| data.task_id | string | `a90e6ab6-...05` | 任务 ID（与提交时返回的一致） |
| data.state | string | `done` | 任务状态：waiting-file（等待文件上传，仅文件上传模式）、uploading(文件下载中)、pending（排队中）、running（解析中）、done（完成）、failed（失败） |
| data.markdown_url | string | `https://cdn-mineru.../full.md` | Markdown 结果文件的 CDN 下载链接，当 state=done 时有效 |
| data.err_msg | string | `file page count exceeds lightweight API limit` | 错误信息，当 state=failed 时有效 |
| data.err_code | int | `-30003` | 错误码，当 state=failed 时有效。详见底部错误码表 |

#### 响应示例（等待文件上传 — 仅文件上传模式）

```json
{
  "code": 0,
  "data": {
    "task_id": "a90e6ab6-44f3-4554-b459-b62fe4c6b43605",
    "state": "waiting-file"
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

#### 响应示例（处理中）

```json
{
  "code": 0,
  "data": {
    "task_id": "a90e6ab6-44f3-4554-b459-b62fe4c6b43605",
    "state": "running"
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

#### 响应示例（完成）

```json
{
  "code": 0,
  "data": {
    "task_id": "a90e6ab6-44f3-4554-b459-b62fe4c6b43605",
    "state": "done",
    "markdown_url": "https://cdn-mineru.openxlab.org.cn/pdf/a90e6ab6-.../full.md"
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

#### 响应示例（失败）

```json
{
  "code": 0,
  "data": {
    "task_id": "a90e6ab6-44f3-4554-b459-b62fe4c6b43605",
    "state": "failed",
    "err_code": -30003,
    "err_msg": "file page count exceeds lightweight API limit (50 pages), please use the standard API"
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

---

## 2.批量文件解析

### 本地文件批量上传解析

#### 接口说明

适用于通过 API 批量创建本地文件解析任务的场景，用户需在 Header 中填写 Token（可在 API 管理页面自定创建）。支持同时提交最多 200 个文件的批量解析任务。

**注意：**
- 单个文件大小不能超过 200MB
- 文件总大小不能超过 1GB
- 每个账号每天享有 1000 页最高优先级解析额度，超过 1000 页的部分优先级降低
- 该接口仅支持文件直接上传方式
- header头中需要包含 Authorization 字段，格式为 Bearer + 空格 + Token

#### Python 请求示例

```python
import requests

token = "API管理页面自定创建的token"

url = "https://mineru.net/api/v4/file-urls/batch"

headers = {
    "Authorization": f"Bearer {token}"
}

files = [
    ("files", ("example1.pdf", open("example1.pdf", "rb"), "application/pdf")),
    ("files", ("example2.docx", open("example2.docx", "rb"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
]

data = {
    "model_version": "vlm",
    "language": "ch"
}

response = requests.post(url, headers=headers, files=files, data=data)

print(response.status_code)
print(response.json())

for file_tuple in files:
    file_tuple[1].close()
```

#### 请求体参数说明

| 参数 | 类型 | 是否必选 | 示例 | 描述 |
|------|------|---------|------|------|
| files | file[] | 是 | - | 文件列表，支持多文件上传，单次最多 200 个文件 |
| model_version | string | 否 | `vlm` | mineru模型版本，三个选项:pipeline、vlm、MinerU-HTML，默认pipeline |
| language | string | 否 | `ch` | 指定文档语言，默认 `ch` |
| is_ocr | bool | 否 | `false` | 是否启动 ocr 功能，默认 false |
| enable_formula | bool | 否 | `true` | 是否开启公式识别，默认 true |
| enable_table | bool | 否 | `true` | 是否开启表格识别，默认 true |
| extra_formats | [string] | 否 | `["docx","html"]` | 额外输出格式，可选 docx、html、latex |

#### 响应参数说明

| 参数 | 类型 | 示例 | 说明 |
|------|------|------|------|
| code | int | `0` | 接口状态码，成功：0 |
| msg | string | `ok` | 接口处理信息，成功："ok" |
| trace_id | string | `c876cd60b202f2396de1f9e39a1b0172` | 请求 ID |
| data.task_ids | list | `["task_id_1", "task_id_2"]` | 批量任务 ID 列表，可用于分别查询每个任务的解析结果 |

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "task_ids": [
      "a90e6ab6-44f3-4554-b459-b62fe4c6b436",
      "b80f7bc7-55g4-5665-c56a-c73gf5d7c547"
    ]
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

### url 批量上传解析

#### 接口说明

适用于通过 API 批量创建 URL 文件解析任务的场景，用户需在 Header 中填写 Token（可在 API 管理页面自定创建）。支持同时提交最多 200 个 URL 的批量解析任务。

**注意：**
- 单个文件大小不能超过 200MB
- 因网络限制，github、aws 等国外 URL 会请求超时
- 每个账号每天享有 1000 页最高优先级解析额度，超过 1000 页的部分优先级降低
- header头中需要包含 Authorization 字段，格式为 Bearer + 空格 + Token

#### Python 请求示例

```python
import requests

token = "API管理页面自定创建的token"

url = "https://mineru.net/api/v4/file-urls/batch"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

data = {
    "urls": [
        "https://cdn-mineru.openxlab.org.cn/demo/example1.pdf",
        "https://cdn-mineru.openxlab.org.cn/demo/example2.docx"
    ],
    "model_version": "vlm",
    "language": "ch"
}

response = requests.post(url, headers=headers, json=data)

print(response.status_code)
print(response.json())
```

#### 请求体参数说明

| 参数 | 类型 | 是否必选 | 示例 | 描述 |
|------|------|---------|------|------|
| urls | string[] | 是 | - | 文件 URL 列表，支持多URL批量提交，单次最多 200 个URL |
| model_version | string | 否 | `vlm` | mineru模型版本，三个选项:pipeline、vlm、MinerU-HTML，默认pipeline |
| language | string | 否 | `ch` | 指定文档语言，默认 `ch` |
| is_ocr | bool | 否 | `false` | 是否启动 ocr 功能，默认 false |
| enable_formula | bool | 否 | `true` | 是否开启公式识别，默认 true |
| enable_table | bool | 否 | `true` | 是否开启表格识别，默认 true |
| extra_formats | [string] | 否 | `["docx","html"]` | 额外输出格式，可选 docx、html、latex |

#### 响应参数说明

| 参数 | 类型 | 示例 | 说明 |
|------|------|------|------|
| code | int | `0` | 接口状态码，成功：0 |
| msg | string | `ok` | 接口处理信息，成功："ok" |
| trace_id | string | `c876cd60b202f2396de1f9e39a1b0172` | 请求 ID |
| data.task_ids | list | `["task_id_1", "task_id_2"]` | 批量任务 ID 列表，可用于分别查询每个任务的解析结果 |

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "task_ids": [
      "a90e6ab6-44f3-4554-b459-b62fe4c6b436",
      "b80f7bc7-55g4-5665-c56a-c73gf5d7c547"
    ]
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

### 批量获取任务结果

批量任务提交后，可使用返回的 task_id 列表中的每个 task_id 分别调用「获取任务结果」接口来获取每个文件的解析结果。

---

## 常见错误码

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| -10001 | Token 无效或已过期 | 请检查 Token 是否正确或在 API 管理页面重新创建 |
| -10002 | 请求频率超限 | 请降低请求频率，稍后重试 |
| -20001 | 文件下载失败 | 请检查 URL 是否可访问，文件是否存在 |
| -20002 | 文件格式不支持 | 请检查文件格式是否在支持列表内 |
| -20003 | 文件大小超出限制 | 文件大小不超过 200MB |
| -20004 | 文件页数超出限制 | 文件页数不超过 200 页 |
| -30001 | 解析任务创建失败 | 请检查请求参数是否正确 |
| -30002 | 解析任务处理失败 | 请联系技术支持 |
| -30003 | 解析超时 | 请稍后重试或简化文档内容 |

---

## ⚡ Agent 轻量解析 API

> 免登录，IP 限频防滥用，专为 AI Agent 工作流设计

### 概述

Agent 轻量解析 API 是专为 AI Agent 场景设计的轻量级文档解析接口。无需注册登录，通过 IP 限频防止滥用，适合快速集成到 AI Agent 工作流中。

**核心特点：**
- 免登录使用，降低接入门槛
- IP 限频机制，防止恶意调用
- 异步处理模式，支持轮询获取结果
- 返回 Markdown 格式，便于 AI 直接使用

**文件限制：**
- 文件大小限制：≤ 10MB
- 页数限制：≤ 20 页
- 支持格式：PDF、图片（png/jpg/jpeg/jp2/webp/gif/bmp）、Doc、Docx、Ppt、PPTx、Xls、Xlsx

---

## 1. URL 解析接口

#### 接口说明

通过提交文件 URL 创建解析任务，返回 task_id 用于后续查询解析结果。

**注意：**
- 单个文件大小不能超过 10MB
- 文件页数不超过 20 页
- github、aws 等国外 URL 可能请求超时

#### 请求示例

```bash
POST https://mineru.net/api/v1/agent/parse/url
Content-Type: application/json

{
  "url": "https://example.com/document.pdf",
  "language": "ch",
  "page_range": null,
  "enable_table": true,
  "is_ocr": false,
  "enable_formula": true
}
```

#### 请求参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| url | string | 是 | - | 文件 URL |
| language | string | 否 | `ch` | 文档语言 |
| page_range | string | 否 | null | 页码范围，如 `"1-5"` 或 `"1,3,5"` |
| enable_table | bool | 否 | true | 是否识别表格 |
| is_ocr | bool | 否 | false | 是否启用 OCR |
| enable_formula | bool | 否 | true | 是否识别公式 |

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "task_id": "a90e6ab6-44f3-4554-b459-b62fe4c6b436"
  },
  "msg": "ok"
}
```

---

## 2. 本地文件上传接口（签名上传）

#### 接口说明

通过两步完成文件上传：首先获取签名上传 URL，然后 PUT 上传文件到 OSS。

#### 步骤一：获取签名上传 URL

**请求示例：**

```bash
POST https://mineru.net/api/v1/agent/parse/file
Content-Type: application/json

{
  "file_name": "document.pdf",
  "language": "ch",
  "page_range": null,
  "enable_table": true,
  "is_ocr": false,
  "enable_formula": true
}
```

**响应示例：**

```json
{
  "code": 0,
  "data": {
    "task_id": "a90e6ab6-44f3-4554-b459-b62fe4c6b436",
    "file_url": "https://oss.example.com/upload/xxx"
  },
  "msg": "ok"
}
```

#### 步骤二：PUT 上传文件到 OSS

使用返回的 file_url 执行 PUT 请求上传文件：

```python
import requests

with open("document.pdf", "rb") as f:
    put_resp = requests.put(file_url, data=f)

if put_resp.status_code not in (200, 201):
    print(f"文件上传失败, HTTP {put_resp.status_code}")
```

---

## 3. 查询解析结果

#### 接口说明

通过 task_id 查询解析任务状态和结果。

**请求示例：**

```bash
GET https://mineru.net/api/v1/agent/parse/{task_id}
Authorization: Bearer {token}  # Agent API 可不带 token
```

**响应参数说明：**

| 参数 | 类型 | 示例 | 说明 |
|------|------|------|------|
| code | int | `0` | 接口状态码，成功：0 |
| msg | string | `ok` | 接口处理信息 |
| trace_id | string | `c876cd60b202f2396de1f9e39a1b0172` | 请求 ID |
| data.task_id | string | `a90e6ab6-...05` | 任务 ID |
| data.state | string | `done` | 任务状态：waiting-file、uploading、pending、running、done、failed |
| data.markdown_url | string | `https://cdn-mineru.../full.md` | Markdown 下载链接（state=done 时有效） |
| data.err_msg | string | 错误描述 | 错误信息（state=failed 时有效） |
| data.err_code | int | `-30003` | 错误码（state=failed 时有效） |

**响应示例（完成）：**

```json
{
  "code": 0,
  "data": {
    "task_id": "a90e6ab6-44f3-4554-b459-b62fe4c6b43605",
    "state": "done",
    "markdown_url": "https://cdn-mineru.openxlab.org.cn/pdf/a90e6ab6-.../full.md"
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

**响应示例（失败）：**

```json
{
  "code": 0,
  "data": {
    "task_id": "a90e6ab6-44f3-4554-b459-b62fe4c6b43605",
    "state": "failed",
    "err_code": -30003,
    "err_msg": "file page count exceeds lightweight API limit (50 pages), please use the standard API"
  },
  "msg": "ok",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

---

## 完整使用示例（Python）

### URL 模式

```python
def parse_by_url(url, language="ch", page_range=None, enable_table=True, is_ocr=False, enable_formula=True):
    """通过 URL 提交文档解析任务并等待结果。"""

    # 1. 提交 URL 解析任务
    data = {
        "url": url,
        "language": language,
        "enable_table": enable_table,
        "is_ocr": is_ocr,
        "enable_formula": enable_formula
    }

    if page_range:
        data["page_range"] = page_range

    resp = requests.post(f"{BASE_URL}/parse/url", json=data)

    result = resp.json()

    if result["code"] != 0:
        print(f"提交失败: {result['msg']}")
        return None


    task_id = result["data"]["task_id"]

    print(f"任务已提交, task_id: {task_id}")



    # 2. 轮询等待结果
    return poll_result(task_id)



def poll_result(task_id, timeout=300, interval=3):
    """轮询查询解析结果。"""

    state_labels = {

        "uploading": "文件下载中",

        "pending": "排队中",

        "running": "解析中",

        "waiting-file": "等待文件上传",

    }

    start = time.time()

    while time.time() - start < timeout:

        resp = requests.get(f"{BASE_URL}/parse/{task_id}")

        result = resp.json()

        state = result["data"]["state"]

        elapsed = int(time.time() - start)



        if state == "done":

            markdown_url = result["data"]["markdown_url"]

            print(f"[{elapsed}s] 解析完成, Markdown 下载链接: {markdown_url}")

            md_resp = requests.get(markdown_url)

            return md_resp.text



        if state == "failed":

            print(f"[{elapsed}s] 解析失败: {result['data'].get('err_msg', '未知错误')}")

            return None



        print(f"[{elapsed}s] {state_labels.get(state, state)}...")

        time.sleep(interval)



    print(f"轮询超时 ({timeout}s)，请稍后手动查询 task_id: {task_id}")

    return None




# 使用示例

content = parse_by_url("https://cdn-mineru.openxlab.org.cn/demo/example.pdf")
```

### 文件上传模式（签名上传）

```python
import requests
import time


BASE_URL = "https://mineru.net/api/v1/agent"


def parse_by_file(file_path, language="ch", page_range=None, enable_table=True, is_ocr=False, enable_formula=True):
    """通过文件上传提交文档解析任务并等待结果。"""

    file_name = file_path.split("/")[-1].split("\\")[-1]



    # 1. 获取签名上传 URL

    data = {
        "file_name": file_name,
        "language": language,
        "enable_table": enable_table,
        "is_ocr": is_ocr,
        "enable_formula": enable_formula
    }

    if page_range:
        data["page_range"] = page_range

    resp = requests.post(f"{BASE_URL}/parse/file", json=data)

    result = resp.json()

    if result["code"] != 0:

        print(f"获取上传链接失败: {result['msg']}")

        return None


    task_id = result["data"]["task_id"]

    file_url = result["data"]["file_url"]

    print(f"任务已创建, task_id: {task_id}")



    # 2. PUT 上传文件到 OSS

    with open(file_path, "rb") as f:

        put_resp = requests.put(file_url, data=f)



        if put_resp.status_code not in (200, 201):

            print(f"文件上传失败, HTTP {put_resp.status_code}")

            return None

    print("文件上传成功，等待解析...")



    # 3. 轮询等待结果

    return poll_result(task_id)



def poll_result(task_id, timeout=300, interval=3):
    """轮询查询解析结果。"""

    state_labels = {

        "pending": "排队中",

        "running": "解析中",

        "waiting-file": "等待文件上传",

    }

    start = time.time()

    while time.time() - start < timeout:

        resp = requests.get(f"{BASE_URL}/parse/{task_id}")

        result = resp.json()

        state = result["data"]["state"]

        elapsed = int(time.time() - start)



        if state == "done":

            markdown_url = result["data"]["markdown_url"]

            print(f"[{elapsed}s] 解析完成, Markdown 下载链接: {markdown_url}")

            md_resp = requests.get(markdown_url)

            return md_resp.text



        if state == "failed":

            print(f"[{elapsed}s] 解析失败: {result['data'].get('err_msg', '未知错误')}")

            return None


        print(f"[{elapsed}s] {state_labels.get(state, state)}...")

        time.sleep(interval)



    print(f"轮询超时 ({timeout}s)，请稍后手动查询 task_id: {task_id}")

    return None




# 使用示例

content = parse_by_file("./document.pdf")
```

---

## Agent 专属错误码

| 错误码 | 说明 | Agent 应对策略 |
|--------|------|----------------|
| -30001 | 文件大小超出轻量接口限制（10MB） | 请使用标准 API 或拆分文件 |
| -30002 | 轻量接口不支持该文件类型 | 请上传 PDF/图片/Doc/PPT/Excel |
| -30003 | 文件页数超出轻量接口限制 | 请使用标准 API 或指定 page_range |
| -30004 | 请求参数错误 | 检查必填参数是否缺失 |

---

## language 取值参考

`language` 字段建议按下表传入。默认值为 `ch`。

### Standalone language packs

| Value | Included languages | 说明 |
|-------|-------------------|------|
| `ch` | Chinese, English, Chinese Traditional | 中英文（默认值） |
| `ch_server` | Chinese, English, Chinese Traditional, Japanese | 繁体、手写体 |
| `en` | English | 纯英文 |
| `japan` | Chinese, English, Chinese Traditional, Japanese | 日文为主 |
| `korean` | Korean, English | 韩文 |
| `chinese_cht` | Chinese, English, Chinese Traditional, Japanese | 繁体中文为主 |
| `ta` | Tamil, English | 泰米尔文 |
| `te` | Telugu, English | 泰卢固文 |
| `ka` | Kannada | 卡纳达文 |
| `el` | Greek, English | 希腊文 |
| `th` | Thai, English | 泰文 |

### Language family packs

| Value | Script/Family | Included languages |
|-------|--------------|-------------------|
| `latin` | Latin script (拉丁语系) | French, German, Afrikaans, Italian, Spanish, Bosnian, Portuguese, Czech, Welsh, Danish, Estonian,... |
| `arabic` | Arabic script (阿拉伯语系) | Arabic, Persian, Uyghur, Urdu, Pashto, Kurdish, Sindhi, Balochi, English |
| `cyrillic` | Cyrillic script (西里尔语系) | Russian, Belarusian, Ukrainian, Serbian (Cyrillic), Bulgarian, Mongolian, Abkhazian, Adyghe, Kaba... |
| `east_slavic` | East Slavic (东斯拉夫语系) | Russian, Belarusian, Ukrainian, English |
| `devanagari` | Devanagari script (天城文语系) | Hindi, Marathi, Nepali, Bihari, Maithili, Angika, Bhojpuri, Magahi, Santali, Newari, Konkani, San... |

---

*© 2025 MinerU. All Rights Reserved.*
