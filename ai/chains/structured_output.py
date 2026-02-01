"""Helper functions for parsing and validating AI output."""

import json
import logging
import re

logger = logging.getLogger(__name__)


def parse_json_response(response_text: str) -> dict:
    """Extract and parse JSON from an AI response.

    Handles responses that may contain JSON wrapped in markdown code blocks
    (e.g., ```json ... ```) or raw JSON text.

    Args:
        response_text: The raw text response from the AI model.

    Returns:
        Parsed dictionary from the JSON content.

    Raises:
        ValueError: If no valid JSON can be extracted from the response.
    """
    # First, try to extract JSON from markdown code blocks
    code_block_pattern = re.compile(
        r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL
    )
    match = code_block_pattern.search(response_text)

    if match:
        json_str = match.group(1).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(
                "Found code block but failed to parse JSON: %s", e
            )

    # Try to find JSON object directly in the response
    # Look for the outermost { ... } pair
    brace_pattern = re.compile(r"\{.*\}", re.DOTALL)
    match = brace_pattern.search(response_text)

    if match:
        json_str = match.group(0).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(
                "Found braces but failed to parse JSON: %s", e
            )

    # Last resort: try parsing the entire response as JSON
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass

    raise ValueError(
        f"Could not extract valid JSON from response: "
        f"{response_text[:200]}..."
    )


def validate_daily_output(data: dict) -> bool:
    """Validate the structure of daily processing AI output.

    Checks that the parsed JSON conforms to the expected schema:
    - 'projects' is a list of dicts with required keys
    - 'technologies' is a list of strings
    - 'notable_moments' is a list of dicts with required keys

    Args:
        data: The parsed dictionary to validate.

    Returns:
        True if the data structure is valid, False otherwise.
    """
    if not isinstance(data, dict):
        logger.error("Daily output is not a dictionary")
        return False

    # Validate 'projects' field
    if "projects" not in data:
        logger.error("Missing 'projects' key in daily output")
        return False

    if not isinstance(data["projects"], list):
        logger.error("'projects' is not a list")
        return False

    required_project_keys = {
        "name", "activities", "technologies_used", "new_project"
    }
    for i, project in enumerate(data["projects"]):
        if not isinstance(project, dict):
            logger.error("Project at index %d is not a dictionary", i)
            return False

        missing_keys = required_project_keys - set(project.keys())
        if missing_keys:
            logger.error(
                "Project at index %d missing keys: %s", i, missing_keys
            )
            return False

        if not isinstance(project["name"], str):
            logger.error("Project at index %d 'name' is not a string", i)
            return False

        if not isinstance(project["activities"], list):
            logger.error(
                "Project at index %d 'activities' is not a list", i
            )
            return False

        if not isinstance(project["technologies_used"], list):
            logger.error(
                "Project at index %d 'technologies_used' is not a list", i
            )
            return False

        if not isinstance(project["new_project"], bool):
            logger.error(
                "Project at index %d 'new_project' is not a boolean", i
            )
            return False

    # Validate 'technologies' field
    if "technologies" not in data:
        logger.error("Missing 'technologies' key in daily output")
        return False

    if not isinstance(data["technologies"], list):
        logger.error("'technologies' is not a list")
        return False

    # Validate 'notable_moments' field
    if "notable_moments" not in data:
        logger.error("Missing 'notable_moments' key in daily output")
        return False

    if not isinstance(data["notable_moments"], list):
        logger.error("'notable_moments' is not a list")
        return False

    required_moment_keys = {"description", "tweetable", "tweet_draft"}
    for i, moment in enumerate(data["notable_moments"]):
        if not isinstance(moment, dict):
            logger.error(
                "Notable moment at index %d is not a dictionary", i
            )
            return False

        missing_keys = required_moment_keys - set(moment.keys())
        if missing_keys:
            logger.error(
                "Notable moment at index %d missing keys: %s",
                i, missing_keys
            )
            return False

        if not isinstance(moment["description"], str):
            logger.error(
                "Notable moment at index %d 'description' is not a string", i
            )
            return False

        if not isinstance(moment["tweetable"], bool):
            logger.error(
                "Notable moment at index %d 'tweetable' is not a boolean", i
            )
            return False

        if not isinstance(moment["tweet_draft"], str):
            logger.error(
                "Notable moment at index %d 'tweet_draft' is not a string", i
            )
            return False

    logger.info("Daily output validation passed")
    return True
