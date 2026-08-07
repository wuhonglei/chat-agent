# 采样工具反爬手段总结

> 基于 `/Users/apple/Desktop/code/sampling-tool` 源码整理，覆盖浏览器指纹、网络代理、账号管理、反检测对抗、异常处理五个层面。

---

## 一、浏览器设备指纹伪装

### 1.1 动态设备指纹生成（DeviceProfile）

**源码**: `src/shared/utils/deviceProfile.ts`

每次创建浏览器上下文时，随机构造一组**内部一致**的设备配置，确保 UA / platform / screen / hardware 属性相互匹配，避免矛盾暴露。

| 属性 | 生成策略 |
|---|---|
| 操作系统 | Windows 10/11 (70%)、macOS (25%)、Linux (5%)，按权重采样 |
| Chrome 版本 | 131-136，按真实发布分布加权（133/134 占主导） |
| User-Agent | 根据平台动态拼接，macOS 随机 6 个大版本，Windows 随机 NT 10.0/11.0，build 号随机 |
| 屏幕分辨率 | Mac 7 种（1440x900 ~ 2560x1440）、Windows 6 种（1366x768 ~ 2560x1440）、Linux 4 种 |
| CPU 核数 | 4/8/12/16 核，按真实分布加权 |
| 内存 | 8/16/32GB，Mac 偏向 16GB，Windows/Linux 偏向 8-16GB |
| maxTouchPoints | 桌面设备统一为 0 |

**调用入口**: `src/infrastructure/browser/managers/contextManager.ts` → `createContext()`

```typescript
const deviceProfile = generateDeviceProfile();
// UA 用于 context options
merge({ userAgent: deviceProfile.userAgent, storageState }, browserContextOptions, getProxyConfig(restOptions));
// 同一个 profile 注入反检测脚本
await context.addInitScript({ path: PathsConfig.antiDetectionScriptPath, arg: deviceProfile });
```

### 1.2 反检测注入脚本

**源码**: `src/infrastructure/browser/libs/anti-detection.js`

通过 `context.addInitScript()` 在每个页面加载前注入，参考 [undetected-chromedriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver) 项目。接收 `DeviceProfile` 参数，所有属性从 profile 读取，无硬编码。

#### Navigator 属性覆盖

| 属性 | 来源 | 说明 |
|---|---|---|
| `navigator.webdriver` | 固定 `false` | 最基本的自动化检测点 |
| `navigator.platform` | `profile.platform` | 与 UA 一致 |
| `navigator.hardwareConcurrency` | `profile.hardwareConcurrency` | CPU 核数 |
| `navigator.deviceMemory` | `profile.deviceMemory` | 设备内存 |
| `navigator.maxTouchPoints` | `profile.maxTouchPoints` | 触摸点数 |
| `navigator.plugins` | 模拟 5 个插件对象 | 空插件数组是自动化特征 |

#### Screen 属性覆盖

| 属性 | 来源 |
|---|---|
| `screen.width / height` | `profile.screenWidth / screenHeight` |
| `screen.availWidth / availHeight` | 同上 |
| `screen.colorDepth / pixelDepth` | `profile.colorDepth`（固定 24） |
| `screen.orientation` | `landscape-primary, angle: 0` |

#### Chrome Runtime 完整模拟

构造 `window.chrome` 对象，包含：
- `chrome.app`（InstallState、RunningState）
- `chrome.runtime`（OnInstalledReason、PlatformArch、PlatformOs 等）
- `chrome.runtime.getPlatformInfo()` → 根据 `profile.os` 返回 `{ arch, os }`
- `chrome.cookies` / `chrome.storage.local`（Promise 接口）

#### 检测对抗

| 手段 | 说明 |
|---|---|
| 删除 `_cdc_asdjflasutopfhvcZLmcfl_` | 清除 chromedriver 特征变量 |
| 删除 `_webDriverEvaluated` | 清除自动化评估标记 |
| 修补 `Function.prototype.toString` | 让被修改的函数返回 `function query() { [native code] }` 形式 |
| 修补 `navigator.permissions.query` | notifications 返回真实 permission 状态 |
| 强制 `attachShadow` 使用 open mode | 避免 closed shadow DOM 检测 |
| 清除自动化 CSS 属性 | 重置 `document.documentElement.style.display/visibility` |
| 注入伪造 localStorage | `last_visit`、`preferences` 等痕迹 |
| 原型链修复 | `Object.setPrototypeOf(navigator, originalNavigatorProto)` |

