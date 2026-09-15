"""Published-site API request/response models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DEFAULT_SITE_SOURCE = "/mnt/user-data/outputs/app-dist"
SiteVisibility = Literal["unlisted", "public"]


class PublishSiteRequest(BaseModel):
    """Create or republish a site for a conversation."""

    conversation_id: str = Field(min_length=1)
    source: str = Field(default=DEFAULT_SITE_SOURCE, min_length=1)
    slug: str | None = Field(
        default=None,
        description="仅前端自定义链接时传入；省略则服务端生成",
    )
    visibility: SiteVisibility = "unlisted"


class RepublishSiteRequest(BaseModel):
    """Re-snapshot an existing slug."""

    source: str = Field(default=DEFAULT_SITE_SOURCE, min_length=1)
    visibility: SiteVisibility | None = None


class PublishedSiteData(BaseModel):
    """Public representation of a published site."""

    slug: str
    version: int
    url: str
    visibility: str
    size_bytes: int
    expires_at: datetime | None
    conversation_id: str
    unpublished_at: datetime | None = None
    entry: str = "index.html"
    file_count: int | None = None
