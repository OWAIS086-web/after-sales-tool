// WhatsApp Analytics Dashboard JavaScript

console.log('=== WHATSAPP ANALYTICS.JS LOADED ===');

// Global variables
let charts = {};
let currentTimePeriod = '7d';

// Change time period
function changeTimePeriod(period) {
    console.log('Changing time period to:', period);
    currentTimePeriod = period;
    
    // Update active button
    document.querySelectorAll('.time-period-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('data-period') === period) {
            btn.classList.add('active');
        }
    });
    
    // Reload data with new time period
    loadWhatsAppAnalytics();
}

// Initialize WhatsApp analytics dashboard
function initializeWhatsAppAnalytics() {
    console.log('Initializing WhatsApp analytics dashboard...');
    
    // Check if Chart.js is loaded
    if (typeof Chart === 'undefined') {
        console.error('Chart.js not loaded yet, retrying...');
        setTimeout(initializeWhatsAppAnalytics, 100);
        return;
    }
    
    // Initialize charts
    initializeCharts();
    
    // Load WhatsApp analytics data
    loadWhatsAppAnalytics();
    
    console.log('WhatsApp analytics dashboard initialized');
}

// Load WhatsApp analytics data
function loadWhatsAppAnalytics() {
    console.log('Loading WhatsApp analytics data...');
    
    showLoadingState();
    
    fetch(`/api/analytics/source?source=whatsapp&period=${currentTimePeriod}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Received WhatsApp data:', data);
                
                // Update charts with real data
                updateCharts(data);
                
                // Load complaints data
                loadComplaintsData('whatsapp');
                
                // Load queries data
                loadQueriesData('whatsapp');
                
                console.log('WhatsApp analytics updated');
            } else {
                console.error('Failed to load WhatsApp analytics:', data.error);
                showErrorState(data.error);
            }
        })
        .catch(error => {
            console.error('Error fetching WhatsApp analytics:', error);
            showErrorState('Failed to load WhatsApp analytics');
        })
        .finally(() => {
            hideLoadingState();
        });
}

// Initialize charts
function initializeCharts() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const colors = getChartColors(isDark);
    
    // Activity Chart (Line Chart)
    createActivityChart(colors);
    
    // Message Types Chart (Doughnut Chart)
    createMessageTypesChart(colors);
}

// Get chart colors based on theme
function getChartColors(isDark) {
    return {
        text: isDark ? '#f0f0f0' : '#2d333a',
        textSecondary: isDark ? '#b8b8b8' : '#6e7681',
        grid: isDark ? '#3a3a3a' : '#e8eaed',
        background: isDark ? '#242424' : '#f8f9fa',
        primary: '#10b981',
        success: '#10b981',
        warning: '#f59e0b',
        info: '#3b82f6',
        error: '#ef4444'
    };
}

// Create activity chart
function createActivityChart(colors) {
    const canvas = document.getElementById('activityChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    charts.activity = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Messages',
                data: [],
                borderColor: colors.primary,
                backgroundColor: colors.primary + '20',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: colors.primary,
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 6,
                pointHoverRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: colors.background,
                    titleColor: colors.text,
                    bodyColor: colors.text,
                    borderColor: colors.primary,
                    borderWidth: 1,
                    cornerRadius: 8,
                    displayColors: false
                }
            },
            scales: {
                x: {
                    grid: {
                        color: colors.grid,
                        drawBorder: false
                    },
                    ticks: {
                        color: colors.textSecondary,
                        font: {
                            size: 12,
                            weight: '500'
                        }
                    }
                },
                y: {
                    grid: {
                        color: colors.grid,
                        drawBorder: false
                    },
                    ticks: {
                        color: colors.textSecondary,
                        font: {
                            size: 12,
                            weight: '500'
                        }
                    }
                }
            }
        }
    });
}

// Create message types chart
function createMessageTypesChart(colors) {
    const canvas = document.getElementById('conversionsChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    charts.messageTypes = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: [],
                borderWidth: 0,
                cutout: '60%'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: colors.background,
                    titleColor: colors.text,
                    bodyColor: colors.text,
                    borderColor: colors.primary,
                    borderWidth: 1,
                    cornerRadius: 8,
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: ${percentage}%`;
                        }
                    }
                }
            }
        }
    });
}

// Update charts with new data
function updateCharts(data) {
    // Update activity chart
    if (charts.activity) {
        charts.activity.data.labels = data.activityData.labels;
        charts.activity.data.datasets[0].data = data.activityData.data;
        charts.activity.update('active');
    }
    
    // Update message types chart
    if (charts.messageTypes) {
        charts.messageTypes.data.labels = data.conversionsData.labels;
        charts.messageTypes.data.datasets[0].data = data.conversionsData.data;
        charts.messageTypes.data.datasets[0].backgroundColor = data.conversionsData.colors;
        charts.messageTypes.update('active');
    }
}

// Download chart function
function downloadChart(chartId) {
    const chart = charts[chartId.replace('Chart', '')];
    if (!chart) return;
    
    const url = chart.toBase64Image();
    const link = document.createElement('a');
    link.download = `${chartId}_whatsapp_${new Date().toISOString().split('T')[0]}.png`;
    link.href = url;
    link.click();
}

// Theme change handler
function updateChartsTheme() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const colors = getChartColors(isDark);
    
    Object.values(charts).forEach(chart => {
        if (chart && chart.options) {
            // Update scales colors
            if (chart.options.scales) {
                if (chart.options.scales.x) {
                    chart.options.scales.x.ticks.color = colors.textSecondary;
                    chart.options.scales.x.grid.color = colors.grid;
                }
                if (chart.options.scales.y) {
                    chart.options.scales.y.ticks.color = colors.textSecondary;
                    chart.options.scales.y.grid.color = colors.grid;
                }
            }
            
            // Update tooltip colors
            if (chart.options.plugins && chart.options.plugins.tooltip) {
                chart.options.plugins.tooltip.backgroundColor = colors.background;
                chart.options.plugins.tooltip.titleColor = colors.text;
                chart.options.plugins.tooltip.bodyColor = colors.text;
            }
            
            chart.update('none');
        }
    });
}

