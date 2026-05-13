---
name: gh-pr-to-main
description: >-
  Creates a GitHub pull request with base branch main using the GitHub CLI (gh),
  and builds the PR title and body from commit messages between main and the
  current branch HEAD. Use when opening a PR to main, using gh pr create, or when
  the user wants a PR description derived from commits since main.
---

# 使用 gh 向 main 开 PR 并基于 commit 生成说明

## 前置条件

- 已安装并登录 [GitHub CLI](https://cli.github.com/)：`gh auth status` 成功。
- 当前不在 `main` 上；当前分支已推送到 `origin`（若未推送，先 `git push -u origin HEAD`）。
- 基线分支名为 `main`（若仓库默认分支不同，将下文 `main` / `origin/main` 换成实际名称）。

## 工作流

### 1. 同步并确认基线

在仓库根目录执行：

```bash
git fetch origin main
```

优先用 **`origin/main`** 作为对比基线（避免本地 `main` 落后远端）。若确定本地 `main` 已是最新，也可用 `main`。

### 2. 列出相对 main 的新增提交

仅标题（常用作 PR 正文条目）：

```bash
git log origin/main..HEAD --no-merges --pretty=format:"- %s"
```

需要完整 commit message（含 body）时：

```bash
git log origin/main..HEAD --no-merges --pretty=format:"### %s%n%n%b%n"
```

若输出为空，说明没有领先 `origin/main` 的提交，**不要**创建 PR。

### 3. 生成 PR 标题与正文

- **标题**：单行、概括本次变更；若只有一个提交，可用该提交第一行主题；多个提交时合并主题为一句（避免把整段日志粘成标题）。
- **正文**：用第 2 步的输出作为基础，整理为 Markdown：
  - 用列表列出各提交的 `subject`；
  - 若有重要 `body`，可放在对应条目下或单独「说明」小节；
  - 可酌情补充测试方式、破坏性变更、关联 issue（`Closes #123`）等。

项目若约定中文 commit（见仓库 `.cursorrules`），PR 标题与正文保持与 commit 语言一致即可。

### 4. 先检查当前分支是否已有 PR

先查看当前分支到 `main` 的 PR（若存在会返回状态）：

```bash
gh pr view --json number,title,url,state,isDraft,mergedAt,baseRefName,headRefName
```

按状态处理：

- `OPEN`：不要重复创建，直接复用已有 PR（必要时 `gh pr edit` 更新标题/正文）。
- `MERGED`：说明该分支历史上的 PR 已合并；若当前又有新提交需要继续合并，创建一个**新的** PR。
- `CLOSED` 且未合并：按团队约定选择 `gh pr reopen` 或新建 PR（默认建议新建，避免历史讨论混淆）。
- 命令报错 `no pull requests found`：说明当前分支尚无 PR，直接新建。

### 5. 使用 gh 创建（或重新创建）PR

当前分支已推送后：

```bash
gh pr create --base main --head "$(git rev-parse --abbrev-ref HEAD)" --title "PR 标题" --body "$(cat <<'EOF'
PR 正文 Markdown
EOF
)"
```

一行内联正文时注意转义；复杂正文可写入临时文件后：

```bash
gh pr create --base main --title "PR 标题" --body-file /path/to/pr-body.md
```

交互式（仍会弹出编辑器，可把已拟好的标题/正文贴入）：

```bash
gh pr create --base main
```

**不要用** `--fill` 作为唯一依据多提交场景的说明：它主要取首个提交，与「汇总 `main..HEAD` 全部 commit message」的目标不一致。

## 自检清单

- [ ] `origin/main..HEAD` 至少有一个提交
- [ ] 分支已 `git push` 到 `origin`
- [ ] `--base main` 与仓库默认合并目标一致
- [ ] 已执行 `gh pr view` 检查当前分支 PR 状态（OPEN / MERGED / CLOSED）
- [ ] 标题概括整体，正文反映各 commit（或合并后的清晰说明）

## 常见问题

| 情况 | 处理 |
|------|------|
| `gh: command not found` | 安装 `gh` 并 `gh auth login` |
| `pull request already exists` | 先 `gh pr view --json state,url` 检查状态；`OPEN` 则编辑现有 PR，`MERGED` 则新建 PR |
| 本地无 `main` | 使用 `origin/main` 做 `git log`；`--base main` 仍指向远端分支名 |
| 需包含 merge commit | 去掉 `git log` 的 `--no-merges` |

## 可选：仅生成正文草稿（不创建 PR）

把列表写入文件供人工润色：

```bash
git log origin/main..HEAD --no-merges --pretty=format:"- %s" > /tmp/pr-commits.md
```
