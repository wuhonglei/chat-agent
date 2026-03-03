---
name: calculator
description: 数学计算，支持四则运算和常见数学函数
---

# 计算器

## 何时使用

当用户需要执行数学计算（加减乘除、幂、开方、三角函数等）时使用本技能。

## 使用方式

通过 execute_python_code 执行数学表达式：

### 基础四则运算

```python
result = 2 + 3 * 4
print(result)  # 14
```

### 使用 math 模块

```python
import math
result = math.sqrt(16) + math.pow(2, 3)
print(result)  # 12.0
```

### 复杂表达式

```python
import math
# 计算 (1+2)*3-4/2
result = (1 + 2) * 3 - 4 / 2
print(result)  # 7.0
# 三角函数
angle = math.radians(90)
print(math.sin(angle))  # 1.0
```

## 注意事项

- 使用 print() 输出结果，否则无法获取返回值
- math 模块需显式 import
- 仅用于数值计算，避免执行不可信用户输入
