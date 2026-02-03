# Processing Module

AI processing logic for analyzing activities and generating outputs.

## Description

The processing module handles AI-powered analysis of raw events, batch management, project detection, and prompt templates. Uses LangChain with OpenRouter/OpenAI for intelligent activity extraction and synthesis.

## Files

- `ai_processor.py` - Main AI processor for daily batch and weekly synthesis
- `batch_manager.py` - Controls batch processing timing and token thresholds
- `project_detector.py` - Conservative project creation and similarity detection
- `prompts/daily_process.py` - Prompt template for daily activity processing
- `prompts/weekly_synthesis.py` - Prompt template for weekly summaries
- `prompts/__init__.py` - Prompts package init
- `__init__.py` - Package initialization

## Key Classes

### AIProcessor
Processes activities using AI models:
- `__init__(model_config)` - Initialize with LangChain ChatOpenAI
- `process_batch(events, existing_projects)` - Analyze events and extract activities
- `weekly_synthesis(project_name, activities, current_readme)` - Generate weekly summary
- `_build_daily_prompt()` - Format prompt with events and projects
- `_parse_response()` - Extract JSON from AI response
- `_record_usage()` - Log token usage to database

Features:
- Retry logic with exponential backoff
- Token usage tracking and cost estimation
- OpenRouter API support via base_url

### BatchManager
Controls when processing runs:
- `__init__(db, max_tokens, interval_hours)` - Configure thresholds
- `should_process()` - Check if processing should run
- `estimate_tokens(events)` - Calculate token count for events
- `get_events_for_batch()` - Retrieve events up to token limit
- `get_last_process_time()` - Check last successful batch
- `get_stats()` - Current pending events and token estimates

Thresholds:
- Minimum 1000 tokens or 10 events
- Respects time interval between runs

### ProjectDetector
Conservative project creation:
- `should_create_project(name, activities)` - Apply 3+ activities / 2+ days rule
- `merge_similar_projects(projects)` - Group similar project names
- `get_project_keywords(name, activities)` - Extract keywords from activities
- `suggest_project_for_activity()` - Match activity to existing project
- `get_conservative_recommendations()` - Filter AI-proposed projects

Rules:
- Minimum 3 activities across 2+ days
- 75% similarity threshold for merging
- Rejects near-duplicate projects

## Prompt Templates

### Daily Processing
Analyzes raw events and produces:
- Grouped activities with project assignments
- Technology extraction
- Tweet drafts for significant work
- New project suggestions

### Weekly Synthesis
Generates README sections with:
- Key developments (3-5 bullet points)
- Challenges encountered
- Next steps
- Optional metrics

## Usage

```python
from processing.ai_processor import AIProcessor
from processing.batch_manager import BatchManager
from storage.database import Database

db = Database("data/activity_system.db")
batch_manager = BatchManager(db)

if batch_manager.should_process():
    events = batch_manager.get_events_for_batch()
    processor = AIProcessor()
    result = processor.process_batch(events, existing_projects)
```

## Dependencies

- `langchain`, `langchain-openai` - LLM integration
- `tenacity` - Retry logic
- Standard library: `json`, `logging`, `dataclasses`
