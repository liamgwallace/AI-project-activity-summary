# API Module

FastAPI server for receiving browser extension data and providing system status endpoints.

## Description

The API module runs a FastAPI server that receives page visit data from the Chrome extension, validates API keys, and stores events in the database. It provides health checks, statistics, and API endpoints for browser activity tracking.

## Files

- `server.py` - Main FastAPI application with all endpoints
- `__init__.py` - Package initialization

## Key Components

### Pydantic Models
- `PageVisitRequest` - Request model for page visit data (URL, title, timestamp, device)
- `PageVisitResponse` - Response model with success status and event ID
- `HealthResponse` - Health check response with status and version
- `StatsResponse` - Statistics response with event counts

### Endpoints
- `GET /api/health` - Health check endpoint
- `POST /api/browser/visit` - Receive page visit from browser extension
- `GET /api/stats` - Get system statistics (requires API key)
- `GET /` - Root endpoint with API info

### Functions
- `verify_api_key()` - Header-based API key validation
- `lifespan()` - Async context manager for startup/shutdown

## Dependencies

```
fastapi
uvicorn
pydantic
```

## Usage

Run the server standalone:
```bash
python api/server.py
```

Or integrated with main application:
```bash
python main.py
```

The server listens on `http://localhost:8000` by default.

## Configuration

Set `PAIS_API_KEY` environment variable to enable API key authentication. The Chrome extension must send this key in the `X-API-Key` header.
