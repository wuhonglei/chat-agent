#!/usr/bin/env python3
"""
将 users.avatar 中的腾讯云 COS 头像下载到 data/avatars，并更新为 /api/avatars/{filename}。

用法:
  cd backend && uv run python scripts/migrate_cos_avatars_to_local.py --dry-run
  cd backend && uv run python scripts/migrate_cos_avatars_to_local.py
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlmodel import Session, select

# 保证 backend 根目录在 path 中
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.models import UserDb  # noqa: E402
from app.utils.avatar import (  # noqa: E402
    avatar_local_path,
    avatar_storage_path,
    filename_from_cos_url,
    is_cos_avatar_url,
    is_valid_avatar_filename,
)
from app.utils.file import get_file_extension  # noqa: E402


def _guess_filename(cos_url: str) -> str:
    parsed = urlparse(cos_url)
    name = Path(parsed.path).name
    if is_valid_avatar_filename(name):
        return name
    ext = get_file_extension(name) or ".png"
    return f"{uuid.uuid4()}{ext}"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        dest.write_bytes(response.content)


def migrate(*, dry_run: bool) -> int:
    avatar_dir = Path(settings.storage.avatar_dir)
    avatar_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    failed: list[tuple[str, str, str]] = []

    with Session(engine) as session:
        users = session.exec(select(UserDb).where(UserDb.avatar != None)).all()  # noqa: E711

        targets = [u for u in users if u.avatar and is_cos_avatar_url(u.avatar)]
        print(f"待迁移 COS 头像用户数: {len(targets)}")

        for user in targets:
            assert user.avatar is not None
            cos_url = user.avatar
            filename = filename_from_cos_url(cos_url) or _guess_filename(cos_url)
            storage_path = avatar_storage_path(filename)
            local_path = avatar_local_path(filename)

            print(
                f"user_id={user.id} cos_url={cos_url} "
                f"filename={filename} db_path={storage_path}"
            )

            if dry_run:
                ok += 1
                continue

            try:
                if not local_path.is_file():
                    _download(cos_url, local_path)
                user.avatar = storage_path
                session.add(user)
                session.commit()
                ok += 1
            except Exception as e:  # noqa: BLE001
                session.rollback()
                failed.append((user.id, cos_url, str(e)))
                print(f"  FAILED: {e}")

    print(f"完成: 成功 {ok}, 失败 {len(failed)}")
    for user_id, url, err in failed:
        print(f"  - {user_id}: {url} -> {err}")
    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="COS 头像迁移到本地")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印将处理的记录，不写盘、不改库",
    )
    args = parser.parse_args()
    raise SystemExit(migrate(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
