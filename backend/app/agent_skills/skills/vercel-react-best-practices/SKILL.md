---
name: vercel-react-best-practices
description: 采用 Vercel React 最佳实践，优化数据获取、渲染性能与包体积。
---

# Vercel React Best Practices Skill

适用场景：
- 用户要求优化 React 应用性能、加载速度、渲染行为或包体积。
- 用户要求按工程化规范改造 React 代码结构与数据获取方式。

安装命令：
- `npx skills add vercel-labs/agent-skills --skill vercel-react-best-practices`

执行步骤：
1. 以“先定位瓶颈、再实施改造”为原则，优先识别网络瀑布与重复请求。
2. 按 SSR 性能、客户端数据获取、重渲染控制、Bundle 体积治理等维度分步优化。
3. 组件改造优先保证行为一致，再做性能提升，避免引入功能回归。
4. 每次改造后给出可验证的收益点（如请求合并、重渲染减少、包体积下降方向）。

约束：
- 不以牺牲可读性为代价进行过度微优化。
- 不引入与当前栈冲突的状态管理或数据层方案。
- 涉及缓存、预取、懒加载时，明确失效与回退策略。
