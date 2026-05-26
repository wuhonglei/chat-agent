#!/usr/bin/env bash
# lint-staged 会把匹配到的路径作为参数追加；在调用 vp check 前剔除 .cursor/skills/ 与 backend/skills/。
set -euo pipefail
files=()
for f in "$@"; do
  [[ "$f" == *".cursor/skills/"* ]] && continue
  [[ "$f" == *"backend/skills/"* ]] && continue

  if [[ "$f" == frontend/* ]]; then
    f="${f#frontend/}"
  fi

  [[ "$f" == /* ]] && continue
  [[ "$f" == ../* ]] && continue
  [[ "$f" == .vscode/* ]] && continue
  [[ -f "$f" ]] || continue

  files+=("$f")
done
((${#files[@]} == 0)) && exit 0
exec vp check --fix "${files[@]}"
