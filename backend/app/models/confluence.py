
from typing import Any
from pydantic import BaseModel


class ConfluenceStorage(BaseModel):
    """Confluence storage structure"""
    value: str
    representation: str
    _expandable: dict[str, str]


class ConfluencePageBody(BaseModel):
    """Confluence page body structure"""
    storage: ConfluenceStorage
    _expandable: dict[str, Any]


class ConfluencePageLinks(BaseModel):
    """Confluence page links structure"""
    webui: str
    edit: str
    tinyui: str
    collection: str
    base: str
    context: str
    self: str


class ConfluencePageExpandable(BaseModel):
    """Confluence page expandable structure"""
    container: str
    metadata: str
    operations: str
    children: str
    restrictions: str
    history: str
    ancestors: str
    version: str
    descendants: str
    space: str


class ConfluencePageExtensions(BaseModel):
    """Confluence page extensions structure"""
    position: int


class ConfluencePageDetail(BaseModel):
    """Confluence page detail structure"""
    id: str
    type: str
    status: str
    title: str
    body: ConfluencePageBody
    extensions: ConfluencePageExtensions
    _links: ConfluencePageLinks
    _expandable: ConfluencePageExpandable
