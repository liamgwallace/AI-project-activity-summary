"""Prompt template for weekly project synthesis."""

WEEKLY_SYNTHESIS_PROMPT = """You are synthesizing weekly progress for a personal project.

Project: {project_name}
Current README:
{readme_content}

This Week's Activity Log (detailed):
{activity_log}

Graph Context:
- Related Projects: {related_projects}
- Technologies Used: {technologies}

Update the README with a new weekly progress section at the top (before any existing weekly sections). Include:
- Key developments
- Challenges encountered
- Next steps
- Links to related concepts/projects using [[wiki-link]] syntax

Return the complete updated README content."""
