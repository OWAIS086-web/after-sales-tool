// Settings Scheduler Integration
// Loads scheduler functionality into the settings page

let schedulerLoaded = false;
let schedulerHistoryLoaded = false;

// Override showSection to handle scheduler loading
const originalShowSection = window.showSection;
window.showSection = function(sectionName) {
    // Call original function
    originalShowSection(sectionName);
    
    // Load scheduler content if scheduler section is shown
    if (sectionName === 'scheduler' && !schedulerLoaded) {
        loadSchedulerContent();
        loadSchedulerHistory();
    }
};

// Load scheduler content via iframe or fetch
function loadSchedulerContent() {
    try {
        const schedulerContent = document.getElementById('scheduler-content');
        if (!schedulerContent) return;
        
        // Show loading state
        schedulerContent.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 40px 20px;">Loading scheduler...</p>';
        
        // Get user's company from debug element
        const userCompany = document.getElementById('debug-company')?.getAttribute('data-company') || 'haval';
        console.log('[Scheduler] User Company:', userCompany);
        console.log('[Scheduler] Debug Element:', document.getElementById('debug-company'));
        
        // Fetch scheduler data - note the /admin prefix
        fetch('/admin/api/scheduler/status')
            .then(response => response.json())
            .then(data => {
                console.log('[Scheduler] All Jobs:', data.jobs);
                
                // Filter jobs by company - only show jobs for the same company
                let filteredJobs = (data.jobs || []).filter(job => {
                    return job.company_id === userCompany;
                });
                
                console.log('[Scheduler] Filtered Jobs:', filteredJobs);
                console.log('[Scheduler] Job Count:', filteredJobs.length);
                
                // The endpoint returns: { status, jobs, stats }
                const formattedData = {
                    success: true,
                    scheduler_status: {
                        running: data.status === 'running',
                        job_count: filteredJobs.length
                    },
                    stats: data.stats || {},
                    jobs: filteredJobs
                };
                renderSchedulerContent(formattedData, schedulerContent);
                schedulerLoaded = true;
            })
            .catch(error => {
                console.error('Error loading scheduler:', error);
                schedulerContent.innerHTML = `<p style="text-align: center; color: var(--text-secondary); padding: 40px 20px;">Error loading scheduler: ${error.message}</p>`;
            });
    } catch (error) {
        console.error('Error in loadSchedulerContent:', error);
    }
}

