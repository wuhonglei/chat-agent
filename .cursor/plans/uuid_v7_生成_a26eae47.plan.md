---
name: UUID v7 生成
overview: 将应用层 ID 生成从 UUIDv4 切换为 UUIDv7：通过 uuid6 库改 `gen_uuid()` 为统一入口，并把业务侧直接调用 `uuid.uuid4()` 的地方收敛到该入口；不改库表类型/已有数据。
todos:
  - id: add-uuid6-dep
    content: 在 backend/pyproject.toml 添加 uuid6 依赖并用 uv sync
    status: in_progress
  - id: impl-uuid7
    content: 在 common.py 用 uuid6.uuid7 改写 gen_uuid
    status: pending
  - id: converge-callers
    content: file_service / file TempFile / sms_service 改为 gen_uuid()
    status: pending
  - id: verify
    content: 跑 lint，抽检 version nibble 为 7
    status: pending
isProject: false
---

# 改为 UUIDv7 生成

## 背景

当前主键与多数业务 ID 经 [`backend/app/utils/common.py`](backend/app/utils/common.py) 的 `gen_uuid()` 生成，内部是 `uuid.uuid4()`；另有几处直接 `uuid.uuid4()`。

项目 `requires-python = ">=3.10"`，标准库 `uuid.uuid7()` 仅在 **Python 3.14+** 可用。本方案用第三方库 **[uuid6](https://pypi.org/project/uuid6/)** 生成 RFC 9562 UUIDv7。

仍保持：**应用层生成 + 字符串存储**（`str` / `max_length=36`）。不做 PostgreSQL `UUID` 类型迁移，也不改已有行（新旧 v4/v7 可并存）。

## 实现方案

1. 在 [`backend/pyproject.toml`](backend/pyproject.toml) 增加依赖 `uuid6`，并 `uv sync` 更新锁文件。
2. 改写 `gen_uuid()`：

```python
from uuid6 import uuid7

def gen_uuid() -> str:
    """Generate a new UUIDv7 string (time-ordered)."""
    return str(uuid7())
```

不再手写回退实现，也不依赖 stdlib `uuid.uuid7`。

## 调用点收敛

| 位置 | 改动 |
|------|------|
| [`gen_uuid`](backend/app/utils/common.py) | `uuid.uuid4()` → `uuid6.uuid7()`（核心） |
| [`file_service.py`](backend/app/services/base_service/file_service.py) 头像文件名 | `uuid.uuid4()` → `gen_uuid()` |
| [`file.py`](backend/app/utils/file.py) TempFileManager | `uuid.uuid4()` → `gen_uuid()` |
| [`sms_service.py`](backend/app/services/auth/sms_service.py) verification_id | `uuid.uuid4()` → `gen_uuid()` |

**不改**：[`scripts/migrate_cos_avatars_to_local.py`](backend/scripts/migrate_cos_avatars_to_local.py)、skills 脚本等一次性/外围脚本；模型 `default_factory=gen_uuid`、已用 `gen_uuid()` 的 API/服务会自动受益。

不改库 schema、不做 Alembic、不改前端（字符串形态仍为 8-4-4-4-12）。

## 验证

- `cd backend && make lint`
- 快速自检：连续调用 `gen_uuid()`，字符串第 15 位（version nibble）为 `7`，且大致随时间递增（字典序/时间有序）