---

## 二、网络代理

### 2.1 住宅代理

**源码**: `src/shared/config/playwright.config.ts` → `getProxyConfig()`

| 配置项 | 值 |
|---|---|
| 供应商 | Proxyrack 住宅代理（`unmetered.residential.proxyrack.net`） |
| 端口池 | 10036-10059，共 24 个端口 |
| 地理位置绑定 | username 中带 `country=${region}` 参数，按任务 region 匹配目标国家 |
| IP 刷新 | `refreshMinutes=300`，每 5 小时自动轮换 IP |
| 认证 | username + password 固定凭证 |

### 2.2 重试换代理

**源码**: `src/core/executor.ts` → `resolveRetryProxyPort()`

- 首次尝试：使用账号自带的代理端口（accountKey 编码了 proxyPort）
- 第 2 次及以后重试：从 `proxyPortList` 中**随机选取**一个不同端口
- 目的：单个代理 IP 被封后，重试时切换 IP 绕过封锁

---

## 三、账号生命周期管理

### 3.1 账号池状态机

**源码**: `src/infrastructure/services/redis/AccountPoolManager.ts`

每个账号有 4 种状态：

```
free → in_use → cooldown → free（循环）
                → expired（终态）
```

| 状态 | 说明 |
|---|---|
| `free` | 空闲可用，等待分配 |
| `in_use` | 正在执行任务 |
| `cooldown` | 任务完成后的冷却期，防止高频使用同一账号 |
| `expired` | 登录态失效，需人工重新登录 |

状态转换通过 Redis Lua 脚本原子操作，避免竞态。

### 3.2 冷却机制

**源码**: `src/infrastructure/services/RedisServer.ts` → `setAccountCooldown()`

- 任务完成后账号进入 cooldown 状态，冷却时间可按 aiPlatform 配置
- 冷却期间设置 TTL 标记，到期后自动回收到 free 池
- 目的：避免同一账号短时间高频请求触发平台风控

### 3.3 登录态持久化（storageState）

**源码**: `src/infrastructure/browser/managers/contextManager.ts` / `src/core/executor.ts`

- 账号的 cookies + localStorage 以 Playwright `storageState` 格式存储在 Redis
- 创建上下文时注入，避免每次重新登录
- 任务成功后将最新 storageState 回写 Redis（`upsertAccount`），保持 cookie 活跃
- 账号 key 格式: `email:proxyPort`，账号与代理绑定

### 3.4 登录失效检测与告警

**源码**: `src/core/executor.ts` → `initializePage()`

- 每次打开目标平台后检查登录状态（`hasLoggedIn()`）
- 失效时：
  - 标记账号为 `expired`
  - 发送 SeaTalk 告警（包含环境、区域、平台、账号、时间等信息）
  - 抛出 `AccountLoginExpiredError`，**终止所有重试**（无意义）

---

## 四、浏览器启动参数

**源码**: `src/shared/config/playwright.config.ts` → `getPlaywrightConfig()`

| 参数 | 作用 |
|---|---|
| `--disable-blink-features=AutomationControlled` | 禁用 Blink 引擎的自动化检测特征 |
| `ignoreDefaultArgs: ['--enable-automation']` | 移除 Playwright 默认的自动化标识 |
| `--disable-extensions` | 禁用扩展，减少特征 |
| `--disable-dev-shm-usage` | 容器环境兼容 |
| `--no-sandbox` | 环境兼容 |
| `--start-maximized` | 非 headless 时最大化窗口，模拟真实用户 |

### 上下文级配置

| 配置 | 值 |
|---|---|
| viewport | headless: 1920x1080；非 headless: null（跟随窗口） |
| locale | `en-US` |
| timezoneId | 按 region 自动设置（sg→Asia/Singapore, id→Asia/Jakarta 等，共 10 个地区） |
| permissions | `clipboard-read`, `clipboard-write` |

---

## 五、验证码 / 拦截页检测

### 5.1 Google 验证码检测

**源码**: `src/infrastructure/browser/config/google-ai-overview.config.ts` / `src/infrastructure/browser/pageObjects/google/GoogleAIOverviewPage.ts`

