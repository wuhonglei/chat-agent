# 类型检查指南

本文档介绍项目中配置的类型检查工具和最佳实践。

## 配置的工具

### 1. MyPy - 静态类型检查器
- **配置文件**: `mypy.ini` 和 `pyproject.toml`
- **启用严格模式**: 强制类型注解和错误检测
- **排除目录**: `tests/`, `app/mcp/`

### 2. Ruff - 代码格式化和Linting
- **配置文件**: `pyproject.toml`
- **支持规则**: E, W, F, I, B, C4, UP 等

### 3. Pre-commit Hooks
- **配置文件**: `.pre-commit-config.yaml`
- **自动检查**: 提交前运行类型检查和代码格式化

## VSCode/Cursor 设置

项目已配置以下设置以提升代码质量：

```json
{
  "python.linting.enabled": true,
  "python.linting.mypyEnabled": true,
  "python.linting.ruffEnabled": true,
  "python.analysis.typeCheckingMode": "strict",
  "python.analysis.diagnosticMode": "openFilesOnly"
}
```

## 常用命令

### 安装依赖
```bash
uv sync --extra dev
```

### 运行类型检查
```bash
make check
# 或
uv run mypy app/
```

### 代码格式化
```bash
make format
# 或
uv run ruff format app/
```

### Linting
```bash
make lint
# 或
uv run ruff check app/
```

### 运行所有检查
```bash
make all
```

## 常见问题解决

### 1. 编辑器不显示类型错误

**问题**: Cursor/VSCode 不显示类型检查错误

**解决方案**:
1. 确保安装了开发依赖: `uv sync --extra dev`
2. 重启 VSCode/Cursor
3. 检查 `.vscode/settings.json` 中的配置
4. 在命令面板中运行: `Python: Restart Language Server`

### 2. MyPy 报告过多错误

**解决方案**:
- 在函数参数前添加 `# type: ignore` 注释来忽略特定错误
- 或者在 `mypy.ini` 中配置忽略特定模块

### 3. 导入错误

如果遇到导入相关错误，可以在 `mypy.ini` 中添加:
```
[mypy-some_module.*]
ignore_errors = True
```

## 类型检查的好处

1. **早期错误检测**: 在运行时之前发现参数不匹配等错误
2. **更好的IDE支持**: 自动补全、跳转、重构
3. **代码文档**: 类型注解作为代码文档
4. **重构安全**: 类型检查确保重构不会破坏代码

## 示例

### 正确的类实例化
```python
# 正确的用法
calculator = TokenCalculator(model_name)
compressor = GenericCompressor(max_length=1000, token_calculator=calculator)
```

### 错误的实例化（会被检测到）
```python
# 这行代码会被 MyPy 标记为错误
compressor = GenericCompressor(max_length=1000)  # 缺少 token_calculator 参数
```