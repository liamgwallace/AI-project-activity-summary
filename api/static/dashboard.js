/**
 * PAIS Dashboard - Client-side JavaScript
 */

// Global state
let paisNetwork = null;
let projectsCache = [];

// =====================
// Initialization
// =====================

document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    loadTokenStats();
    loadProjects();

    // Load data when tabs are activated
    document.getElementById('events-tab').addEventListener('shown.bs.tab', () => loadEvents());
    document.getElementById('activities-tab').addEventListener('shown.bs.tab', () => loadActivities());
    document.getElementById('entities-tab').addEventListener('shown.bs.tab', () => loadEntities());
    document.getElementById('graph-tab').addEventListener('shown.bs.tab', () => loadGraph());
    document.getElementById('logs-tab').addEventListener('shown.bs.tab', () => loadLogs());

    // Refresh health every 30s
    setInterval(checkHealth, 30000);
});


// =====================
// Health Check
// =====================

async function checkHealth() {
    const badge = document.getElementById('health-badge');
    try {
        const resp = await fetch('/api/health');
        if (resp.ok) {
            badge.className = 'badge bg-success';
            badge.textContent = 'Healthy';
        } else {
            badge.className = 'badge bg-danger';
            badge.textContent = 'Error';
        }
    } catch {
        badge.className = 'badge bg-danger';
        badge.textContent = 'Offline';
    }
}


// =====================
// Projects (shared)
// =====================

async function loadProjects() {
    try {
        const resp = await fetch('/api/dashboard/projects');
        const data = await resp.json();
        projectsCache = data.projects || [];

        // Populate project dropdowns
        const selectors = ['activities-project', 'graph-project'];
        for (const id of selectors) {
            const sel = document.getElementById(id);
            if (!sel) continue;
            // Keep the "All" option
            while (sel.options.length > 1) sel.remove(1);
            for (const p of projectsCache) {
                const opt = document.createElement('option');
                opt.value = p.name;
                opt.textContent = p.name;
                sel.appendChild(opt);
            }
        }
    } catch (e) {
        console.error('Failed to load projects:', e);
    }
}


// =====================
// Command Execution
// =====================

async function runCommand(commandName) {
    const buttons = document.querySelectorAll('.cmd-btn');
    const spinner = document.getElementById('cmd-spinner');
    const status = document.getElementById('cmd-status');
    const output = document.getElementById('cmd-output');
    const duration = document.getElementById('cmd-duration');

    // Disable buttons, show spinner
    buttons.forEach(b => b.disabled = true);
    spinner.classList.remove('d-none');
    status.textContent = `Running ${commandName}...`;
    output.textContent = '';
    output.className = 'cmd-output';
    duration.textContent = '';

    try {
        const resp = await fetch('/api/dashboard/commands/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: commandName }),
        });

        if (resp.status === 409) {
            output.textContent = 'A command is already running. Please wait.';
            output.classList.add('error');
            return;
        }

        const data = await resp.json();
        output.textContent = data.output || (data.success ? 'Done (no output)' : 'Failed');
        output.classList.add(data.success ? 'success' : 'error');
        duration.textContent = `Completed in ${data.duration_seconds}s`;

        if (data.error) {
            output.textContent += `\n\nERROR: ${data.error}`;
        }

        // Refresh token stats after command
        loadTokenStats();
    } catch (err) {
        output.textContent = `Fetch error: ${err.message}`;
        output.classList.add('error');
    } finally {
        buttons.forEach(b => b.disabled = false);
        spinner.classList.add('d-none');
    }
}


// =====================
// Token Stats
// =====================

async function loadTokenStats() {
    try {
        const resp = await fetch('/api/dashboard/token-stats?days=30');
        const data = await resp.json();

        document.getElementById('stat-total-tokens').textContent =
            (data.total_tokens || 0).toLocaleString();
        document.getElementById('stat-total-cost').textContent =
            `$${(data.total_cost || 0).toFixed(4)}`;
        document.getElementById('stat-batches-completed').textContent =
            data.batches?.completed ?? '--';
        document.getElementById('stat-batches-failed').textContent =
            data.batches?.failed ?? '--';
    } catch (e) {
        console.error('Failed to load token stats:', e);
    }
}


// =====================
// Events Table
// =====================

async function loadEvents() {
    const days = document.getElementById('events-days').value;
    const source = document.getElementById('events-source').value;
    const limit = document.getElementById('events-limit').value;

    try {
        const resp = await fetch(`/api/dashboard/events?days=${days}&limit=${limit}&source=${source}`);
        const data = await resp.json();

        document.getElementById('events-total').textContent = `${data.total} total`;

        const tbody = document.getElementById('events-body');
        tbody.innerHTML = '';

        if (!data.events || data.events.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No events found</td></tr>';
            return;
        }

        for (const e of data.events) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${e.id}</td>
                <td><span class="source-badge ${e.source}">${e.source}</span></td>
                <td>${e.event_type}</td>
                <td><small>${formatTime(e.event_time)}</small></td>
                <td><span class="badge ${e.processed ? 'badge-processed' : 'badge-unprocessed'}">${e.processed ? 'Processed' : 'Pending'}</span></td>
                <td><small>${escapeHtml(e.summary || '')}</small></td>
            `;
            tbody.appendChild(tr);
        }
    } catch (e) {
        console.error('Failed to load events:', e);
    }
}


// =====================
// Activities Table
// =====================

async function loadActivities() {
    const days = document.getElementById('activities-days').value;
    const project = document.getElementById('activities-project').value;

    try {
        const resp = await fetch(`/api/dashboard/activities?days=${days}&limit=100&project=${project}`);
        const data = await resp.json();

        document.getElementById('activities-total').textContent = `${data.total} total`;

        const tbody = document.getElementById('activities-body');
        tbody.innerHTML = '';

        if (!data.activities || data.activities.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No activities found</td></tr>';
            return;
        }

        for (const a of data.activities) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${a.id}</td>
                <td><small>${formatTime(a.timestamp)}</small></td>
                <td><span class="badge bg-primary">${escapeHtml(a.project_name)}</span></td>
                <td>${escapeHtml(a.activity_type)}</td>
                <td><small>${escapeHtml(a.description)}</small></td>
            `;
            tbody.appendChild(tr);
        }
    } catch (e) {
        console.error('Failed to load activities:', e);
    }
}


