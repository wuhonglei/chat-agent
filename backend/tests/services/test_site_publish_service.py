"""Tests for site slug helpers, snapshots, MCP publish_site, and REST mapping."""

from __future__ import annotations

import inspect
from contextlib import nullcontext
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import DetachedInstanceError

from app.mcp.constants import MUTATING_LLM_TOOLS, PUBLISH_SITE_LLM
from app.mcp.mcp_servers.file_mcp.base import ToolContext
from app.mcp.mcp_servers.file_mcp.publish_site import PublishSiteTool
from app.mcp.mcp_servers.file_mcp.server import publish_site as publish_site_mcp
from app.models.published_site import PublishedSite
from app.services.site_publish_service import (
    PublishResult,
    SitePublishError,
    SitePublishService,
    generate_candidate_slug,
    slugify_title,
    switch_current,
    unlink_current,
    validate_requested_slug,
)
from app.utils.context import set_request_context
from app.utils.date import get_datetime_now
from app.vfs.config import vfs_config
from app.vfs.paths import Paths


class _FakeDb:
    def __init__(self) -> None:
        self.sites: dict[str, PublishedSite] = {}
        self.conversations: dict[str, SimpleNamespace] = {}

    def get(self, model: object, pk: str) -> object | None:
        if model is PublishedSite:
            return self.sites.get(pk)
        return self.conversations.get(pk)

    def add(self, obj: object) -> None:
        if isinstance(obj, PublishedSite):
            self.sites[obj.slug] = obj

    def flush(self) -> None:
        return None

    def delete(self, obj: object) -> None:
        if isinstance(obj, PublishedSite):
            self.sites.pop(obj.slug, None)

    def begin_nested(self) -> object:
        return nullcontext()

    def exec(self, _statement: object) -> SimpleNamespace:
        return SimpleNamespace(first=lambda: None, all=lambda: [], one=lambda: 0)


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    return Paths(base_dir=tmp_path / "user_data", sites_root=tmp_path / "sites")


@pytest.fixture
def patched_paths(paths: Paths, monkeypatch: pytest.MonkeyPatch) -> Paths:
    monkeypatch.setattr("app.vfs.paths.get_paths", lambda: paths)
    monkeypatch.setattr("app.vfs.resolver.get_paths", lambda: paths)
    return paths


def _bind_lookups(service: SitePublishService, db: _FakeDb) -> None:
    def get_by_conversation(conversation_id: str) -> PublishedSite | None:
        for site in db.sites.values():
            if site.conversation_id == conversation_id:
                return site
        return None

    service._get_by_conversation = get_by_conversation  # type: ignore[method-assign]
    service._assert_user_quota = lambda _uid: None  # type: ignore[method-assign]


def _seed_app_dist(paths: Paths, user_id: str, conversation_id: str) -> Path:
    paths.ensure_conversation_dirs(user_id, conversation_id)
    dist = paths.sandbox_outputs_dir(user_id, conversation_id) / "app-dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    (assets / "index.js").write_text("console.log(1)", encoding="utf-8")
    return dist


def test_slugify_title_ascii_and_reserved() -> None:
    assert slugify_title("My Resume Site!") == "my-resume-site"
    assert slugify_title("简历") == ""
    candidate = generate_candidate_slug("www")
    assert candidate.startswith("site-")
    assert len(candidate) == 11
    short = generate_candidate_slug("ab")
    assert short.startswith("site-")
    assert len(short) == 11


def test_validate_requested_slug_rejects_illegal_and_reserved() -> None:
    assert validate_requested_slug("resume-site") == "resume-site"
    with pytest.raises(SitePublishError) as illegal:
        validate_requested_slug("AB")
    assert illegal.value.status_code == 400
    with pytest.raises(SitePublishError) as reserved:
        validate_requested_slug("admin")
    assert reserved.value.status_code == 400
    with pytest.raises(SitePublishError):
        validate_requested_slug("has_underscore")