// Listen for theme changes
const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
        if (mutation.type === 'attributes' && mutation.attributeName === 'data-theme') {
            setTimeout(updateChartsTheme, 100);
        }
    });
});

observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme']
});

// Export functions for global access
window.initializeWhatsAppAnalytics = initializeWhatsAppAnalytics;
window.downloadChart = downloadChart;
window.changeTimePeriod = changeTimePeriod;

console.log('WhatsApp Analytics JavaScript loaded successfully');

// Loading state functions
function showLoadingState() {
    console.log('Showing loading state');
}

function hideLoadingState() {
    console.log('Hiding loading state');
}

function showErrorState(error) {
    console.error('WhatsApp analytics error:', error);
}

// Load complaints data for the table
function loadComplaintsData(source) {
    fetch(`/api/analytics/complaints?source=${source}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateComplaintsTable(data.complaints);
                console.log('Complaints data loaded:', data.complaints.length, 'complaints');
            } else {
                console.error('Failed to load complaints data:', data.error);
                showComplaintsError();
            }
        })
        .catch(error => {
            console.error('Error fetching complaints data:', error);
            showComplaintsError();
        });
}

// Update complaints table
function updateComplaintsTable(complaints) {
    const tbody = document.getElementById('activity-table-body');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    if (complaints.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="4" style="text-align: center; padding: 20px; color: var(--text-secondary);">
                    No complaints found for this source
                </td>
            </tr>
        `;
        return;
    }
    
    // Show only first 10 complaints in main table
    const displayComplaints = complaints.slice(0, 10);
    
    displayComplaints.forEach(complaint => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>
                <div class="user-info">
                    <div class="user-avatar">${getInitials(complaint.user)}</div>
                    <span class="user-name">${complaint.user}</span>
                </div>
            </td>
            <td>
                <div class="complaint-text" title="${complaint.message || complaint.activity}">
                    ${complaint.message ? complaint.message : complaint.activity}
                </div>
            </td>
            <td><span class="source-badge ${complaint.source}">${complaint.source.charAt(0).toUpperCase() + complaint.source.slice(1)}</span></td>
            <td>${formatDate(complaint.date)}</td>
        `;
        tbody.appendChild(tr);
    });
}

// Show complaints error
function showComplaintsError() {
    const tbody = document.getElementById('activity-table-body');
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="4" style="text-align: center; padding: 20px; color: var(--color-error);">
                    Failed to load complaints data
                </td>
            </tr>
        `;
    }
}

// Load queries data for the table
function loadQueriesData(source) {
    fetch(`/api/analytics/queries?source=${source}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateQueriesTable(data.queries);
                console.log('Queries data loaded:', data.queries.length, 'queries');
            } else {
                console.error('Failed to load queries data:', data.error);
                showQueriesError();
            }
        })
        .catch(error => {
            console.error('Error fetching queries data:', error);
            showQueriesError();
        });
}

// Update queries table
function updateQueriesTable(queries) {
    const tbody = document.getElementById('queries-table-body');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    if (queries.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="4" style="text-align: center; padding: 20px; color: var(--text-secondary);">
                    No queries found for this source
                </td>
            </tr>
        `;
        return;
    }
    
    // Show only first 10 queries in main table
    const displayQueries = queries.slice(0, 10);
    
    displayQueries.forEach(query => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>
                <div class="user-info">
                    <div class="user-avatar">${getInitials(query.user)}</div>
                    <span class="user-name">${query.user}</span>
                </div>
            </td>
            <td>
                <div class="complaint-text" title="${query.message || query.activity}">
                    ${query.message ? query.message : query.activity}
                </div>
            </td>
            <td><span class="source-badge ${query.source}">${query.source.charAt(0).toUpperCase() + query.source.slice(1)}</span></td>
            <td>${formatDate(query.date)}</td>
        `;
        tbody.appendChild(tr);
    });
}

// Show queries error
function showQueriesError() {
    const tbody = document.getElementById('queries-table-body');
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="4" style="text-align: center; padding: 20px; color: var(--color-error);">
                    Failed to load queries data
                </td>
            </tr>
        `;
    }
}

// Get user initials
function getInitials(name) {
    return name.split(' ').map(n => n[0]).join('').toUpperCase();
}

// Format date for display
function formatDate(dateStr) {
    if (!dateStr || dateStr === 'Unknown') return 'Unknown';
    
    if (dateStr.includes('ago') || dateStr.includes('hour') || dateStr.includes('minute')) {
        return dateStr;
    }
    
    try {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now - date;
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        const diffDays = Math.floor(diffHours / 24);
        
        if (diffHours < 1) return 'Just now';
        if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
        if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
        
        return date.toLocaleDateString();
    } catch (e) {
        return dateStr;
    }
}