// =====================
// Entities Table
// =====================

async function loadEntities() {
    const days = document.getElementById('entities-days').value;
    const limit = document.getElementById('entities-limit').value;

    try {
        const resp = await fetch(`/api/dashboard/entities?days=${days}&limit=${limit}`);
        const data = await resp.json();

        document.getElementById('entities-total').textContent = `${data.total} total`;

        const tbody = document.getElementById('entities-body');
        tbody.innerHTML = '';

        if (!data.entities || data.entities.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No entities found</td></tr>';
            return;
        }

        for (const e of data.entities) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${e.id}</td>
                <td><span class="entity-badge ${e.entity_type}">${e.entity_type}</span></td>
                <td>${escapeHtml(e.name)}</td>
                <td>${escapeHtml(e.display_name)}</td>
                <td>${e.mention_count}</td>
                <td><small>${formatTime(e.first_seen)}</small></td>
                <td><small>${formatTime(e.last_seen)}</small></td>
            `;
            tbody.appendChild(tr);
        }
    } catch (e) {
        console.error('Failed to load entities:', e);
    }
}


// =====================
// Graph (vis.js)
// =====================

async function loadGraph() {
    const days = document.getElementById('graph-days').value;
    const project = document.getElementById('graph-project').value;
    const container = document.getElementById('graph-container');
    const emptyMsg = document.getElementById('graph-empty');

    try {
        const resp = await fetch(`/api/dashboard/graph?days=${days}&project=${project}`);
        const data = await resp.json();

        if (!data.nodes || data.nodes.length === 0) {
            container.style.display = 'none';
            emptyMsg.classList.remove('d-none');
            return;
        }

        container.style.display = 'block';
        emptyMsg.classList.add('d-none');

        const nodes = new vis.DataSet(data.nodes);
        const edges = new vis.DataSet(data.edges);

        const options = {
            physics: {
                forceAtlas2Based: {
                    gravitationalConstant: -150,
                    centralGravity: 0.005,
                    springLength: 200,
                    springConstant: 0.05,
                },
                maxVelocity: 50,
                solver: 'forceAtlas2Based',
                timestep: 0.35,
                adaptiveTimestep: true,
                stabilization: { enabled: true, iterations: 1000, updateInterval: 25 },
            },
            interaction: {
                hover: true,
                tooltipDelay: 200,
                hideEdgesOnDrag: true,
            },
            edges: {
                smooth: { type: 'continuous', forceDirection: 'none' },
                color: { color: '#cccccc', highlight: '#666666' },
                font: { size: 9, color: '#999' },
            },
            nodes: {
                font: { size: 11 },
            },
        };

        // Destroy previous network
        if (paisNetwork) {
            paisNetwork.destroy();
            paisNetwork = null;
        }

        paisNetwork = new vis.Network(container, { nodes, edges }, options);
    } catch (e) {
        console.error('Failed to load graph:', e);
    }
}


// =====================
// Logs
// =====================

async function loadLogs() {
    const lines = document.getElementById('logs-lines').value;
    const level = document.getElementById('logs-level').value;

    try {
        const resp = await fetch(`/api/dashboard/logs?lines=${lines}&level=${level}`);
        const data = await resp.json();

        document.getElementById('logs-count').textContent = `${data.total_lines} lines`;

        const output = document.getElementById('logs-output');
        output.innerHTML = '';

        if (!data.lines || data.lines.length === 0) {
            output.textContent = 'No log entries found.';
            return;
        }

        // Color-code log lines
        for (const line of data.lines) {
            const span = document.createElement('span');
            if (line.includes(' - ERROR - ')) {
                span.className = 'log-error';
            } else if (line.includes(' - WARNING - ')) {
                span.className = 'log-warning';
            } else if (line.includes(' - INFO - ')) {
                span.className = 'log-info';
            }
            span.textContent = line + '\n';
            output.appendChild(span);
        }

        // Scroll to bottom
        output.scrollTop = output.scrollHeight;
    } catch (e) {
        console.error('Failed to load logs:', e);
    }
}


// =====================
// Helpers
// =====================

function formatTime(isoStr) {
    if (!isoStr) return '--';
    try {
        const d = new Date(isoStr);
        if (isNaN(d.getTime())) return isoStr;
        return d.toLocaleString();
    } catch {
        return isoStr;
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
