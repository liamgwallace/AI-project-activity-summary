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
  document.getElementById('history-btn').addEventListener('click', toggleHistory);
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

// Toggle history display
async function toggleHistory() {
  const historySection = document.getElementById('history-section');
  const historyBtn = document.getElementById('history-btn');
  
  if (historySection.style.display === 'none') {
    historyBtn.textContent = 'Loading...';
    historyBtn.disabled = true;
    
    try {
      await displayHistory();
      historySection.style.display = 'block';
      historyBtn.textContent = 'Hide History';
    } catch (error) {
      console.error('Failed to load history:', error);
      historyBtn.textContent = 'Error';
      setTimeout(() => {
        historyBtn.textContent = 'View History';
      }, 2000);
    } finally {
      historyBtn.disabled = false;
    }
  } else {
    historySection.style.display = 'none';
    historyBtn.textContent = 'View History';
  }
}

// Fetch and display recent history
async function displayHistory() {
  const historyList = document.getElementById('history-list');
  historyList.innerHTML = '<div style="color: #666;">Loading...</div>';
  
  try {
    // Request history from background script
    const response = await chrome.runtime.sendMessage({ 
      action: 'getRecentHistory',
      limit: 10 
    });
    
    if (!response.success) {
      throw new Error(response.error || 'Failed to fetch history');
    }
    
    const history = response.history;
    
    if (history.length === 0) {
      historyList.innerHTML = '<div style="color: #666;">No recent history found</div>';
      return;
    }
    
    // Build history HTML
    let html = '';
    history.forEach(item => {
      const time = formatTime(item.lastVisitTime);
      const title = escapeHtml(item.title || 'Untitled');
      const url = escapeHtml(item.url);
      const shortUrl = url.length > 50 ? url.substring(0, 50) + '...' : url;
      
      html += `
        <div class="history-item">
          <div class="history-title">${title}</div>
          <div class="history-url">${shortUrl}</div>
          <div class="history-time">${time} · ${item.visitCount} visit${item.visitCount !== 1 ? 's' : ''}</div>
        </div>
      `;
    });
    
    historyList.innerHTML = html;
    
  } catch (error) {
    console.error('Error displaying history:', error);
    historyList.innerHTML = `<div style="color: #c62828;">Error: ${error.message}</div>`;
    throw error;
  }
}

// Format timestamp to readable string
function formatTime(timestamp) {
  if (!timestamp) return 'Unknown';
  
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  
  return date.toLocaleDateString();
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);