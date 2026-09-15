---
name: webapp-building
description: Tools for building modern React webapps with TypeScript, Tailwind CSS and shadcn/ui. Best suited for applications with complex UI components and state management. Layout is desktop-first; pages must still work on phones.
---

# WebApp Building

**Stack**: React + TypeScript + Vite + Tailwind CSS + shadcn/ui + **pnpm**

## Virtual paths (chat-agent VFS)

| Purpose | Path |
|---------|------|
| Project scaffold & development | `/mnt/user-data/workspace/app/` |
| Built static site (deliverable) | `/mnt/user-data/outputs/app-dist/` |
| Init script (read-only skill) | `/mnt/skills/public/webapp-building/scripts/init-webapp.sh` |

- Do all temporary work under `workspace/` (source, `node_modules`, intermediate builds).
- Copy the production `dist/` to `outputs/` when ready.

## Workflow

1. Run `init-webapp.sh` — scaffold project in `/mnt/user-data/workspace/app/`
2. Edit source under `src/` (desktop-first layout; phone-compatible, see below)
3. `pnpm run build` in the workspace project
4. Copy `dist/` to `/mnt/user-data/outputs/app-dist/`, then call `present_files`

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
- Uses **pnpm** with `pnpm-lock.yaml` and `pnpm install --frozen-lockfile` (requires `pnpm` in sandbox; backend Docker image includes it)
- `.npmrc` points at `https://registry.npmmirror.com/`
- Skill directory is read-only; never write generated app files under `/mnt/skills/`

This creates a fully configured project with:

- React + TypeScript (Vite)
- Tailwind CSS 3.4.19 with shadcn/ui theming
- Viewport meta + `useIsMobile` (768px) for phone compatibility
- Path aliases (`@/`) configured
- 40+ shadcn/ui components pre-installed
- Radix UI dependencies included
- Production build via Vite
- Node 20+ and pnpm 9 compatibility

### 2. Develop

Edit files under `/mnt/user-data/workspace/app/src/`:

- Page sections → `src/sections/`
- Custom hooks → `src/hooks/`
- Types → `src/types/`

Dev server (optional):

```bash
cd /mnt/user-data/workspace/app && pnpm run dev
```

### Layout: desktop-first, phone-compatible

**PC is the primary experience.** Design and ship the desktop layout as the source of truth. Phone support is required compatibility — the same site must remain usable on a narrow screen, not a separate mobile product.

Do not ship a stretched mobile page on desktop, and do not hide core desktop features just to simplify the phone view.

**Desktop (≥ 768px / `md`) — default**

- Canonical layout: multi-column, sidebar, hover affordances, generous spacing.
- Unprefixed Tailwind classes describe this layout (`grid-cols-3`, `flex-row`, fixed sidebar).

**Phone (< 768px) — compatible**

- Same information architecture: stack, wrap, or collapse — do not invent a different app.
- Use `max-md:` (and `max-sm:` if needed) for phone overrides. Example: `grid-cols-3 max-md:grid-cols-1`.
- No horizontal overflow (`overflow-x-hidden` on the page shell if needed); images/media `max-w-full h-auto`.
- Collapse sidebar / dense nav with `useIsMobile` + Sheet (`src/hooks/use-mobile.ts`, `src/components/ui/sidebar.tsx`).
- Essential actions must work without hover; tap targets ≥ 44px.
- Keep the viewport tag in `index.html`: `width=device-width, initial-scale=1.0`.

**Do not**

- Switch to a mobile-first visual (single-column stretched to 1440px, huge type, app-bar-only chrome) unless the user asked for a mobile app.
- Rely on hover-only for primary actions.
- Use a second breakpoint strategy; 768px matches `useIsMobile`.

### 3. Build

```bash
cd /mnt/user-data/workspace/app && pnpm run build 2>&1
```

**Build output** (`dist/` inside workspace):

- `index.html` — entry point
- `assets/index-[hash].js` — bundled JS
- `assets/index-[hash].css` — bundled CSS
- Optimized images, fonts, and other assets

### 4. Deliver

Copy the production build to outputs, then present it to the user.

**Step A — copy build artifacts**

```bash
rm -rf /mnt/user-data/outputs/app-dist
mkdir -p /mnt/user-data/outputs/app-dist
# Copy directory contents (not the folder itself) for predictable layout.
cp -r /mnt/user-data/workspace/app/dist/. /mnt/user-data/outputs/app-dist/
```

**Step B — present deliverables (`present_files` tool)**

After the copy succeeds, call the `present_files` tool so the client can show the deliverable and open the project preview panel.

```json
{
  "filepaths": ["/mnt/user-data/outputs/app-dist/index.html"]
}
```

Rules:

- Only virtual paths under `/mnt/user-data/outputs/` are accepted (not `workspace/` or host paths).
- Each entry must be an **existing file** (directories are rejected).
- For a static site, presenting `index.html` is enough; the UI exposes file browsing and zip download.
- Briefly describe what was built (pages, features) in your reply after presenting.

**Step C — publish a public URL (`publish_site` tool, only if asked)**

Call `publish_site` only when the user explicitly wants a public URL, external share, or domain access. Do not publish just because the build succeeded.

```json
{
  "source": "/mnt/user-data/outputs/app-dist"
}
```

If the deliverable is a simple page at `outputs/index.html` instead of a Vite build, pass `"source": "/mnt/user-data/outputs"` (or `/mnt/user-data/outputs/index.html`). Omit `source` to let the server pick `app-dist` when it exists, otherwise `outputs/index.html`.

Rules:

- Do not pass a `slug`. The server generates or reuses one for this conversation.
- Do not call `/api/sites/me` and do not invent `{slug}.apps...` URLs.
- Tell the user the returned `url` verbatim. Do not retry just to change the slug.
- Repeating `publish_site` in the same conversation reuses the slug and publishes a new version.

## Debugging

1. Fix source files in `workspace/app/src/`
2. `pnpm run build`
3. Verify `workspace/app/dist/`
4. Re-copy to `outputs/app-dist/` and call `present_files` again with `/mnt/user-data/outputs/app-dist/index.html`

## Maintainer: refresh template dependencies

Optional — run locally when updating the template, not required for agents:

```bash
bash /mnt/skills/public/webapp-building/scripts/.prepare-template.sh
```

## Reference

- [shadcn/ui Components](https://ui.shadcn.com/docs/components)