// Render scheduler content
function renderSchedulerContent(data, container) {
    try {
        const scheduler = data.scheduler_status || {};
        const stats = data.stats || {};
        const jobs = data.jobs || [];
        
        let html = `
            <!-- Status Overview -->
            <div class="scheduler-status-grid">
                <div class="scheduler-status-card">
                    <div class="scheduler-status-icon ${scheduler.running ? 'running' : 'stopped'}">
                        ${scheduler.running ? 'OK' : '🚦'}
                    </div>
                    <div class="scheduler-status-info">
                        <h3>Status</h3>
                        <div class="scheduler-status-value">${scheduler.running ? 'Running' : 'Stopped'}</div>
                    </div>
                </div>
                
                <div class="scheduler-status-card">
                    <div class="scheduler-status-icon jobs">🗓️</div>
                    <div class="scheduler-status-info">
                        <h3>Scheduled Jobs</h3>
                        <div class="scheduler-status-value">${scheduler.job_count || 0}</div>
                    </div>
                </div>
                
                <div class="scheduler-status-card">
                    <div class="scheduler-status-icon success">✅</div>
                    <div class="scheduler-status-info">
                        <h3>Successful (24h)</h3>
                        <div class="scheduler-status-value">${stats.success || 0}</div>
                    </div>
                </div>
                
                <div class="scheduler-status-card">
                    <div class="scheduler-status-icon failed">❌</div>
                    <div class="scheduler-status-info">
                        <h3>Failed</h3>
                        <div class="scheduler-status-value">${stats.failed || 0}</div>
                    </div>
                </div>
            </div>
            
            <!-- Scheduled Jobs -->
            <h3 class="scheduler-section-title">Scheduled Jobs</h3>
        `;
        
        if (jobs.length > 0) {
            html += '<div class="scheduler-jobs-grid">';
            
            jobs.forEach(job => {
                const isEnabled = job.enabled !== false;
                const lastExec = job.last_execution || {};
                // Format next run time with time remaining
                let nextRunDisplay = 'N/A';
                if (job.next_run_time) {
                    try {
                        const nextRunDate = new Date(job.next_run_time);
                        const now = new Date();
                        const diffMs = nextRunDate - now;
                        
                        if (diffMs > 0) {
                            const diffMins = Math.floor(diffMs / 60000);
                            const diffHours = Math.floor(diffMins / 60);
                            const diffDays = Math.floor(diffHours / 24);
                            
                            if (diffDays > 0) {
                                nextRunDisplay = `${diffDays}d ${diffHours % 24}h`;
                            } else if (diffHours > 0) {
                                nextRunDisplay = `${diffHours}h ${diffMins % 60}m`;
                            } else {
                                nextRunDisplay = `${diffMins}m`;
                            }
                        } else {
                            nextRunDisplay = 'Soon';
                        }
                    } catch (e) {
                        nextRunDisplay = 'N/A';
                    }
                }
                // Format schedule display
                let scheduleDisplay = 'N/A';
                if (job.schedule_display) {
                    scheduleDisplay = job.schedule_display;
                } else if (job.schedule) {
                    const sched = job.schedule;
                    if (typeof sched === 'string') {
                        scheduleDisplay = sched;
                    } else if (typeof sched === 'object') {
                        const freq = sched.frequency || 'unknown';
                        const time = sched.time || '00:00';
                        if (freq === 'daily') {
                            scheduleDisplay = `Daily at ${time}`;
                        } else if (freq === 'weekly') {
                            const day = sched.day_of_week || 'Monday';
                            scheduleDisplay = `Weekly on ${day} at ${time}`;
                        } else if (freq === 'monthly') {
                            const day = sched.day_of_month || '1';
                            scheduleDisplay = `Monthly on day ${day} at ${time}`;
                        } else {
                            scheduleDisplay = `${freq} at ${time}`;
                        }
                    }
                }
                
                const lastRun = lastExec.started_at ? new Date(lastExec.started_at).toLocaleString() : 'Never';
                
                // Calculate estimated cost
                let costEstimate = '';
                const jobType = job.id ? job.id.split('_')[0] : null;
                if (jobType === 'pakwheels' || jobType === 'reddit') {
                    const maxPosts = job.parameters?.max_posts || 1000;
                    const costPerPost = 0.0001;
                    const estimatedCost = (maxPosts * costPerPost).toFixed(4);
                    costEstimate = `<div class="scheduler-job-detail-row">
                        <span class="scheduler-job-detail-label">Est. Cost:</span>
                        <span class="scheduler-job-detail-value">$${estimatedCost}</span>
                    </div>`;
                } else if (jobType === 'wati') {
                    // WATI cost estimation based on frequency
                    const frequency = job.schedule?.frequency || 'daily';
                    let estimatedCost = '0.50';
                    if (frequency === 'daily') {
                        estimatedCost = '0.50';
                    } else if (frequency === 'weekly') {
                        estimatedCost = '1.20';
                    } else if (frequency === 'monthly') {
                        estimatedCost = '3.50';
                    }
                    costEstimate = `<div class="scheduler-job-detail-row">
                        <span class="scheduler-job-detail-label">Est. Cost:</span>
                        <span class="scheduler-job-detail-value">$${estimatedCost}</span>
                    </div>`;
                }
                
                html += `
                    <div class="scheduler-job-card" data-job-id="${job.id}" data-disabled="${!isEnabled}">
                        <div class="scheduler-job-header">
                            <div>
                                <div class="scheduler-job-title">${job.id}</div>
                                <div class="scheduler-job-type">${(job.type || 'unknown').toUpperCase()} - ${job.company_id || 'N/A'}</div>
                            </div>
                            <div class="scheduler-job-status">
                                <span class="scheduler-badge ${isEnabled ? 'enabled' : 'disabled'}">
                                    ${isEnabled ? 'Enabled' : 'Disabled'}
                                </span>
                            </div>
                        </div>
                        
                        <div class="scheduler-job-details">
                            <div class="scheduler-job-detail-row">
                                <span class="scheduler-job-detail-label">Schedule:</span>
                                <span class="scheduler-job-detail-value">${scheduleDisplay}</span>
                            </div>
                            <div class="scheduler-job-detail-row">
                                <span class="scheduler-job-detail-label">Last Run:</span>
                                <span class="scheduler-job-detail-value">${lastRun}</span>
                            </div>
                            <div class="scheduler-job-detail-row">
                                <span class="scheduler-job-detail-label">Next Run:</span>
                                <span class="scheduler-job-detail-value">${nextRunDisplay}</span>
                            </div>
                            ${costEstimate}
                        </div>
                        
                        <div class="scheduler-job-actions">
                            <button class="scheduler-btn scheduler-btn-primary" onclick="runSchedulerJobNow('${job.id}')" ${!isEnabled ? 'disabled' : ''}>
                                Run Now
                            </button>
                            <button class="scheduler-btn scheduler-btn-secondary" onclick="toggleSchedulerJob('${job.id}', ${isEnabled})">
                                ${isEnabled ? 'Disable' : 'Enable'}
                            </button>
                            <button class="scheduler-btn scheduler-btn-secondary" onclick="editSchedulerJob('${job.id}')">
                                Edit
                            </button>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
        } else {
            html += '<p style="text-align: center; color: var(--text-secondary); padding: 20px;">No scheduled jobs found</p>';
        }
        
        // Add Quick Actions section
        html += `
            <div style="margin-top: 2rem; padding: 1.5rem; background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-lg);">
                <h3 class="scheduler-section-title">Quick Actions</h3>
                <div style="display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 1rem;">
                    <button class="scheduler-btn scheduler-btn-secondary" onclick="clearSchedulerHistory()" style="flex: 1; min-width: 200px;">
                        Clear Execution History
                    </button>
                    <button class="scheduler-btn scheduler-btn-secondary" onclick="reloadSchedulerConfig()" style="flex: 1; min-width: 200px;">
                        Reload Configuration
                    </button>
                </div>
            </div>
        `;
        
        container.innerHTML = html;
        
        // Add styles if not already added
        addSchedulerStyles();
    } catch (error) {
        console.error('Error rendering scheduler content:', error);
        container.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 40px 20px;">Error rendering scheduler</p>';
    }
}

// Toggle scheduler job
function toggleSchedulerJob(jobId, currentlyEnabled) {
    try {
        const newStatus = !currentlyEnabled;
        const action = newStatus ? 'enable' : 'disable';
        
        fetch(`/admin/api/scheduler/toggle/${jobId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled: newStatus })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(`Job ${action}d successfully`, 'success');
                // Reload scheduler content to reflect changes
                schedulerLoaded = false;
                loadSchedulerContent();
            } else {
                showNotification(`Error ${action}ing job: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification(`Error ${action}ing job`, 'error');
        });
    } catch (error) {
        console.error('Error in toggleSchedulerJob:', error);
    }
}

// Run scheduler job now
function runSchedulerJobNow(jobId) {
    try {
        const button = event.target;
        const originalText = button.innerHTML;
        button.innerHTML = '⏳ Running...';
        button.disabled = true;
        
        fetch(`/admin/api/scheduler/run-now/${jobId}`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('Job started successfully', 'success');
                // Reload scheduler content after a delay
                setTimeout(() => {
                    schedulerLoaded = false;
                    loadSchedulerContent();
                }, 2000);
            } else {
                showNotification(`Error running job: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error running job', 'error');
        })
        .finally(() => {
            button.innerHTML = originalText;
            button.disabled = false;
        });
    } catch (error) {
        console.error('Error in runSchedulerJobNow:', error);
    }
}

// View scheduler job history (deprecated - history now shown in same tab)
function viewSchedulerHistory(jobId) {
    try {
        // This function is deprecated - history is now shown in the same scheduler tab
        console.log('History view for job:', jobId);
    } catch (error) {
        console.error('Error in viewSchedulerHistory:', error);
    }
}

// Clear all execution history
function clearSchedulerHistory() {
    try {
        if (!confirm('Clear all execution history? This will permanently delete all logs from the database.')) return;
        
        fetch('/admin/api/scheduler/clear-history', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('Execution history cleared successfully', 'success');
                // Reload scheduler content after a delay
                setTimeout(() => {
                    schedulerLoaded = false;
                    loadSchedulerContent();
                }, 1000);
            } else {
                showNotification(`Error clearing history: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error clearing history', 'error');
        });
    } catch (error) {
        console.error('Error in clearSchedulerHistory:', error);
    }
}

// Reload scheduler configuration
function reloadSchedulerConfig() {
    try {
        if (!confirm('Reload scheduler configuration? This will restart all scheduled jobs.')) return;
        
        fetch('/admin/api/scheduler/reload', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('Scheduler configuration reloaded successfully', 'success');
                // Reload scheduler content after a delay
                setTimeout(() => {
                    schedulerLoaded = false;
                    loadSchedulerContent();
                }, 1500);
            } else {
                showNotification(`Error reloading configuration: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error reloading configuration', 'error');
        });
    } catch (error) {
        console.error('Error in reloadSchedulerConfig:', error);
    }
}

// Load all scheduler history
function loadSchedulerHistory() {
    try {
        const historyContent = document.getElementById('scheduler-history-content');
        if (!historyContent) return;
        
        // Show loading state
        historyContent.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 40px 20px;">Loading execution history...</p>';
        
        // Fetch all history - use correct endpoint without job_id filter
        fetch('/admin/api/scheduler/history')
            .then(response => {
                // Check if response is ok
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                // Check content type
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    throw new Error('Response is not JSON');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Convert executions array to history object format
                    const historyData = {};
                    const executions = data.executions || [];
                    
                    executions.forEach(exec => {
                        const jobId = exec.job_id || 'unknown';
                        if (!historyData[jobId]) {
                            historyData[jobId] = [];
                        }
                        historyData[jobId].push(exec);
                    });
                    
                    renderAllSchedulerHistory(historyData, historyContent);
                    schedulerHistoryLoaded = true;
                } else {
                    historyContent.innerHTML = `<p style="text-align: center; color: var(--text-secondary); padding: 40px 20px;">Error loading history: ${data.error || 'Unknown error'}</p>`;
                }
            })
            .catch(error => {
                console.error('Error loading scheduler history:', error);
                historyContent.innerHTML = `<p style="text-align: center; color: var(--text-secondary); padding: 40px 20px;">Error loading history: ${error.message}</p>`;
            });
    } catch (error) {
        console.error('Error in loadSchedulerHistory:', error);
    }
}

