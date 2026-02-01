"""
Webpage content fetching utility for the Personal Activity Intelligence System.

Provides both async and sync functions to fetch a webpage, strip HTML tags,
and return the plain text content. Uses requests for HTTP fetching and
BeautifulSoup for HTML parsing.
"""

import asyncio
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Maximum number of characters to return from a fetched page
MAX_CONTENT_LENGTH = 10000

# Default request timeout in seconds
REQUEST_TIMEOUT = 15

# User-Agent header to avoid being blocked by simple bot detection
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; PersonalActivityBot/1.0; "
    "+https://github.com/personal-activity-intelligence)"
)


def _extract_text_from_html(html: str) -> str:
    """Extract plain text from HTML content using BeautifulSoup.

    Removes script tags, style tags, and other non-content elements
    before extracting the visible text.

    Args:
        html: Raw HTML string.

    Returns:
        Cleaned plain text extracted from the HTML.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove elements that don't contain useful text
    for element in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        element.decompose()

    # Extract text with newline separators between block elements
    text = soup.get_text(separator="\n", strip=True)

    # Collapse multiple blank lines into single newlines
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    text = "\n".join(lines)

    return text


def fetch_page_content_sync(url: str) -> str:
    """Synchronously fetch a webpage and return its plain text content.

    Fetches the URL using requests, strips HTML to extract visible text
    content, and truncates to MAX_CONTENT_LENGTH characters.

    Args:
        url: The URL of the webpage to fetch.

    Returns:
        The plain text content of the page, truncated to MAX_CONTENT_LENGTH.
        Returns an empty string on any failure.
    """
    if not url:
        logger.warning("Empty URL provided to fetch_page_content_sync")
        return ""

    try:
        logger.debug("Fetching page content from: %s", url)

        headers = {"User-Agent": DEFAULT_USER_AGENT}
        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()

        # Check that we got HTML content
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            logger.debug(
                "Non-HTML content type received (%s) for URL: %s",
                content_type,
                url,
            )
            # Still try to extract text - might be plain text
            text = response.text[:MAX_CONTENT_LENGTH]
            return text

        text = _extract_text_from_html(response.text)

        # Truncate to maximum length
        if len(text) > MAX_CONTENT_LENGTH:
            text = text[:MAX_CONTENT_LENGTH]
            logger.debug(
                "Truncated content from %s to %d characters",
                url,
                MAX_CONTENT_LENGTH,
            )

        logger.debug(
            "Successfully fetched %d characters from: %s", len(text), url
        )
        return text

    except requests.exceptions.Timeout:
        logger.warning("Timeout fetching URL: %s", url)
        return ""
    except requests.exceptions.ConnectionError:
        logger.warning("Connection error fetching URL: %s", url)
        return ""
    except requests.exceptions.HTTPError as e:
        logger.warning("HTTP error %s fetching URL: %s", e.response.status_code, url)
        return ""
    except requests.exceptions.RequestException as e:
        logger.warning("Request error fetching URL %s: %s", url, str(e))
        return ""
    except Exception as e:
        logger.error("Unexpected error fetching URL %s: %s", url, str(e))
        return ""


async def fetch_page_content(url: str) -> str:
    """Asynchronously fetch a webpage and return its plain text content.

    This is an async wrapper around the synchronous fetch function.
    It runs the blocking HTTP request in a thread pool executor to
    avoid blocking the event loop.

    Args:
        url: The URL of the webpage to fetch.

    Returns:
        The plain text content of the page, truncated to MAX_CONTENT_LENGTH.
        Returns an empty string on any failure.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fetch_page_content_sync, url)
