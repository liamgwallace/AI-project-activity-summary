# Chrome Extension

Browser extension for tracking page visits and sending data to PAIS API.

## Description

PAI Browser Tracker is a Chrome extension (Manifest V3) that monitors browsing activity and sends page visit data to the PAIS FastAPI server. It tracks URL, page title, timestamp, and device type.

## Files

- `manifest.json` - Extension manifest with permissions and configuration
- `background.js` - Service worker that tracks tab updates and sends data
- `popup.html/js` - Extension popup UI for status and controls
- `options.html/js` - Options page for configuration
- `generate_icons.py` - Script to generate extension icons
- `icons/` - Extension icons (16px, 48px, 128px)

## Key Features

### Background Script (History Polling Mode)
- Polls Chrome History API every minute for new visits
- Captures ALL browser history (desktop + synced mobile visits)
- Tracks last sync time to avoid duplicates
- Sends visit data to `http://localhost:8000/api/browser/visit`
- Implements offline queue with retry logic
- Detects device type from user agent
- Supports API key authentication
- Fetches available endpoints from server on startup

### Popup Interface
- Toggle tracking on/off
- View current endpoint and queue status
- Manual sync trigger for offline queue
- Device type display
- **Stats button** - Fetches and displays statistics from `/api/stats` endpoint
- **Health check button** - Verifies server connectivity via `/api/health` endpoint
- **View History button** - Displays recent Chrome history (last 24 hours) with timestamps and visit counts

### Options Page
- Configure base URL for the PAIS server
- Set API key for authentication
- Set device name identifier
- View configured API endpoints with descriptions
- Test connection to verify configuration

## Configuration

Default configuration in `background.js`:
```javascript
{
  apiEndpoint: 'http://localhost:8000/api/browser/visit',
  apiKey: 'your-api-key-here',
  enabled: true,
  baseUrl: 'http://localhost:8000',
  deviceName: 'desktop'
}
```

### API Endpoints Used

The extension automatically uses the following endpoints based on the configured base URL:

- `GET /api/health` - Health check endpoint
- `GET /api/stats` - Statistics endpoint (total events, unprocessed events, recent visits)
- `POST /api/browser/visit` - Page visit tracking endpoint
- `GET /` - Root endpoint to fetch available API endpoints

## Installation

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `chrome_extension/` directory

## Usage

The extension automatically polls Chrome's history every minute when enabled. This captures ALL visits including those synced from mobile Chrome. Data is sent to the PAIS API server. If offline, visits are queued and retried when connection is restored.

### How History Polling Works
- Extension queries Chrome History API every minute
- Tracks last sync time to avoid sending duplicates
- Captures visits from desktop Chrome AND mobile Chrome (via sync)
- Filters out chrome:// and chrome-extension:// URLs
- Stores failed sends in offline queue for retry

### View History
Click the "View History" button to see your recent Chrome history:
- Shows last 20 visits from past 24 hours
- Displays page title, URL, and visit time
- Shows visit count for each page
- Useful for verifying the extension can see your history

### Stats Button
Click the "Show Stats" button in the popup to fetch and display:
- Total events (last 24 hours)
- Unprocessed events count
- Recent browser visits count

### Health Check
Click the "Check Health" button to verify server connectivity and display:
- Server health status
- PAIS version
- Server timestamp

## Permissions

- `history` - Read Chrome browsing history
- `alarms` - Schedule periodic history polling
- `tabs` - Access tab information
- `storage` - Store configuration and offline queue
- `activeTab` - Access current tab
- `<all_urls>` - Track all URLs (excluding chrome://)
