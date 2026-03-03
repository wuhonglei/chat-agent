---
name: code_executor
description: 在安全沙箱中执行 Python 代码片段
version: 1.0.0
author: AI Doc Team
tags: [code, execution, sandbox, python]
permissions: [code_execution]
warnings: [仅支持受限的 Python 内置函数和操作，禁止文件/网络访问]
parameters: {"code": {"type": "string", "description": "要执行的 Python 代码片段"}}
timeout: 30
---

# Code Executor Skill

在 RestrictedPython 沙箱中执行 Python 代码，返回最后一条表达式结果或 print 输出。

## 限制

- 仅允许 math、datetime 等安全模块
- 禁止文件、网络、子进程访问
- 执行超时 30 秒