// Export complaints function
function exportComplaints() {
    const table = document.querySelector('.data-table');
    if (!table) return;
    
    let csv = 'User,Complaint,Source,Date\n';
    
    const rows = table.querySelectorAll('tbody tr');
    rows.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 4) {
            const user = cells[0].querySelector('.user-name')?.textContent || '';
            const complaint = cells[1].textContent.trim();
            const source = cells[2].textContent.trim();
            const date = cells[3].textContent.trim();
            
            csv += `"${user}","${complaint}","${source}","${date}"\n`;
        }
    });
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `complaints_whatsapp_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
}

// View all complaints function
function viewAllComplaints(timePeriod = '7d') {
    console.log('View All clicked for WhatsApp, time period:', timePeriod);
    
    // Create modal HTML
    const modalHTML = `
        <div id="complaints-modal" style="
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            animation: fadeIn 0.3s ease;
        ">
            <div style="
                background: var(--bg-primary);
                border-radius: var(--radius-large);
                width: 90%;
                max-width: 1000px;
                max-height: 90vh;
                display: flex;
                flex-direction: column;
                box-shadow: var(--shadow-medium);
                animation: slideUp 0.3s ease;
            ">
                <div style="
                    padding: 24px;
                    border-bottom: 1px solid var(--border-color);
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    position: sticky;
                    top: 0;
                    background: var(--bg-secondary);
                    z-index: 100;
                ">
                    <div>
                        <h2 style="margin: 0; font-size: 20px; color: var(--text-primary);">
                            All Complaints - WhatsApp
                        </h2>
                        <p style="margin: 8px 0 0 0; font-size: 14px; color: var(--text-secondary);" id="modal-complaint-count">
                            Loading...
                        </p>
                    </div>
                    <button onclick="closeComplaintsModal()" style="
                        background: none;
                        border: none;
                        font-size: 24px;
                        cursor: pointer;
                        color: var(--text-secondary);
                    ">×</button>
                </div>
                
                <div style="
                    padding: 16px 24px;
                    border-bottom: 1px solid var(--border-color);
                    display: flex;
                    gap: 8px;
                    background: var(--bg-secondary);
                    flex-wrap: wrap;
                ">
                    <button class="complaint-period-btn active" data-period="7d" onclick="updateComplaintsModal('7d')" style="
                        padding: 8px 16px;
                        border: 1px solid var(--border-color);
                        background: var(--accent-color);
                        color: white;
                        border-radius: 6px;
                        cursor: pointer;
                        font-weight: 500;
                        font-size: 12px;
                    ">7D</button>
                    <button class="complaint-period-btn" data-period="1m" onclick="updateComplaintsModal('1m')" style="
                        padding: 8px 16px;
                        border: 1px solid var(--border-color);
                        background: var(--bg-tertiary);
                        color: var(--text-primary);
                        border-radius: 6px;
                        cursor: pointer;
                        font-weight: 500;
                        font-size: 12px;
                    ">1M</button>
                    <button class="complaint-period-btn" data-period="3m" onclick="updateComplaintsModal('3m')" style="
                        padding: 8px 16px;
                        border: 1px solid var(--border-color);
                        background: var(--bg-tertiary);
                        color: var(--text-primary);
                        border-radius: 6px;
                        cursor: pointer;
                        font-weight: 500;
                        font-size: 12px;
                    ">3M</button>
                    <button class="complaint-period-btn" data-period="1y" onclick="updateComplaintsModal('1y')" style="
                        padding: 8px 16px;
                        border: 1px solid var(--border-color);
                        background: var(--bg-tertiary);
                        color: var(--text-primary);
                        border-radius: 6px;
                        cursor: pointer;
                        font-weight: 500;
                        font-size: 12px;
                    ">1Y</button>
                    <button class="complaint-period-btn" data-period="3y" onclick="updateComplaintsModal('3y')" style="
                        padding: 8px 16px;
                        border: 1px solid var(--border-color);
                        background: var(--bg-tertiary);
                        color: var(--text-primary);
                        border-radius: 6px;
                        cursor: pointer;
                        font-weight: 500;
                        font-size: 12px;
                    ">3Y</button>
                </div>
                
                <div id="modal-complaints-container" style="padding: 24px; overflow-y: auto; flex: 1;">
                    <div style="text-align: center; padding: 40px;">
                        <div style="width: 40px; height: 40px; border: 3px solid var(--accent-color); border-top: 3px solid transparent; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto;"></div>
                        <p style="margin-top: 16px; color: var(--text-secondary);">Loading all complaints...</p>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Add modal to page
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Load complaints for the selected time period
    updateComplaintsModal(timePeriod);
}

// Update complaints modal with time period filter
function updateComplaintsModal(timePeriod) {
    console.log('Updating modal with time period:', timePeriod);
    
    // Update active button
    document.querySelectorAll('.complaint-period-btn').forEach(btn => {
        btn.classList.remove('active');
        btn.style.background = 'var(--bg-tertiary)';
        btn.style.color = 'var(--text-primary)';
        if (btn.getAttribute('data-period') === timePeriod) {
            btn.classList.add('active');
            btn.style.background = 'var(--accent-color)';
            btn.style.color = 'white';
        }
    });
    
    // Fetch complaints for the time period
    fetch(`/api/analytics/complaints?source=whatsapp&period=${timePeriod}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(`Found ${data.complaints.length} complaints for ${timePeriod}`);
                
                // Build complaints table
                let tableHTML = `
                    <table style="width: 100%; border-collapse: collapse; table-layout: fixed;">
                        <thead>
                            <tr style="background: var(--bg-tertiary); border-bottom: 2px solid var(--border-color);">
                                <th style="padding: 12px; text-align: left; font-weight: 600; color: var(--text-primary); width: 15%;">User</th>
                                <th style="padding: 12px; text-align: left; font-weight: 600; color: var(--text-primary); width: 50%;">Complaint</th>
                                <th style="padding: 12px; text-align: left; font-weight: 600; color: var(--text-primary); width: 15%;">Source</th>
                                <th style="padding: 12px; text-align: left; font-weight: 600; color: var(--text-primary); width: 20%;">Date</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                if (data.complaints.length === 0) {
                    tableHTML += `
                        <tr>
                            <td colspan="4" style="padding: 40px; text-align: center; color: var(--text-secondary);">
                                No complaints found for this period
                            </td>
                        </tr>
                    `;
                } else {
                    // Store complaints globally for modal access
                    window.currentComplaintsWhatsApp = data.complaints;
                    
                    data.complaints.forEach((complaint, index) => {
                        tableHTML += `
                            <tr style="border-bottom: 1px solid var(--border-color); height: auto; cursor: pointer; transition: background 0.2s;" 
                                onmouseover="this.style.background='var(--bg-tertiary)'" 
                                onmouseout="this.style.background='transparent'"
                                onclick="openWhatsAppComplaintDetailByIndex(${index})"
                                data-complaint-index="${index}">
                                <td style="padding: 12px; color: var(--text-primary); word-wrap: break-word;">
                                    <div style="display: flex; align-items: center; gap: 8px;">
                                        <div style="
                                            width: 32px;
                                            height: 32px;
                                            border-radius: 50%;
                                            background: var(--accent-color);
                                            color: white;
                                            display: flex;
                                            align-items: center;
                                            justify-content: center;
                                            font-size: 12px;
                                            font-weight: 600;
                                            flex-shrink: 0;
                                        ">${getInitials(complaint.user)}</div>
                                        <span style="word-break: break-word;">${complaint.user}</span>
                                    </div>
                                </td>
                                <td style="padding: 12px; color: var(--text-primary); word-wrap: break-word; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 400px;">
                                    ${complaint.message || complaint.activity}
                                </td>
                                <td style="padding: 12px; color: var(--text-primary); word-wrap: break-word;">
                                    <span style="
                                        background: rgba(16, 185, 129, 0.1);
                                        color: var(--color-success);
                                        padding: 4px 8px;
                                        border-radius: 12px;
                                        font-size: 12px;
                                        font-weight: 600;
                                        display: inline-block;
                                    ">WhatsApp</span>
                                </td>
                                <td style="padding: 12px; color: var(--text-secondary); word-wrap: break-word;">
                                    ${formatDate(complaint.date)}
                                </td>
                            </tr>
                        `;
                    });
                }
                
                tableHTML += `
                        </tbody>
                    </table>
                    <div style="margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--border-color); text-align: center; color: var(--text-secondary);">
                        Total: ${data.complaints.length} complaints
                    </div>
                `;
                
                // Update modal content
                const container = document.getElementById('modal-complaints-container');
                if (container) {
                    container.innerHTML = tableHTML;
                }
                
                // Update complaint count in header
                const countElement = document.getElementById('modal-complaint-count');
                if (countElement) {
                    countElement.textContent = `Total: ${data.complaints.length} complaints`;
                }
                
                showNotification(`Loaded ${data.complaints.length} complaints for ${timePeriod}`, 'success');
            } else {
                console.error('Failed to load complaints:', data.error);
                showNotification('Failed to load complaints', 'error');
                const container = document.getElementById('modal-complaints-container');
                if (container) {
                    container.innerHTML = `<p style="text-align: center; color: var(--color-error);">Failed to load complaints</p>`;
                }
            }
        })
        .catch(error => {
            console.error('Error fetching complaints:', error);
            showNotification('Error loading complaints', 'error');
            const container = document.getElementById('modal-complaints-container');
            if (container) {
                container.innerHTML = `<p style="text-align: center; color: var(--color-error);">Error loading complaints</p>`;
            }
        });
}

