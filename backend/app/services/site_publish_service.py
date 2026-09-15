"""Publish conversation outputs as an immutable static-site snapshot."""

from __future__ import annotations

import os
import re
import secrets
import shutil
import unicodedata
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.core.config import settings
from app.models.conversation_db import ConversationDb
from app.models.published_site import PublishedSite
from app.schemas.sites import DEFAULT_SITE_SOURCE, PublishedSiteData
from app.services.base_service.db_service import DbService
from app.utils.date import get_datetime_now
from app.utils.logger import logger
from app.vfs.config import vfs_config
from app.vfs.paths import Paths, get_paths
from app.vfs.resolver import PathResolver

RESERVED_SLUGS = frozenset(
    {"www", "api", "admin", "chat", "static", "apps", "mail", "ftp"}
)
SLUG_PATTERN = re.compile(r"^[a-z0-9-]{3,40}$")
_NANOID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
DEFAULT_ENTRY = "index.html"
_INDEX_FILENAMES = frozenset({"index.html", "index.htm"})
SiteVisibility = Literal["unlisted", "public"]


class SitePublishError(Exception):
    """Domain error mapped to HTTP / MCP failures."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class PublishResult:
    """Snapshot publish outcome."""

    site: PublishedSite
    file_count: int
    url: str


def _nanoid(length: int = 6) -> str:
    return "".join(secrets.choice(_NANOID_ALPHABET) for _ in range(length))


def slugify_title(title: str) -> str:
    """ASCII slug from a conversation title; may be empty or shorter than 3."""
    normalized = unicodedata.normalize("NFKD", title or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
    dashed = re.sub(r"[^a-z0-9]+", "-", ascii_only)
    collapsed = re.sub(r"-{2,}", "-", dashed).strip("-")
    return collapsed[:40].strip("-")


def is_reserved_slug(slug: str) -> bool:
    return slug in RESERVED_SLUGS


def validate_requested_slug(slug: str) -> str:
    normalized = (slug or "").strip().lower()
    if not SLUG_PATTERN.fullmatch(normalized):
        raise SitePublishError(
            "slug 非法：仅允许 3–40 位小写字母、数字和连字符",
            status_code=400,
        )
    if is_reserved_slug(normalized):
        raise SitePublishError("slug 为保留字，不可使用", status_code=400)
    return normalized


def generate_candidate_slug(title: str) -> str:
    base = slugify_title(title)
    if len(base) < 3 or is_reserved_slug(base):
        return f"site-{_nanoid(6)}"
    return base


def public_site_url(slug: str) -> str:
    return f"https://{slug}.{settings.sites.public_base_domain}"


def to_site_data(
    site: PublishedSite, *, file_count: int | None = None
) -> PublishedSiteData:
    return PublishedSiteData(
        slug=site.slug,
        version=site.version,
        url=public_site_url(site.slug),
        visibility=site.visibility,
        size_bytes=site.size_bytes,
        expires_at=site.expires_at,
        conversation_id=site.conversation_id,
        unpublished_at=site.unpublished_at,
        entry=site.entry,
        file_count=file_count,
    )


def _copy_snapshot(source: Path, dest: Path) -> tuple[int, int]:
    """Copy regular files only; do not follow symlinks out of outputs."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    file_count = 0
    size_bytes = 0
    for dirpath, dirnames, filenames in os.walk(source, followlinks=False):
        dirnames[:] = [name for name in dirnames if not name.startswith(".")]
        rel_dir = Path(dirpath).relative_to(source)
        target_dir = dest / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            if name.startswith("."):
                continue
            src_file = Path(dirpath) / name
            if src_file.is_symlink() or not src_file.is_file():
                continue
            shutil.copy2(src_file, target_dir / name)
            file_count += 1
            size_bytes += src_file.stat().st_size
    return file_count, size_bytes


def switch_current(paths: Paths, slug: str, version: int) -> None:
    """Atomically point ``current`` at ``{version}/`` via a relative symlink."""
    current = paths.site_current_link(slug)
    current.parent.mkdir(parents=True, exist_ok=True)
    tmp = current.parent / f".current.tmp.{os.getpid()}"
    if tmp.exists() or tmp.is_symlink():
        tmp.unlink()
    os.symlink(str(version), tmp)
    os.replace(tmp, current)


