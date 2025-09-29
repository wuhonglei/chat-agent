
import html
from typing import Any, Optional, Dict
from pydantic import BaseModel, Field, field_validator


class ConfluenceStorage(BaseModel):
    """Confluence storage structure"""
    value: str
    representation: str
    expandable: dict[str, str] = Field(
        default_factory=dict, alias="_expandable")


class ConfluencePageBody(BaseModel):
    """Confluence page body structure"""
    storage: ConfluenceStorage
    expandable: dict[str, Any] = Field(
        default_factory=dict, alias="_expandable")


class ConfluencePageLinks(BaseModel):
    """Confluence page links structure"""
    webui: Optional[str] = None
    edit: Optional[str] = None
    tinyui: Optional[str] = None
    collection: Optional[str] = None
    base: Optional[str] = None
    context: Optional[str] = None
    self: Optional[str] = None


class ConfluencePageExpandable(BaseModel):
    """Confluence page expandable structure"""
    container: Optional[str] = None
    metadata: Optional[str] = None
    operations: Optional[str] = None
    children: Optional[str] = None
    restrictions: Optional[str] = None
    history: Optional[str] = None
    ancestors: Optional[str] = None
    version: Optional[str] = None
    descendants: Optional[str] = None
    space: Optional[str] = None


class ConfluencePageExtensions(BaseModel):
    """Confluence page extensions structure"""
    position: Optional[int] = None

    @field_validator('position', mode='before')
    @classmethod
    def validate_position(cls, v):
        if v is None or v == 'none' or v == '':
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None


class ConfluenceVersionBy(BaseModel):
    """Confluence version 'by' user structure"""
    type: Optional[str] = None
    username: Optional[str] = None
    userKey: Optional[str] = None
    accountId: Optional[str] = None
    publicName: Optional[str] = None
    displayName: Optional[str] = None


class ConfluenceVersion(BaseModel):
    """Confluence version structure"""
    by: Optional[ConfluenceVersionBy] = None
    when: Optional[str] = None  # ISO datetime string
    number: Optional[int] = None
    message: Optional[str] = None
    minorEdit: Optional[bool] = None


class ConfluenceHistoryLastUpdated(BaseModel):
    """Confluence history last updated structure"""
    by: Optional[ConfluenceVersionBy] = None
    when: Optional[str] = None  # ISO datetime string
    number: Optional[int] = None


class ConfluenceHistory(BaseModel):
    """Confluence history structure"""
    lastUpdated: Optional[ConfluenceHistoryLastUpdated] = None
    createdDate: Optional[str] = None  # ISO datetime string


class ConfluenceCQLSearchContent(BaseModel):
    """Content structure in CQL search result"""

    id: str
    type: str  # "page" or other content types
    status: str  # "current" etc
    title: str
    restrictions: Dict[str, Any] = Field(default_factory=dict)
    links: Optional[ConfluencePageLinks] = Field(default=None, alias="_links")
    expandable: Optional[ConfluencePageExpandable] = Field(
        default=None, alias="_expandable")


class ConfluenceCQLResultContainer(BaseModel):
    """Container info in CQL search result"""

    title: str
    displayUrl: str


class ConfluenceCQLSearchResult(BaseModel):
    """Single CQL search result structure"""

    content: ConfluenceCQLSearchContent
    title: str  # HTML with highlights like @@@hl@@@keyword@@@endhl@@@
    excerpt: Optional[str] = None  # Content excerpt with highlights
    url: str  # Relative URL path
    resultGlobalContainer: Optional[ConfluenceCQLResultContainer] = None
    entityType: str  # "content"
    iconCssClass: str  # "aui-icon content-type-page"
    lastModified: str  # ISO datetime string
    friendlyLastModified: str  # Human readable date
    timestamp: int  # Unix timestamp in milliseconds

    @property
    def snippet(self) -> str:
        """Get clean snippet without highlight markers

        Removes @@@hl@@@ and @@@endhl@@@ markers from excerpt and unescapes HTML entities
        """
        highlight_start = '@@@hl@@@'
        highlight_end = '@@@endhl@@@'
        if not self.excerpt or highlight_start not in self.excerpt or highlight_end not in self.excerpt:
            return ""

        # Remove highlight markers
        clean_text = self.excerpt.replace(
            highlight_start, "").replace(highlight_end, "")

        # Unescape HTML entities using Python's built-in html module
        clean_text = html.unescape(clean_text)
        return clean_text.strip()


class ConfluenceCQLSearchResponse(BaseModel):
    """CQL search response structure"""

    results: list[ConfluenceCQLSearchResult] = Field(default_factory=list)
    start: int = 0
    limit: int = 25
    size: int = 0
    totalSize: Optional[int] = None
    cqlQuery: Optional[str] = None
    searchDuration: Optional[int] = None

    @property
    def id_to_result(self) -> dict[str, ConfluenceCQLSearchResult]:
        """Get the result map by id"""
        return {result.content.id: result for result in self.results}


class ConfluencePageDetail(BaseModel):
    """Confluence page detail structure"""
    id: str
    type: str
    status: str
    title: str
    body: ConfluencePageBody
    extensions: ConfluencePageExtensions
    links: Optional[ConfluencePageLinks] = Field(default=None, alias="_links")
    expandable: Optional[ConfluencePageExpandable] = Field(
        default=None, alias="_expandable")
    version: Optional[ConfluenceVersion] = None
    history: Optional[ConfluenceHistory] = None

    def get_last_modified_time(self) -> Optional[str]:
        """获取最后修改时间"""
        if self.history and self.history.lastUpdated:
            return self.history.lastUpdated.when
        elif self.version:
            return self.version.when
        return None

    def get_last_modifier_name(self) -> Optional[str]:
        """获取最后修改人名称"""
        if self.history and self.history.lastUpdated and self.history.lastUpdated.by:
            return self.history.lastUpdated.by.displayName or self.history.lastUpdated.by.publicName
        elif self.version and self.version.by:
            return self.version.by.displayName or self.version.by.publicName
        return None

    def get_last_modifier_id(self) -> Optional[str]:
        """获取最后修改人ID"""
        if self.history and self.history.lastUpdated and self.history.lastUpdated.by:
            return self.history.lastUpdated.by.accountId or self.history.lastUpdated.by.userKey
        elif self.version and self.version.by:
            return self.version.by.accountId or self.version.by.userKey
        return None