// Close complaints modal
function closeComplaintsModal() {
    const modal = document.getElementById('complaints-modal');
    if (modal) {
        modal.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => modal.remove(), 300);
    }
}

// Export queries function
function exportQueries() {
    const table = document.querySelector('.data-table');
    if (!table) return;
    
    let csv = 'User,Query,Source,Date\n';
    
    const rows = table.querySelectorAll('tbody tr');
    rows.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 4) {
            const user = cells[0].querySelector('.user-name')?.textContent || '';
            const query = cells[1].textContent.trim();
            const source = cells[2].textContent.trim();
            const date = cells[3].textContent.trim();
            
            csv += `"${user}","${query}","${source}","${date}"\n`;
        }
    });
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `queries_whatsapp_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
}

// View all queries function
function viewAllQueries(timePeriod = '7d') {
    console.log('View All clicked for WhatsApp queries, time period:', timePeriod);
    
    // Create modal HTML
    const modalHTML = `
        <div id="queries-modal" style="
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            animation: fadeIn 0.3s ease;
        ">
            <div style="
                background: var(--bg-primary);
                border-radius: var(--radius-large);
                width: 90%;
                max-width: 1000px;
                max-height: 90vh;
                display: flex;
                flex-direction: column;
                box-shadow: var(--shadow-medium);
                animation: slideUp 0.3s ease;
            ">
                <div style="
                    padding: 24px;
                    border-bottom: 1px solid var(--border-color);
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    position: sticky;
                    top: 0;
                    background: var(--bg-secondary);
                    z-index: 100;
                ">
                    <div>
                        <h2 style="margin: 0; font-size: 20px; color: var(--text-primary);">
                            All Queries - WhatsApp
                        </h2>
                        <p style="margin: 8px 0 0 0; font-size: 14px; color: var(--text-secondary);" id="modal-queries-count">
                            Loading...
                        </p>
                    </div>
                    <button onclick="closeQueriesModal()" style="
                        background: none;
                        border: none;
                        font-size: 24px;
                        cursor: pointer;
                        color: var(--text-secondary);
                    ">×</button>
                </div>
                
                <div style="
                    padding: 16px 24px;
                    border-bottom: 1px solid var(--border-color);
                    display: flex;
                    gap: 8px;
                    background: var(--bg-secondary);
                    flex-wrap: wrap;
                ">
                    <button class="queries-period-btn active" data-period="7d" onclick="updateQueriesModal('7d')" style="
                        padding: 8px 16px;
                        border: 1px solid var(--border-color);
                        background: var(--accent-color);
                        color: white;
                        border-radius: 6px;
                        cursor: pointer;
                        font-weight: 500;
                        font-size: 12px;
                    ">7D</button>
                    <button class="queries-period-btn" data-period="1m" onclick="updateQueriesModal('1m')" style="
                        padding: 8px 16px;
                        border: 1px solid var(--border-color);
                        background: var(--bg-tertiary);
                        color: var(--text-primary);
                        border-radius: 6px;
                        cursor: pointer;
                        font-weight: 500;
                        font-size: 12px;
                    ">1M</button>
                    <button class="queries-period-btn" data-period="3m" onclick="updateQueriesModal('3m')" style="
                        padding: 8px 16px;
                        border: 1px solid var(--border-color);
                        background: var(--bg-tertiary);
                        color: var(--text-primary);
                        border-radius: 6px;
                        cursor: pointer;
                        font-weight: 500;
                        font-size: 12px;
                    ">3M</button>
                    <button class="queries-period-btn" data-period="1y" onclick="updateQueriesModal('1y')" style="
                        padding: 8px 16px;
                        border: 1px solid var(--border-color);
                        background: var(--bg-tertiary);
                        color: var(--text-primary);
                        border-radius: 6px;
                        cursor: pointer;
                        font-weight: 500;
                        font-size: 12px;
                    ">1Y</button>
                    <button class="queries-period-btn" data-period="3y" onclick="updateQueriesModal('3y')" style="
                        padding: 8px 16px;
                        border: 1px solid var(--border-color);
                        background: var(--bg-tertiary);
                        color: var(--text-primary);
                        border-radius: 6px;
                        cursor: pointer;
                        font-weight: 500;
                        font-size: 12px;
                    ">3Y</button>
                </div>
                
                <div id="modal-queries-container" style="padding: 24px; overflow-y: auto; flex: 1;">
                    <div style="text-align: center; padding: 40px;">
                        <div style="width: 40px; height: 40px; border: 3px solid var(--accent-color); border-top: 3px solid transparent; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto;"></div>
                        <p style="margin-top: 16px; color: var(--text-secondary);">Loading all queries...</p>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Add modal to page
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Load queries for the selected time period
    updateQueriesModal(timePeriod);
}

