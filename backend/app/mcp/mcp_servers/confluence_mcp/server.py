"""Confluence FastMCP server instance and tool definitions."""

import json
import logging
from typing import Annotated

from fastmcp import Context, FastMCP
from pydantic import BeforeValidator, Field
from .services import ConfluenceFetcher


logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="Confluence MCP Service",
    description="Provides tools for interacting with Atlassian Confluence.",
)


@mcp.tool(tags={"confluence", "read"})
async def search(
    ctx: Context,
    query: Annotated[
        str,
        Field(
            description=(
                "Search query - can be either a simple text (e.g. 'project documentation') or a CQL query string. "
                "Simple queries use 'siteSearch' by default, to mimic the WebUI search, with an automatic fallback "
                "to 'text' search if not supported. Examples of CQL:\n"
                "- Basic search: 'type=page AND space=DEV'\n"
                "- Personal space search: 'space=\"~username\"' (note: personal space keys starting with ~ must be quoted)\n"
                "- Search by title: 'title~\"Meeting Notes\"'\n"
                "- Use siteSearch: 'siteSearch ~ \"important concept\"'\n"
                "- Use text search: 'text ~ \"important concept\"'\n"
                "- Recent content: 'created >= \"2023-01-01\"'\n"
                "- Content with specific label: 'label=documentation'\n"
                "- Recently modified content: 'lastModified > startOfMonth(\"-1M\")'\n"
                "- Content modified this year: 'creator = currentUser() AND lastModified > startOfYear()'\n"
                "- Content you contributed to recently: 'contributor = currentUser() AND lastModified > startOfWeek()'\n"
                "- Content watched by user: 'watcher = \"user@domain.com\" AND type = page'\n"
                '- Exact phrase in content: \'text ~ "\\"Urgent Review Required\\"" AND label = "pending-approval"\'\n'
                '- Title wildcards: \'title ~ "Minutes*" AND (space = "HR" OR space = "Marketing")\'\n'
                'Note: Special identifiers need proper quoting in CQL: personal space keys (e.g., "~username"), '
                "reserved words, numeric IDs, and identifiers with special characters."
            )
        ),
    ],
    limit: Annotated[
        int,
        Field(
            description="Maximum number of results (1-50)",
            default=10,
            ge=1,
            le=50,
        ),
    ] = 10,
    spaces_filter: Annotated[
        str | None,
        Field(
            description=(
                "(Optional) Comma-separated list of space keys to filter results by. "
                "Overrides the environment variable CONFLUENCE_SPACES_FILTER if provided. "
                "Use empty string to disable filtering."
            ),
            default=None,
        ),
    ] = None,
) -> str:
    """Search Confluence content using simple terms or CQL.

    Args:
        ctx: The FastMCP context.
        query: Search query - can be simple text or a CQL query string.
        limit: Maximum number of results (1-50).
        spaces_filter: Comma-separated list of space keys to filter by.

    Returns:
        JSON string representing a list of simplified Confluence page objects.
    """
    confluence_fetcher = await get_confluence_fetcher(ctx)
    # Check if the query is a simple search term or already a CQL query
    if query and not any(
        x in query for x in ["=", "~", ">", "<", " AND ", " OR ", "currentUser()"]
    ):
        original_query = query
        try:
            query = f'siteSearch ~ "{original_query}"'
            logger.info(
                f"Converting simple search term to CQL using siteSearch: {query}"
            )
            pages = confluence_fetcher.search(
                query, limit=limit, spaces_filter=spaces_filter
            )
        except Exception as e:
            logger.warning(
                f"siteSearch failed ('{e}'), falling back to text search.")
            query = f'text ~ "{original_query}"'
            logger.info(f"Falling back to text search with CQL: {query}")
            pages = confluence_fetcher.search(
                query, limit=limit, spaces_filter=spaces_filter
            )
    else:
        pages = confluence_fetcher.search(
            query, limit=limit, spaces_filter=spaces_filter
        )
    search_results = [page.to_simplified_dict() for page in pages]
    return json.dumps(search_results, indent=2, ensure_ascii=False)


