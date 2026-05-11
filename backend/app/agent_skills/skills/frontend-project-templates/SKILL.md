---
name: frontend-project-templates
description: 通过复制本技能 templates 目录中的精选起始文件（Next.js App Router 脚手架）来初始化新的前端仓库。当用户要求创建新的前端项目、从零开始的 Next.js 应用，或希望基于模板搭建 React/TypeScript Web 应用（而不是临时拼凑目录结构）时使用。
---

# 前端项目模板

## 何时使用该技能

当用户希望创建一个**新的**前端代码库（例如 Next.js），并且更适合使用**经过验证的起始结构**，而不是基于经验临时生成目录时，使用此技能。

## 模板布局

所有模板都与该文件位于同级目录：

| Template | Path | Stack |
|----------|------|--------|
| Next.js (App Router, TypeScript) | [templates/next-app](templates/next-app) | Next.js, React, TypeScript |

## 工作流程

1. **选择模板** —— 匹配用户所需框架（Next.js 需求优先使用 `next-app`）。
2. **复制文件** —— 将所选模板目录内容复制到用户目标项目根目录（新目录或现有仓库均可），保留 `app/`、配置文件和 `package.json`。
3. **安装依赖** —— 在项目根目录按用户偏好执行包管理器安装（`pnpm install`、`npm install` 或 `yarn`）；若未指定，默认使用 **pnpm**。
4. **对齐版本** —— 若用户需要最新主版本，可在临时目录运行官方脚手架（`create-next-app`）并比对 `package.json` / lockfile，或在安装前调整已复制 `package.json` 中的版本范围。该模板默认采用当前稳定版本的 caret 范围。
5. **完善细节** —— 复制完成后，结合 [next-best-practices](../next-best-practices/SKILL.md) 优化路由、RSC 边界与数据获取模式。

## 可选：优先使用官方 CLI

如果用户明确希望使用 Vercel 默认向导（如 turbopack、eslint 选项、src 目录等），先在目标路径执行 `create-next-app`，然后将 `templates/next-app` 中的项目约定（例如 `app/globals.css` 设计变量、`tsconfig` 路径别名）**合并**进去，而不是覆盖用户在向导中的选择。

## 禁止事项

- 不要把这些模板当作依赖安装步骤的替代，也不要在 Next.js API 变化时跳过官方文档核对；不确定时请通过 Context7 或项目内 `next-best-practices` 进行确认。
- 不要把其他无关技能中的大型参考目录复制到用户应用中；仅使用 `templates/<name>/` 下的文件。