// Update queries modal with time period filter
function updateQueriesModal(timePeriod) {
    console.log('Updating queries modal with time period:', timePeriod);
    
    // Update active button
    document.querySelectorAll('.queries-period-btn').forEach(btn => {
        btn.classList.remove('active');
        btn.style.background = 'var(--bg-tertiary)';
        btn.style.color = 'var(--text-primary)';
        if (btn.getAttribute('data-period') === timePeriod) {
            btn.classList.add('active');
            btn.style.background = 'var(--accent-color)';
            btn.style.color = 'white';
        }
    });
    
    // Fetch queries for the time period
    fetch(`/api/analytics/queries?source=whatsapp&period=${timePeriod}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(`Found ${data.queries.length} queries for ${timePeriod}`);
                
                // Build queries table
                let tableHTML = `
                    <table style="width: 100%; border-collapse: collapse; table-layout: fixed;">
                        <thead>
                            <tr style="background: var(--bg-tertiary); border-bottom: 2px solid var(--border-color);">
                                <th style="padding: 12px; text-align: left; font-weight: 600; color: var(--text-primary); width: 15%;">User</th>
                                <th style="padding: 12px; text-align: left; font-weight: 600; color: var(--text-primary); width: 50%;">Query</th>
                                <th style="padding: 12px; text-align: left; font-weight: 600; color: var(--text-primary); width: 15%;">Source</th>
                                <th style="padding: 12px; text-align: left; font-weight: 600; color: var(--text-primary); width: 20%;">Date</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                if (data.queries.length === 0) {
                    tableHTML += `
                        <tr>
                            <td colspan="4" style="padding: 40px; text-align: center; color: var(--text-secondary);">
                                No queries found for this period
                            </td>
                        </tr>
                    `;
                } else {
                    // Store queries globally for modal access
                    window.currentQueriesWhatsApp = data.queries;
                    
                    data.queries.forEach((query, index) => {
                        tableHTML += `
                            <tr style="border-bottom: 1px solid var(--border-color); height: auto; cursor: pointer; transition: background 0.2s;" 
                                onmouseover="this.style.background='var(--bg-tertiary)'" 
                                onmouseout="this.style.background='transparent'"
                                onclick="openWhatsAppQueryDetailByIndex(${index})"
                                data-query-index="${index}">
                                <td style="padding: 12px; color: var(--text-primary); word-wrap: break-word;">
                                    <div style="display: flex; align-items: center; gap: 8px;">
                                        <div style="
                                            width: 32px;
                                            height: 32px;
                                            border-radius: 50%;
                                            background: var(--accent-color);
                                            color: white;
                                            display: flex;
                                            align-items: center;
                                            justify-content: center;
                                            font-size: 12px;
                                            font-weight: 600;
                                            flex-shrink: 0;
                                        ">${getInitials(query.user)}</div>
                                        <span style="word-break: break-word;">${query.user}</span>
                                    </div>
                                </td>
                                <td style="padding: 12px; color: var(--text-primary); word-wrap: break-word; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 400px;">
                                    ${query.message || query.activity}
                                </td>
                                <td style="padding: 12px; color: var(--text-primary); word-wrap: break-word;">
                                    <span style="
                                        background: rgba(16, 185, 129, 0.1);
                                        color: var(--color-success);
                                        padding: 4px 8px;
                                        border-radius: 12px;
                                        font-size: 12px;
                                        font-weight: 600;
                                        display: inline-block;
                                    ">WhatsApp</span>
                                </td>
                                <td style="padding: 12px; color: var(--text-secondary); word-wrap: break-word;">
                                    ${formatDate(query.date)}
                                </td>
                            </tr>
                        `;
                    });
                }
                
                tableHTML += `
                        </tbody>
                    </table>
                    <div style="margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--border-color); text-align: center; color: var(--text-secondary);">
                        Total: ${data.queries.length} queries
                    </div>
                `;
                
                // Update modal content
                const container = document.getElementById('modal-queries-container');
                if (container) {
                    container.innerHTML = tableHTML;
                }
                
                // Update queries count in header
                const countElement = document.getElementById('modal-queries-count');
                if (countElement) {
                    countElement.textContent = `Total: ${data.queries.length} queries`;
                }
                
                showNotification(`Loaded ${data.queries.length} queries for ${timePeriod}`, 'success');
            } else {
                console.error('Failed to load queries:', data.error);
                showNotification('Failed to load queries', 'error');
                const container = document.getElementById('modal-queries-container');
                if (container) {
                    container.innerHTML = `<p style="text-align: center; color: var(--color-error);">Failed to load queries</p>`;
                }
            }
        })
        .catch(error => {
            console.error('Error fetching queries:', error);
            showNotification('Error loading queries', 'error');
            const container = document.getElementById('modal-queries-container');
            if (container) {
                container.innerHTML = `<p style="text-align: center; color: var(--color-error);">Error loading queries</p>`;
            }
        });
}

// Close queries modal
function closeQueriesModal() {
    const modal = document.getElementById('queries-modal');
    if (modal) {
        modal.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => modal.remove(), 300);
    }
}

