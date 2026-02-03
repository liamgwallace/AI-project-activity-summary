// PAI Browser Tracker - Options Page Script

document.addEventListener('DOMContentLoaded', loadSettings);
document.getElementById('settingsForm').addEventListener('submit', saveSettings);
document.getElementById('testButton').addEventListener('click', testConnection);

async function loadSettings() {
    const result = await chrome.storage.local.get([
        'pai_api_endpoint',
        'pai_api_key',
        'pai_device_name'
    ]);
    
    document.getElementById('apiEndpoint').value = result.pai_api_endpoint || '';
    document.getElementById('apiKey').value = result.pai_api_key || '';
    document.getElementById('deviceName').value = result.pai_device_name || 'desktop';
}

async function saveSettings(e) {
    e.preventDefault();
    
    const settings = {
        pai_api_endpoint: document.getElementById('apiEndpoint').value,
        pai_api_key: document.getElementById('apiKey').value,
        pai_device_name: document.getElementById('deviceName').value || 'desktop'
    };
    
    await chrome.storage.local.set(settings);
    
    showStatus('Settings saved successfully!', 'success');
}

async function testConnection() {
    const endpoint = document.getElementById('apiEndpoint').value;
    const apiKey = document.getElementById('apiKey').value;
    const device = document.getElementById('deviceName').value || 'desktop';
    
    if (!endpoint || !apiKey) {
        showStatus('Please fill in API endpoint and API key first', 'error');
        return;
    }
    
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