def unlink_current(paths: Paths, slug: str) -> None:
    current = paths.site_current_link(slug)
    if current.is_symlink() or current.exists():
        current.unlink()


class SitePublishService(DbService):
    """Publish, republish, unpublish, and purge static sites."""

    def __init__(
        self, db: Session | None = None, *, paths: Paths | None = None
    ) -> None:
        super().__init__(db)
        self._paths = paths or get_paths()

    def publish(
        self,
        *,
        user_id: str,
        conversation_id: str,
        source: str = DEFAULT_SITE_SOURCE,
        visibility: SiteVisibility = "unlisted",
        requested_slug: str | None = None,
        allow_requested_slug: bool = False,
    ) -> PublishResult:
        self._validate_visibility(visibility)
        conversation = self._require_conversation(user_id, conversation_id)
        source_dir = self._resolve_source_dir(user_id, conversation_id, source)

        existing = self._get_by_conversation(conversation_id)
        if existing is not None:
            if existing.user_id != user_id:
                raise SitePublishError("站点不属于当前用户", status_code=403)
            return self._snapshot_and_activate(
                existing,
                source_dir=source_dir,
                visibility=visibility,
            )

        slug = self._allocate_new_slug(
            title=conversation.title,
            requested_slug=requested_slug,
            allow_requested_slug=allow_requested_slug,
        )
        self._assert_user_quota(user_id)
        now = get_datetime_now()
        site = PublishedSite(
            slug=slug,
            user_id=user_id,
            conversation_id=conversation_id,
            site_root="",
            version=1,
            entry=DEFAULT_ENTRY,
            visibility=visibility,
            size_bytes=0,
            expires_at=now + timedelta(days=settings.sites.default_ttl_days),
            created_at=now,
            updated_at=now,
            unpublished_at=None,
        )
        return self._insert_and_activate(site, source_dir=source_dir)

    def republish(
        self,
        *,
        user_id: str,
        slug: str,
        source: str = DEFAULT_SITE_SOURCE,
        visibility: SiteVisibility | None = None,
    ) -> PublishResult:
        site = self._require_owned_site(user_id, slug)
        if visibility is not None:
            self._validate_visibility(visibility)
            next_visibility = visibility
        else:
            next_visibility = self._coerce_visibility(site.visibility)
        source_dir = self._resolve_source_dir(user_id, site.conversation_id, source)
        return self._snapshot_and_activate(
            site,
            source_dir=source_dir,
            visibility=next_visibility,
        )

    def unpublish(self, *, user_id: str, slug: str) -> PublishedSite:
        site = self._require_owned_site(user_id, slug)
        unlink_current(self._paths, site.slug)
        site.unpublished_at = get_datetime_now()
        site.updated_at = site.unpublished_at
        self.session.add(site)
        self.session.flush()
        logger.info("Site unpublished", slug=site.slug, user_id=user_id)
        return site

    def purge_for_conversation(self, *, user_id: str, conversation_id: str) -> None:
        """Unlink, delete snapshot dirs, and drop the row. Call before deleting the conversation."""
        site = self._get_by_conversation(conversation_id)
        if site is None:
            return
        if site.user_id != user_id:
            logger.warning(
                "Skip purging site owned by another user",
                slug=site.slug,
                conversation_id=conversation_id,
            )
            return
        unlink_current(self._paths, site.slug)
        shutil.rmtree(self._paths.site_dir(site.slug), ignore_errors=True)
        self.session.delete(site)
        self.session.flush()
        logger.info(
            "Site purged with conversation",
            slug=site.slug,
            conversation_id=conversation_id,
        )

    def list_for_user(self, user_id: str) -> list[PublishedSite]:
        statement = (
            select(PublishedSite)
            .where(PublishedSite.user_id == user_id)
            .order_by(col(PublishedSite.updated_at).desc())
        )
        return list(self.session.exec(statement).all())

    def expire_due_sites(self) -> int:
        now = get_datetime_now()
        statement = select(PublishedSite).where(
            col(PublishedSite.unpublished_at).is_(None),
            col(PublishedSite.expires_at).is_not(None),
            col(PublishedSite.expires_at) <= now,
        )
        rows = list(self.session.exec(statement).all())
        for site in rows:
            unlink_current(self._paths, site.slug)
            site.unpublished_at = now
            site.updated_at = now
            self.session.add(site)
        if rows:
            self.session.flush()
            logger.info("Expired published sites", count=len(rows))
        return len(rows)

    def _insert_and_activate(
        self, site: PublishedSite, *, source_dir: Path, attempts: int = 0
    ) -> PublishResult:
        if attempts > 5:
            raise SitePublishError("发布失败，请重试", status_code=409)
        file_count, size_bytes = self._write_version_dir(site.slug, 1, source_dir)
        now = get_datetime_now()
        site.version = 1
        site.size_bytes = size_bytes
        site.site_root = str(self._paths.site_version_dir(site.slug, 1))
        site.unpublished_at = None
        site.expires_at = now + timedelta(days=settings.sites.default_ttl_days)
        site.updated_at = now
        try:
            with self.session.begin_nested():
                self.session.add(site)
                self.session.flush()
        except IntegrityError as exc:
            existing = self._get_by_conversation(site.conversation_id)
            if existing is not None and existing.user_id == site.user_id:
                shutil.rmtree(
                    self._paths.site_version_dir(site.slug, 1), ignore_errors=True
                )
                return self._snapshot_and_activate(
                    existing,
                    source_dir=source_dir,
                    visibility=self._coerce_visibility(site.visibility),
                )
            collision = self.session.get(PublishedSite, site.slug)
            if collision is not None:
                fallback = f"site-{_nanoid(6)}"
                shutil.rmtree(
                    self._paths.site_version_dir(site.slug, 1), ignore_errors=True
                )
                site.slug = fallback
                return self._insert_and_activate(
                    site, source_dir=source_dir, attempts=attempts + 1
                )
            raise SitePublishError("发布失败，请重试", status_code=409) from exc

        switch_current(self._paths, site.slug, 1)
        logger.info(
            "Site published",
            slug=site.slug,
            version=1,
            conversation_id=site.conversation_id,
        )
        return PublishResult(
            site=site, file_count=file_count, url=public_site_url(site.slug)
        )

    def _snapshot_and_activate(
        self,
        site: PublishedSite,
        *,
        source_dir: Path,
        visibility: SiteVisibility,
    ) -> PublishResult:
        if site.unpublished_at is not None:
            self._assert_user_quota(site.user_id)
        next_version = site.version + 1
        file_count, size_bytes = self._write_version_dir(
            site.slug, next_version, source_dir
        )
        now = get_datetime_now()
        site.version = next_version
        site.size_bytes = size_bytes
        site.site_root = str(self._paths.site_version_dir(site.slug, next_version))
        site.visibility = visibility
        site.unpublished_at = None
        site.expires_at = now + timedelta(days=settings.sites.default_ttl_days)
        site.updated_at = now
        self.session.add(site)
        self.session.flush()
        switch_current(self._paths, site.slug, next_version)
        logger.info(
            "Site republished",
            slug=site.slug,
            version=next_version,
            conversation_id=site.conversation_id,
        )
        return PublishResult(
            site=site, file_count=file_count, url=public_site_url(site.slug)
        )

    def _write_version_dir(
        self, slug: str, version: int, source_dir: Path
    ) -> tuple[int, int]:
        dest = self._paths.site_version_dir(slug, version)
        dest.parent.mkdir(parents=True, exist_ok=True)
        file_count, size_bytes = _copy_snapshot(source_dir, dest)
        if size_bytes > settings.sites.max_size_bytes:
            shutil.rmtree(dest, ignore_errors=True)
            raise SitePublishError(
                "站点体积超过上限",
                status_code=413,
            )
        return file_count, size_bytes

    def _allocate_new_slug(
        self,
        *,
        title: str,
        requested_slug: str | None,
        allow_requested_slug: bool,
    ) -> str:
        if allow_requested_slug and requested_slug:
            slug = validate_requested_slug(requested_slug)
            taken = self.session.get(PublishedSite, slug)
            if taken is not None:
                raise SitePublishError("slug 已被占用", status_code=409)
            return slug

        base = generate_candidate_slug(title)
        candidate = base
        suffix = 2
        while True:
            taken = self.session.get(PublishedSite, candidate)
            if taken is None:
                return candidate
            next_candidate = f"{base}-{suffix}"
            if len(next_candidate) > 40 or suffix > 20:
                fallback = f"site-{_nanoid(6)}"
                if self.session.get(PublishedSite, fallback) is None:
                    return fallback
                continue
            candidate = next_candidate
            suffix += 1

    def _assert_user_quota(self, user_id: str) -> None:
        count = self.session.exec(
            select(func.count())
            .select_from(PublishedSite)
            .where(
                PublishedSite.user_id == user_id,
                col(PublishedSite.unpublished_at).is_(None),
            )
        ).one()
        if int(count) >= settings.sites.max_sites_per_user:
            raise SitePublishError("已达到站点数量上限", status_code=413)

    def _require_conversation(
        self, user_id: str, conversation_id: str
    ) -> ConversationDb:
        conversation = self.session.get(ConversationDb, conversation_id)
        if conversation is None or conversation.user_id != user_id:
            raise SitePublishError("对话不存在", status_code=404)
        return conversation

    def _require_owned_site(self, user_id: str, slug: str) -> PublishedSite:
        try:
            normalized = self._paths.validate_slug(slug)
        except ValueError as exc:
            raise SitePublishError("slug 非法", status_code=400) from exc
        site = self.session.get(PublishedSite, normalized)
        if site is None or site.user_id != user_id:
            raise SitePublishError("站点不存在", status_code=404)
        return site

    def _get_by_conversation(self, conversation_id: str) -> PublishedSite | None:
        statement = select(PublishedSite).where(
            PublishedSite.conversation_id == conversation_id
        )
        return self.session.exec(statement).first()

    def _resolve_source_dir(
        self, user_id: str, conversation_id: str, source: str
    ) -> Path:
        filepath = (source or "").strip().rstrip("/")
        if not filepath:
            filepath = DEFAULT_SITE_SOURCE.rstrip("/")
        try:
            return self._resolve_existing_site_dir(user_id, conversation_id, filepath)
        except SitePublishError as exc:
            if (
                filepath != DEFAULT_SITE_SOURCE.rstrip("/")
                or "does not exist" not in exc.message
            ):
                raise
            outputs_root = vfs_config.outputs_prefix.rstrip("/")
            try:
                return self._resolve_existing_site_dir(
                    user_id, conversation_id, outputs_root
                )
            except SitePublishError:
                raise exc from None

    def _resolve_existing_site_dir(
        self, user_id: str, conversation_id: str, filepath: str
    ) -> Path:
        outputs_prefix = vfs_config.outputs_prefix.rstrip("/")
        if filepath != outputs_prefix and not filepath.startswith(f"{outputs_prefix}/"):
            raise SitePublishError(
                f"source 必须位于 {vfs_config.outputs_prefix} 下",
                status_code=400,
            )
        try:
            resolver = PathResolver()
            actual, _permission = resolver.resolve_virtual_to_physical(
                filepath,
                user_id,
                conversation_id,
            )
        except ValueError as exc:
            raise SitePublishError(str(exc), status_code=400) from exc
        if not actual.exists():
            raise SitePublishError(f"Path does not exist: {filepath}", status_code=400)
        if actual.is_file():
            if actual.name.lower() not in _INDEX_FILENAMES:
                raise SitePublishError(
                    "source 必须是已存在的目录，或指向 index.html",
                    status_code=400,
                )
            actual = actual.parent
        if not actual.is_dir():
            raise SitePublishError("source 必须是已存在的目录", status_code=400)
        entry = actual / DEFAULT_ENTRY
        if not entry.is_file():
            raise SitePublishError(
                f"source 缺少入口文件 {DEFAULT_ENTRY}",
                status_code=400,
            )
        return actual

    @staticmethod
    def _validate_visibility(visibility: str) -> None:
        if visibility not in ("unlisted", "public"):
            raise SitePublishError(
                "visibility 仅支持 unlisted 或 public", status_code=400
            )

    @staticmethod
    def _coerce_visibility(visibility: str) -> SiteVisibility:
        if visibility == "public":
            return "public"
        return "unlisted"
