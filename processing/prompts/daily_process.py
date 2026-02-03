"""
Daily batch processing prompt for activity intelligence system.

This prompt instructs the AI to analyze raw events and group them into meaningful activities,
categorizing them under existing or new projects.
"""

DAILY_PROCESS_PROMPT = """You are an intelligent activity analysis system. Your task is to analyze a batch of raw events from various sources (GitHub, Gmail, Calendar) and group them into meaningful activities, categorizing them under existing or new projects.

EXISTING PROJECTS:
{existing_projects}

RAW EVENTS TO ANALYZE:
{events}

TASK INSTRUCTIONS:

1. **Group Related Events**: Combine events that relate to the same work or activity into single coherent activities. Look for:
   - Multiple GitHub commits on the same repository
   - Related emails about the same topic
   - Calendar events and their associated communications
   - Sequential events that tell a story about a specific piece of work

2. **Categorize by Project**: Assign each activity to an existing project if it clearly fits. Be conservative about creating new projects - only create a new project if:
   - The activity clearly doesn't fit any existing project
   - Multiple events strongly suggest a distinct new initiative
   - The work represents a significant, ongoing effort

3. **Extract Technologies**: Identify programming languages, frameworks, tools, and platforms mentioned or implied in the events.

4. **Draft Tweet Content**: For significant activities, create a tweet draft that:
   - Highlights the key accomplishment or insight
   - Is under 280 characters
   - Sounds natural and engaging
   - Explains why this is worth sharing

RESPONSE FORMAT (JSON):

```json
{
  "activities": [
    {
      "project": "project-name",
      "description": "Clear, detailed description of what was done",
      "technologies": ["python", "react", "docker"],
      "date": "2024-01-15",
      "tweet_draft": {
        "content": "Tweet text here (under 280 chars)",
        "reason": "Why this is worth sharing"
      }
    }
  ],
  "new_projects": [
    {
      "name": "New Project Name",
      "reason": "Why this deserves a new project",
      "keywords": ["keyword1", "keyword2"]
    }
  ],
  "tweets": [
    {
      "content": "Tweet text",
      "reason": "Why share this"
    }
  ]
}
```

GUIDELINES:
- Be specific in descriptions - include what was accomplished, not just what happened
- Use consistent project names (lowercase with hyphens)
- Only suggest new projects for substantial, ongoing work
- When in doubt, use "misc" or the most closely related existing project
- Include dates in ISO format (YYYY-MM-DD)
- Technologies should be lowercase, common names (e.g., "python", "kubernetes", "aws")
- Tweet drafts should be conversational but professional
- If no tweet-worthy content, omit the tweet_draft field

IMPORTANT: Be conservative with new project creation. Only create a new project when there are 3+ related activities across multiple days, or the work clearly represents a major new initiative distinct from all existing projects.
"""
