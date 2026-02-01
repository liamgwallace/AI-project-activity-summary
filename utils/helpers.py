"""
Utility helper functions for the Personal Activity Intelligence System.

Provides common operations: text slugification, truncation, datetime parsing,
and text chunking with sentence-boundary awareness.
"""

import re
import unicodedata
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug.

    Normalizes unicode characters, lowercases, replaces non-alphanumeric
    characters with hyphens, and strips leading/trailing hyphens.

    Args:
        text: The input text to slugify.

    Returns:
        A URL-safe slug string.

    Examples:
        >>> slugify("Hello World!")
        'hello-world'
        >>> slugify("My Project - v2.0")
        'my-project-v2-0'
    """
    if not text:
        return ""

    # Normalize unicode characters to ASCII equivalents
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # Lowercase and strip
    text = text.lower().strip()

    # Replace any non-alphanumeric character (except hyphens) with a hyphen
    text = re.sub(r"[^a-z0-9\-]", "-", text)

    # Collapse multiple consecutive hyphens into one
    text = re.sub(r"-+", "-", text)

    # Strip leading and trailing hyphens
    text = text.strip("-")

    return text


def truncate(text: str, max_chars: int, suffix: str = "...") -> str:
    """Truncate text to a maximum number of characters with an ellipsis.

    If the text is shorter than max_chars, it is returned unchanged.
    Otherwise, it is cut at max_chars minus the suffix length and the
    suffix is appended.

    Args:
        text: The input text to truncate.
        max_chars: Maximum number of characters in the output.
        suffix: The suffix to append when truncating. Defaults to '...'.

    Returns:
        The truncated string.

    Raises:
        ValueError: If max_chars is less than the length of the suffix.
    """
    if not text:
        return ""

    if max_chars < len(suffix):
        raise ValueError(
            f"max_chars ({max_chars}) must be >= suffix length ({len(suffix)})"
        )

    if len(text) <= max_chars:
        return text

    return text[: max_chars - len(suffix)] + suffix


def parse_datetime(dt_string: str) -> Optional[datetime]:
    """Parse a datetime string into a datetime object.

    Supports multiple common formats:
    - ISO 8601: 2024-01-15T10:30:00
    - ISO 8601 with timezone: 2024-01-15T10:30:00Z, 2024-01-15T10:30:00+00:00
    - Date only: 2024-01-15
    - Space-separated: 2024-01-15 10:30:00
    - Compact: 20240115T103000

    Args:
        dt_string: A string representing a datetime.

    Returns:
        A datetime object, or None if parsing fails.
    """
    if not dt_string:
        return None

    # Strip whitespace
    dt_string = dt_string.strip()

    # Remove trailing 'Z' (UTC indicator) and replace with +00:00
    if dt_string.endswith("Z"):
        dt_string = dt_string[:-1] + "+00:00"

    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d",
        "%Y%m%dT%H%M%S",
        "%m/%d/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(dt_string, fmt)
        except ValueError:
            continue

    logger.warning("Failed to parse datetime string: %s", dt_string)
    return None


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Format a datetime object into a human-readable string.

    Args:
        dt: The datetime object to format.
        fmt: The format string. Defaults to '%Y-%m-%d %H:%M'.

    Returns:
        A formatted datetime string. Returns an empty string if dt is None.
    """
    if dt is None:
        return ""

    return dt.strftime(fmt)


def chunk_text(text: str, max_chars: int) -> list[str]:
    """Split text into chunks respecting sentence boundaries.

    Attempts to split at sentence endings (., !, ?). If a single sentence
    exceeds max_chars, it falls back to splitting at word boundaries.
    If a single word exceeds max_chars, it is split at the character level.

    Args:
        text: The input text to split.
        max_chars: Maximum number of characters per chunk.

    Returns:
        A list of text chunks, each at most max_chars characters long.

    Raises:
        ValueError: If max_chars is less than 1.
    """
    if max_chars < 1:
        raise ValueError("max_chars must be >= 1")

    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    # Split into sentences using regex (keeps the delimiter attached)
    sentence_pattern = re.compile(r"(?<=[.!?])\s+")
    sentences = sentence_pattern.split(text)

    chunks: list[str] = []
    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # If adding this sentence would exceed the limit
        if current_chunk and (len(current_chunk) + 1 + len(sentence)) > max_chars:
            # Save the current chunk
            chunks.append(current_chunk.strip())
            current_chunk = ""

        # If a single sentence exceeds max_chars, split by words
        if len(sentence) > max_chars:
            # Flush any current chunk first
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            words = sentence.split()
            word_chunk = ""

            for word in words:
                if word_chunk and (len(word_chunk) + 1 + len(word)) > max_chars:
                    chunks.append(word_chunk.strip())
                    word_chunk = ""

                # If a single word exceeds max_chars, hard split
                if len(word) > max_chars:
                    if word_chunk:
                        chunks.append(word_chunk.strip())
                        word_chunk = ""
                    for i in range(0, len(word), max_chars):
                        chunks.append(word[i : i + max_chars])
                else:
                    if word_chunk:
                        word_chunk += " " + word
                    else:
                        word_chunk = word

            if word_chunk:
                current_chunk = word_chunk
        else:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks
