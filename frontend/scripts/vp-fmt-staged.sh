#!/usr/bin/env bash
# lint-staged 会把匹配到的路径作为参数追加；在调用 vp fmt 前剔除任意路径段下的 .cursor/skills/，
# 避免 fmt.ignorePatterns 把它们全部滤掉后出现「Expected at least one target file」。
set -euo pipefail
files=()
for f in "$@"; do
  [[ "$f" == *".cursor/skills/"* ]] && continue
  files+=("$f")
done
((${#files[@]} == 0)) && exit 0
exec vp fmt "${files[@]}"