// Render all scheduler history in a single table
function renderAllSchedulerHistory(historyData, container) {
    try {
        let html = `
            <div class="scheduler-history-container">
                <div class="scheduler-history-filters">
                    <div class="filter-group">
                        <label for="historyJobFilter">Filter by Job:</label>
                        <select id="historyJobFilter" class="scheduler-form-control" onchange="filterSchedulerHistory()" style="max-width: 300px;">
                            <option value="">All Jobs</option>
        `;
        
        // Get unique job IDs
        const jobIds = new Set();
        Object.keys(historyData).forEach(jobId => {
            jobIds.add(jobId);
        });
        
        jobIds.forEach(jobId => {
            html += `<option value="${jobId}">${jobId}</option>`;
        });
        
        html += `
                        </select>
                    </div>
                    <div class="filter-group">
                        <label for="historyStatusFilter">Filter by Status:</label>
                        <select id="historyStatusFilter" class="scheduler-form-control" onchange="filterSchedulerHistory()" style="max-width: 200px;">
                            <option value="">All Status</option>
                            <option value="success">Success</option>
                            <option value="failed">Failed</option>
                            <option value="running">Running</option>
                        </select>
                    </div>
                </div>
                
                <div id="scheduler-history-table-container" class="scheduler-history-table-container">
        `;
        
        // Build history table
        if (Object.keys(historyData).length > 0) {
            html += `
                <table class="scheduler-history-table">
                    <thead>
                        <tr>
                            <th>Job ID</th>
                            <th>Status</th>
                            <th>Started At</th>
                            <th>Duration</th>
                            <th>Records</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody id="scheduler-history-tbody">
            `;
            
            // Flatten and sort all executions
            const allExecutions = [];
            Object.entries(historyData).forEach(([jobId, executions]) => {
                if (Array.isArray(executions)) {
                    executions.forEach(exec => {
                        allExecutions.push({
                            jobId: jobId,
                            ...exec
                        });
                    });
                }
            });
            
            // Sort by started_at descending
            allExecutions.sort((a, b) => {
                const dateA = new Date(a.started_at || 0);
                const dateB = new Date(b.started_at || 0);
                return dateB - dateA;
            });
            
            // Display executions
            allExecutions.forEach(exec => {
                const statusColor = exec.status === 'success' ? '#10b981' : exec.status === 'failed' ? '#ef4444' : '#f59e0b';
                const startedAt = new Date(exec.started_at).toLocaleString();
                const duration = exec.duration_display || formatDuration(exec.duration_seconds);
                const records = exec.records_processed || '-';
                const details = exec.error_message || exec.details || '-';
                
                html += `
                    <tr class="history-row" data-job-id="${exec.jobId}" data-status="${exec.status}">
                        <td class="job-id-cell">${exec.jobId}</td>
                        <td class="status-cell">
                            <span class="status-badge status-${exec.status}">
                                ${exec.status}
                            </span>
                        </td>
                        <td class="date-cell">${startedAt}</td>
                        <td class="duration-cell">${duration}</td>
                        <td class="records-cell">${records}</td>
                        <td class="details-cell" title="${details}">${details}</td>
                    </tr>
                `;
            });
            
            html += `
                    </tbody>
                </table>
            `;
        } else {
            html += `<p style="text-align: center; color: var(--text-secondary); padding: 20px;">No execution history found</p>`;
        }
        
        html += `
                </div>
            </div>
        `;
        
        container.innerHTML = html;
        addSchedulerHistoryStyles();
    } catch (error) {
        console.error('Error rendering scheduler history:', error);
        container.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 40px 20px;">Error rendering history</p>';
    }
}

