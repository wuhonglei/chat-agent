"""Confluence FastMCP server instance and tool definitions."""

import logging
import asyncio
from fastmcp import FastMCP
from pydantic import Field
from .services import ConfluenceFetcher, ConfluenceConfig
from .config import config
from .models.confluence import ConfluencePage


logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="Shopee Internal Company Knowledge Base Confluence MCP Service",
)

confluence_fetcher = ConfluenceFetcher(config=ConfluenceConfig(
    url=config.CONFLUENCE_URL,
    personal_token=config.CONFLUENCE_PERSONAL_TOKEN,
    auth_type=config.AUTH_TYPE,
))


async def _confluence_get_page(
    page_id: str = Field(
        description=(
            "Shopee internal company knowledge base Confluence page ID (numeric ID, can be found in the page URL). "
            "For example, in the URL 'https://confluence.shopee.io/pages/viewpage.action?pageId=1234567890', "
            "the page ID is '1234567890'. "
            "Provide this OR both 'title' and 'space_key'. If page_id is provided, title and space_key will be ignored."
        ),
        default=None,
    ),
    title: str = Field(
        description=(
            "The exact title of the Shopee internal company knowledge base Confluence page. Use this with 'space_key' if 'page_id' is not known. "
            "For example, in the URL 'https://confluence.shopee.io/display/MKT/FE+code+specification', "
            "the title is 'FE code specification'."
        ),
        default=None,
    ),
    space_key: str = Field(
        description=(
            "The key of the Shopee internal company knowledge base Confluence space where the page resides (e.g., 'DEV', 'TEAM'). Required if using 'title'. "
            "For example, in the URL 'https://confluence.shopee.io/display/MKT/01+FE+code+specification', "
            "the space key is 'MKT'."
        ),
        default=None,
    ),
) -> ConfluencePage:
    """Get content of a specific Confluence page by its ID, or by its title and space key.

    Args:
        page_id: Confluence page ID. If provided, 'title' and 'space_key' are ignored.
        title: The exact title of the page. Must be used with 'space_key'.
        space_key: The key of the space. Must be used with 'title'.
        convert_to_markdown: Convert content to markdown (true) or keep raw HTML (false).

    Returns:
        ConfluencePage object representing the page content, or an error if not found or parameters are invalid.
    """
    if page_id:
        return await asyncio.to_thread(confluence_fetcher.get_page_content, page_id)
    elif title and space_key:
        return await asyncio.to_thread(confluence_fetcher.get_page_by_title, space_key, title)
    raise ValueError(
        "Either 'page_id' OR both 'title' and 'space_key' must be provided.")


