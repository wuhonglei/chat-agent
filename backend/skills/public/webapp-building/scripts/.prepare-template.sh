#!/bin/bash
# Maintainer-only: pre-install deps into scripts/template (optional).
# Agents normally run init-webapp.sh, which runs npm install in workspace.
set -e

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_PATH="$SCRIPTS_DIR/template"

cd "$TEMPLATE_PATH"
echo "Installing template dependencies (maintainer)..."
npm install

echo ""
echo "Template ready: $TEMPLATE_PATH"
echo "Commit package-lock.json; node_modules stays gitignored."
echo ""
