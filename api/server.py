"""
FastAPI server for PAIS browser receiver.
Receives page visit data from browser extension.
"""

from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from contextlib import asynccontextmanager

from config.settings import get_settings
from storage.database import Database
from collectors.browser_receiver import BrowserReceiver

# Set up logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Initialize database and receiver
db = Database(settings.database.path)
browser_receiver = BrowserReceiver()


# Pydantic models
class PageVisitRequest(BaseModel):
    """Request model for page visit data."""
    model_config = {"extra": "ignore"}  # Ignore extra fields like 'source'
    
    url: str
    title: str
    timestamp: datetime
    device: str


class PageVisitResponse(BaseModel):
    """Response model for page visit endpoint."""
    success: bool
    message: str
    event_id: Optional[int] = None


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    version: str
    timestamp: str


class StatsResponse(BaseModel):
    """Response model for stats endpoint."""
    total_events: int
    unprocessed_events: int
    recent_visits: int


# API key validation
def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """Verify the API key from request header."""
    expected_key = getattr(settings, 'api_key', None)
    
    if expected_key and x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return x_api_key or ""


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifespan events."""
    # Startup
    Path(settings.log_dir).mkdir(parents=True, exist_ok=True)
    print(f"PAIS Browser Receiver started on http://localhost:8000")
    yield
    # Shutdown
    print("PAIS Browser Receiver shutting down")


# Create FastAPI app
app = FastAPI(
    title="PAI Browser Receiver",
    description="Receives browser activity data from PAIS browser extension",
    version=settings.version,
    lifespan=lifespan,
)


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=settings.version,
        timestamp=datetime.now().isoformat()
    )


@app.post("/api/browser/visit", response_model=PageVisitResponse)
async def receive_page_visit(
    request: PageVisitRequest,
    x_api_key: Optional[str] = Header(None),
    verbose: bool = False
):
    """
    Receive a page visit from the browser extension.
    
    Requires X-API-Key header if API key is configured.
    
    Query params:
    - verbose: Set to true for detailed logging (default: concise)
    """
    # Concise logging by default, verbose when requested
    if verbose:
        logger.info("=" * 60)
        logger.info("📥 BROWSER VISIT RECEIVED")
        logger.info(f"🔗 URL: {request.url}")
        logger.info(f"📄 Title: {request.title}")
        logger.info(f"🖥️  Device: {request.device}")
        logger.info(f"⏰ Timestamp: {request.timestamp}")
        logger.info(f"🔑 API Key: {x_api_key if x_api_key else 'None'}")
        logger.info("=" * 60)
    else:
        # Concise one-line log
        logger.info(f"📥 {request.title[:60]} | {request.url[:80]}")
    
    try:
        result = browser_receiver.receive_page_visit(
            url=request.url,
            title=request.title,
            timestamp=request.timestamp,
            device=request.device,
            api_key=x_api_key
        )
        
        if not result["success"]:
            if "Invalid API key" in result["message"]:
                raise HTTPException(status_code=401, detail=result["message"])
            raise HTTPException(status_code=400, detail=result["message"])
        
        # Log successful storage (only in verbose mode)
        if verbose:
            logger.info(f"✅ STORED: Event ID {result.get('event_id')} - {request.title[:50]}...")
        
        return PageVisitResponse(
            success=result["success"],
            message=result["message"],
            event_id=result.get("event_id")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats(x_api_key: Optional[str] = Header(None)):
    """
    Get basic statistics about stored events.
    
    Requires X-API-Key header if API key is configured.
    """
    # Verify API key
    expected_key = getattr(settings, 'api_key', None)
    if expected_key and x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    try:
        # Get stats from database
        since = datetime.now() - __import__("datetime").timedelta(days=1)
        recent_events = db.get_events_since(since)
        
        unprocessed = db.get_unprocessed_events(limit=1000)
        
        # Count browser visits
        recent_visits = len([e for e in recent_events if e.source == "browser"])
        
        return StatsResponse(
            total_events=len(recent_events),
            unprocessed_events=len(unprocessed),
            recent_visits=recent_visits
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {str(e)}")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "PAI Browser Receiver",
        "version": settings.version,
        "endpoints": [
            {"path": "/api/health", "method": "GET", "description": "Health check"},
            {"path": "/api/browser/visit", "method": "POST", "description": "Receive page visit"},
            {"path": "/api/stats", "method": "GET", "description": "Get statistics"},
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
