---
name: webapp-building
description: Tools for building modern React webapps with TypeScript, Tailwind CSS and shadcn/ui. Best suited for applications with complex UI components and state management.
---

# WebApp Building

**Stack**: React + TypeScript + Vite + Tailwind CSS + shadcn/ui

## Virtual paths (chat-agent VFS)

| Purpose | Path |
|---------|------|
| Project scaffold & development | `/mnt/user-data/workspace/app/` |
| Built static site (deliverable) | `/mnt/user-data/outputs/app-dist/` |
| Init script (read-only skill) | `/mnt/skills/public/webapp-building/scripts/init-webapp.sh` |

- Do all temporary work under `workspace/` (source, `node_modules`, intermediate builds).
- Copy the production `dist/` to `outputs/` when ready, then use `present_file` to show it to the user.

## Workflow

1. Run `init-webapp.sh` — scaffold project in `/mnt/user-data/workspace/app/`
2. Edit source under `src/`
3. `npm run build` in the workspace project
4. Copy `dist/` to `/mnt/user-data/outputs/app-dist/` and `present_file` the deliverable

## Quick Start

### 1. Initialize

```bash
bash /mnt/skills/public/webapp-building/scripts/init-webapp.sh "<website-title>"
cd /mnt/user-data/workspace/app
```

Override install location (optional):

```bash
PROJECT_PATH=/mnt/user-data/workspace/my-app \
  bash /mnt/skills/public/webapp-building/scripts/init-webapp.sh "<website-title>"
```

**AI agent notes**

- Shell tool cwd is the conversation **workspace root**; `init-webapp.sh` defaults to `./app` (Docker: `/mnt/user-data/workspace/app`; local: physical path under `data/user_data/.../workspace/app`)
- Override with `PROJECT_PATH=./my-app` or a virtual path on the command line (local shell rewrites `/mnt/user-data/...` in the command string)
- Script is non-interactive; runs `npm install` after copying the template
- Skill directory is read-only; never write generated app files under `/mnt/skills/`

This creates a fully configured project with:

- React + TypeScript (Vite)
- Tailwind CSS 3.4.19 with shadcn/ui theming
- Path aliases (`@/`) configured
- 40+ shadcn/ui components pre-installed
- Radix UI dependencies included
- Production build via Vite
- Node 20+ compatibility

### 2. Develop

Edit files under `/mnt/user-data/workspace/app/src/`:

- Page sections → `src/sections/`
- Custom hooks → `src/hooks/`
- Types → `src/types/`

Dev server (optional):

```bash
cd /mnt/user-data/workspace/app && npm run dev
```

### 3. Build

```bash
cd /mnt/user-data/workspace/app && npm run build 2>&1
```

**Build output** (`dist/` inside workspace):

- `index.html` — entry point
- `assets/index-[hash].js` — bundled JS
- `assets/index-[hash].css` — bundled CSS
- Optimized images, fonts, and other assets

### 4. Deliver

Copy the production build to outputs, then present to the user:

```bash
rm -rf /mnt/user-data/outputs/app-dist
cp -r /mnt/user-data/workspace/app/dist /mnt/user-data/outputs/app-dist
```

Use `present_file` on files under `/mnt/user-data/outputs/app-dist/` (e.g. `index.html`).

If the user needs the full source repo as a deliverable, zip or copy the workspace project into `outputs/` instead of (or in addition to) `dist/`.

## Debugging

1. Fix source files in `workspace/app/src/`
2. `npm run build`
3. Verify `workspace/app/dist/`
4. Re-copy to `outputs/app-dist/` and present again

## Maintainer: refresh template dependencies

Optional — run locally when updating the template, not required for agents:

```bash
bash /mnt/skills/public/webapp-building/scripts/.prepare-template.sh
```

## Reference

- [shadcn/ui Components](https://ui.shadcn.com/docs/components)