// Open query detail modal by index
function openWhatsAppQueryDetailByIndex(index) {
    if (!window.currentQueriesWhatsApp || !window.currentQueriesWhatsApp[index]) {
        console.error('Query not found at index:', index);
        showNotification('Error loading query details', 'error');
        return;
    }
    
    const query = window.currentQueriesWhatsApp[index];
    console.log('Opening query detail:', query);
    
    // Create detail modal HTML
    const detailModalHTML = `
        <div id="query-detail-modal" style="
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10001;
            animation: fadeIn 0.3s ease;
        ">
            <div style="
                background: var(--bg-primary);
                border-radius: var(--radius-large);
                width: 90%;
                max-width: 600px;
                max-height: 80vh;
                display: flex;
                flex-direction: column;
                box-shadow: var(--shadow-medium);
                animation: slideUp 0.3s ease;
                overflow: hidden;
            ">
                <div style="
                    padding: 24px;
                    border-bottom: 1px solid var(--border-color);
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    background: var(--bg-secondary);
                ">
                    <div>
                        <h2 style="margin: 0; font-size: 18px; color: var(--text-primary);">
                            Query Details
                        </h2>
                        <p style="margin: 8px 0 0 0; font-size: 12px; color: var(--text-secondary);">
                            WhatsApp Query
                        </p>
                    </div>
                    <button onclick="closeQueryDetail()" style="
                        background: none;
                        border: none;
                        font-size: 24px;
                        cursor: pointer;
                        color: var(--text-secondary);
                        transition: color 0.2s;
                    " onmouseover="this.style.color='var(--text-primary)'" onmouseout="this.style.color='var(--text-secondary)'">×</button>
                </div>
                
                <div style="
                    padding: 24px;
                    overflow-y: auto;
                    flex: 1;
                ">
                    <div style="margin-bottom: 24px;">
                        <label style="display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
                            User
                        </label>
                        <div style="
                            display: flex;
                            align-items: center;
                            gap: 12px;
                            padding: 12px;
                            background: var(--bg-tertiary);
                            border-radius: var(--radius);
                        ">
                            <div style="
                                width: 40px;
                                height: 40px;
                                border-radius: 50%;
                                background: var(--accent-color);
                                color: white;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                font-size: 14px;
                                font-weight: 600;
                                flex-shrink: 0;
                            ">${getInitials(query.user)}</div>
                            <div>
                                <p style="margin: 0; font-weight: 600; color: var(--text-primary);">${query.user}</p>
                                <p style="margin: 4px 0 0 0; font-size: 12px; color: var(--text-secondary);">WhatsApp Customer</p>
                            </div>
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 24px;">
                        <label style="display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
                            Contact Number
                        </label>
                        <div style="
                            padding: 12px;
                            background: var(--bg-tertiary);
                            border-radius: var(--radius);
                            border: 1px solid var(--border-color);
                        ">
                            <p style="margin: 0; font-weight: 600; color: var(--text-primary); margin-bottom: 6px;">
                                📱 +${query.country_code || '92'} ${query.contact_number || 'N/A'}
                            </p>
                            <p style="margin: 0; font-size: 12px; color: var(--text-secondary);">WhatsApp Contact Information</p>
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 24px;">
                        <label style="display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
                            Full Query
                        </label>
                        <div style="
                            padding: 16px;
                            background: var(--bg-tertiary);
                            border-radius: var(--radius);
                            border-left: 4px solid var(--accent-color);
                            line-height: 1.6;
                            color: var(--text-primary);
                            word-wrap: break-word;
                          
                            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        ">
                            ${query.message || query.activity || 'No query content'}
                        </div>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px;">
                        <div>
                            <label style="display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
                                Source
                            </label>
                            <div style="
                                padding: 12px;
                                background: var(--bg-tertiary);
                                border-radius: var(--radius);
                                text-align: center;
                            ">
                                <span style="
                                    background: rgba(16, 185, 129, 0.1);
                                    color: var(--color-success);
                                    padding: 6px 12px;
                                    border-radius: 12px;
                                    font-size: 12px;
                                    font-weight: 600;
                                    display: inline-block;
                                ">WhatsApp</span>
                            </div>
                        </div>
                        
                        <div>
                            <label style="display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
                                Date
                            </label>
                            <div style="
                                padding: 12px;
                                background: var(--bg-tertiary);
                                border-radius: var(--radius);
                                text-align: center;
                                color: var(--text-primary);
                                font-weight: 500;
                            ">
                                ${formatDate(query.date)}
                            </div>
                        </div>
                    </div>
                    
                    <div style="
                        padding: 16px;
                        background: rgba(16, 185, 129, 0.05);
                        border-radius: var(--radius);
                        border-left: 4px solid var(--color-success);
                    ">
                        <p style="margin: 0; font-size: 12px; color: var(--text-secondary);">
                            <strong style="color: var(--text-primary);">Tip:</strong> You can copy this query and use it for reference or follow-up actions.
                        </p>
                    </div>
                </div>
                
                <div style="
                    padding: 16px 24px;
                    border-top: 1px solid var(--border-color);
                    background: var(--bg-secondary);
                    display: flex;
                    gap: 12px;
                    justify-content: flex-end;
                ">
                    <button onclick="copyQueryMessage('${(query.message || query.activity || '').replace(/'/g, "\\'").replace(/\n/g, '\\n')}')" style="
                        padding: 10px 16px;
                        background: var(--accent-color);
                        color: white;
                        border: none;
                        border-radius: var(--radius);
                        cursor: pointer;
                        font-weight: 500;
                        font-size: 14px;
                        transition: opacity 0.2s;
                    " onmouseover="this.style.opacity='0.9'" onmouseout="this.style.opacity='1'">
                        Copy Query
                    </button>
                    <button onclick="closeQueryDetail()" style="
                        padding: 10px 16px;
                        background: var(--bg-tertiary);
                        color: var(--text-primary);
                        border: 1px solid var(--border-color);
                        border-radius: var(--radius);
                        cursor: pointer;
                        font-weight: 500;
                        font-size: 14px;
                        transition: background 0.2s;
                    " onmouseover="this.style.background='var(--border-color)'" onmouseout="this.style.background='var(--bg-tertiary)'">
                        Close
                    </button>
                </div>
            </div>
        </div>
    `;
    
    // Add modal to page
    document.body.insertAdjacentHTML('beforeend', detailModalHTML);
}

