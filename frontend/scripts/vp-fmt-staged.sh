#!/usr/bin/env bash
# lint-staged 会把匹配到的路径作为参数追加；在调用 vp fmt 前剔除任意路径段下的 .cursor/skills/，
# 避免 fmt.ignorePatterns 把它们全部滤掉后出现「Expected at least one target file」。
set -euo pipefail
files=()
for f in "$@"; do
  [[ "$f" == *".cursor/skills/"* ]] && continue

  # lint-staged 默认给的是 repo root 相对路径；本脚本在 frontend 目录下执行，
  # 需要把前缀 frontend/ 规整掉，否则会变成指向不存在的路径，进而触发 vp fmt 报错。
  if [[ "$f" == frontend/* ]]; then
    f="${f#frontend/}"
  fi

  # 只处理 frontend 目录内的文件（规避误传入其它包路径）
  [[ "$f" == /* ]] && continue
  [[ "$f" == ../* ]] && continue

  # vp fmt 通常不会处理编辑器配置目录；传入会导致 “Expected at least one target file”
  [[ "$f" == .vscode/* ]] && continue

  # 只保留真实存在的文件；vp fmt 对“全部被忽略/不存在”的输入会报错
  [[ -f "$f" ]] || continue

  files+=("$f")
done
((${#files[@]} == 0)) && exit 0
exec vp fmt "${files[@]}"
