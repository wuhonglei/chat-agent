---
name: shadcn/ui
description: 自动识别项目配置并按 shadcn/ui 官方工作流生成与维护组件。
---

# shadcn/ui Skill

适用场景：
- 用户要求基于 shadcn/ui 新增、改造或排查组件。
- 用户要求初始化或校准 shadcn 相关配置（主题、别名、registry、图标库）。

安装命令：
- `pnpm dlx skills add shadcn/ui`

执行步骤：
1. 每次交互先运行 `shadcn info --json`，识别框架类型、Tailwind 版本、路径别名、基础库（radix/base）与图标库。
2. 优先使用 shadcn 官方 CLI 与 registry 工作流，不手写偏离官方结构的脚手架代码。
3. 生成组件时保持主题变量与设计令牌一致，避免破坏现有样式体系。
4. 涉及组件升级或替换时，先保证 API 兼容，再处理样式和交互细节。

约束：
- 不假设项目一定使用同一套基础库，必须以 `shadcn info --json` 实际输出为准。
- 不绕过 CLI 直接复制未知来源实现。
- 新增组件前先检查是否已有同名或功能重复组件。
