"""Tweet draft generator for the Personal Activity Intelligence System.

Creates markdown tweet draft files from notable moments identified
by the AI during daily processing.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import OUTPUTS_DIR

logger = logging.getLogger(__name__)

TWEETS_DIR = os.path.join(OUTPUTS_DIR, "tweets")


class TweetDrafter:
    """Generates tweet draft markdown files from AI-identified notable moments.

    Each tweet draft is saved as a markdown file in outputs/tweets/ with
    metadata and the draft text.
    """

    def __init__(self) -> None:
        os.makedirs(TWEETS_DIR, exist_ok=True)

    def create_draft(
        self,
        description: str,
        tweet_text: str,
        project_name: Optional[str] = None,
    ) -> str:
        """Create a tweet draft markdown file.

        Args:
            description: Description of the notable moment.
            tweet_text: The draft tweet text.
            project_name: Optional project this tweet relates to.

        Returns:
            The file path of the created draft.
        """
        now = datetime.utcnow()
        filename = f"{now.strftime('%Y-%m-%d_%H%M%S')}"
        if project_name:
            filename += f"_{project_name}"
        filename += ".md"

        content_lines = [
            "---",
            f"date: {now.strftime('%Y-%m-%d %H:%M')}",
            f"project: {project_name or 'none'}",
            "status: draft",
            "---",
            "",
            f"## {description}",
            "",
            tweet_text,
            "",
        ]

        filepath = os.path.join(TWEETS_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(content_lines))

        logger.info("Created tweet draft: %s", filepath)
        return filepath

    def list_drafts(self) -> list:
        """List all tweet draft files.

        Returns:
            A list of file paths to draft markdown files.
        """
        if not os.path.isdir(TWEETS_DIR):
            return []

        drafts = []
        for filename in sorted(os.listdir(TWEETS_DIR)):
            if filename.endswith(".md"):
                drafts.append(os.path.join(TWEETS_DIR, filename))
        return drafts
