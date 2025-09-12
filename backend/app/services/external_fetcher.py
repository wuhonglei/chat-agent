"""External document fetcher service"""

import re
from typing import Dict, Tuple

import httpx
from atlassian import Confluence
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build
from loguru import logger

from app.core.config import settings


class ExternalDocumentFetcher:
    """Fetch documents from external sources"""

    def __init__(self):
        self.confluence_client = self._init_confluence()
        self.google_docs_service = self._init_google_docs()
        self.google_slides_service = self._init_google_slides()

    def _init_confluence(self):
        """Initialize Confluence client"""
        if settings.CONFLUENCE_URL and settings.CONFLUENCE_API_TOKEN:
            return Confluence(
                url=settings.CONFLUENCE_URL,
                username=settings.CONFLUENCE_USERNAME,
                password=settings.CONFLUENCE_API_TOKEN,
                cloud=True,
            )
        return None

    def _init_google_docs(self):
        """Initialize Google Docs service"""
        # TODO: Implement Google service account authentication
        return None

    def _init_google_slides(self):
        """Initialize Google Slides service"""
        # TODO: Implement Google service account authentication
        return None

    async def fetch_confluence(self, url: str) -> Tuple[str, Dict]:
        """Fetch content from Confluence"""
        try:
            if not self.confluence_client:
                raise ValueError("Confluence not configured")

            # Extract page ID from URL
            page_id = self._extract_confluence_page_id(url)

            # Get page content
            page = self.confluence_client.get_page_by_id(
                page_id,
                expand='body.storage,version,space'
            )

            # Extract content
            html_content = page['body']['storage']['value']
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = soup.get_text()

            # Build metadata
            metadata = {
                'title': page['title'],
                'space': page['space']['name'],
                'version': page['version']['number'],
                'last_updated': page['version']['when'],
                'author': page['version']['by']['displayName'],
                'url': url,
            }

            return text_content, metadata

        except Exception as e:
            logger.error(f"Failed to fetch Confluence page: {e}")
            raise

    async def fetch_google_docs(self, url: str) -> Tuple[str, Dict]:
        """Fetch content from Google Docs"""
        try:
            # Extract document ID from URL
            doc_id = self._extract_google_doc_id(url)

            # For MVP, use public documents or require manual copy-paste
            # TODO: Implement proper Google Docs API integration

            # Fetch public document as HTML
            export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

            async with httpx.AsyncClient() as client:
                response = await client.get(export_url)

                if response.status_code == 200:
                    content = response.text
                    metadata = {
                        'title': f"Google Doc {doc_id}",
                        'url': url,
                        'doc_id': doc_id,
                    }
                    return content, metadata
                else:
                    raise ValueError(
                        f"Failed to fetch Google Doc: {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to fetch Google Doc: {e}")
            raise

    async def fetch_google_slides(self, url: str) -> Tuple[str, Dict]:
        """Fetch content from Google Slides"""
        try:
            # Extract presentation ID from URL
            presentation_id = self._extract_google_slides_id(url)

            # For MVP, extract text from public presentations
            # TODO: Implement proper Google Slides API integration

            # Fetch public presentation as text
            export_url = f"https://docs.google.com/presentation/d/{presentation_id}/export?format=txt"

            async with httpx.AsyncClient() as client:
                response = await client.get(export_url)

                if response.status_code == 200:
                    content = response.text
                    metadata = {
                        'title': f"Google Slides {presentation_id}",
                        'url': url,
                        'presentation_id': presentation_id,
                    }
                    return content, metadata
                else:
                    raise ValueError(
                        f"Failed to fetch Google Slides: {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to fetch Google Slides: {e}")
            raise

    def _extract_confluence_page_id(self, url: str) -> str:
        """Extract page ID from Confluence URL"""
        # Pattern for Confluence Cloud URLs
        pattern = r'/pages/(\d+)/'
        match = re.search(pattern, url)
        if match:
            return match.group(1)

        # Try alternative pattern
        pattern = r'pageId=(\d+)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)

        raise ValueError(f"Could not extract page ID from URL: {url}")

    def _extract_google_doc_id(self, url: str) -> str:
        """Extract document ID from Google Docs URL"""
        pattern = r'/document/d/([a-zA-Z0-9-_]+)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        raise ValueError(f"Could not extract document ID from URL: {url}")

    def _extract_google_slides_id(self, url: str) -> str:
        """Extract presentation ID from Google Slides URL"""
        pattern = r'/presentation/d/([a-zA-Z0-9-_]+)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        raise ValueError(f"Could not extract presentation ID from URL: {url}")
