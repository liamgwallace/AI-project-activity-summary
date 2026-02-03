// PAI Browser Tracker - Popup Script

let currentConfig = null;

// Get device type
function getDeviceType() {
  const ua = navigator.userAgent;
  if (/mobile/i.test(ua)) return 'Mobile';
  if (/tablet/i.test(ua)) return 'Tablet';
  return 'Desktop';
}

// Initialize popup
async function init() {
  // Load configuration
  const result = await chrome.storage.sync.get(['paiConfig']);
  currentConfig = result.paiConfig || {
    apiEndpoint: 'http://localhost:8000/api/browser/visit',
    apiKey: 'your-api-key-here',
    enabled: true
  };
  
  // Load offline queue stats
  const localResult = await chrome.storage.local.get(['offlineQueue']);
  const queueLength = localResult.offlineQueue ? localResult.offlineQueue.length : 0;
  
  // Update UI
  updateUI(currentConfig, queueLength);
  
  // Setup event listeners
  document.getElementById('toggle-btn').addEventListener('click', toggleTracking);
  document.getElementById('settings-btn').addEventListener('click', openSettings);
  document.getElementById('sync-btn').addEventListener('click', syncNow);
}

// Update UI elements
function updateUI(config, queueLength) {
  const statusEl = document.getElementById('status');
  const statusTextEl = document.getElementById('status-text');
  const toggleBtn = document.getElementById('toggle-btn');
  const endpointEl = document.getElementById('endpoint');
  const queuedEl = document.getElementById('queued');
  const deviceEl = document.getElementById('device');
  const offlineBadge = document.getElementById('offline-badge');
  
  // Update status
  if (config.enabled) {
    statusEl.className = 'status enabled';
    statusTextEl.textContent = 'Tracking Enabled';
    toggleBtn.textContent = 'Disable Tracking';
    toggleBtn.className = 'btn-danger';
  } else {
    statusEl.className = 'status disabled';
    statusTextEl.textContent = 'Tracking Disabled';
    toggleBtn.textContent = 'Enable Tracking';
    toggleBtn.className = 'btn-primary';
  }
  
  // Update stats
  const endpoint = config.apiEndpoint || 'http://localhost:8000/api/browser/visit';
  endpointEl.textContent = endpoint.replace('http://', '').replace('https://', '').split('/')[0];
  queuedEl.textContent = queueLength;
  deviceEl.textContent = getDeviceType();
  
  // Show offline badge if there are queued visits
  if (queueLength > 0) {
    offlineBadge.classList.add('visible');
  } else {
    offlineBadge.classList.remove('visible');
  }
}

// Toggle tracking enabled/disabled
async function toggleTracking() {
  if (!currentConfig) return;
  
  currentConfig.enabled = !currentConfig.enabled;
  
  await chrome.storage.sync.set({ paiConfig: currentConfig });
  
  // Reload offline queue count
  const result = await chrome.storage.local.get(['offlineQueue']);
  const queueLength = result.offlineQueue ? result.offlineQueue.length : 0;
  
  updateUI(currentConfig, queueLength);
}

// Open settings/options page
function openSettings() {
  chrome.tabs.create({ url: 'options.html' });
  window.close();
}

// Trigger sync manually
async function syncNow() {
  const syncBtn = document.getElementById('sync-btn');
  const originalText = syncBtn.textContent;
  
  syncBtn.textContent = 'Syncing...';
  syncBtn.disabled = true;
  
  try {
    // Send message to background to retry offline queue
    await chrome.runtime.sendMessage({ action: 'retryOfflineQueue' });
    
    // Refresh queue count
    const result = await chrome.storage.local.get(['offlineQueue']);
    const queueLength = result.offlineQueue ? result.offlineQueue.length : 0;
    
    updateUI(currentConfig, queueLength);
    
    syncBtn.textContent = queueLength === 0 ? 'Synced!' : 'Sync Failed';
    setTimeout(() => {
      syncBtn.textContent = originalText;
      syncBtn.disabled = false;
    }, 2000);
  } catch (error) {
    syncBtn.textContent = 'Error';
    setTimeout(() => {
      syncBtn.textContent = originalText;
      syncBtn.disabled = false;
    }, 2000);
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);