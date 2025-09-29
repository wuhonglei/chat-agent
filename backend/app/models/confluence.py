
from typing import Any, Optional
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