@mcp.tool()
async def shopee_confluence_search(
    query: str = Field(
        description=(
            "Search query for Shopee internal company knowledge base Confluence - can be either simple text (e.g. 'project documentation') or CQL query string. "
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
    limit: int = Field(
        description="Maximum number of results (1-50)",
        default=10,
        ge=1,
        le=50,
    ),
    spaces_filter: str = Field(
        description=(
            "(Optional) Comma-separated list of Shopee internal company knowledge base Confluence space keys to filter results by. "
            "Overrides the environment variable CONFLUENCE_SPACES_FILTER if provided. "
            "Use empty string to disable filtering."
        ),
        default=None,
    ),
    include_content: bool = Field(
        description="Whether to fetch detailed content for each page",
        default=True,
    ),
) -> list[ConfluencePage]:
    """Search Shopee internal company knowledge base Confluence content using simple terms or CQL queries."""
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
            pages = await asyncio.to_thread(
                confluence_fetcher.search,
                query, limit=limit, spaces_filter=spaces_filter
            )
        except Exception as e:
            logger.warning(
                f"siteSearch failed ('{e}'), falling back to text search.")
            query = f'text ~ "{original_query}"'
            logger.info(f"Falling back to text search with CQL: {query}")
            pages = await asyncio.to_thread(
                confluence_fetcher.search,
                query, limit=limit, spaces_filter=spaces_filter
            )
    else:
        pages = await asyncio.to_thread(
            confluence_fetcher.search,
            query, limit=limit, spaces_filter=spaces_filter
        )

    # If include_content is True, fetch detailed content for each page
    if include_content and pages:
        logger.info(f"Fetching detailed content for {len(pages)} pages")

        async def fetch_page_content(page: ConfluencePage) -> ConfluencePage:
            """Fetch detailed content for a single page with error handling."""
            try:
                detailed_page = await _confluence_get_page(page_id=page.id)
                # Preserve the original search result metadata (excerpt, etc.)
                detailed_page.excerpt = page.excerpt
                return detailed_page
            except Exception as e:
                logger.warning(
                    f"Failed to fetch detailed content for page {page.id} ({page.title}): {e}")
                # Return the original page if detailed content fetch fails
                return page

        # Fetch detailed content for all pages concurrently
        pages = await asyncio.gather(
            *[fetch_page_content(page) for page in pages],
        )

        logger.info(
            f"Successfully fetched detailed content for {len(pages)} pages")

    return pages


@mcp.tool()
async def shopee_confluence_get_page(
    page_id: str = Field(
        description=(
            "Shopee internal company knowledge base Confluence page ID (numeric ID, can be found in the page URL). "
            "For example, in the URL 'https://confluence.shopee.io/pages/viewpage.action?pageId=1234567890', "
            "the page ID is '1234567890'. "
            "Provide this OR both 'title' and 'space_key'. If page_id is provided, title and space_key will be ignored."
        ),
        default=None,
    ),
    title: str = Field(
        description=(
            "The exact title of the Shopee internal company knowledge base Confluence page. Use this with 'space_key' if 'page_id' is not known. "
            "For example, in the URL 'https://confluence.shopee.io/display/MKT/FE+code+specification', "
            "the title is 'FE+code+specification'."
        ),
        default=None,
    ),
    space_key: str = Field(
        description=(
            "The key of the Shopee internal company knowledge base Confluence space where the page resides (e.g., 'DEV', 'TEAM'). Required if using 'title'. "
            "For example, in the URL 'https://confluence.shopee.io/display/MKT/01+FE+code+specification', "
            "the space key is 'MKT'."
        ),
        default=None,
    ),
) -> ConfluencePage:
    """Get content of a specific page from Shopee internal company knowledge base Confluence by its ID, or by its title and space key."""
    return await _confluence_get_page(page_id, title, space_key)


@mcp.tool()
async def shopee_confluence_get_page_children(
    parent_id: str = Field(
        description="The ID of the parent page from Shopee internal company knowledge base Confluence whose children you want to retrieve"
    ),
    expand: str = Field(
        description="Fields to expand in the response (e.g., 'version', 'body.storage')",
        default="version",
    ),
    limit: int = Field(
        description="Maximum number of child pages to return (1-50)",
        default=25,
        ge=1,
        le=50,
    ),
    include_content: bool = Field(
        description="Whether to include the page content in the response",
        default=False,
    ),
    convert_to_markdown: bool = Field(
        description="Whether to convert page content to markdown (true) or keep it in raw HTML format (false). Only relevant if include_content is true.",
        default=True,
    ),
    start: int = Field(
        description="Starting index for pagination (0-based)", default=0, ge=0),
) -> list[ConfluencePage]:
    """Get child pages of a specific page from Shopee internal company knowledge base Confluence."""
    if include_content and "body" not in expand:
        expand = f"{expand},body.storage" if expand else "body.storage"

    try:
        pages = await asyncio.to_thread(
            confluence_fetcher.get_page_children,
            page_id=parent_id,
            start=start,
            limit=limit,
            expand=expand,
            convert_to_markdown=convert_to_markdown,
        )
        return pages
    except Exception as e:
        logger.error(
            f"Error getting/processing children for page ID {parent_id}: {e}",
            exc_info=True,
        )
        raise Exception(f"Failed to get child pages: {e}") from e


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Confluence MCP Server")
    parser.add_argument("--transport", choices=["http", "stdio"], default="http",
                        help="Transport mode: http or stdio")
    parser.add_argument("--port", type=int, default=8003,
                        help="Port number for HTTP mode")

    args = parser.parse_args()

    if args.transport == "stdio":
        # Stdio mode: communicate with client via stdin/stdout
        mcp.run(transport="stdio")
    else:
        # HTTP mode: start HTTP server
        mcp.run(transport="http", port=args.port)
