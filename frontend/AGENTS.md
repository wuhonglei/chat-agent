<!--VITE PLUS START-->

# 使用 Vite+：面向 Web 的统一工具链

本项目使用 Vite+：一个构建在 Vite、Rolldown、Vitest、tsdown、Oxlint、Oxfmt 与 Vite Task 之上的统一工具链。Vite+ 将运行时管理、包管理与前端工具封装到一个名为 `vp` 的全局 CLI 中。Vite+ 与 Vite 不同，但会通过 `vp dev` 与 `vp build` 来调用 Vite。

## Vite+ 工作流

`vp` 是一个覆盖完整开发生命周期的全局可执行程序。运行 `vp help` 查看命令列表，运行 `vp <command> --help` 查看某个具体命令的说明。

### Start

- create - 从模板创建新项目
- migrate - 将现有项目迁移到 Vite+
- config - 配置 hooks 与 agent 集成
- staged - 对暂存区文件运行代码检查工具（linter）
- install (`i`) - 安装依赖
- env - 管理 Node.js 版本

### Develop

- dev - 启动开发服务器
- check - 执行格式化、lint 与 TypeScript 类型检查
- lint - 运行代码检查（lint）
- fmt - 运行格式化
- test - 运行测试

### Execute

- run - 运行 monorepo 任务
- exec - 执行本地 `node_modules/.bin` 中的命令
- dlx - 无需安装为依赖即可执行某个包的二进制命令
- cache - 管理任务缓存

### Build

- build - 构建生产版本
- pack - 构建库（libraries）
- preview - 预览生产构建产物

### Manage Dependencies

Vite+ 会通过 `package.json` 中的 `packageManager` 字段或各包管理器专用的 lockfile，自动识别并封装底层的包管理器（如 pnpm、npm 或 Yarn）。

- add - 添加依赖包
- remove (`rm`, `un`, `uninstall`) - 移除依赖包
- update (`up`) - 将依赖升级到最新版本
- dedupe - 依赖去重
- outdated - 检查过期依赖
- list (`ls`) - 列出已安装的包
- why (`explain`) - 显示某个包为何会被安装
- info (`view`, `show`) - 查看注册表中的包信息
- link (`ln`) / unlink - 管理本地包链接
- pm - 将命令转发给底层包管理器

### Maintain

- upgrade - 将 `vp` 自身升级到最新版本

这些命令会映射到对应的底层工具。例如，`vp dev --port 3000` 会启动 Vite 的开发服务器，其行为与直接使用 Vite 一致；`vp test` 会通过内置的 Vitest 运行 JavaScript 测试。你可以通过 `vp --version` 查看所有工具的版本信息，这在排查文档差异、功能特性与 bug 时很有帮助。

## 常见坑点

- **直接使用包管理器：** 不要直接使用 pnpm、npm 或 Yarn。Vite+ 可以处理所有包管理操作。
- **始终用 Vite+ 命令运行工具：** 不要尝试运行 `vp vitest` 或 `vp oxlint`，这些命令不存在。请改用 `vp test` 与 `vp lint`。
- **运行脚本：** Vite+ 命令优先级高于 `package.json` 的 scripts。如果 `scripts` 中定义了 `test` 且与内置 `vp test` 命令冲突，请使用 `vp run test` 来运行该脚本。
- **不要直接安装 Vitest / Oxlint / Oxfmt / tsdown：** Vite+ 已封装这些工具，禁止直接安装。你也无法通过安装最新版来单独升级它们；请始终使用 Vite+ 命令。
- **一次性二进制执行请用 Vite+ 封装：** 使用 `vp dlx`，不要使用包管理器自带的 `dlx`/`npx` 命令。
- **从 `vite-plus` 导入 JavaScript 模块：** 不要从 `vite` 或 `vitest` 导入；所有模块都应从项目依赖 `vite-plus` 导入。例如：`import { defineConfig } from 'vite-plus';` 或 `import { expect, test, vi } from 'vite-plus/test';`。为导入测试工具而安装 `vitest` 是不允许的。
- **类型感知的 Lint：** 无需安装 `oxlint-tsgolint`，直接使用 `vp lint --type-aware` 即可开箱即用。

## Agent 复核清单

- [ ] 拉取远端变更后、开始开发前先运行 `vp install`。
- [ ] 运行 `vp check` 与 `vp test` 验证改动。
<!--VITE PLUS END-->
