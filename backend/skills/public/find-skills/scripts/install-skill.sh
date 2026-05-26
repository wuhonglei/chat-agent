#!/bin/bash

# Install a skill and link it to the user's custom skills directory.
# Usage: install-skill.sh <owner/repo@skill-name>
# Example: install-skill.sh vercel-labs/agent-skills@vercel-react-best-practices
#
# Target directory (first match):
#   USER_SKILLS_DIR — e.g. /mnt/skills/custom in Docker sandbox

set -e

if [[ -z "$1" ]]; then
  echo "Usage: $0 <owner/repo@skill-name>"
  echo "Example: $0 vercel-labs/agent-skills@vercel-react-best-practices"
  exit 1
fi

FULL_SKILL_NAME="$1"

SKILL_NAME="${FULL_SKILL_NAME##*@}"

if [[ -z "$SKILL_NAME" || "$SKILL_NAME" == "$FULL_SKILL_NAME" ]]; then
  echo "Error: Invalid skill format. Expected: owner/repo@skill-name"
  exit 1
fi

if [[ -n "${USER_SKILLS_DIR:-}" ]]; then
  SKILL_TARGET="$USER_SKILLS_DIR"
else
  echo "Error: USER_SKILLS_DIR is not set (expected /mnt/skills/custom in sandbox)"
  exit 1
fi

SKILL_SOURCE="$HOME/.agents/skills/$SKILL_NAME"

npx skills add "$FULL_SKILL_NAME" -g -y > /dev/null 2>&1

if [[ ! -d "$SKILL_SOURCE" ]]; then
  echo "Skill '$SKILL_NAME' installation failed"
  exit 1
fi

mkdir -p "$SKILL_TARGET"
ln -sf "$SKILL_SOURCE" "$SKILL_TARGET/$SKILL_NAME"

echo "Skill '$SKILL_NAME' installed successfully at $SKILL_TARGET/$SKILL_NAME"
echo "Virtual path: /mnt/skills/custom/$SKILL_NAME/"
