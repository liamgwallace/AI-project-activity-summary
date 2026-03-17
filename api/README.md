# API Module

FastAPI server providing the web dashboard, browser extension receiver, and dashboard API endpoints.

## Description

The API module runs a FastAPI server that serves the web dashboard UI, receives page visit data from the Chrome extension, and exposes REST endpoints for browsing data, running commands, viewing the entity graph, and tailing logs.

## Files

- `server.py` - Main FastAPI application, mounts static files/templates, includes dashboard router
- `dashboard_routes.py` - Dashboard API router (commands, data browse, graph, logs)
- `templates/dashboard.html` - Single-page dashboard (Jinja2 template, Bootstrap 5 + vis.js)
- `static/dashboard.js` - Client-side JavaScript for all dashboard interactions
- `static/dashboard.css` - Dashboard styles
- `__init__.py` - Package initialization

## Endpoints

### Core
- `GET /` - Root endpoint with API info
- `GET /api/health` - Health check
- `GET /dashboard` - Web dashboard UI

### Browser Extension
- `POST /api/browser/visit` - Receive page visit from Chrome extension
- `GET /api/stats` - Get event statistics (requires API key)

### Dashboard API (`/api/dashboard/...`)
- `POST /api/dashboard/commands/run` - Run a command (collect-all, process-now, weekly-synthesis, run-cycle)
- `GET /api/dashboard/events` - Browse raw events (params: days, limit, source)
- `GET /api/dashboard/activities` - Browse processed activities (params: days, limit, project)
- `GET /api/dashboard/entities` - Browse entities (params: days, limit)
- `GET /api/dashboard/projects` - List configured projects
- `GET /api/dashboard/token-stats` - Token usage statistics (params: days)
- `GET /api/dashboard/graph` - Entity/relationship graph data for vis.js (params: days, project)
- `GET /api/dashboard/logs` - Tail app.log (params: lines, level)

## Dashboard

Access at `http://localhost:8000/dashboard` after starting the server.

**Tabs:**
- **Commands** - Run collect, process, weekly synthesis, full cycle with live output
- **Events** - Browse raw events with source/days filtering
- **Activities** - Browse AI-processed activities by project
- **Entities** - Browse extracted entities (technologies, concepts, etc.)
- **Graph** - Interactive vis.js entity/relationship graph
- **Logs** - Tail application logs with level filtering

## Dependencies

```
fastapi
uvicorn
pydantic
jinja2
```

## Usage

```bash
# Via main application (recommended)
python main.py
# Then open http://localhost:8000/dashboard

# Standalone
python api/server.py
```

## Configuration

Set `PAIS_API_KEY` environment variable to enable API key authentication. The Chrome extension must send this key in the `X-API-Key` header.