def test_site_paths_and_current_symlink(paths: Paths) -> None:
    version_dir = paths.site_version_dir("resume-site", 1)
    version_dir.mkdir(parents=True)
    (version_dir / "index.html").write_text("v1", encoding="utf-8")
    switch_current(paths, "resume-site", 1)
    current = paths.site_current_link("resume-site")
    assert current.is_symlink()
    assert current.resolve() == version_dir.resolve()
    assert (current / "index.html").read_text(encoding="utf-8") == "v1"

    version2 = paths.site_version_dir("resume-site", 2)
    version2.mkdir(parents=True)
    (version2 / "index.html").write_text("v2", encoding="utf-8")
    switch_current(paths, "resume-site", 2)
    assert current.resolve() == version2.resolve()
    assert version_dir.exists()

    unlink_current(paths, "resume-site")
    assert not current.exists()


def test_publish_site_mcp_schema_has_no_slug() -> None:
    assert "slug" not in inspect.signature(publish_site_mcp).parameters
    assert PUBLISH_SITE_LLM in MUTATING_LLM_TOOLS


def test_publish_rejects_workspace_source(patched_paths: Paths) -> None:
    user_id = "user-1"
    conversation_id = "conv-1"
    patched_paths.ensure_conversation_dirs(user_id, conversation_id)
    workspace_app = patched_paths.sandbox_work_dir(user_id, conversation_id) / "app"
    workspace_app.mkdir(parents=True)
    (workspace_app / "index.html").write_text("nope", encoding="utf-8")
    db = _FakeDb()
    db.conversations[conversation_id] = SimpleNamespace(title="Hello", user_id=user_id)
    service = SitePublishService(db, paths=patched_paths)  # type: ignore[arg-type]
    _bind_lookups(service, db)

    with pytest.raises(SitePublishError, match="outputs"):
        service.publish(
            user_id=user_id,
            conversation_id=conversation_id,
            source=f"{vfs_config.workspace_prefix}app",
        )


def test_publish_rejects_file_and_missing_source(patched_paths: Paths) -> None:
    user_id = "user-1"
    conversation_id = "conv-1"
    patched_paths.ensure_conversation_dirs(user_id, conversation_id)
    outputs = patched_paths.sandbox_outputs_dir(user_id, conversation_id)
    (outputs / "index.html").write_text("<html></html>", encoding="utf-8")
    db = _FakeDb()
    db.conversations[conversation_id] = SimpleNamespace(title="Hello", user_id=user_id)
    service = SitePublishService(db, paths=patched_paths)  # type: ignore[arg-type]
    _bind_lookups(service, db)

    with pytest.raises(SitePublishError, match="目录"):
        service.publish(
            user_id=user_id,
            conversation_id=conversation_id,
            source=f"{vfs_config.outputs_prefix}index.html",
        )
    with pytest.raises(SitePublishError, match="does not exist"):
        service.publish(
            user_id=user_id,
            conversation_id=conversation_id,
            source=f"{vfs_config.outputs_prefix}missing-app",
        )


def test_auto_slug_appends_suffix_on_conflict(patched_paths: Paths) -> None:
    user_id = "user-1"
    conversation_id = "conv-1"
    _seed_app_dist(patched_paths, user_id, conversation_id)
    db = _FakeDb()
    db.sites["my-resume-site"] = PublishedSite(
        slug="my-resume-site",
        user_id="other",
        conversation_id="other-conv",
        site_root="/tmp",
        version=1,
    )
    db.conversations[conversation_id] = SimpleNamespace(
        title="My Resume Site", user_id=user_id
    )
    service = SitePublishService(db, paths=patched_paths)  # type: ignore[arg-type]
    _bind_lookups(service, db)

    result = service.publish(user_id=user_id, conversation_id=conversation_id)
    assert result.site.slug == "my-resume-site-2"


def test_publish_reuses_slug_and_increments_version(
    patched_paths: Paths,
) -> None:
    user_id = "user-1"
    conversation_id = "conv-1"
    _seed_app_dist(patched_paths, user_id, conversation_id)
    db = _FakeDb()
    db.conversations[conversation_id] = SimpleNamespace(
        title="My Resume Site", user_id=user_id
    )
    service = SitePublishService(db, paths=patched_paths)  # type: ignore[arg-type]
    _bind_lookups(service, db)

    first = service.publish(user_id=user_id, conversation_id=conversation_id)
    assert first.site.slug == "my-resume-site"
    assert first.site.version == 1
    current = patched_paths.site_current_link("my-resume-site")
    assert (
        current.resolve()
        == patched_paths.site_version_dir("my-resume-site", 1).resolve()
    )

    second = service.publish(user_id=user_id, conversation_id=conversation_id)
    assert second.site.slug == "my-resume-site"
    assert second.site.version == 2
    assert patched_paths.site_version_dir("my-resume-site", 1).exists()
    assert (
        current.resolve()
        == patched_paths.site_version_dir("my-resume-site", 2).resolve()
    )


