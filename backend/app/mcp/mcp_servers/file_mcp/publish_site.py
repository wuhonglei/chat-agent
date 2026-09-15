"""publish_site MCP tool: snapshot outputs to a public static-site URL."""

from __future__ import annotations

from typing import Any

from app.mcp.mcp_servers.file_mcp.base import ToolBase, ToolContext, ToolResult
from app.schemas.sites import DEFAULT_SITE_SOURCE
from app.utils.logger import logger

PUBLISH_SITE_DESCRIPTION = """Publish the built static site under /mnt/user-data/outputs/ so the user can open it on a public URL.

When to use:
- Only when the user explicitly asks to publish, share externally, or get a public/domain URL
- After the production build has been copied to /mnt/user-data/outputs/app-dist/

When NOT to use:
- For in-session preview only
- When the user did not ask to make the site publicly reachable

Notes:
- Do not guess or pass a slug; the server generates or reuses one
- Do not call /api/sites/me and do not construct {slug}.apps... yourself
- Tell the user the returned url verbatim; do not retry just to change the slug
- Repeating the call for the same conversation reuses the slug and increments version
"""


class PublishSiteTool(ToolBase):
    """Publish a static site from conversation outputs. Schema has no slug."""

    name = "publish_site"
    description = PUBLISH_SITE_DESCRIPTION

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> ToolResult:
        source = arguments.get("source") or DEFAULT_SITE_SOURCE
        visibility = arguments.get("visibility") or "unlisted"
        if not isinstance(source, str) or not source.strip():
            return ToolResult(
                content="Error: source must be a non-empty string", is_error=True
            )
        if not isinstance(visibility, str):
            return ToolResult(
                content="Error: visibility must be a string", is_error=True
            )

        if not ctx.user_id or not ctx.conversation_id:
            return ToolResult(
                content="Error: missing user or conversation context",
                is_error=True,
            )

        # Circular import: MCP registry may load this module while
        # app.models.conversation_db is still initializing
        # (conversation_db → schemas.conversation → schemas.chat → app.mcp).
        from app.services.site_publish_service import (  # noqa: I001
            SitePublishError,
            SitePublishService,
            to_site_data,
        )

        try:
            with SitePublishService() as service:
                result = service.publish(
                    user_id=ctx.user_id,
                    conversation_id=ctx.conversation_id,
                    source=source.strip(),
                    visibility=visibility,  # type: ignore[arg-type]
                    allow_requested_slug=False,
                )
                # Snapshot before DbService.__exit__ commits and expires the ORM row.
                data = to_site_data(result.site, file_count=result.file_count)
                url = result.url
        except SitePublishError as exc:
            logger.warning(
                "publish_site failed",
                error=exc.message,
                status_code=exc.status_code,
                source=source,
            )
            return ToolResult(content=f"Error: {exc.message}", is_error=True)
        except Exception as exc:
            logger.exception("publish_site unexpected error", error=exc)
            return ToolResult(content=f"Error: {exc}", is_error=True)

        payload = {
            "slug": data.slug,
            "version": data.version,
            "url": url,
            "entry": data.entry,
            "file_count": data.file_count,
            "size_bytes": data.size_bytes,
        }
        logger.info("Site published via MCP", **payload)
        return ToolResult(
            content=(
                "Published successfully. Tell the user this url verbatim and do not "
                f"invent a different domain: {url}"
            ),
            structured_content=payload,
        )
