"""Prompt template for daily activity session processing."""

DAILY_PROCESS_PROMPT = """You are analyzing a session of personal activity. Extract structured information.

Active Projects (context):
{active_projects}

Known Technologies (context):
{known_technologies}

Session Activity (chronological):
{events}

Return JSON with this structure:
{{
  "projects": [
    {{
      "name": "project-name",
      "activities": ["description1", "description2"],
      "technologies_used": ["tech1", "tech2"],
      "new_project": false
    }}
  ],
  "technologies": ["tech1", "tech2"],
  "notable_moments": [
    {{
      "description": "Started new MQTT integration",
      "tweetable": true,
      "tweet_draft": "Started wiring up MQTT for home sensors today..."
    }}
  ]
}}

If you detect a new coherent project theme not in the active projects list, set "new_project": true and provide a sensible name."""
