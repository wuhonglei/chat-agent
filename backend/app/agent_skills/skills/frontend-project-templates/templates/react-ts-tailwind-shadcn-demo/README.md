# React + TypeScript + Tailwind + shadcn/ui Demo

一个基于 `Vite` 的前端示例项目，集成了 `React 19`、`TypeScript 6`、`Tailwind CSS 3` 与 `shadcn/ui` 风格体系，可作为轻量起步模板。

## 技术栈

- 构建与开发：`Vite 8`、`@vitejs/plugin-react`
- 框架：`React 19`、`React DOM 19`
- 语言与类型：`TypeScript 6`
- 样式：`Tailwind CSS 3`、`PostCSS`、`Autoprefixer`
- UI 相关：`shadcn`、`@base-ui/react`、`lucide-react`
- 工具库：`clsx`、`class-variance-authority`、`tailwind-merge`
- 动画与字体：`tw-animate-css`、`@fontsource-variable/geist`
- 代码检查：`ESLint 10` + `typescript-eslint`

## 快速开始

```bash
npm install
npm run dev
```

默认开发地址：`http://localhost:5173`

## 可用脚本

- `npm run dev`：启动开发服务器（HMR）
- `npm run build`：TypeScript 构建检查并打包
- `npm run preview`：本地预览生产构建
- `npm run lint`：运行 ESLint

## 项目结构

```txt
.
├─ @/
│  ├─ components/
│  │  └─ ui/
│  │     └─ button.tsx
│  └─ lib/
│     └─ utils.ts
├─ src/
│  ├─ App.tsx
│  ├─ App.css
│  ├─ index.css
│  ├─ main.tsx
│  └─ assets/
│     ├─ react.svg
│     └─ vite.svg
├─ index.html
├─ package.json
├─ tsconfig.json
├─ tsconfig.app.json
├─ tsconfig.node.json
├─ eslint.config.js
├─ tailwind.config.js
├─ postcss.config.js
├─ vite.config.ts
└─ components.json
```

## 样式与主题说明

- `tailwind.config.js` 启用了 `class` 模式暗黑主题（`darkMode: ["class"]`）。
- `src/index.css` 引入了 `tw-animate-css` 与 `shadcn/tailwind.css`，并通过 CSS Variables 管理主题色。
- 字体使用 `Geist Variable`，在 `src/index.css` 中通过 `--font-sans` 统一设置。

## shadcn/ui 配置

`components.json` 已配置：

- 样式风格：`base-nova`
- 图标库：`lucide`
- Tailwind 入口：`tailwind.config.js` + `src/index.css`
- 路径别名：`@` -> `src`

在 `vite.config.ts` 中也已配置 `@` 别名，便于在组件中使用 `@/` 路径导入。
