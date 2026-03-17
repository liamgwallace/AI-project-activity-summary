"""
Dashboard API routes for PAIS web UI.
Provides endpoints for browsing data, running commands, viewing logs, and graph data.
"""

import asyncio
import io
import json
import logging
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config.settings import get_settings
from storage.database import Database

logger = logging.getLogger(__name__)

router = APIRouter()

# Lock to prevent concurrent command execution
_command_lock = asyncio.Lock()


# ---------------------
# Pydantic models
# ---------------------

class CommandRequest(BaseModel):
    command: str


class CommandResponse(BaseModel):
    success: bool
    command: str
    duration_seconds: float
    output: str
    error: Optional[str] = None


# ---------------------
# Command execution
# ---------------------

@router.post("/commands/run", response_model=CommandResponse)
async def run_command(request: CommandRequest):
    """Run a PAIS command (blocking). Returns output when complete."""
    valid_commands = {"collect-all", "process-now", "weekly-synthesis", "run-cycle"}
    if request.command not in valid_commands:
        raise HTTPException(status_code=400, detail=f"Unknown command: {request.command}")

    if _command_lock.locked():
        raise HTTPException(status_code=409, detail="A command is already running")

    async with _command_lock:
        # Capture log output during execution
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

        start = time.time()
        try:
            from main import run_collectors, check_and_process, run_weekly_synthesis
            from config.settings import load_settings
            load_settings()

            if request.command == "collect-all":
                await asyncio.to_thread(run_collectors)
            elif request.command == "process-now":
                await asyncio.to_thread(check_and_process, True)
            elif request.command == "weekly-synthesis":
                await asyncio.to_thread(run_weekly_synthesis)
            elif request.command == "run-cycle":
                await asyncio.to_thread(run_collectors)
                await asyncio.to_thread(check_and_process, False)

            return CommandResponse(
                success=True,
                command=request.command,
                duration_seconds=round(time.time() - start, 1),
                output=log_capture.getvalue(),
                error=None,
            )
        except Exception as e:
            logger.error(f"Command {request.command} failed: {e}")
            return CommandResponse(
                success=False,
                command=request.command,
                duration_seconds=round(time.time() - start, 1),
                output=log_capture.getvalue(),
                error=str(e),
            )
        finally:
            root_logger.removeHandler(handler)


# ---------------------
# Data browse endpoints
# ---------------------

@router.get("/events")
async def get_events(
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(50, ge=1, le=500),
    source: str = Query("", description="Filter by source (github, gmail, calendar, browser, youtube)"),
):
    """Get raw events from the database."""
    settings = get_settings()
    db = Database(settings.database.path)
    since = datetime.now() - timedelta(days=days)
    events = db.get_events_since(since)

    if source:
        events = [e for e in events if e.source == source]

    result = []
    for e in events[:limit]:
        raw = e.raw_data
        try:
            data = json.loads(raw)
            summary = _summarize_event_data(data, e.event_type)
        except Exception:
            summary = raw[:200] if raw else ""

        result.append({
            "id": e.id,
            "source": e.source,
            "event_type": e.event_type,
            "event_time": e.event_time,
            "processed": bool(e.processed),
            "summary": summary,
        })

    return {"events": result, "total": len(events)}


@router.get("/activities")
async def get_activities(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=500),
    project: str = Query("", description="Filter by project name"),
):
    """Get processed activities."""
    settings = get_settings()
    db = Database(settings.database.path)
    since = datetime.now() - timedelta(days=days)

    activities = db.get_activities_for_period(
        start=since,
        end=datetime.now(),
        project_name=project if project else None,
    )

    result = []
    for a in activities[:limit]:
        result.append({
            "id": a.id,
            "timestamp": a.timestamp,
            "project_name": a.project_name,
            "activity_type": a.activity_type,
            "description": a.description,
        })

    return {"activities": result, "total": len(activities)}


@router.get("/entities")
async def get_entities(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
):
    """Get recent entities."""
    settings = get_settings()
    db = Database(settings.database.path)
    entities = db.get_recent_entities(days=days, limit=limit)

    result = []
    for e in entities:
        meta = {}
        if e.metadata:
            try:
                meta = json.loads(e.metadata) if isinstance(e.metadata, str) else e.metadata
            except Exception:
                meta = {}

        result.append({
            "id": e.id,
            "entity_type": e.entity_type,
            "name": e.name,
            "display_name": e.display_name or e.name,
            "mention_count": e.mention_count,
            "first_seen": e.first_seen,
            "last_seen": e.last_seen,
            "metadata": meta,
        })

    return {"entities": result, "total": len(result)}


@router.get("/projects")
async def get_projects():
    """Get all configured projects."""
    settings = get_settings()
    result = []
    for name, proj in settings.projects.items():
        result.append({
            "name": name,
            "description": proj.description,
            "tags": proj.tags,
            "keywords": proj.keywords,
            "active": proj.active,
            "created_at": proj.created_at,
        })
    return {"projects": result}


@router.get("/token-stats")
async def get_token_stats(days: int = Query(30, ge=1, le=365)):
    """Get token usage statistics."""
    settings = get_settings()
    db = Database(settings.database.path)
    stats = db.get_token_stats(days=days)
    return stats


# ---------------------
# Graph endpoint
# ---------------------

