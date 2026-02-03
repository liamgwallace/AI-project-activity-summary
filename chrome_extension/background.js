// PAI Browser Tracker - Background Service Worker
// Tracks page visits and sends to PAI API

// Configuration
const DEFAULT_CONFIG = {
  apiEndpoint: 'http://localhost:8000/api/browser/visit',
  apiKey: 'your-api-key-here',
  enabled: true,
  baseUrl: 'http://localhost:8000',
  deviceName: 'desktop'
};

let config = { ...DEFAULT_CONFIG };
let offlineQueue = [];

// Load configuration from storage
chrome.storage.sync.get(['paiConfig'], (result) => {
  if (result.paiConfig) {
    config = { ...DEFAULT_CONFIG, ...result.paiConfig };
    // Ensure apiEndpoint is set if baseUrl is provided
    if (config.baseUrl && !config.apiEndpoint) {
      config.apiEndpoint = `${config.baseUrl}/api/browser/visit`;
    }
  }
});

// Listen for configuration changes
chrome.storage.onChanged.addListener((changes, namespace) => {
  if (namespace === 'sync' && changes.paiConfig) {
    config = { ...DEFAULT_CONFIG, ...changes.paiConfig.newValue };
    console.log('PAI: Configuration updated');
  }
});

// Get device type based on user agent
function getDeviceType() {
  const ua = navigator.userAgent;
  if (/mobile/i.test(ua)) return 'mobile';
  if (/tablet/i.test(ua)) return 'tablet';
  return 'desktop';
}

// Send visit to API
async function sendVisit(visitData) {
  if (!config.enabled) {
    console.log('PAI: Tracking disabled, skipping visit');
    return;
  }

  // Verbose logging - show what we're about to send
  console.log('PAI: Sending visit:');
  console.log('  URL:', visitData.url);
  console.log('  Title:', visitData.title);
  console.log('  Device:', visitData.device);
  console.log('  Timestamp:', visitData.timestamp);
  console.log('  Endpoint:', config.apiEndpoint);

  try {
    const response = await fetch(config.apiEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': config.apiKey
      },
      body: JSON.stringify(visitData)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const responseData = await response.json();
    console.log('PAI: ✅ Visit tracked successfully!');
    console.log('  Event ID:', responseData.event_id);
    console.log('  URL:', visitData.url);
    console.log('  Title:', visitData.title);
  } catch (error) {
    console.error('PAI: ❌ Failed to send visit!');
    console.error('  URL:', visitData.url);
    console.error('  Error:', error.message);
    console.warn('PAI: Queuing for retry...');
    offlineQueue.push({
      ...visitData,
      retryCount: 0,
      queuedAt: new Date().toISOString()
    });
    
    // Store offline queue
    chrome.storage.local.set({ offlineQueue });
  }
}

// Retry offline queue
async function retryOfflineQueue() {
  if (offlineQueue.length === 0) return;
  
  const queue = [...offlineQueue];
  offlineQueue = [];
  
  for (const visit of queue) {
    try {
      console.log('PAI: Retrying visit:', {
        url: visit.url,
        title: visit.title,
        timestamp: visit.timestamp,
        device: visit.device
      });
      
      const response = await fetch(config.apiEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': config.apiKey
        },
        body: JSON.stringify({
          url: visit.url,
          title: visit.title,
          timestamp: visit.timestamp,
          device: visit.device
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`PAI: HTTP ${response.status} error:`, errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      
      console.log('PAI: Retried visit sent successfully', visit.url);
    } catch (error) {
      console.error('PAI: Failed to retry visit:', error.message);
      visit.retryCount++;
      if (visit.retryCount < 5) {
        offlineQueue.push(visit);
      } else {
        console.error('PAI: Max retries exceeded for visit', visit.url);
      }
    }
  }
  
  chrome.storage.local.set({ offlineQueue });
}

// Listen for tab updates
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  // Only track when page has finished loading
  if (changeInfo.status !== 'complete') return;
  
  // Skip chrome:// URLs and invalid URLs
  if (!tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://')) {
    return;
  }

  const visitData = {
    url: tab.url,
    title: tab.title || 'Untitled',
    timestamp: new Date().toISOString(),
    device: getDeviceType()
  };

  sendVisit(visitData);
});

// Retry offline queue periodically (every 5 minutes)
setInterval(retryOfflineQueue, 5 * 60 * 1000);

// Retry when coming online
self.addEventListener('online', () => {
  console.log('PAI: Connection restored, retrying offline queue');
  retryOfflineQueue();
});

// Restore offline queue on startup
chrome.storage.local.get(['offlineQueue'], (result) => {
  if (result.offlineQueue) {
    offlineQueue = result.offlineQueue;
  }
});

// Fetch available endpoints from server
async function fetchServerEndpoints() {
  const baseUrl = config.baseUrl || 'http://localhost:8000';
  
  try {
    const response = await fetch(`${baseUrl}/`);
    if (response.ok) {
      const data = await response.json();
      if (data.endpoints && Array.isArray(data.endpoints)) {
        // Store available endpoints
        config.availableEndpoints = data.endpoints;
        console.log('PAI: Available endpoints loaded:', data.endpoints);
        return data.endpoints;
      }
    }
  } catch (error) {
    console.log('PAI: Could not fetch endpoints from server');
  }
  return null;
}

// Fetch endpoints on startup
fetchServerEndpoints();

// Refresh endpoints periodically (every 30 minutes)
setInterval(fetchServerEndpoints, 30 * 60 * 1000);

// Listen for messages from popup.js
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('PAI Background: Received message:', request);
  
  if (request.action === 'retryOfflineQueue') {
    console.log('PAI Background: Processing retryOfflineQueue, queue length:', offlineQueue.length);
    
    retryOfflineQueue().then(() => {
      console.log('PAI Background: retryOfflineQueue completed');
      sendResponse({ success: true, queueLength: offlineQueue.length });
    }).catch((error) => {
      console.error('PAI Background: Error retrying offline queue:', error);
      sendResponse({ success: false, error: error.message });
    });
    return true; // Required for async sendResponse
  }
});

console.log('PAI: Browser Tracker initialized');