| 检测方式 | 具体规则 |
|---|---|
| URL 匹配 | `/sorry/`、`google.com/sorry` |
| DOM 选择器 | `form#captcha-form`、`iframe[src*="recaptcha"]`、`#captchaimg` |

在 `open()` 和 `performInteraction()` 等关键步骤前调用 `assertNotCaptchaPage()`，检测到则抛出异常。

### 5.2 Cloudflare 挑战检测

**源码**: `src/infrastructure/browser/config/chatgpt.config.ts` / `src/infrastructure/browser/pageObjects/chatgpt/ChatGPTPage.ts`

| 检测方式 | 具体规则 |
|---|---|
| URL 匹配 | `/cdn-cgi/challenge-platform`、`__cf_chl`、`challenges.cloudflare.com` |
| DOM 选择器 | `iframe[src*="challenges.cloudflare.com"]`、`#challenge-running`、`form#challenge-form` |

在 ChatGPT 页面的 `open()`、`performInteraction()`、`collectData()` 前调用 `assertNotCloudflarePage()`。

### 5.3 错误分类与标记

**源码**: `src/core/errors/classifySamplingFailure.ts`

命中验证码/拦截后，错误归类为 `browser_block`，关键词匹配：`cloudflare`、`验证码`、`拦截`、`验证页`、`异常页面`。

---

## 六、静态资源缓存

**源码**: `src/infrastructure/browser/managers/contextManager.ts`

通过 `playwright-network-cache` 缓存静态资源，TTL 2 天：

- `**/*.js`
- `**/*.css`
- `**/*.{png,jpg,jpeg,gif,ico}`
- `**/*.{woff,woff2,ttf,eot}`
- `**/*.{svg,webp}`

目的：减少重复请求，降低被识别为爬虫的风险。

---

## 七、Kafka 消费层的流控保护

**源码**: `src/infrastructure/services/KafkaConsumerService.ts`

| 机制 | 说明 |
|---|---|
| 最大并发任务数 | `MAX_CONCURRENT_TASKS = 1`，同一时刻只执行一个采样任务 |
| 账号池为空暂停 | 可用账号为 0 时暂停消费，每 5 秒轮询恢复 |
| 并发超限暂停 | 运行中任务数 > 1 时暂停消费，任务完成后自动恢复 |
| 消息解析失败跳过 | JSON 解析失败或校验不通过的消息直接提交 offset 跳过，避免死循环 |

---

## 八、重试策略中的反爬考量

**源码**: `src/core/executor.ts`

| 策略 | 说明 |
|---|---|
| 默认重试 3 次 | `DEFAULT_RETRY_COUNT = 3` |
| 单次超时 5 分钟 | `DEFAULT_TIMEOUT_MS = 5 * 60 * 1000` |
| 重试换代理 | 第 2 次起随机切换代理端口 |
| 账号复用 | 整个 execute 生命周期复用同一账号，不重复取号 |
| 不重试错误 | `AccountLoginExpiredError`（登录失效）、`NoWebSearchError`（无搜索结果）立即终止 |

---

## 架构总览

```
请求入口 (HTTP / Kafka)
  │
  ├─ 1. 账号预占用 (Redis 原子操作, free → in_use)
  │
  ├─ 2. 浏览器上下文创建
  │     ├─ 动态 DeviceProfile 生成 (UA/platform/screen/hardware 一致)
  │     ├─ 住宅代理注入 (按 region 选国家)
  │     ├─ storageState 注入 (登录态持久化)
  │     ├─ 反检测脚本注入 (navigator/chrome/screen 覆盖)
  │     └─ 静态资源缓存 (减少请求频率)
  │
  ├─ 3. 页面操作
  │     ├─ 验证码/拦截页检测 (Google CAPTCHA / Cloudflare)
  │     ├─ 登录状态检查 (失效 → expired + 告警)
  │     └─ AI 交互 + 数据采集
  │
  ├─ 4. 结果处理
  │     ├─ 成功 → storageState 回写 Redis, 账号 → cooldown
  │     └─ 失败 → 错误分类, 重试(换代理) 或 终止
  │
  └─ 5. 账号释放 (in_use → cooldown, TTL 后自动 → free)
```
