---
name: frontend-project-templates
description: Bootstraps new frontend repositories by copying curated starter files from this skill's templates directory (Next.js App Router scaffold). Use when the user asks to create a new frontend project, greenfield Next.js app, or scaffold React/TypeScript web app from a template instead of improvising file layout.
---

# Frontend project templates

## When to use this skill

Use when the user wants a **new** frontend codebase (for example Next.js) and a **known-good starting layout** is preferable to generating structure from memory.

## Template layout

All templates live next to this file:

| Template | Path | Stack |
|----------|------|--------|
| Next.js (App Router, TypeScript) | [templates/next-app](templates/next-app) | Next.js, React, TypeScript |

## Workflow

1. **Choose template** — Match the user's framework (start with `next-app` for Next.js requests).
2. **Copy files** — Copy the chosen template directory contents into the user's target project root (new folder or existing repo), preserving `app/`, config files, and `package.json`.
3. **Install** — In the project root run the package manager install (`pnpm install`, `npm install`, or `yarn`) per user preference; default to **pnpm** if unspecified.
4. **Align versions** — If the user needs the latest major line, run the official scaffold (`create-next-app`) in a temp dir and diff `package.json` / lockfile, or bump ranges in the copied `package.json` before install. The template favors current stable caret ranges.
5. **Polish** — After copy, apply [next-best-practices](../next-best-practices/SKILL.md) for routing, RSC boundaries, and data patterns.

## Optional: official CLI first

If the user explicitly wants the default Vercel wizard (turbopack, eslint choice, src dir, etc.), run `create-next-app` in the target path, then **merge** any project conventions from `templates/next-app` (for example `app/globals.css` tokens, `tsconfig` paths) instead of overwriting their choices.

## Do not

- Do not treat these templates as a substitute for dependency installs or for Next.js docs when APIs change; verify against Context7 or project `next-best-practices` when unsure.
- Do not copy unrelated skills' large reference trees into the user's app; only use files under `templates/<name>/`.
