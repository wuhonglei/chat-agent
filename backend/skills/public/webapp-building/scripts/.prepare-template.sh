#!/bin/bash
# Maintainer-only: refresh pnpm-lock.yaml in scripts/template (optional).
# Agents normally run init-webapp.sh, which runs pnpm install in workspace.
set -e

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_PATH="$SCRIPTS_DIR/template"

! command -v pnpm &>/dev/null && { echo "Error: pnpm not found"; exit 1; }

cd "$TEMPLATE_PATH"
echo "Installing template dependencies (maintainer, pnpm)..."
pnpm install

echo ""
echo "Template ready: $TEMPLATE_PATH"
echo "Commit pnpm-lock.yaml; node_modules stays gitignored."
echo ""