// Display specific job history
function displayJobHistory(jobId, executions) {
    try {
        const container = document.getElementById('scheduler-history-content');
        if (!container) return;
        
        let html = `
            <div class="scheduler-history-container">
                <div class="scheduler-history-header">
                    <h3 style="margin: 0; color: var(--text-primary);">Job: ${jobId}</h3>
                    <button class="scheduler-btn scheduler-btn-secondary" onclick="loadSchedulerHistory()" style="margin-left: auto;">
                        ← Back to All History
                    </button>
                </div>
                
                <div class="scheduler-history-table-container">
        `;
        
        if (executions && executions.length > 0) {
            html += `
                <table class="scheduler-history-table">
                    <thead>
                        <tr>
                            <th>Status</th>
                            <th>Started At</th>
                            <th>Duration</th>
                            <th>Records</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            executions.forEach(exec => {
                const statusColor = exec.status === 'success' ? '#10b981' : exec.status === 'failed' ? '#ef4444' : '#f59e0b';
                const startedAt = new Date(exec.started_at).toLocaleString();
                const duration = exec.duration_display || formatDuration(exec.duration_seconds);
                const records = exec.records_processed || '-';
                const details = exec.error_message || exec.details || '-';
                
                html += `
                    <tr>
                        <td class="status-cell">
                            <span class="status-badge status-${exec.status}">
                                ${exec.status}
                            </span>
                        </td>
                        <td class="date-cell">${startedAt}</td>
                        <td class="duration-cell">${duration}</td>
                        <td class="records-cell">${records}</td>
                        <td class="details-cell" title="${details}">${details}</td>
                    </tr>
                `;
            });
            
            html += `
                    </tbody>
                </table>
            `;
        } else {
            html += `<p style="text-align: center; color: var(--text-secondary); padding: 20px;">No execution history found for this job</p>`;
        }
        
        html += `
                </div>
            </div>
        `;
        
        container.innerHTML = html;
        addSchedulerHistoryStyles();
    } catch (error) {
        console.error('Error displaying job history:', error);
    }
}

// Filter scheduler history
function filterSchedulerHistory() {
    try {
        const jobFilter = document.getElementById('historyJobFilter').value;
        const statusFilter = document.getElementById('historyStatusFilter').value;
        const rows = document.querySelectorAll('.history-row');
        
        rows.forEach(row => {
            const jobId = row.getAttribute('data-job-id');
            const status = row.getAttribute('data-status');
            
            const jobMatch = !jobFilter || jobId === jobFilter;
            const statusMatch = !statusFilter || status === statusFilter;
            
            row.style.display = (jobMatch && statusMatch) ? '' : 'none';
        });
    } catch (error) {
        console.error('Error filtering history:', error);
    }
}

// Show history modal (kept for backward compatibility, but not used)
function showHistoryModal(jobId, executions) {
    try {
        let historyHtml = `
            <div id="scheduler-history-modal" class="scheduler-modal active">
                <div class="scheduler-modal-content" style="max-width: 800px;">
                    <div class="scheduler-modal-header">
                        <h2>Execution History - ${jobId}</h2>
                        <button class="scheduler-modal-close" onclick="closeHistoryModal()">&times;</button>
                    </div>
                    <div class="scheduler-modal-body">
        `;
        
        if (executions && executions.length > 0) {
            historyHtml += `
                <table style="width: 100%; border-collapse: collapse; font-size: 0.875rem;">
                    <thead>
                        <tr style="border-bottom: 2px solid var(--border-color);">
                            <th style="text-align: left; padding: 0.75rem; color: var(--text-secondary); font-weight: 600;">Status</th>
                            <th style="text-align: left; padding: 0.75rem; color: var(--text-secondary); font-weight: 600;">Started</th>
                            <th style="text-align: left; padding: 0.75rem; color: var(--text-secondary); font-weight: 600;">Duration</th>
                            <th style="text-align: left; padding: 0.75rem; color: var(--text-secondary); font-weight: 600;">Records</th>
                            <th style="text-align: left; padding: 0.75rem; color: var(--text-secondary); font-weight: 600;">Details</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            executions.forEach(exec => {
                const statusColor = exec.status === 'success' ? '#10b981' : exec.status === 'failed' ? '#ef4444' : '#f59e0b';
                const startedAt = new Date(exec.started_at).toLocaleString();
                const duration = exec.duration_display || formatDuration(exec.duration_seconds);
                const records = exec.records_processed || '-';
                const details = exec.error_message || exec.details || '-';
                
                historyHtml += `
                    <tr style="border-bottom: 1px solid var(--border-color);">
                        <td style="padding: 0.75rem;">
                            <span style="display: inline-block; padding: 4px 8px; border-radius: 4px; background: rgba(${statusColor === '#10b981' ? '16, 185, 129' : statusColor === '#ef4444' ? '239, 68, 68' : '245, 158, 11'}, 0.1); color: ${statusColor}; font-weight: 600; font-size: 0.7rem; text-transform: uppercase;">
                                ${exec.status}
                            </span>
                        </td>
                        <td style="padding: 0.75rem; color: var(--text-primary);">${startedAt}</td>
                        <td style="padding: 0.75rem; color: var(--text-primary);">${duration}</td>
                        <td style="padding: 0.75rem; color: var(--text-primary);">${records}</td>
                        <td style="padding: 0.75rem; color: var(--text-secondary); max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${details}">${details}</td>
                    </tr>
                `;
            });
            
            historyHtml += `
                    </tbody>
                </table>
            `;
        } else {
            historyHtml += `<p style="text-align: center; color: var(--text-secondary); padding: 20px;">No execution history found</p>`;
        }
        
        historyHtml += `
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if any
        const existingModal = document.getElementById('scheduler-history-modal');
        if (existingModal) existingModal.remove();
        
        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', historyHtml);
        
        // Add modal styles if not already added
        addSchedulerModalStyles();
        
        // Add click handler to close modal when clicking backdrop
        const modal = document.getElementById('scheduler-history-modal');
        if (modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === modal) {
                    closeHistoryModal();
                }
            });
        }
    } catch (error) {
        console.error('Error in showHistoryModal:', error);
    }
}

// Close history modal
function closeHistoryModal() {
    const modal = document.getElementById('scheduler-history-modal');
    if (modal) {
        modal.classList.remove('active');
        setTimeout(() => modal.remove(), 300);
    }
}

// Format duration helper
function formatDuration(seconds) {
    if (!seconds) return '-';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h`;
}

// Show notification
function showNotification(message, type = 'success') {
    try {
        const container = document.getElementById('flashMessages') || createFlashContainer();
        const notification = document.createElement('div');
        notification.className = `flash-message ${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            padding: 12px 20px;
            border-radius: 8px;
            margin-bottom: 10px;
            font-size: 0.875rem;
            animation: slideIn 0.3s ease;
            background: ${type === 'success' ? 'rgba(16, 185, 129, 0.9)' : 'rgba(239, 68, 68, 0.9)'};
            color: white;
        `;
        container.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 5000);
    } catch (error) {
        console.error('Error showing notification:', error);
    }
}

