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

### Popup Interface
- Toggle tracking on/off
- View current endpoint and queue status
- Manual sync trigger for offline queue
- Device type display

### Options Page
- Configure API endpoint URL
- Set API key for authentication
- Enable/disable tracking

## Configuration

Default configuration in `background.js`:
```javascript
{
  apiEndpoint: 'http://localhost:8000/api/browser/visit',
  apiKey: 'your-api-key-here',
  enabled: true
}
```

## Installation

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `chrome_extension/` directory

## Usage

The extension automatically tracks page visits when enabled. Data is sent to the PAIS API server. If offline, visits are queued and retried when connection is restored.

## Permissions

- `tabs` - Access tab information
- `storage` - Store configuration and offline queue
- `activeTab` - Access current tab
- `<all_urls>` - Track all URLs (excluding chrome://)
