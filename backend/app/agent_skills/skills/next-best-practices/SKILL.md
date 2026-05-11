---
name: next-best-practices
description: 采用 Next.js 最佳实践规范文件约定、RSC 边界与数据获取模式。
---

# Next.js Best Practices Skill

适用场景：
- 用户要求在 Next.js 项目中新增页面、路由、数据获取逻辑或架构改造。
- 用户要求优化 App Router 约定、RSC 边界、服务端与客户端职责划分。

安装命令：
- `npx skills add vercel-labs/next-skills --skill next-best-practices`

执行步骤：
1. 先核对文件约定（路由层级、layout、loading、error、not-found）再开始编码。
2. 明确 RSC 与 Client Component 边界，避免不必要的客户端下沉。
3. 按 Next.js 推荐的数据模式组织请求、缓存与重验证策略。
4. 改造中优先保证 SEO、首屏性能和可维护性。

约束：
- 不混用与当前路由模式冲突的旧约定。
- 不在客户端组件中放置应在服务端执行的数据与安全逻辑。
- 涉及缓存与重验证时，明确触发条件与失效范围。
