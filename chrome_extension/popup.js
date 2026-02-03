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
    enabled: true,
    baseUrl: 'http://localhost:8000'
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
  document.getElementById('stats-btn').addEventListener('click', toggleStats);
  document.getElementById('health-btn').addEventListener('click', checkHealth);
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
    console.log('PAI Popup: Sending retryOfflineQueue message');
    const response = await chrome.runtime.sendMessage({ action: 'retryOfflineQueue' });
    console.log('PAI Popup: Received response:', response);
    
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
    console.error('PAI Popup: Sync error:', error);
    syncBtn.textContent = 'Error';
    setTimeout(() => {
      syncBtn.textContent = originalText;
      syncBtn.disabled = false;
    }, 2000);
  }
}

// Toggle stats display
async function toggleStats() {
  const statsSection = document.getElementById('stats-section');
  const statsBtn = document.getElementById('stats-btn');
  
  if (statsSection.style.display === 'none') {
    statsBtn.textContent = 'Loading...';
    statsBtn.disabled = true;
    
    try {
      await fetchStats();
      statsSection.style.display = 'block';
      statsBtn.textContent = 'Hide Stats';
    } catch (error) {
      statsBtn.textContent = 'Error';
      setTimeout(() => {
        statsBtn.textContent = 'Show Stats';
      }, 2000);
    } finally {
      statsBtn.disabled = false;
    }
  } else {
    statsSection.style.display = 'none';
    statsBtn.textContent = 'Show Stats';
  }
}

// Fetch stats from API
async function fetchStats() {
  if (!currentConfig) return;
  
  const baseUrl = currentConfig.baseUrl || 'http://localhost:8000';
  const statsUrl = `${baseUrl}/api/stats`;
  
  try {
    const response = await fetch(statsUrl, {
      method: 'GET',
      headers: {
        'X-API-Key': currentConfig.apiKey || ''
      }
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const stats = await response.json();
    
    document.getElementById('stats-total').textContent = stats.total_events || 0;
    document.getElementById('stats-unprocessed').textContent = stats.unprocessed_events || 0;
    document.getElementById('stats-visits').textContent = stats.recent_visits || 0;
    
  } catch (error) {
    console.error('Failed to fetch stats:', error);
    document.getElementById('stats-total').textContent = 'Error';
    document.getElementById('stats-unprocessed').textContent = 'Error';
    document.getElementById('stats-visits').textContent = 'Error';
    throw error;
  }
}

// Check health endpoint
async function checkHealth() {
  const healthBtn = document.getElementById('health-btn');
  const originalText = healthBtn.textContent;
  
  healthBtn.textContent = 'Checking...';
  healthBtn.disabled = true;
  
  try {
    const baseUrl = currentConfig?.baseUrl || 'http://localhost:8000';
    const healthUrl = `${baseUrl}/api/health`;
    
    const response = await fetch(healthUrl);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const health = await response.json();
    
    // Show alert with health info
    alert(`Health Check: ${health.status}\nVersion: ${health.version}\nTimestamp: ${new Date(health.timestamp).toLocaleString()}`);
    
    healthBtn.textContent = 'Healthy!';
    setTimeout(() => {
      healthBtn.textContent = originalText;
      healthBtn.disabled = false;
    }, 2000);
    
  } catch (error) {
    console.error('Health check failed:', error);
    alert(`Health Check Failed: ${error.message}`);
    healthBtn.textContent = 'Failed';
    setTimeout(() => {
      healthBtn.textContent = originalText;
      healthBtn.disabled = false;
    }, 2000);
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);