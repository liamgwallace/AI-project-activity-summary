// PAI Browser Tracker - Background Service Worker
// Tracks page visits via Chrome History API polling

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

  console.log('PAI: Sending visit:', {
    url: visitData.url,
    title: visitData.title,
    timestamp: visitData.timestamp,
    device: visitData.device
  });

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
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    const responseData = await response.json();
    console.log('PAI: Visit tracked successfully! Event ID:', responseData.event_id);
  } catch (error) {
    console.error('PAI: Failed to send visit:', error.message);
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

// Query Chrome history for recent visits
async function pollHistory() {
  if (!config.enabled) {
    console.log('PAI: Tracking disabled, skipping history poll');
    return;
  }

  console.log('PAI: Polling Chrome history...');
  
  // Get last sync time
  const result = await chrome.storage.local.get(['lastHistorySync']);
  const lastSync = result.lastHistorySync ? new Date(result.lastHistorySync) : new Date(Date.now() - 60000);
  const now = new Date();
  
  // Search history for items visited since last sync
  chrome.history.search({
    text: '',
    startTime: lastSync.getTime(),
    endTime: now.getTime(),
    maxResults: 100
  }, async (historyItems) => {
    console.log(`PAI: Found ${historyItems.length} history items since last sync`);
    
    for (const item of historyItems) {
      // Skip chrome:// URLs and invalid URLs
      if (!item.url || item.url.startsWith('chrome://') || item.url.startsWith('chrome-extension://')) {
        continue;
      }

      // Get detailed visit information
      const visits = await chrome.history.getVisits({ url: item.url });
      
      // Filter visits that happened after last sync
      const newVisits = visits.filter(visit => visit.visitTime > lastSync.getTime());
      
      for (const visit of newVisits) {
        const visitData = {
          url: item.url,
          title: item.title || 'Untitled',
          timestamp: new Date(visit.visitTime).toISOString(),
          device: getDeviceType(),
          visitId: visit.visitId,
          transition: visit.transition
        };

        await sendVisit(visitData);
      }
    }
    
    // Update last sync time
    await chrome.storage.local.set({ lastHistorySync: now.toISOString() });
    console.log('PAI: History poll completed');
  });
}

// Get recent history for display (used by popup)
async function getRecentHistory(limit = 20) {
  return new Promise((resolve) => {
    chrome.history.search({
      text: '',
      startTime: Date.now() - (24 * 60 * 60 * 1000), // Last 24 hours
      maxResults: limit
    }, async (historyItems) => {
      const detailedHistory = [];
      
      for (const item of historyItems.slice(0, limit)) {
        if (!item.url || item.url.startsWith('chrome://') || item.url.startsWith('chrome-extension://')) {
          continue;
        }
        
        detailedHistory.push({
          url: item.url,
          title: item.title || 'Untitled',
          lastVisitTime: item.lastVisitTime,
          visitCount: item.visitCount
        });
      }
      
      resolve(detailedHistory);
    });
  });
}

// Set up periodic polling
chrome.alarms.create('historyPoll', { periodInMinutes: 1 });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'historyPoll') {
    pollHistory();
  }
});

// Retry offline queue periodically (every 5 minutes)
chrome.alarms.create('retryQueue', { periodInMinutes: 5 });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'retryQueue') {
    retryOfflineQueue();
  }
});

// Restore offline queue on startup
chrome.storage.local.get(['offlineQueue', 'lastHistorySync'], (result) => {
  if (result.offlineQueue) {
    offlineQueue = result.offlineQueue;
  }
  
  // Do initial poll on startup
  pollHistory();
});

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
    return true;
  }
  
  if (request.action === 'getRecentHistory') {
    console.log('PAI Background: Getting recent history');
    
    getRecentHistory(request.limit || 20).then((history) => {
      sendResponse({ success: true, history: history });
    }).catch((error) => {
      console.error('PAI Background: Error getting history:', error);
      sendResponse({ success: false, error: error.message });
    });
    return true;
  }
  
  if (request.action === 'pollHistory') {
    console.log('PAI Background: Manual history poll requested');
    
    pollHistory().then(() => {
      sendResponse({ success: true });
    }).catch((error) => {
      console.error('PAI Background: Error polling history:', error);
      sendResponse({ success: false, error: error.message });
    });
    return true;
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
chrome.alarms.create('refreshEndpoints', { periodInMinutes: 30 });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'refreshEndpoints') {
    fetchServerEndpoints();
  }
});

console.log('PAI: Browser Tracker initialized (History Polling Mode)');
