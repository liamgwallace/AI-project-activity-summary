// PAI Browser Tracker - Options Page Script

document.addEventListener('DOMContentLoaded', loadSettings);
document.getElementById('settingsForm').addEventListener('submit', saveSettings);
document.getElementById('testButton').addEventListener('click', testConnection);

async function loadSettings() {
    // Load from both storage types for backward compatibility
    const localResult = await chrome.storage.local.get([
        'pai_api_endpoint',
        'pai_api_key',
        'pai_device_name',
        'pai_base_url'
    ]);
    
    const syncResult = await chrome.storage.sync.get(['paiConfig']);
    
    // Get base URL from sync storage first, then local, then default
    let baseUrl = 'http://localhost:8000';
    let apiKey = '';
    let deviceName = 'desktop';
    
    if (syncResult.paiConfig) {
        baseUrl = syncResult.paiConfig.baseUrl || baseUrl;
        apiKey = syncResult.paiConfig.apiKey || apiKey;
        deviceName = syncResult.paiConfig.deviceName || deviceName;
    }
    
    // Fall back to local storage if sync not available
    if (localResult.pai_base_url) baseUrl = localResult.pai_base_url;
    if (localResult.pai_api_key) apiKey = localResult.pai_api_key;
    if (localResult.pai_device_name) deviceName = localResult.pai_device_name;
    
    document.getElementById('baseUrl').value = baseUrl;
    document.getElementById('apiKey').value = apiKey;
    document.getElementById('deviceName').value = deviceName;
    
    // Fetch available endpoints from the server
    fetchEndpoints(baseUrl);
}

async function saveSettings(e) {
    e.preventDefault();
    
    const baseUrl = document.getElementById('baseUrl').value.replace(/\/$/, ''); // Remove trailing slash
    const apiKey = document.getElementById('apiKey').value;
    const deviceName = document.getElementById('deviceName').value || 'desktop';
    
    const settings = {
        pai_base_url: baseUrl,
        pai_api_key: apiKey,
        pai_device_name: deviceName
    };
    
    // Also save to sync storage for popup.js compatibility
    const paiConfig = {
        apiEndpoint: `${baseUrl}/api/browser/visit`,
        apiKey: apiKey,
        enabled: true,
        baseUrl: baseUrl,
        deviceName: deviceName
    };
    
    await chrome.storage.local.set(settings);
    await chrome.storage.sync.set({ paiConfig: paiConfig });
    
    showStatus('Settings saved successfully!', 'success');
    
    // Refresh endpoints list
    fetchEndpoints(baseUrl);
}

// Fetch available endpoints from the root endpoint
async function fetchEndpoints(baseUrl) {
    try {
        const response = await fetch(`${baseUrl}/`);
        if (response.ok) {
            const data = await response.json();
            if (data.endpoints && Array.isArray(data.endpoints)) {
                updateEndpointsList(data.endpoints);
            }
        }
    } catch (error) {
        console.log('Could not fetch endpoints from server:', error);
    }
}

// Update the endpoints list in the UI
function updateEndpointsList(endpoints) {
    const listContainer = document.getElementById('endpoints-list');
    if (!listContainer || !endpoints) return;
    
    listContainer.innerHTML = '';
    
    endpoints.forEach(endpoint => {
        const item = document.createElement('div');
        item.className = 'endpoint-item';
        item.innerHTML = `
            <span class="endpoint-path">${endpoint.path}</span>
            <span class="endpoint-method">${endpoint.method}</span>
            <span class="endpoint-desc">${endpoint.description}</span>
        `;
        listContainer.appendChild(item);
    });
}

async function testConnection() {
    const baseUrl = document.getElementById('baseUrl').value.replace(/\/$/, '');
    const apiKey = document.getElementById('apiKey').value;
    const device = document.getElementById('deviceName').value || 'desktop';
    
    if (!baseUrl || !apiKey) {
        showStatus('Please fill in base URL and API key first', 'error');
        return;
    }
    
    const endpoint = `${baseUrl}/api/browser/visit`;
    
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': apiKey
            },
            body: JSON.stringify({
                url: 'https://example.com/test',
                title: 'Test Page - PAI Browser Tracker',
                timestamp: new Date().toISOString(),
                device: device
            })
        });
        
        if (response.ok) {
            showStatus('Connection successful! Test event sent.', 'success');
        } else {
            const error = await response.text();
            showStatus(`Connection failed: ${response.status} - ${error}`, 'error');
        }
    } catch (error) {
        showStatus(`Connection error: ${error.message}`, 'error');
    }
}

function showStatus(message, type) {
    const status = document.getElementById('status');
    status.textContent = message;
    status.className = `status ${type}`;
    
    setTimeout(() => {
        status.style.display = 'none';
    }, 5000);
}
