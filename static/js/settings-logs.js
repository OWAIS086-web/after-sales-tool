/**
 * Settings Page - Logs Management
 * Handles log file listing and downloading
 */

let logsLoaded = false;

// Load logs when section is shown
function loadLogsOnShow() {
    const logsSection = document.getElementById('logs-section');
    if (logsSection && logsSection.classList.contains('active') && !logsLoaded) {
        loadLogsList();
    }
}

// Load logs list
function loadLogsList() {
    try {
        const logsList = document.getElementById('logs-list');
        if (!logsList) return;
        
        // Show loading state
        logsList.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 40px 20px; grid-column: 1/-1;">Loading logs...</p>';
        
        // Fetch logs list
        fetch('/api/logs/list')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    renderLogsList(data.logs, logsList);
                    logsLoaded = true;
                } else {
                    logsList.innerHTML = `<p style="text-align: center; color: var(--text-secondary); padding: 40px 20px; grid-column: 1/-1;">Error loading logs: ${data.error}</p>`;
                }
            })
            .catch(error => {
                console.error('Error loading logs:', error);
                logsList.innerHTML = `<p style="text-align: center; color: var(--text-secondary); padding: 40px 20px; grid-column: 1/-1;">Error loading logs: ${error.message}</p>`;
            });
    } catch (error) {
        console.error('Error in loadLogsList:', error);
    }
}

// Render logs list
function renderLogsList(logs, container) {
    try {
        if (!logs || logs.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 40px 20px; grid-column: 1/-1;">No log files found</p>';
            return;
        }

        let html = '';
        logs.forEach(log => {
            const sizeInMB = (log.size / (1024 * 1024)).toFixed(2);
            const modifiedDate = new Date(log.modified).toLocaleString();
            
            html += `
                <div class="log-file-card">
                    <div class="log-file-header">
                        <div class="log-file-name">${log.name}</div>
                        <div class="log-file-size">${sizeInMB} MB</div>
                    </div>
                    <div class="log-file-info">
                        <small>Modified: ${modifiedDate}</small>
                    </div>
                    <div class="log-file-actions">
                        <button class="btn btn-sm btn-primary" onclick="downloadLog('${log.name}')">
                            📥 Download
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="deleteLog('${log.name}')">
                            🗑️ Delete
                        </button>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    } catch (error) {
        console.error('Error rendering logs list:', error);
        container.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 40px 20px; grid-column: 1/-1;">Error rendering logs</p>';
    }
}

// Download log file
function downloadLog(filename) {
    try {
        showNotification(`Downloading ${filename}...`, 'info');
        
        // Create download link
        const downloadUrl = `/api/logs/download?filename=${encodeURIComponent(filename)}`;
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        showNotification(`${filename} download started`, 'success');
    } catch (error) {
        console.error('Error downloading log:', error);
        showNotification(`Error downloading log: ${error.message}`, 'error');
    }
}

// Delete log file
function deleteLog(filename) {
    try {
        if (!confirm(`Are you sure you want to delete ${filename}?`)) {
            return;
        }

        showNotification(`Deleting ${filename}...`, 'info');
        
        fetch(`/api/logs/delete?filename=${encodeURIComponent(filename)}`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(`${filename} deleted successfully`, 'success');
                logsLoaded = false;
                loadLogsList();
            } else {
                showNotification(`Error deleting log: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            console.error('Error deleting log:', error);
            showNotification(`Error deleting log: ${error.message}`, 'error');
        });
    } catch (error) {
        console.error('Error in deleteLog:', error);
    }
}

// Refresh logs list
function refreshLogsList() {
    try {
        logsLoaded = false;
        loadLogsList();
        showNotification('Logs list refreshed', 'success');
    } catch (error) {
        console.error('Error refreshing logs:', error);
        showNotification('Error refreshing logs', 'error');
    }
}

// Clear all logs
function clearAllLogs() {
    try {
        if (!confirm('Are you sure you want to delete ALL log files? This cannot be undone.')) {
            return;
        }

        showNotification('Clearing all logs...', 'info');
        
        fetch('/api/logs/clear', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('All logs cleared successfully', 'success');
                logsLoaded = false;
                loadLogsList();
            } else {
                showNotification(`Error clearing logs: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            console.error('Error clearing logs:', error);
            showNotification(`Error clearing logs: ${error.message}`, 'error');
        });
    } catch (error) {
        console.error('Error in clearAllLogs:', error);
    }
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        console.log('[Logs] Initialization complete');
    });
} else {
    console.log('[Logs] Initialization complete');
}
