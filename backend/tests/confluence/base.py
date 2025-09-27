"""Base preprocessing module."""

import logging
import re
import warnings
from typing import Any, Protocol
from urllib.parse import quote

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md

logger = logging.getLogger("mcp-atlassian")


class ConfluenceClient(Protocol):
    """Protocol for Confluence client."""

    def get_user_details_by_accountid(self, account_id: str) -> dict[str, Any]:
        """Get user details by account ID."""
        ...

    def get_user_details_by_username(self, username: str) -> dict[str, Any]:
        """Get user details by username (for Server/DC compatibility)."""
        ...

    def get_user_details_by_userkey(self, userkey: str) -> dict[str, Any]:
        """Get user details by userkey (for Server/DC compatibility)."""
        ...


class BasePreprocessor:
    """Base class for text preprocessing operations."""

    def __init__(self, base_url: str = "") -> None:
        """
        Initialize the base text preprocessor.

        Args:
            base_url: Base URL for API server
        """
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.cache_user_details = {
            "account_id": {},
            "userkey": {},
        }

    def process_html_content(
        self,
        html_content: str,
        confluence_client: ConfluenceClient | None = None,
        image_prefix: str = "",
    ) -> tuple[str, str]:
        """
        Process HTML content to replace user refs and page links.

        Args:
            html_content: The HTML content to process
            confluence_client: Optional Confluence client for user lookups
            image_prefix: Optional prefix for constructing image URLs

        Returns:
            Tuple of (processed_html, processed_markdown)
        """
        try:
            # Parse the HTML content
            soup = BeautifulSoup(html_content, "html.parser")

            # Process user mentions
            self._process_user_mentions_in_soup(soup, confluence_client)
            self._process_user_profile_macros_in_soup(soup, confluence_client)
            # Process code macros
            self._process_code_macros_in_soup(soup)
            # Process time tags
            self._process_time_tags_in_soup(soup)
            # Process images
            self._process_images_in_soup(soup, image_prefix)
            # Process internal page links
            self._process_page_links_in_soup(soup)

            # Convert to string and markdown
            processed_html = str(soup)
            processed_markdown = md(processed_html)

            return processed_html, processed_markdown

        except Exception as e:
            logger.error(f"Error in process_html_content: {str(e)}")
            raise

    def _process_user_mentions_in_soup(
        self, soup: BeautifulSoup, confluence_client: ConfluenceClient | None = None
    ) -> None:
        """
        Process user mentions in BeautifulSoup object.

        Args:
            soup: BeautifulSoup object containing HTML
            confluence_client: Optional Confluence client for user lookups
        """
        # Find all ac:link elements that might contain user mentions
        user_mentions = soup.find_all("ac:link")

        for user_element in user_mentions:
            user_ref = user_element.find("ri:user")
            if user_ref:
                # Check for account-id (Confluence Cloud)
                account_id = user_ref.get("ri:account-id")
                userkey = user_ref.get("ri:userkey")

                if account_id and isinstance(account_id, str):
                    self._replace_user_mention_by_accountid(
                        user_element, account_id, confluence_client
                    )
                elif userkey and isinstance(userkey, str):
                    self._replace_user_mention_by_userkey(
                        user_element, userkey, confluence_client
                    )

    def _process_user_profile_macros_in_soup(
        self, soup: BeautifulSoup, confluence_client: ConfluenceClient | None = None
    ) -> None:
        """
        Process Confluence User Profile macros in BeautifulSoup object.
        Replaces <ac:structured-macro ac:name="profile">...</ac:structured-macro>
        with the user's display name, typically formatted as @DisplayName.

        Args:
            soup: BeautifulSoup object containing HTML
            confluence_client: Optional Confluence client for user lookups
        """
        profile_macros = soup.find_all(
            "ac:structured-macro", attrs={"ac:name": "profile"}
        )

        for macro_element in profile_macros:
            user_param = macro_element.find(
                "ac:parameter", attrs={"ac:name": "user"})
            if not user_param:
                logger.debug(
                    "User profile macro found without a 'user' parameter. Replacing with placeholder."
                )
                macro_element.replace_with("[User Profile Macro (Malformed)]")
                continue

            user_ref = user_param.find("ri:user")
            if not user_ref:
                logger.debug(
                    "User profile macro's 'user' parameter found without 'ri:user' tag. Replacing with placeholder."
                )
                macro_element.replace_with("[User Profile Macro (Malformed)]")
                continue

            account_id = user_ref.get("ri:account-id")
            # Fallback for Confluence Server/DC
            userkey = user_ref.get("ri:userkey")

            user_identifier_for_log = account_id or userkey
            display_name = None

            if confluence_client and user_identifier_for_log:
                try:
                    if account_id and isinstance(account_id, str):
                        user_details = confluence_client.get_user_details_by_accountid(
                            account_id
                        )
                        display_name = user_details.get("displayName")
                    elif userkey and isinstance(userkey, str):
                        # For Confluence Server/DC, use userkey
                        user_details = confluence_client.get_user_details_by_userkey(
                            userkey
                        )
                        display_name = user_details.get("displayName")
                except Exception as e:
                    logger.warning(
                        f"Error fetching user details for profile macro (user: {user_identifier_for_log}): {e}"
                    )
            elif not confluence_client:
                logger.warning(
                    "Confluence client not available for User Profile Macro processing."
                )

            if display_name:
                replacement_text = f"@{display_name}"
                macro_element.replace_with(replacement_text)
            else:
                fallback_identifier = (
                    user_identifier_for_log
                    if user_identifier_for_log
                    else "unknown_user"
                )
                fallback_text = f"[User Profile: {fallback_identifier}]"
                macro_element.replace_with(fallback_text)
                logger.debug(
                    f"Using fallback for user profile macro: {fallback_text}")

    def _process_code_macros_in_soup(self, soup: BeautifulSoup) -> None:
        """
        Process Confluence code macros in BeautifulSoup object.
        Converts <ac:structured-macro ac:name="code">...</ac:structured-macro>
        to standard HTML <pre><code> blocks.

        Args:
            soup: BeautifulSoup object containing HTML
        """
        code_macros = soup.find_all(
            "ac:structured-macro", attrs={"ac:name": "code"}
        )

        for macro_element in code_macros:
            # Find the plain text body containing the code
            plain_text_body = macro_element.find("ac:plain-text-body")

            if plain_text_body:
                # Extract the CDATA content
                code_content = plain_text_body.string or ""

                # Clean up CDATA markers if present
                if code_content.startswith("<![CDATA["):
                    code_content = code_content[9:]  # Remove "<![CDATA["
                if code_content.endswith("]]>"):
                    code_content = code_content[:-3]  # Remove "]]>"

                # Find language parameter if it exists
                language_param = macro_element.find(
                    "ac:parameter", attrs={"ac:name": "language"}
                )
                language = language_param.string if language_param else ""

                # Create new pre/code block
                pre_tag = soup.new_tag("pre")
                code_tag = soup.new_tag("code")
                if language:
                    code_tag["class"] = f"language-{language}"
                code_tag.string = code_content.strip()
                pre_tag.append(code_tag)

                # Replace the macro with the pre/code block
                macro_element.replace_with(pre_tag)
            else:
                # If no plain-text-body found, replace with placeholder
                logger.warning("Code macro found without plain-text-body")
                placeholder = soup.new_tag("pre")
                code_tag = soup.new_tag("code")
                code_tag.string = "[Code block - content not found]"
                placeholder.append(code_tag)
                macro_element.replace_with(placeholder)

    def _process_time_tags_in_soup(self, soup: BeautifulSoup) -> None:
        """
        Process time tags in BeautifulSoup object.
        Replaces <time datetime="YYYY-MM-DD" /> with readable date format.

        Args:
            soup: BeautifulSoup object containing HTML
        """
        time_tags = soup.find_all("time")

        for time_tag in time_tags:
            datetime_attr = time_tag.get("datetime")
            if datetime_attr:
                try:
                    # Parse the datetime attribute (assuming YYYY-MM-DD format)
                    from datetime import datetime
                    date_obj = datetime.strptime(datetime_attr, "%Y-%m-%d")
                    # Format as readable date
                    formatted_date = date_obj.strftime("%Y年%m月%d日")
                    time_tag.replace_with(formatted_date)
                except ValueError as e:
                    logger.warning(
                        f"Error parsing datetime '{datetime_attr}': {e}")
                    # Fallback: use the datetime attribute as-is
                    time_tag.replace_with(datetime_attr)
            else:
                # If no datetime attribute, remove the tag but keep any text content
                time_tag.unwrap()

    def _process_images_in_soup(self, soup: BeautifulSoup, image_prefix: str) -> None:
        """
        Process Confluence image macros in BeautifulSoup object.
        Converts <ac:image><ri:attachment ri:filename="..."></ri:attachment></ac:image>
        to standard HTML <img> tags.

        Args:
            soup: BeautifulSoup object containing HTML
            image_prefix: The prefix for constructing download URLs
        """
        # Find all ac:image elements
        image_elements = soup.find_all("ac:image")

        for image_element in image_elements:
            # Find the attachment reference
            attachment_ref = image_element.find("ri:attachment")
            if attachment_ref:
                filename = attachment_ref.get("ri:filename")
                if filename and image_prefix:
                    # Create img tag with download URL
                    img_tag = soup.new_tag("img")
                    # Construct the download URL for the attachment
                    img_tag["src"] = f"{image_prefix}/{quote(filename)}"

                    # Copy width attribute if present
                    if image_element.has_attr("ac:width"):
                        img_tag["width"] = image_element["ac:width"]

                    # Copy height attribute if present
                    if image_element.has_attr("ac:height"):
                        img_tag["height"] = image_element["ac:height"]

                    # Add alt text for accessibility
                    img_tag["alt"] = filename

                    # Replace the ac:image element with the img tag
                    image_element.replace_with(img_tag)
                    logger.debug(
                        f"Processed image: {filename} for page {image_prefix}")
                elif filename and not image_prefix:
                    # If no page_id provided, create a placeholder
                    logger.warning(
                        f"Image found but no image_prefix provided for {filename}")
                    placeholder = f"[Image: {filename}]"
                    image_element.replace_with(placeholder)
                else:
                    # No filename found
                    logger.warning("Image element found without filename")
                    image_element.replace_with("[Image: No filename]")

            url_ref = image_element.find("ri:url")
            if url_ref:
                url = url_ref.get("ri:value")
                if url:
                    # Create img tag with download URL
                    img_tag = soup.new_tag("img")
                    img_tag["src"] = url
                    img_tag["alt"] = url
                    image_element.replace_with(img_tag)
                    logger.debug(f"Processed image: {url}")

    def _process_page_links_in_soup(self, soup: BeautifulSoup) -> None:
        """
        Process Confluence internal page links in BeautifulSoup object.
        Converts <ac:link><ri:page ri:content-title="..."/></ac:link>
        to standard HTML <a> tags.

        Args:
            soup: BeautifulSoup object containing HTML
        """
        # Find all ac:link elements that contain page references
        link_elements = soup.find_all("ac:link")

        for link_element in link_elements:
            # Find the page reference
            page_ref = link_element.find("ri:page")
            if page_ref:
                # Get the page title from ri:content-title attribute
                page_title = page_ref.get("ri:content-title")
                if page_title:
                    # Create a link to the Confluence page
                    a_tag = soup.new_tag("a")
                    # Construct the URL for the page (using search as fallback)
                    # Note: This assumes the base URL is available and uses search
                    # In production, you might want to resolve actual page URLs
                    if self.base_url:
                        # Use Confluence search URL as a fallback
                        a_tag["href"] = f"{self.base_url}/dosearchsite.action?queryString={page_title}"
                    else:
                        # If no base URL, just use a placeholder
                        a_tag["href"] = f"#page:{page_title}"

                    # Set the link text to the page title
                    a_tag.string = page_title

                    # Replace the ac:link element with the a tag
                    link_element.replace_with(a_tag)
                    logger.debug(f"Processed page link: {page_title}")
                else:
                    # No page title found
                    logger.warning("Page link found without title")
                    link_element.replace_with("[Page link: No title]")

    def _replace_user_mention_by_accountid(
        self,
        user_element: Tag,
        account_id: str,
        confluence_client: ConfluenceClient | None = None,
    ) -> None:
        """
        Replace a user mention with the user's display name using account ID.

        Args:
            user_element: The HTML element containing the user mention
            account_id: The user's account ID
            confluence_client: Optional Confluence client for user lookups
        """
        try:
            # Only attempt to get user details if we have a valid confluence client
            if confluence_client is not None:
                has_cached = account_id in self.cache_user_details["account_id"]
                if has_cached:
                    user_details = self.cache_user_details["account_id"][account_id]
                else:
                    user_details = confluence_client.get_user_details_by_accountid(
                        account_id
                    )
                    self.cache_user_details["account_id"][account_id] = user_details
                display_name = user_details.get("displayName", "")
                if display_name:
                    new_text = f"@{display_name}"
                    user_element.replace_with(new_text)
                    return
            # If we don't have a confluence client or couldn't get user details,
            # use fallback
            self._use_fallback_user_mention(user_element, account_id)
        except Exception as e:
            logger.warning(
                f"Error processing user mention by account ID: {str(e)}")
            self._use_fallback_user_mention(user_element, account_id)

    def _replace_user_mention_by_userkey(
        self,
        user_element: Tag,
        userkey: str,
        confluence_client: ConfluenceClient | None = None,
    ) -> None:
        """
        Replace a user mention with the user's display name using userkey.

        Args:
            user_element: The HTML element containing the user mention
            userkey: The user's userkey
            confluence_client: Optional Confluence client for user lookups
        """
        try:
            # Only attempt to get user details if we have a valid confluence client
            if confluence_client is not None:
                has_cached = userkey in self.cache_user_details["userkey"]
                if has_cached:
                    user_details = self.cache_user_details["userkey"][userkey]
                else:
                    user_details = confluence_client.get_user_details_by_userkey(
                        userkey
                    )
                    self.cache_user_details["userkey"][userkey] = user_details
                display_name = user_details.get("displayName", "")
                if display_name:
                    new_text = f"@{display_name}"
                    user_element.replace_with(new_text)
                    return
            # If we don't have a confluence client or couldn't get user details,
            # use fallback
            self._use_fallback_user_mention(user_element, userkey)
        except Exception as e:
            logger.warning(
                f"Error processing user mention by userkey: {str(e)}")
            self._use_fallback_user_mention(user_element, userkey)

    def _use_fallback_user_mention(self, user_element: Tag, identifier: str) -> None:
        """
        Replace user mention with a fallback when the API call fails.

        Args:
            user_element: The HTML element containing the user mention
            identifier: The user's account ID or userkey
        """
        # Fallback: just use the identifier
        new_text = f"@user_{identifier}"
        user_element.replace_with(new_text)

    def _convert_html_to_markdown(self, text: str) -> str:
        """Convert HTML content to markdown if needed."""
        if re.search(r"<[^>]+>", text):
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning)
                    soup = BeautifulSoup(f"<div>{text}</div>", "html.parser")
                    html = str(soup.div.decode_contents()
                               ) if soup.div else text
                    text = md(html)
            except Exception as e:
                logger.warning(f"Error converting HTML to markdown: {str(e)}")
        return text