// Close query detail modal
function closeQueryDetail() {
    const modal = document.getElementById('query-detail-modal');
    if (modal) {
        modal.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => modal.remove(), 300);
    }
}

// Copy query message to clipboard
function copyQueryMessage(message) {
    navigator.clipboard.writeText(message).then(() => {
        showNotification('Query copied to clipboard', 'success');
    }).catch(err => {
        console.error('Failed to copy:', err);
        showNotification('Failed to copy query', 'error');
    });
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        background: ${type === 'success' ? 'var(--color-success)' : type === 'error' ? 'var(--color-error)' : 'var(--color-info)'};
        color: white;
        border-radius: var(--radius);
        box-shadow: var(--shadow-medium);
        z-index: 10000;
        animation: slideIn 0.3s ease;
        font-weight: 500;
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}


// Open complaint detail modal by index (WhatsApp)
function openWhatsAppComplaintDetailByIndex(index) {
    if (!window.currentComplaintsWhatsApp || !window.currentComplaintsWhatsApp[index]) {
        console.error('Complaint not found at index:', index);
        showNotification('Error loading complaint details', 'error');
        return;
    }
    
    const complaint = window.currentComplaintsWhatsApp[index];
    console.log('Opening complaint detail:', complaint);
    
    // Create detail modal HTML
    const detailModalHTML = `
        <div id="complaint-detail-modal" style="
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10001;
            animation: fadeIn 0.3s ease;
        ">
            <div style="
                background: var(--bg-primary);
                border-radius: var(--radius-large);
                width: 90%;
                max-width: 600px;
                max-height: 80vh;
                display: flex;
                flex-direction: column;
                box-shadow: var(--shadow-medium);
                animation: slideUp 0.3s ease;
                overflow: hidden;
            ">
                <div style="
                    padding: 24px;
                    border-bottom: 1px solid var(--border-color);
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    background: var(--bg-secondary);
                ">
                    <div>
                        <h2 style="margin: 0; font-size: 18px; color: var(--text-primary);">
                            Complaint Details
                        </h2>
                        <p style="margin: 8px 0 0 0; font-size: 12px; color: var(--text-secondary);">
                            WhatsApp Complaint
                        </p>
                    </div>
                    <button onclick="closeComplaintDetail()" style="
                        background: none;
                        border: none;
                        font-size: 24px;
                        cursor: pointer;
                        color: var(--text-secondary);
                        transition: color 0.2s;
                    " onmouseover="this.style.color='var(--text-primary)'" onmouseout="this.style.color='var(--text-secondary)'">×</button>
                </div>
                
                <div style="
                    padding: 24px;
                    overflow-y: auto;
                    flex: 1;
                ">
                    <div style="margin-bottom: 24px;">
                        <label style="display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
                            User
                        </label>
                        <div style="
                            display: flex;
                            align-items: center;
                            gap: 12px;
                            padding: 12px;
                            background: var(--bg-tertiary);
                            border-radius: var(--radius);
                        ">
                            <div style="
                                width: 40px;
                                height: 40px;
                                border-radius: 50%;
                                background: var(--accent-color);
                                color: white;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                font-size: 14px;
                                font-weight: 600;
                                flex-shrink: 0;
                            ">${getInitials(complaint.user)}</div>
                            <div>
                                <p style="margin: 0; font-weight: 600; color: var(--text-primary);">${complaint.user}</p>
                                <p style="margin: 4px 0 0 0; font-size: 12px; color: var(--text-secondary);">WhatsApp Customer</p>
                            </div>
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 24px;">
                        <label style="display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
                            Contact Number
                        </label>
                        <div style="
                            padding: 12px;
                            background: var(--bg-tertiary);
                            border-radius: var(--radius);
                            border: 1px solid var(--border-color);
                        ">
                            <p style="margin: 0; font-weight: 600; color: var(--text-primary); margin-bottom: 6px;">
                                📱 +${complaint.country_code || '92'} ${complaint.contact_number || 'N/A'}
                            </p>
                            <p style="margin: 0; font-size: 12px; color: var(--text-secondary);">WhatsApp Contact Information</p>
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 24px;">
                        <label style="display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
                            Full Message
                        </label>
                        <div style="
                            padding: 16px;
                            background: var(--bg-tertiary);
                            border-radius: var(--radius);
                            border-left: 4px solid var(--accent-color);
                            line-height: 1.6;
                            color: var(--text-primary);
                            word-wrap: break-word;
                            
                            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        ">
                            ${complaint.message || complaint.activity || 'No message content'}
                        </div>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px;">
                        <div>
                            <label style="display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
                                Source
                            </label>
                            <div style="
                                padding: 12px;
                                background: var(--bg-tertiary);
                                border-radius: var(--radius);
                                text-align: center;
                            ">
                                <span style="
                                    background: rgba(16, 185, 129, 0.1);
                                    color: var(--color-success);
                                    padding: 6px 12px;
                                    border-radius: 12px;
                                    font-size: 12px;
                                    font-weight: 600;
                                    display: inline-block;
                                ">WhatsApp</span>
                            </div>
                        </div>
                        
                        <div>
                            <label style="display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
                                Date
                            </label>
                            <div style="
                                padding: 12px;
                                background: var(--bg-tertiary);
                                border-radius: var(--radius);
                                text-align: center;
                                color: var(--text-primary);
                                font-weight: 500;
                            ">
                                ${formatDate(complaint.date)}
                            </div>
                        </div>
                    </div>
                    
                    <div style="
                        padding: 16px;
                        background: rgba(16, 185, 129, 0.05);
                        border-radius: var(--radius);
                        border-left: 4px solid var(--color-success);
                    ">
                        <p style="margin: 0; font-size: 12px; color: var(--text-secondary);">
                            <strong style="color: var(--text-primary);">Tip:</strong> You can copy this message and use it for reference or follow-up actions.
                        </p>
                    </div>
                </div>
                
                <div style="
                    padding: 16px 24px;
                    border-top: 1px solid var(--border-color);
                    background: var(--bg-secondary);
                    display: flex;
                    gap: 12px;
                    justify-content: flex-end;
                ">
                    <button onclick="copyComplaintMessage('${(complaint.message || complaint.activity || '').replace(/'/g, "\\'").replace(/\n/g, '\\n')}')" style="
                        padding: 10px 16px;
                        background: var(--accent-color);
                        color: white;
                        border: none;
                        border-radius: var(--radius);
                        cursor: pointer;
                        font-weight: 500;
                        font-size: 14px;
                        transition: opacity 0.2s;
                    " onmouseover="this.style.opacity='0.9'" onmouseout="this.style.opacity='1'">
                        Copy Message
                    </button>
                    <button onclick="closeComplaintDetail()" style="
                        padding: 10px 16px;
                        background: var(--bg-tertiary);
                        color: var(--text-primary);
                        border: 1px solid var(--border-color);
                        border-radius: var(--radius);
                        cursor: pointer;
                        font-weight: 500;
                        font-size: 14px;
                        transition: background 0.2s;
                    " onmouseover="this.style.background='var(--border-color)'" onmouseout="this.style.background='var(--bg-tertiary)'">
                        Close
                    </button>
                </div>
            </div>
        </div>
    `;
    
    // Add modal to page
    document.body.insertAdjacentHTML('beforeend', detailModalHTML);
}

