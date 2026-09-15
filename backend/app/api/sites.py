"""Published static-site APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.db import get_db
from app.schemas.auth import AuthTokenPayload
from app.schemas.response import ApiResponse
from app.schemas.sites import (
    PublishedSiteData,
    PublishSiteRequest,
    RepublishSiteRequest,
)
from app.services.site_publish_service import (
    SitePublishError,
    SitePublishService,
    to_site_data,
)
from app.utils.auth_deps import get_auth_token_info

router = APIRouter()


def _http_error(exc: SitePublishError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/")
async def publish_site(
    request: PublishSiteRequest,
    db: Session = Depends(get_db),
    auth_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[PublishedSiteData]:
    """Publish or republish the conversation's outputs as a public static site."""
    service = SitePublishService(db)
    try:
        result = service.publish(
            user_id=auth_info.user_id,
            conversation_id=request.conversation_id,
            source=request.source,
            visibility=request.visibility,
            requested_slug=request.slug,
            allow_requested_slug=True,
        )
    except SitePublishError as exc:
        raise _http_error(exc) from exc
    return ApiResponse.success(
        data=to_site_data(result.site, file_count=result.file_count),
        msg="发布成功",
    )


@router.post("/{slug}/republish")
async def republish_site(
    slug: str,
    request: RepublishSiteRequest,
    db: Session = Depends(get_db),
    auth_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[PublishedSiteData]:
    """Take a new snapshot and switch ``current`` (version+1)."""
    service = SitePublishService(db)
    try:
        result = service.republish(
            user_id=auth_info.user_id,
            slug=slug,
            source=request.source,
            visibility=request.visibility,
        )
    except SitePublishError as exc:
        raise _http_error(exc) from exc
    return ApiResponse.success(
        data=to_site_data(result.site, file_count=result.file_count),
        msg="重新发布成功",
    )


@router.get("/me")
async def list_my_sites(
    db: Session = Depends(get_db),
    auth_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[list[PublishedSiteData]]:
    """List sites owned by the current user (not an agent conflict-check API)."""
    service = SitePublishService(db)
    sites = service.list_for_user(auth_info.user_id)
    return ApiResponse.success(data=[to_site_data(site) for site in sites])


@router.delete("/{slug}")
async def unpublish_site(
    slug: str,
    db: Session = Depends(get_db),
    auth_info: AuthTokenPayload = Depends(get_auth_token_info),
) -> ApiResponse[PublishedSiteData]:
    """Unpublish: unlink ``current`` so nginx 404s immediately."""
    service = SitePublishService(db)
    try:
        site = service.unpublish(user_id=auth_info.user_id, slug=slug)
    except SitePublishError as exc:
        raise _http_error(exc) from exc
    return ApiResponse.success(data=to_site_data(site), msg="已下线")