// Create flash container if it doesn't exist
function createFlashContainer() {
    let container = document.getElementById('flashMessages');
    if (!container) {
        container = document.createElement('div');
        container.id = 'flashMessages';
        container.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            z-index: 1001;
        `;
        document.body.appendChild(container);
    }
    return container;
}

// Add scheduler styles
function addSchedulerStyles() {
    if (document.getElementById('scheduler-settings-styles')) return;
    
    const styles = document.createElement('style');
    styles.id = 'scheduler-settings-styles';
    styles.textContent = `
        .scheduler-status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        
        .scheduler-status-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-large);
            padding: 1.25rem;
            display: flex;
            align-items: center;
            gap: 1rem;
            transition: all 0.3s ease;
        }
        
        .scheduler-status-card:hover {
            box-shadow: var(--shadow-medium);
            transform: translateY(-2px);
        }
        
        .scheduler-status-icon {
            width: 48px;
            height: 48px;
            border-radius: var(--radius);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            font-weight: bold;
        }
        
        .scheduler-status-icon.running {
            background: rgba(16, 185, 129, 0.1);
            color: #10b981;
        }
        
        .scheduler-status-icon.stopped {
            background: rgba(239, 68, 68, 0.1);
            color: #ef4444;
        }
        
        .scheduler-status-icon.jobs {
            background: rgba(163, 16, 16, 0.1);
            color: var(--accent-color);
        }
        
        .scheduler-status-icon.success {
            background: rgba(16, 185, 129, 0.1);
            color: #10b981;
        }
        
        .scheduler-status-icon.failed {
            background: rgba(239, 68, 68, 0.1);
            color: #ef4444;
        }
        
        .scheduler-status-info h3 {
            font-size: 0.8rem;
            font-weight: 500;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin: 0;
        }
        
        .scheduler-status-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        
        .scheduler-section-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border-color);
        }
        
        .scheduler-jobs-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        
        .scheduler-job-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-large);
            padding: 1.5rem;
            transition: all 0.3s ease;
        }
        
        .scheduler-job-card:hover {
            box-shadow: var(--shadow-medium);
            transform: translateY(-2px);
        }
        
        .scheduler-job-card[data-disabled="true"] {
            opacity: 0.6;
            background: var(--bg-tertiary);
        }
        
        .scheduler-job-card[data-disabled="true"]:hover {
            transform: none;
            box-shadow: none;
        }
        
        .scheduler-job-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1rem;
        }
        
        .scheduler-job-title {
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .scheduler-job-type {
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 2px;
        }
        
        .scheduler-job-status {
            display: flex;
            align-items: center;
        }
        
        .scheduler-badge {
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .scheduler-badge.enabled {
            background: rgba(16, 185, 129, 0.1);
            color: #10b981;
        }
        
        .scheduler-badge.disabled {
            background: rgba(107, 114, 128, 0.1);
            color: var(--text-secondary);
        }
        
        .scheduler-job-details {
            margin-bottom: 1rem;
        }
        
        .scheduler-job-detail-row {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.875rem;
        }
        
        .scheduler-job-detail-row:last-child {
            border-bottom: none;
        }
        
        .scheduler-job-detail-label {
            color: var(--text-secondary);
        }
        
        .scheduler-job-detail-value {
            color: var(--text-primary);
            font-weight: 500;
        }
        
        .scheduler-job-actions {
            display: flex;
            gap: 0.5rem;
            margin-top: 1rem;
        }
        
        .scheduler-btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 16px;
            border-radius: var(--radius);
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            border: none;
            transition: all 0.2s ease;
            flex: 1;
            justify-content: center;
        }
        
        .scheduler-btn-primary {
            background: var(--accent-color);
            color: white;
        }
        
        .scheduler-btn-primary:hover {
            background: var(--accent-hover);
            transform: translateY(-1px);
            box-shadow: var(--shadow-light);
        }
        
        .scheduler-btn-secondary {
            background: var(--bg-tertiary);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
        }
        
        .scheduler-btn-secondary:hover {
            background: var(--border-color);
            transform: translateY(-1px);
        }
        
        .scheduler-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        /* Scheduler History Styles */
        .scheduler-history-container {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-large);
            padding: 1.5rem;
        }
        
        .scheduler-history-filters {
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
        }
        
        .filter-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        
        .filter-group label {
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--text-secondary);
        }
        
        .scheduler-history-header {
            display: flex;
            align-items: center;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
        }
        
        .scheduler-history-table-container {
            overflow-x: auto;
        }
        
        .scheduler-history-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }
        
        .scheduler-history-table thead {
            background: var(--bg-tertiary);
        }
        
        .scheduler-history-table th {
            text-align: left;
            padding: 0.75rem;
            color: var(--text-secondary);
            font-weight: 600;
            border-bottom: 2px solid var(--border-color);
        }
        
        .scheduler-history-table td {
            padding: 0.75rem;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-primary);
        }
        
        .scheduler-history-table tbody tr:hover {
            background: var(--bg-tertiary);
        }
        
        .status-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.7rem;
            text-transform: uppercase;
        }
        
        .status-badge.status-success {
            background: rgba(16, 185, 129, 0.1);
            color: #10b981;
        }
        
        .status-badge.status-failed {
            background: rgba(239, 68, 68, 0.1);
            color: #ef4444;
        }
        
        .status-badge.status-running {
            background: rgba(245, 158, 11, 0.1);
            color: #f59e0b;
        }
        
        .job-id-cell {
            font-weight: 500;
            color: var(--accent-color);
        }
        
        .date-cell {
            white-space: nowrap;
        }
        
        .duration-cell {
            text-align: center;
        }
        
        .records-cell {
            text-align: center;
        }
        
        .details-cell {
            max-width: 250px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: var(--text-secondary);
        }
    `;
    
    document.head.appendChild(styles);
}

// Add scheduler history styles
function addSchedulerHistoryStyles() {
    if (document.getElementById('scheduler-history-styles')) return;
    
    const styles = document.createElement('style');
    styles.id = 'scheduler-history-styles';
    styles.textContent = `
        .scheduler-history-container {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-large);
            padding: 1.5rem;
        }
        
        .scheduler-history-filters {
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
        }
        
        .filter-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        
        .filter-group label {
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--text-secondary);
        }
        
        .scheduler-history-header {
            display: flex;
            align-items: center;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
        }
        
        .scheduler-history-table-container {
            overflow-x: auto;
        }
        
        .scheduler-history-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }
        
        .scheduler-history-table thead {
            background: var(--bg-tertiary);
        }
        
        .scheduler-history-table th {
            text-align: left;
            padding: 0.75rem;
            color: var(--text-secondary);
            font-weight: 600;
            border-bottom: 2px solid var(--border-color);
        }
        
        .scheduler-history-table td {
            padding: 0.75rem;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-primary);
        }
        
        .scheduler-history-table tbody tr:hover {
            background: var(--bg-tertiary);
        }
        
        .status-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.7rem;
            text-transform: uppercase;
        }
        
        .status-badge.status-success {
            background: rgba(16, 185, 129, 0.1);
            color: #10b981;
        }
        
        .status-badge.status-failed {
            background: rgba(239, 68, 68, 0.1);
            color: #ef4444;
        }
        
        .status-badge.status-running {
            background: rgba(245, 158, 11, 0.1);
            color: #f59e0b;
        }
        
        .job-id-cell {
            font-weight: 500;
            color: var(--accent-color);
        }
        
        .date-cell {
            white-space: nowrap;
        }
        
        .duration-cell {
            text-align: center;
        }
        
        .records-cell {
            text-align: center;
        }
        
        .details-cell {
            max-width: 250px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: var(--text-secondary);
        }
    `;
    
    document.head.appendChild(styles);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Scheduler settings integration loaded');
});


// Edit scheduler job
function editSchedulerJob(jobId) {
    try {
        // Fetch job configuration
        fetch(`/admin/api/scheduler/job-config/${jobId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showEditModal(jobId, data.config);
                } else {
                    showNotification(`Error loading job config: ${data.error}`, 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Error loading job configuration', 'error');
            });
    } catch (error) {
        console.error('Error in editSchedulerJob:', error);
    }
}