// Open complaint detail modal (legacy - kept for backward compatibility)
function openComplaintDetail(element) {
    // Get complaint data from data attribute
    const complaintData = element.getAttribute('data-complaint');
    if (complaintData) {
        const complaint = JSON.parse(complaintData);
        // Store in global array and open by index
        window.currentComplaintsWhatsApp = [complaint];
        openWhatsAppComplaintDetailByIndex(0);
    }
}

// Close complaint detail modal
function closeComplaintDetail() {
    const modal = document.getElementById('complaint-detail-modal');
    if (modal) {
        modal.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => modal.remove(), 300);
    }
}

// Copy complaint message to clipboard
function copyComplaintMessage(message) {
    navigator.clipboard.writeText(message).then(() => {
        showNotification('Message copied to clipboard', 'success');
    }).catch(err => {
        console.error('Failed to copy:', err);
        showNotification('Failed to copy message', 'error');
    });
}


// Conversation Panel Functions
function openConversationPanel() {
    const panel = document.getElementById('conversationPanel');
    if (panel) {
        panel.classList.add('open');
        loadConversations();
    }
}

function closeConversationPanel() {
    const panel = document.getElementById('conversationPanel');
    if (panel) {
        panel.classList.remove('open');
    }
}

function loadConversations() {
    const conversationsList = document.getElementById('conversationsList');
    if (!conversationsList) return;
    
    conversationsList.innerHTML = '<div class="loading-state">Loading conversations...</div>';
    
    fetch('/api/whatsapp/conversations')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.conversations) {
                displayConversations(data.conversations);
            } else {
                conversationsList.innerHTML = '<div class="loading-state">No conversations found</div>';
            }
        })
        .catch(error => {
            console.error('Error loading conversations:', error);
            conversationsList.innerHTML = '<div class="loading-state">Error loading conversations</div>';
        });
}

function displayConversations(conversations) {
    const conversationsList = document.getElementById('conversationsList');
    if (!conversationsList) return;
    
    if (conversations.length === 0) {
        conversationsList.innerHTML = '<div class="loading-state">No conversations available</div>';
        return;
    }
    
    conversationsList.innerHTML = conversations.map(conv => {
        // Handle message_types as either array or string
        const messageTypes = Array.isArray(conv.message_types) ? conv.message_types : (conv.message_types ? conv.message_types.split(',') : []);
        
        return `
            <a href="/view_whatsapp_conversation/${encodeURIComponent(conv.customer_name)}/${conv.conversation_date}" 
               class="conversation-item" 
               data-customer="${conv.customer_name.toLowerCase()}"
               data-date="${conv.conversation_date}">
                <div class="conversation-item-header">
                    <div class="conversation-item-name">${escapeHtml(conv.customer_name)}</div>
                    <div class="conversation-item-date">${conv.conversation_date}</div>
                </div>
                <div class="conversation-item-meta">
                    <span class="conversation-item-count">${conv.message_count} msg${conv.message_count !== 1 ? 's' : ''}</span>
                    <span>${conv.last_message_time ? new Date(conv.last_message_time).toLocaleTimeString() : 'N/A'}</span>
                </div>
                <div class="conversation-item-types">
                    ${messageTypes.map(type => {
                        const trimmedType = type.trim();
                        const icon = trimmedType === 'complaint' ? '❗' : trimmedType === 'query' ? '❓' : '💬';
                        return `<span class="conversation-type-badge ${trimmedType}">${icon} ${trimmedType}</span>`;
                    }).join('')}
                </div>
            </a>
        `;
    }).join('');
}

function filterConversations() {
    const searchInput = document.getElementById('conversationSearch');
    const conversationItems = document.querySelectorAll('.conversation-item');
    
    if (!searchInput) return;
    
    const searchTerm = searchInput.value.toLowerCase();
    
    conversationItems.forEach(item => {
        const customerName = item.getAttribute('data-customer');
        const date = item.getAttribute('data-date');
        
        if (customerName.includes(searchTerm) || date.includes(searchTerm)) {
            item.style.display = 'block';
        } else {
            item.style.display = 'none';
        }
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize conversation panel on page load
document.addEventListener('DOMContentLoaded', function() {
    // Close panel when clicking outside
    document.addEventListener('click', function(event) {
        const panel = document.getElementById('conversationPanel');
        const btn = document.querySelector('.view-conversations-btn');
        
        if (panel && btn && !panel.contains(event.target) && !btn.contains(event.target)) {
            if (panel.classList.contains('open')) {
                closeConversationPanel();
            }
        }
    });
});
