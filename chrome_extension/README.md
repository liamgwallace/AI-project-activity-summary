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

### Background Script
- Tracks `chrome.tabs.onUpdated` events
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

The extension automatically tracks page visits when enabled. Data is sent to the PAIS API server. If offline, visits are queued and retried when connection is restored.

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

- `tabs` - Access tab information
- `storage` - Store configuration and offline queue
- `activeTab` - Access current tab
- `<all_urls>` - Track all URLs (excluding chrome://)
