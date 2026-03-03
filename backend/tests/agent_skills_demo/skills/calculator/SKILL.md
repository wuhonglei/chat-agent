---
name: calculator
description: 执行数学计算，支持四则运算和常用数学函数
version: 1.0.0
author: AI Doc Team
tags: [math, calculation, utility]
permissions: []
parameters: {"expression": {"type": "string", "description": "数学表达式，如 1+2*3、sqrt(16)"}}
timeout: 5
---

# Calculator Skill

执行安全的数学表达式计算。

## 支持的操作

- 四则运算：`+`, `-`, `*`, `/`
- 幂运算：`**`
- 括号：`()`
- 常用函数：`sqrt`, `sin`, `cos`, `tan`, `log`, `abs`

## 示例

- `2 + 3 * 4` -> 14
- `sqrt(16)` -> 4