def test_requested_slug_conflict_is_409(patched_paths: Paths) -> None:
    db = _FakeDb()
    taken = PublishedSite(
        slug="resume-site",
        user_id="other",
        conversation_id="other-conv",
        site_root="/tmp",
        version=1,
    )
    db.sites["resume-site"] = taken
    db.conversations["conv-1"] = SimpleNamespace(title="Hello", user_id="user-1")
    _seed_app_dist(patched_paths, "user-1", "conv-1")
    service = SitePublishService(db, paths=patched_paths)  # type: ignore[arg-type]
    _bind_lookups(service, db)

    with pytest.raises(SitePublishError) as exc:
        service.publish(
            user_id="user-1",
            conversation_id="conv-1",
            requested_slug="resume-site",
            allow_requested_slug=True,
        )
    assert exc.value.status_code == 409


def test_insert_collision_retries_without_raising_409(
    patched_paths: Paths,
) -> None:
    """IntegrityError on slug PK is retried internally (MCP must not see HTTP 409)."""
    user_id = "user-1"
    conversation_id = "conv-1"
    _seed_app_dist(patched_paths, user_id, conversation_id)
    taken = PublishedSite(
        slug="my-resume-site",
        user_id="other",
        conversation_id="other-conv",
        site_root="/tmp",
        version=1,
    )

    class _RaceDb(_FakeDb):
        def __init__(self) -> None:
            super().__init__()
            self.flush_calls = 0
            self._pending: PublishedSite | None = None

        def add(self, obj: object) -> None:
            if isinstance(obj, PublishedSite):
                self._pending = obj
                return
            super().add(obj)

        def get(self, model: object, pk: str) -> object | None:
            if model is PublishedSite:
                if self.flush_calls == 0:
                    return self.sites.get(pk)
                if pk == "my-resume-site":
                    return taken
                if self._pending is not None and self._pending.slug == pk:
                    return self._pending
                return self.sites.get(pk)
            return super().get(model, pk)

        def flush(self) -> None:
            self.flush_calls += 1
            if self.flush_calls == 1:
                raise IntegrityError("INSERT", {}, Exception("duplicate slug"))
            if self._pending is not None:
                self.sites[self._pending.slug] = self._pending
                self._pending = None

    db = _RaceDb()
    db.conversations[conversation_id] = SimpleNamespace(
        title="My Resume Site", user_id=user_id
    )
    service = SitePublishService(db, paths=patched_paths)  # type: ignore[arg-type]
    _bind_lookups(service, db)

    result = service.publish(user_id=user_id, conversation_id=conversation_id)
    assert result.site.slug.startswith("site-")
    assert result.site.slug != "my-resume-site"
    assert result.site.version == 1


def test_mcp_path_ignores_requested_slug_argument(
    patched_paths: Paths,
) -> None:
    """allow_requested_slug=False never reads a caller-supplied slug."""
    user_id = "user-1"
    conversation_id = "conv-1"
    _seed_app_dist(patched_paths, user_id, conversation_id)
    db = _FakeDb()
    db.conversations[conversation_id] = SimpleNamespace(
        title="My Resume Site", user_id=user_id
    )
    service = SitePublishService(db, paths=patched_paths)  # type: ignore[arg-type]
    _bind_lookups(service, db)

    result = service.publish(
        user_id=user_id,
        conversation_id=conversation_id,
        requested_slug="admin",
        allow_requested_slug=False,
    )
    assert result.site.slug == "my-resume-site"


