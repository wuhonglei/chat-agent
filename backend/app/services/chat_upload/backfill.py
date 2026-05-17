"""历史聊天附件 storage_key 回填任务。

降本执行方案：
1. 作为离线脚本按需执行，不放入请求链路，避免影响用户对话延迟。
2. 使用 batch_size 分批扫描消息，并通过本地 checkpoint 支持断点续跑。
3. 跳过已具备当前 STORAGE_VERSION 与 storage_key 的附件块，减少重复 DB/文件 IO。
4. 仅在新版 shared/uploads 目标文件不存在时复制旧 uploads 文件，降低磁盘写入成本。
5. 建议在业务低峰运行，并根据数据库与磁盘 IO 情况调小 --batch-size。

执行命令:
cd backend
uv run -m app.services.chat_upload.backfill
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from app.core.db import engine
from app.models import ConversationDb, MessageDb
from app.services.chat_upload.attachment import (
    STORAGE_VERSION,
    build_attachment_preview_url,
    build_derived_markdown_storage_key,
    build_raw_storage_key,
    media_type_for_preview,
    mount_conversation_attachment,
    upsert_attachment_file,
    user_upload_file_path,
)
from app.utils.logger import logger

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_STATE_PATH = _BACKEND_ROOT / "data" / "migration_state" / "attachment_backfill.json"
_PREVIEW_PREFIX = "/api/file/preview/"


def _load_checkpoint() -> str | None:
    if not _STATE_PATH.is_file():
        return None
    try:
        data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    value = data.get("last_processed_message_id")
    return value if isinstance(value, str) and value else None


def _save_checkpoint(message_id: str) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(
        json.dumps({"last_processed_message_id": message_id}, ensure_ascii=False),
        encoding="utf-8",
    )


def _parse_preview_url(url: str) -> tuple[str, str] | None:
    path = urlparse(url).path
    if not path.startswith(_PREVIEW_PREFIX):
        return None
    rest = path[len(_PREVIEW_PREFIX) :]
    parts = rest.split("/", 1)
    if len(parts) != 2:
        return None
    return (unquote(parts[0]), unquote(parts[1]))


def _copy_legacy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        return
    shutil.copy2(source, target)


def _storage_key_for_block(
    block: dict[str, Any],
    filename: str,
    *,
    parent_pdf_id: str | None = None,
) -> str | None:
    ext = Path(filename).suffix.lower()
    block_type = block.get("type")
    content_id = str(block.get("id") or Path(filename).stem)
    if block_type == "pdf" and ext == ".pdf":
        return build_raw_storage_key(content_id, ext)
    if block_type == "markdown" and ext == ".md":
        if parent_pdf_id:
            return build_derived_markdown_storage_key(parent_pdf_id)
        return build_raw_storage_key(content_id, ext)
    if block_type == "image" and ext in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        return build_raw_storage_key(content_id, ext)
    return None


def _backfill_block(
    *,
    db: Session,
    block: dict[str, Any],
    conversation: ConversationDb,
    parent_pdf_id: str | None = None,
) -> bool:
    changed = False
    nested = block.get("markdown")
    if isinstance(nested, dict):
        changed = (
            _backfill_block(
                db=db,
                block=nested,
                conversation=conversation,
                parent_pdf_id=str(block.get("id") or "") or None,
            )
            or changed
        )

    if block.get("storage_version") == STORAGE_VERSION and block.get("storage_key"):
        return changed

    url = block.get("url")
    if not isinstance(url, str) or not url:
        return changed
    parsed = _parse_preview_url(url)
    if parsed is None:
        return changed
    user_id, filename = parsed
    if user_id != conversation.user_id:
        return changed

    storage_key = _storage_key_for_block(block, filename, parent_pdf_id=parent_pdf_id)
    if storage_key is None:
        return changed

    source_path = user_upload_file_path(user_id, filename)
    target_path = user_upload_file_path(user_id, storage_key)
    if source_path.is_file():
        _copy_legacy_file(source_path, target_path)

    content_id = str(block.get("id") or Path(filename).stem)
    display_name = str(block.get("name") or Path(filename).name)
    attachment_file = upsert_attachment_file(
        db=db,
        user_id=user_id,
        content_id=content_id,
        storage_key=storage_key,
        kind=storage_key.split("/", 1)[0],
        mime=str(block.get("mime") or media_type_for_preview(storage_key)),
        size=int(
            block.get("size")
            or (target_path.stat().st_size if target_path.exists() else 0)
        ),
        display_name=display_name,
        derived_from_id=parent_pdf_id if storage_key.startswith("derived/") else None,
        derived_kind="pdf_to_markdown" if storage_key.startswith("derived/") else None,
        legacy_source=str(source_path),
    )
    mount_conversation_attachment(
        db=db,
        user_id=user_id,
        conversation_id=conversation.id,
        attachment_file=attachment_file,
    )

    block["storage_key"] = storage_key
    block["storage_version"] = STORAGE_VERSION
    block["url"] = build_attachment_preview_url(user_id, storage_key)
    if storage_key.startswith("derived/") and parent_pdf_id:
        block["derived_from_id"] = parent_pdf_id
        block["derived_kind"] = "pdf_to_markdown"
    return True


def run_attachment_storage_backfill(
    *,
    batch_size: int = 500,
    resume: bool = True,
) -> None:
    last_processed = _load_checkpoint() if resume else None
    processed = 0
    with Session(engine) as db:
        while True:
            statement = select(MessageDb).order_by(MessageDb.id).limit(batch_size)
            if last_processed:
                statement = statement.where(MessageDb.id > last_processed)
            messages = db.exec(statement).all()
            if not messages:
                break
            for message in messages:
                last_processed = message.id
                conversation = db.get(ConversationDb, message.conversation_id)
                if conversation is None or conversation.user_id is None:
                    _save_checkpoint(message.id)
                    continue
                blocks = message.content_blocks
                if not isinstance(blocks, list):
                    _save_checkpoint(message.id)
                    continue
                updated = False
                for block in blocks:
                    if isinstance(block, dict):
                        updated = (
                            _backfill_block(
                                db=db, block=block, conversation=conversation
                            )
                            or updated
                        )
                if updated:
                    message.content_blocks = blocks
                    flag_modified(message, "content_blocks")
                    db.add(message)
                _save_checkpoint(message.id)
                processed += 1
            db.commit()
    logger.info(f"Attachment storage backfill completed, processed={processed}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill chat attachment storage keys"
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    run_attachment_storage_backfill(
        batch_size=args.batch_size,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