@mcp.tool(tags={"confluence", "read"})
async def get_page(
    ctx: Context,
    page_id: Annotated[
        str | None,
        Field(
            description=(
                "Confluence page ID (numeric ID, can be found in the page URL). "
                "For example, in the URL 'https://example.atlassian.net/wiki/spaces/TEAM/pages/123456789/Page+Title', "
                "the page ID is '123456789'. "
                "Provide this OR both 'title' and 'space_key'. If page_id is provided, title and space_key will be ignored."
            ),
            default=None,
        ),
    ] = None,
    title: Annotated[
        str | None,
        Field(
            description=(
                "The exact title of the Confluence page. Use this with 'space_key' if 'page_id' is not known."
            ),
            default=None,
        ),
    ] = None,
    space_key: Annotated[
        str | None,
        Field(
            description=(
                "The key of the Confluence space where the page resides (e.g., 'DEV', 'TEAM'). Required if using 'title'."
            ),
            default=None,
        ),
    ] = None,
    include_metadata: Annotated[
        bool,
        Field(
            description="Whether to include page metadata such as creation date, last update, version, and labels.",
            default=True,
        ),
    ] = True,
    convert_to_markdown: Annotated[
        bool,
        Field(
            description=(
                "Whether to convert page to markdown (true) or keep it in raw HTML format (false). "
                "Raw HTML can reveal macros (like dates) not visible in markdown, but CAUTION: "
                "using HTML significantly increases token usage in AI responses."
            ),
            default=True,
        ),
    ] = True,
) -> str:
    """Get content of a specific Confluence page by its ID, or by its title and space key.

    Args:
        ctx: The FastMCP context.
        page_id: Confluence page ID. If provided, 'title' and 'space_key' are ignored.
        title: The exact title of the page. Must be used with 'space_key'.
        space_key: The key of the space. Must be used with 'title'.
        include_metadata: Whether to include page metadata.
        convert_to_markdown: Convert content to markdown (true) or keep raw HTML (false).

    Returns:
        JSON string representing the page content and/or metadata, or an error if not found or parameters are invalid.
    """
    confluence_fetcher = await get_confluence_fetcher(ctx)
    page_object = None

    if page_id:
        if title or space_key:
            logger.warning(
                "page_id was provided; title and space_key parameters will be ignored."
            )
        try:
            page_object = confluence_fetcher.get_page_content(
                page_id, convert_to_markdown=convert_to_markdown
            )
        except Exception as e:
            logger.error(f"Error fetching page by ID '{page_id}': {e}")
            return json.dumps(
                {"error": f"Failed to retrieve page by ID '{page_id}': {e}"},
                indent=2,
                ensure_ascii=False,
            )
    elif title and space_key:
        page_object = confluence_fetcher.get_page_by_title(
            space_key, title, convert_to_markdown=convert_to_markdown
        )
        if not page_object:
            return json.dumps(
                {
                    "error": f"Page with title '{title}' not found in space '{space_key}'."
                },
                indent=2,
                ensure_ascii=False,
            )
    else:
        raise ValueError(
            "Either 'page_id' OR both 'title' and 'space_key' must be provided."
        )

    if not page_object:
        return json.dumps(
            {"error": "Page not found with the provided identifiers."},
            indent=2,
            ensure_ascii=False,
        )

    if include_metadata:
        result = {"metadata": page_object.to_simplified_dict()}
    else:
        result = {"content": {"value": page_object.content}}

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool(tags={"confluence", "read"})
async def get_page_children(
    ctx: Context,
    parent_id: Annotated[
        str,
        Field(
            description="The ID of the parent page whose children you want to retrieve"
        ),
    ],
    expand: Annotated[
        str,
        Field(
            description="Fields to expand in the response (e.g., 'version', 'body.storage')",
            default="version",
        ),
    ] = "version",
    limit: Annotated[
        int,
        Field(
            description="Maximum number of child pages to return (1-50)",
            default=25,
            ge=1,
            le=50,
        ),
    ] = 25,
    include_content: Annotated[
        bool,
        Field(
            description="Whether to include the page content in the response",
            default=False,
        ),
    ] = False,
    convert_to_markdown: Annotated[
        bool,
        Field(
            description="Whether to convert page content to markdown (true) or keep it in raw HTML format (false). Only relevant if include_content is true.",
            default=True,
        ),
    ] = True,
    start: Annotated[
        int,
        Field(description="Starting index for pagination (0-based)", default=0, ge=0),
    ] = 0,
) -> str:
    """Get child pages of a specific Confluence page.

    Args:
        ctx: The FastMCP context.
        parent_id: The ID of the parent page.
        expand: Fields to expand.
        limit: Maximum number of child pages.
        include_content: Whether to include page content.
        convert_to_markdown: Convert content to markdown if include_content is true.
        start: Starting index for pagination.

    Returns:
        JSON string representing a list of child page objects.
    """
    confluence_fetcher = await get_confluence_fetcher(ctx)
    if include_content and "body" not in expand:
        expand = f"{expand},body.storage" if expand else "body.storage"

    try:
        pages = confluence_fetcher.get_page_children(
            page_id=parent_id,
            start=start,
            limit=limit,
            expand=expand,
            convert_to_markdown=convert_to_markdown,
        )
        child_pages = [page.to_simplified_dict() for page in pages]
        result = {
            "parent_id": parent_id,
            "count": len(child_pages),
            "limit_requested": limit,
            "start_requested": start,
            "results": child_pages,
        }
    except Exception as e:
        logger.error(
            f"Error getting/processing children for page ID {parent_id}: {e}",
            exc_info=True,
        )
        result = {"error": f"Failed to get child pages: {e}"}

    return json.dumps(result, indent=2, ensure_ascii=False)