def test_unpublish_and_expire_unlink_current(patched_paths: Paths) -> None:
    user_id = "user-1"
    conversation_id = "conv-1"
    _seed_app_dist(patched_paths, user_id, conversation_id)
    db = _FakeDb()
    db.conversations[conversation_id] = SimpleNamespace(
        title="My Resume Site", user_id=user_id
    )
    service = SitePublishService(db, paths=patched_paths)  # type: ignore[arg-type]
    _bind_lookups(service, db)
    published = service.publish(user_id=user_id, conversation_id=conversation_id)
    current = patched_paths.site_current_link(published.site.slug)
    assert current.exists()

    service.unpublish(user_id=user_id, slug=published.site.slug)
    assert not current.exists()
    assert patched_paths.site_version_dir(published.site.slug, 1).exists()

    service.publish(user_id=user_id, conversation_id=conversation_id)
    published.site.expires_at = get_datetime_now() - timedelta(days=1)
    published.site.unpublished_at = None
    db.exec = lambda _statement: SimpleNamespace(  # type: ignore[method-assign]
        all=lambda: [published.site]
    )
    expired = service.expire_due_sites()
    assert expired == 1
    assert not current.exists()
    assert published.site.unpublished_at is not None


def test_purge_removes_slug_directory(patched_paths: Paths) -> None:
    user_id = "user-1"
    conversation_id = "conv-1"
    _seed_app_dist(patched_paths, user_id, conversation_id)
    db = _FakeDb()
    db.conversations[conversation_id] = SimpleNamespace(
        title="My Resume Site", user_id=user_id
    )
    service = SitePublishService(db, paths=patched_paths)  # type: ignore[arg-type]
    _bind_lookups(service, db)
    published = service.publish(user_id=user_id, conversation_id=conversation_id)
    site_dir = patched_paths.site_dir(published.site.slug)
    assert site_dir.exists()
    service.purge_for_conversation(user_id=user_id, conversation_id=conversation_id)
    assert not site_dir.exists()
    assert published.site.slug not in db.sites


def test_copy_snapshot_skips_symlinks(patched_paths: Paths) -> None:
    user_id = "user-1"
    conversation_id = "conv-1"
    dist = _seed_app_dist(patched_paths, user_id, conversation_id)
    leaked = patched_paths.conversation_dir(user_id, conversation_id) / "secret.txt"
    leaked.write_text("secret", encoding="utf-8")
    (dist / "link.txt").symlink_to(leaked)

    db = _FakeDb()
    db.conversations[conversation_id] = SimpleNamespace(
        title="site-ok", user_id=user_id
    )
    service = SitePublishService(db, paths=patched_paths)  # type: ignore[arg-type]
    _bind_lookups(service, db)
    result = service.publish(user_id=user_id, conversation_id=conversation_id)
    snapshot = patched_paths.site_version_dir(result.site.slug, 1)
    assert not (snapshot / "link.txt").exists()
    assert (snapshot / "index.html").is_file()


class _DetachingSite:
    """Mimics expire_on_commit: attributes work until the session closes."""

    def __init__(self) -> None:
        self._detached = False
        self.slug = "dev"
        self.version = 2
        self.entry = "index.html"
        self.size_bytes = 42
        self.visibility = "unlisted"
        self.expires_at = None
        self.conversation_id = "conv-1"
        self.unpublished_at = None

    def detach(self) -> None:
        self._detached = True

    def __getattribute__(self, name: str) -> object:
        if name in {"_detached", "detach"}:
            return object.__getattribute__(self, name)
        if object.__getattribute__(self, "_detached"):
            raise DetachedInstanceError(
                "Instance is not bound to a Session; attribute refresh "
                "operation cannot proceed"
            )
        return object.__getattribute__(self, name)


@pytest.mark.asyncio
async def test_publish_site_tool_snapshots_before_session_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = _DetachingSite()
    result = PublishResult(
        site=site,  # type: ignore[arg-type]
        file_count=3,
        url="https://dev.example.com",
    )

    class _Service:
        def __enter__(self) -> _Service:
            return self

        def __exit__(self, *args: object) -> None:
            site.detach()

        def publish(self, **kwargs: object) -> PublishResult:
            return result

    monkeypatch.setattr(
        "app.services.site_publish_service.SitePublishService",
        lambda: _Service(),
    )
    set_request_context(user_id="user-1", conversation_id="conv-1")

    tool_result = await PublishSiteTool().execute({}, ToolContext())

    assert tool_result.is_error is False
    assert tool_result.structured_content == {
        "slug": "dev",
        "version": 2,
        "url": "https://dev.example.com",
        "entry": "index.html",
        "file_count": 3,
        "size_bytes": 42,
    }
    assert "https://dev.example.com" in tool_result.content
