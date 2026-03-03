---
name: code_executor
description: 在安全沙箱中执行 Python 代码片段
---

# Code Executor Skill

在 RestrictedPython 沙箱中执行 Python 代码，返回最后一条表达式结果或 print 输出。

## Instructions

当用户需要执行 Python 代码片段时，调用此 Skill。

## 限制

- 仅允许 math、datetime 等安全模块
- 禁止文件、网络、子进程访问
- 执行超时 30 秒