// Show edit modal
function showEditModal(jobId, config) {
    try {
        // Create modal HTML
        const modalHtml = `
            <div id="scheduler-edit-modal" class="scheduler-modal active">
                <div class="scheduler-modal-content">
                    <div class="scheduler-modal-header">
                        <h2>Edit Schedule - ${jobId}</h2>
                        <button class="scheduler-modal-close" onclick="closeEditModal()">&times;</button>
                    </div>
                    <div class="scheduler-modal-body">
                        <form id="scheduler-edit-form" onsubmit="saveSchedulerJob(event, '${jobId}')">
                            <input type="hidden" id="scheduler-job-id" value="${jobId}">
                            
                            <div class="scheduler-form-group">
                                <label for="scheduler-frequency">Frequency</label>
                                <select id="scheduler-frequency" name="frequency" class="scheduler-form-control" onchange="updateSchedulerFields()" required>
                                    <option value="daily" ${config.frequency === 'daily' ? 'selected' : ''}>Daily</option>
                                    <option value="weekly" ${config.frequency === 'weekly' ? 'selected' : ''}>Weekly</option>
                                    <option value="monthly" ${config.frequency === 'monthly' ? 'selected' : ''}>Monthly</option>
                                </select>
                            </div>

                            <div class="scheduler-form-group" id="scheduler-day-of-week-group" style="display: ${config.frequency === 'weekly' ? 'block' : 'none'};">
                                <label for="scheduler-day-of-week">Day of Week</label>
                                <select id="scheduler-day-of-week" name="day_of_week" class="scheduler-form-control">
                                    <option value="monday" ${config.day_of_week === 'monday' ? 'selected' : ''}>Monday</option>
                                    <option value="tuesday" ${config.day_of_week === 'tuesday' ? 'selected' : ''}>Tuesday</option>
                                    <option value="wednesday" ${config.day_of_week === 'wednesday' ? 'selected' : ''}>Wednesday</option>
                                    <option value="thursday" ${config.day_of_week === 'thursday' ? 'selected' : ''}>Thursday</option>
                                    <option value="friday" ${config.day_of_week === 'friday' ? 'selected' : ''}>Friday</option>
                                    <option value="saturday" ${config.day_of_week === 'saturday' ? 'selected' : ''}>Saturday</option>
                                    <option value="sunday" ${config.day_of_week === 'sunday' ? 'selected' : ''}>Sunday</option>
                                </select>
                            </div>

                            <div class="scheduler-form-group" id="scheduler-day-of-month-group" style="display: ${config.frequency === 'monthly' ? 'block' : 'none'};">
                                <label for="scheduler-day-of-month">Day of Month (1-31)</label>
                                <input type="number" id="scheduler-day-of-month" name="day_of_month" class="scheduler-form-control" min="1" max="31" value="${config.day_of_month || 1}">
                            </div>

                            <div class="scheduler-form-group">
                                <label for="scheduler-time">Time (24-hour format)</label>
                                <input type="time" id="scheduler-time" name="time" class="scheduler-form-control" value="${config.time || '00:00'}" required>
                            </div>

                            <div class="scheduler-form-group" id="scheduler-max-posts-group" style="display: ${config.max_posts ? 'block' : 'none'};">
                                <label for="scheduler-max-posts">Maximum Posts per Execution</label>
                                <input type="number" id="scheduler-max-posts" name="max_posts" class="scheduler-form-control" min="100" max="50000" step="100" value="${config.max_posts || 1000}" onchange="updateSchedulerCostEstimate()">
                                <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem;">
                                    Number of posts to scrape per run (100-50000)
                                </div>
                            </div>

                            <div class="scheduler-form-group">
                                <div id="scheduler-cost-estimate" style="padding: 0.75rem; background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: var(--radius); display: none;">
                                    <div style="font-size: 0.8rem; font-weight: 600; color: var(--text-secondary); margin-bottom: 0.5rem;">Estimated Cost</div>
                                    <div style="font-size: 1.1rem; font-weight: 700; color: var(--accent-color);" id="scheduler-cost-value">-</div>
                                    <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem;" id="scheduler-cost-details">Based on average data volume</div>
                                </div>
                            </div>

                            <div class="scheduler-form-group">
                                <label class="scheduler-checkbox-label">
                                    <input type="checkbox" id="scheduler-job-enabled" name="enabled" ${config.enabled !== false ? 'checked' : ''}>
                                    <span>Enabled</span>
                                </label>
                            </div>

                            <div class="scheduler-modal-actions">
                                <button type="button" class="scheduler-btn scheduler-btn-secondary" onclick="closeEditModal()">Cancel</button>
                                <button type="submit" class="scheduler-btn scheduler-btn-primary">Save Schedule</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal if any
        const existingModal = document.getElementById('scheduler-edit-modal');
        if (existingModal) existingModal.remove();

        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Add modal styles if not already added
        addSchedulerModalStyles();
        
        // Add click handler to close modal when clicking backdrop
        const modal = document.getElementById('scheduler-edit-modal');
        if (modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === modal) {
                    closeEditModal();
                }
            });
        }
        
        // Update field visibility and cost estimate
        setTimeout(() => {
            updateSchedulerFields();
            updateSchedulerCostEstimate();
        }, 100);
    } catch (error) {
        console.error('Error in showEditModal:', error);
    }
}

// Close edit modal
function closeEditModal() {
    const modal = document.getElementById('scheduler-edit-modal');
    if (modal) {
        modal.classList.remove('active');
        setTimeout(() => modal.remove(), 300);
    }
}

// Update scheduler fields based on frequency
function updateSchedulerFields() {
    const frequency = document.getElementById('scheduler-frequency').value;
    const jobId = document.getElementById('scheduler-job-id').value;
    const jobType = jobId ? jobId.split('_')[0] : null;

    const dayOfWeekGroup = document.getElementById('scheduler-day-of-week-group');
    const dayOfMonthGroup = document.getElementById('scheduler-day-of-month-group');
    const maxPostsGroup = document.getElementById('scheduler-max-posts-group');

    // Hide all conditional fields
    dayOfWeekGroup.style.display = 'none';
    dayOfMonthGroup.style.display = 'none';

    // Show relevant field based on frequency
    if (frequency === 'weekly') {
        dayOfWeekGroup.style.display = 'block';
    } else if (frequency === 'monthly') {
        dayOfMonthGroup.style.display = 'block';
    }

    // Show max_posts field only for pakwheels and reddit
    if (jobType === 'pakwheels' || jobType === 'reddit') {
        maxPostsGroup.style.display = 'block';
    } else {
        maxPostsGroup.style.display = 'none';
    }

    // Update cost estimate when frequency changes
    updateSchedulerCostEstimate();
}

// Cost estimation data for each data source and frequency
const costEstimates = {
    pakwheels: {
        daily: { min: 0.4, max: 0.6, unit: 'day' },
        weekly: { min: 1.0, max: 1.5, unit: 'week' },
        monthly: { min: 2.0, max: 3.0, unit: 'month' }
    },
    reddit: {
        daily: { min: 0.4, max: 0.6, unit: 'day' },
        weekly: { min: 1.0, max: 1.5, unit: 'week' },
        monthly: { min: 2.0, max: 3.0, unit: 'month' }
    },
    wati: {
        daily: { min: 0.4, max: 0.6, unit: 'day' },
        weekly: { min: 1.0, max: 1.5, unit: 'week' },
        monthly: { min: 2.0, max: 3.0, unit: 'month' }
    }
};

// Update cost estimate
function updateSchedulerCostEstimate() {
    const jobId = document.getElementById('scheduler-job-id').value;
    const frequency = document.getElementById('scheduler-frequency').value;

    // Extract job type from job_id (e.g., 'pakwheels_haval' -> 'pakwheels')
    const jobType = jobId ? jobId.split('_')[0] : null;

    const costEstimateDiv = document.getElementById('scheduler-cost-estimate');
    const costValue = document.getElementById('scheduler-cost-value');
    const costDetails = document.getElementById('scheduler-cost-details');

    if (jobType && costEstimates[jobType] && costEstimates[jobType][frequency]) {
        const baseCost = costEstimates[jobType][frequency];

        // Get max_posts value (only for pakwheels and reddit)
        let costMultiplier = 1.0;
        if (jobType === 'pakwheels' || jobType === 'reddit') {
            const maxPostsInput = document.getElementById('scheduler-max-posts');
            const maxPosts = parseInt(maxPostsInput.value) || 1000;

            // Calculate cost multiplier based on max_posts
            // Base: 1000 posts = 1x, 10000 posts = 3x, linear scaling
            if (maxPosts <= 1000) {
                costMultiplier = 1.0;
            } else if (maxPosts >= 10000) {
                costMultiplier = 3.0;
            } else {
                // Linear interpolation: 1x at 1000, 3x at 10000
                costMultiplier = 1 + ((maxPosts - 1000) / 9000) * 2;
            }
        }

        // Apply multiplier to base costs
        const finalMinCost = baseCost.min * costMultiplier;
        const finalMaxCost = baseCost.max * costMultiplier;

        costValue.textContent = '$' + finalMinCost.toFixed(2) + ' - $' + finalMaxCost.toFixed(2) + ' USD / ' + baseCost.unit;

        // Professional note with details
        let details = '';
        if (jobType === 'wati') {
            details = 'Estimated for ~400 conversations';
        } else if (jobType === 'pakwheels' || jobType === 'reddit') {
            const maxPosts = parseInt(document.getElementById('scheduler-max-posts').value) || 1000;
            details = 'Based on ' + maxPosts.toLocaleString() + ' posts per execution. ';
            details += 'Note: Costs depend on new discussions in forums. ';
            details += 'Duplicate or previously processed discussions are automatically filtered and won\'t be re-ingested.';
        }
        costDetails.textContent = details;

        costEstimateDiv.style.display = 'block';
    } else {
        costEstimateDiv.style.display = 'none';
    }
}

// Save scheduler job
function saveSchedulerJob(event, jobId) {
    event.preventDefault();
    
    try {
        const form = document.getElementById('scheduler-edit-form');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);
        data.enabled = document.getElementById('scheduler-job-enabled').checked;

        const button = event.target.querySelector('button[type="submit"]');
        const originalText = button.innerHTML;
        button.innerHTML = 'Saving...';
        button.disabled = true;

        fetch(`/admin/api/scheduler/update-schedule/${jobId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('Schedule saved successfully', 'success');
                closeEditModal();
                // Reload scheduler content
                schedulerLoaded = false;
                loadSchedulerContent();
            } else {
                showNotification(`Error saving schedule: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error saving schedule', 'error');
        })
        .finally(() => {
            button.innerHTML = originalText;
            button.disabled = false;
        });
    } catch (error) {
        console.error('Error in saveSchedulerJob:', error);
    }
}

// Add modal styles
function addSchedulerModalStyles() {
    if (document.getElementById('scheduler-modal-styles')) return;
    
    const styles = document.createElement('style');
    styles.id = 'scheduler-modal-styles';
    styles.textContent = `
        .scheduler-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            z-index: 3000;
            align-items: center;
            justify-content: center;
        }

        .scheduler-modal.active {
            display: flex;
        }

        .scheduler-modal-content {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-large);
            max-width: 500px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            animation: schedulerModalSlideIn 0.3s ease;
        }

        @keyframes schedulerModalSlideIn {
            from {
                opacity: 0;
                transform: translateY(-50px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .scheduler-modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.5rem;
            border-bottom: 1px solid var(--border-color);
        }

        .scheduler-modal-header h2 {
            margin: 0;
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary);
        }

        .scheduler-modal-close {
            background: none;
            border: none;
            font-size: 2rem;
            color: var(--text-secondary);
            cursor: pointer;
            line-height: 1;
            padding: 0;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: var(--radius);
            transition: all 0.2s ease;
        }

        .scheduler-modal-close:hover {
            background: var(--border-color);
            color: var(--text-primary);
        }

        .scheduler-modal-body {
            padding: 1.5rem;
        }

        .scheduler-form-group {
            margin-bottom: 1.25rem;
        }

        .scheduler-form-group label {
            display: block;
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--text-primary);
            margin-bottom: 0.5rem;
        }

        .scheduler-form-control {
            width: 100%;
            padding: 0.625rem;
            font-size: 0.875rem;
            color: var(--text-primary);
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            font-family: 'Inter', sans-serif;
            transition: all 0.2s ease;
        }

        .scheduler-form-control:focus {
            outline: none;
            border-color: var(--accent-color);
            background: var(--bg-secondary);
        }

        .scheduler-checkbox-label {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            cursor: pointer;
            font-size: 0.875rem;
            color: var(--text-primary);
        }

        .scheduler-checkbox-label input[type="checkbox"] {
            width: 18px;
            height: 18px;
            cursor: pointer;
        }

        .scheduler-modal-actions {
            display: flex;
            gap: 0.75rem;
            justify-content: flex-end;
            margin-top: 1.5rem;
        }
    `;
    
    document.head.appendChild(styles);
}