@router.get("/graph")
async def get_graph_data(
    days: int = Query(30, ge=1, le=365),
    project: str = Query("", description="Filter by project name"),
):
    """Get graph nodes and edges for vis.js rendering."""
    from visualize_graph import (
        ENTITY_COLORS,
        ENTITY_SHAPES,
        get_entities_and_relationships,
        get_project_nodes,
    )

    settings = get_settings()
    db_path = settings.database.path

    entities, relationships = get_entities_and_relationships(
        db_path=db_path,
        project_filter=project or None,
        days=days,
    )
    projects = get_project_nodes(db_path, project or None)

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    entity_id_map: Dict[int, str] = {}
    project_ids: Dict[str, str] = {}

    # Project nodes
    for proj in projects:
        node_id = f"project_{proj['id']}"
        project_ids[proj["name"]] = node_id
        keywords = proj.get("keywords", "")
        if keywords:
            try:
                kw_list = json.loads(keywords)
                kw_str = ", ".join(kw_list)
            except Exception:
                kw_str = keywords
        else:
            kw_str = ""

        nodes.append({
            "id": node_id,
            "label": proj["name"],
            "title": f"Project: {proj['name']}<br>Keywords: {kw_str}",
            "color": ENTITY_COLORS.get("project", "#FFC107"),
            "shape": ENTITY_SHAPES.get("project", "hexagon"),
            "size": 10,
        })

    # Entity nodes
    for entity in entities:
        node_id = f"entity_{entity['id']}"
        entity_id_map[entity["id"]] = node_id
        entity_type = entity.get("entity_type", "unknown")
        mentions = entity.get("mention_count", 1)

        meta = entity.get("metadata", "{}")
        try:
            meta_dict = json.loads(meta) if meta else {}
            meta_str = "<br>".join(f"{k}: {v}" for k, v in meta_dict.items() if v)[:200]
        except Exception:
            meta_str = ""

        title = f"{entity_type.title()}: {entity.get('display_name', entity['name'])}<br>Mentions: {mentions}"
        if meta_str:
            title += f"<br><br>{meta_str}"

        nodes.append({
            "id": node_id,
            "label": entity.get("display_name", entity["name"]),
            "title": title,
            "color": ENTITY_COLORS.get(entity_type, "#999999"),
            "shape": ENTITY_SHAPES.get(entity_type, "dot"),
            "size": min(6 + (mentions * 0.8), 12),
        })

    # Entity-to-entity edges
    for rel in relationships:
        if rel["from_type"] == "entity" and rel["to_type"] == "entity":
            from_id = entity_id_map.get(rel["from_id"])
            to_id = entity_id_map.get(rel["to_id"])
            if from_id and to_id:
                edges.append({
                    "from": from_id,
                    "to": to_id,
                    "label": rel["rel_type"],
                    "title": f"{rel['rel_type']} (confidence: {rel.get('confidence', 1.0)})",
                    "arrows": "to",
                })

    # Project-entity edges (reuse pattern from visualize_graph.add_project_entity_edges)
    if projects and entity_id_map:
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            for proj in projects:
                proj_node_id = project_ids.get(proj["name"])
                if not proj_node_id:
                    continue
                cursor.execute("""
                    SELECT e.id, COUNT(*) as usage_count
                    FROM entities e
                    JOIN relationships r ON (
                        (r.from_type = 'entity' AND r.from_id = e.id AND r.to_type = 'activity')
                        OR (r.to_type = 'entity' AND r.to_id = e.id AND r.from_type = 'activity')
                    )
                    JOIN activities a ON a.id =
                        CASE
                            WHEN r.from_type = 'activity' THEN r.from_id
                            ELSE r.to_id
                        END
                    WHERE a.project_name = ?
                    GROUP BY e.id
                    ORDER BY usage_count DESC
                    LIMIT 10
                """, (proj["name"],))
                for row in cursor.fetchall():
                    entity_node_id = entity_id_map.get(row[0])
                    if entity_node_id:
                        edges.append({
                            "from": proj_node_id,
                            "to": entity_node_id,
                            "title": f"uses ({row[1]} times)",
                            "color": {"color": "#ff9800", "opacity": 0.6},
                            "dashes": True,
                            "arrows": "to",
                        })
            conn.close()
        except Exception as e:
            logger.warning(f"Error adding project-entity edges: {e}")

    return {"nodes": nodes, "edges": edges}


# ---------------------
# Logs endpoint
# ---------------------

@router.get("/logs")
async def get_logs(
    lines: int = Query(200, ge=10, le=1000),
    level: str = Query("", description="Filter by log level (INFO, WARNING, ERROR)"),
):
    """Get recent log lines from app.log."""
    settings = get_settings()
    log_path = Path(settings.log_dir) / "app.log"

    if not log_path.exists():
        return {"lines": [], "total_lines": 0, "log_file": str(log_path)}

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            # Read more lines than needed if filtering by level
            max_read = lines * 3 if level else lines
            all_lines = deque(f, maxlen=max_read)

        result_lines = [line.rstrip("\n") for line in all_lines]

        if level:
            result_lines = [l for l in result_lines if f" - {level.upper()} - " in l]

        result_lines = result_lines[-lines:]

        return {"lines": result_lines, "total_lines": len(result_lines), "log_file": str(log_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading logs: {e}")


# ---------------------
# Helpers
# ---------------------

def _summarize_event_data(data: dict, event_type: str) -> str:
    """Create a short summary from raw event data."""
    if event_type == "commit":
        return data.get("message", data.get("commit_message", ""))[:120]
    elif event_type == "pr":
        return data.get("title", "")[:120]
    elif event_type == "email":
        return f"{data.get('from', '')} - {data.get('subject', '')}"[:120]
    elif event_type in ("calendar_event", "event"):
        return data.get("summary", data.get("title", ""))[:120]
    elif event_type == "page_visit":
        return f"{data.get('title', '')} ({data.get('url', '')[:60]})"[:120]
    elif event_type == "video_like":
        return f"{data.get('channel', '')} - {data.get('title', '')}"[:120]
    else:
        return str(data)[:120]
