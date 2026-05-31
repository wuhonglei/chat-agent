#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="$1"

_update_html_title() {
  local file="$1"
  local title="$2"
  local escaped
  escaped=$(printf '%s\n' "$title" | sed 's/[\/&]/\\&/g')
  # Do not store "sed -i ''" in a variable — expanding it breaks on macOS and
  # leaves a stray backup file named index.html''.
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/<title>.*<\/title>/<title>${escaped}<\/title>/" "$file"
  else
    sed -i "s/<title>.*<\/title>/<title>${escaped}<\/title>/" "$file"
  fi
}

# Shell MCP cwd is the conversation workspace root (physical on local, virtual in Docker).
# Use a relative default so local mode does not write to non-existent /mnt/... paths.
DEFAULT_PROJECT_PATH="./app"
PROJECT_PATH=${PROJECT_PATH:-$DEFAULT_PROJECT_PATH}
TEMP_PATH=${TEMP_PATH:-"/tmp/temp-webapp-$$"}

_resolve_project_path() {
  local target="$1"
  # Local sandbox: env may still carry virtual paths that are not on the host filesystem.
  if [[ ! -e "$target" && "$target" == /mnt/user-data/workspace/* ]]; then
    local suffix="${target#/mnt/user-data/workspace/}"
    suffix="${suffix#/}"
    target="./${suffix}"
  fi
  mkdir -p "$target"
  (cd "$target" && pwd)
}

# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

! command -v pnpm &>/dev/null && { echo "Error: pnpm not found (install via npm i -g pnpm or use project Docker image)"; exit 1; }
[[ -z "$1" ]] && {
  echo "Usage: $0 <website-title>"
  echo "  Default PROJECT_PATH=${DEFAULT_PROJECT_PATH} (under shell workspace cwd)"
  echo "  Virtual equivalent: /mnt/user-data/workspace/app"
  exit 1
}

PROJECT_PATH="$(_resolve_project_path "$PROJECT_PATH")"

# ─────────────────────────────────────────────────────────────────────────────
# Project creation
# ─────────────────────────────────────────────────────────────────────────────

echo "Creating project: $PROJECT_PATH"
rm -rf "$TEMP_PATH"
mkdir -p "$TEMP_PATH"

# Copy including dotfiles (.npmrc, .gitignore); plain "/*" skips them.
cp -r "$SCRIPTS_DIR/template/." "$TEMP_PATH/"
_update_html_title "$TEMP_PATH/index.html" "$PROJECT_NAME"
cp -r "$TEMP_PATH/." "$PROJECT_PATH/"
rm -rf "$TEMP_PATH"

# ─────────────────────────────────────────────────────────────────────────────
# Dependencies
# ─────────────────────────────────────────────────────────────────────────────

echo "Installing dependencies in $PROJECT_PATH (pnpm) ..."
(cd "$PROJECT_PATH" && pnpm install --frozen-lockfile)

# ─────────────────────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────────────────────

echo "Using pnpm, Node.js 20+, Tailwind CSS v3.4.19, and Vite"
echo ""
echo "Tailwind CSS has been set up with the shadcn theme"
echo ""
echo "Setup complete: $PROJECT_PATH"
echo ""
echo "Next steps:"
echo "  cd $PROJECT_PATH"
echo "  pnpm run dev    # optional local preview"
echo "  pnpm run build  # production build -> dist/"
echo "  rm -rf /mnt/user-data/outputs/app-dist && mkdir -p /mnt/user-data/outputs/app-dist"
echo "  cp -r dist/. /mnt/user-data/outputs/app-dist/  # deliverable (paths rewritten in local shell)"
echo ""
echo "Components (40+):"
echo "  accordion, alert-dialog, alert, aspect-ratio, avatar, badge, breadcrumb,"
echo "  button-group, button, calendar, card, carousel, chart, checkbox, collapsible,"
echo "  command, context-menu, dialog, drawer, dropdown-menu, empty, field, form,"
echo "  hover-card, input-group, input-otp, input, item, kbd, label, menubar,"
echo "  navigation-menu, pagination, popover, progress, radio-group, resizable,"
echo "  scroll-area, select, separator, sheet, sidebar, skeleton, slider, sonner,"
echo "  spinner, switch, table, tabs, textarea, toggle-group, toggle, tooltip"
echo ""
echo "Usage:"
echo "  import { Button } from '@/components/ui/button'"
echo "  import { Card, CardHeader, CardTitle } from '@/components/ui/card'"
echo ""
echo "Structure:"
echo "  src/sections/        Page sections"
echo "  src/hooks/           Custom hooks"
echo "  src/types/           Type definitions"
echo "  src/App.css          Styles specific to the webapp"
echo "  src/App.tsx          Root React component"
echo "  src/index.css        Global styles"
echo "  src/main.tsx         Entry point"
echo "  index.html           HTML shell"
echo "  tailwind.config.js   Tailwind theme and plugins"
echo "  vite.config.ts       Vite dev/build config"
echo "  postcss.config.js    PostCSS pipeline"
