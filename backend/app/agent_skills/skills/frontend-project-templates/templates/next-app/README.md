# Next.js Template

这是一个基于 **Next.js 16** 的前端模板，默认集成了 **React 19**、**TypeScript**、**Tailwind CSS v4** 和 **shadcn/ui**，适合快速启动中后台或 AI 产品前端项目。

## 技术栈

- Next.js `16.1.7`（App Router）
- React `19.2.4`
- TypeScript `5.9.x`
- Tailwind CSS `4.2.x`
- shadcn/ui `4.7.x` + Radix UI + Lucide Icons
- ESLint + Prettier（含 Tailwind 排序插件）

## 常用命令

```bash
# 本地开发（Turbopack）
npm run dev

# 生产构建
npm run build

# 启动生产服务
npm run start

# 代码检查
npm run lint

# 格式化（ts/tsx）
npm run format

# 类型检查
npm run typecheck
```

## shadcn/ui 组件

添加组件：

```bash
npx shadcn@latest add button
```

组件会生成在 `components/ui` 目录下，可直接按如下方式引入：

```tsx
import { Button } from "@/components/ui/button";
```

## 目录建议

- `app/`：路由与页面（App Router）
- `components/`：通用组件与 UI 组件
- `lib/`：工具函数（如 `cn`）
- `public/`：静态资源
