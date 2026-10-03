// New Analytics Dashboard JavaScript

// Disable frontend logging - set to false to disable all console logs
const ENABLE_FRONTEND_LOGGING = false;

// Override console methods if logging is disabled
if (!ENABLE_FRONTEND_LOGGING) {
    console.log = function () { };
    console.warn = function () { };
    console.info = function () { };
    console.debug = function () { };
}

// Global variables
let charts = {};
let currentSource = 'pakwheels';
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
    switchSource(currentSource);
}

// Initialize analytics dashboard
function initializeAnalytics() {
    console.log('Initializing analytics dashboard...');

    // Check if Chart.js is loaded
    if (typeof Chart === 'undefined') {
        console.error('Chart.js not loaded yet, retrying...');
        setTimeout(initializeAnalytics, 100);
        return;
    }

    // Set up source tab listeners
    setupSourceTabs();

    // Initialize charts
    initializeCharts();

    // Load default data (PakWheels)
    switchSource('pakwheels');

    console.log('Analytics dashboard initialized');
}

// Setup source tab functionality
function setupSourceTabs() {
    const sourceTabs = document.querySelectorAll('.source-tab');

    sourceTabs.forEach(tab => {
        tab.addEventListener('click', function () {
            const source = this.getAttribute('data-source');

            // Don't switch if already loading
            if (this.classList.contains('loading')) {
                return;
            }

            // Add loading state to clicked tab
            this.classList.add('loading');

            switchSource(source);

            // Update active tab
            sourceTabs.forEach(t => {
                t.classList.remove('active');
                if (t !== this) {
                    t.classList.remove('loading');
                }
            });
            this.classList.add('active');
        });
    });
}

// Switch data source
function switchSource(source) {
    console.log('Switching to source:', source, 'with time period:', currentTimePeriod);
    currentSource = source;

    // Show loading state
    showLoadingState();

    // Toggle Category header visibility based on source
    const categoryTh = document.getElementById('category-th');
    if (categoryTh) {
        categoryTh.style.display = source === 'pakwheels' ? '' : 'none';
    }

    // Fetch data from API with time period parameter
    fetch(`/api/analytics/source?source=${source}&period=${currentTimePeriod}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Received real data from database:', data);

                // Validate data structure before processing
                if (!data || typeof data !== 'object') {
                    console.error('Invalid data structure received:', data);
                    showErrorState('Invalid data format received from server');
                    return;
                }

                // Update stats with real database data
                if (data.stats) {
                    updateStats(data.stats, source);
                }

                // Update charts with real data - ensure data has required properties
                if (data.most_asked_queries !== undefined || data.query_topics !== undefined) {
                    updateCharts(data);
                } else {
                    console.warn('Missing chart data in response:', {
                        has_queries: data.most_asked_queries !== undefined,
                        has_topics: data.query_topics !== undefined
                    });
                }

                // Load complaints data for the table
                loadComplaintsData(source);

                console.log('Source switched to:', source, 'with real data');
            } else {
                console.error('Failed to load analytics data:', data.error);
                showErrorState(data.error || 'Failed to load analytics data');
            }
        })
        .catch(error => {
            console.error('Error fetching analytics data:', error);
            showErrorState('Failed to load analytics data: ' + error.message);
        })
        .finally(() => {
            hideLoadingState();

            // Remove loading state from all tabs
            const sourceTabs = document.querySelectorAll('.source-tab');
            sourceTabs.forEach(tab => tab.classList.remove('loading'));
        });
}

// Update statistics cards
function updateStats(stats, source) {
    const sourceLabel = source.charAt(0).toUpperCase() + source.slice(1);

    // Update stat values with real data
    document.getElementById('total-posts').textContent = stats.totalPosts || 0;
    document.getElementById('active-users').textContent = stats.activeUsers || 0;
    document.getElementById('new-users').textContent = stats.newUsers || 0;
    document.getElementById('unique-users-total').textContent = stats.uniqueUsersTotal || 0;

    // Update total posts label based on source
    const totalPostsLabel = document.getElementById('total-posts-label');
    if (totalPostsLabel) {
        if (source === 'whatsapp') {
            totalPostsLabel.textContent = 'Total Messages';
        } else {
            totalPostsLabel.textContent = 'Total Posts';
        }
    }

    // Update source labels
    document.getElementById('stat-source-1').textContent = sourceLabel;
    document.getElementById('stat-source-2').textContent = sourceLabel;
    document.getElementById('stat-source-3').textContent = sourceLabel;
    document.getElementById('stat-source-5').textContent = sourceLabel;

    // Reset error styling
    const statValues = document.querySelectorAll('.stat-value');
    statValues.forEach(stat => {
        stat.style.color = '';
    });

    // Add animation effect
    statValues.forEach(stat => {
        stat.style.transform = 'scale(1.1)';
        setTimeout(() => {
            stat.style.transform = 'scale(1)';
        }, 200);
    });
}

// Initialize charts
function initializeCharts() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const colors = getChartColors(isDark);

    // Activity Chart (Line Chart)
    createActivityChart(colors);

    // Conversions Chart (Doughnut Chart)
    createConversionsChart(colors);
    
    // Query Topics Distribution Chart (Doughnut Chart)
    createTopicsChart(colors);
    
    // Most Asked Queries Chart (Bar Chart)
    createQueriesChart(colors);
}

// Get chart colors based on theme
function getChartColors(isDark) {
    return {
        text: isDark ? '#f0f0f0' : '#2d333a',
        textSecondary: isDark ? '#b8b8b8' : '#6e7681',
        grid: isDark ? '#3a3a3a' : '#e8eaed',
        background: isDark ? '#242424' : '#f8f9fa',
        primary: '#a31010',
        success: '#10b981',
        warning: '#f59e0b',
        info: '#3b82f6',
        purple: '#8b5cf6'
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
                label: getActivityChartLabel(currentSource),
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
            },
            elements: {
                point: {
                    hoverBackgroundColor: colors.primary
                }
            }
        }
    });
}

// Get activity chart label based on source
function getActivityChartLabel(source) {
    switch (source) {
        case 'pakwheels':
            return 'Posts';
        case 'whatsapp':
            return 'Messages';
        case 'reddit':
            return 'Posts';
        default:
            return 'Activity';
    }
}

// Create conversions chart
function createConversionsChart(colors) {
    const canvas = document.getElementById('conversionsChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    charts.conversions = new Chart(ctx, {
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
                        label: function (context) {
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

// Create most asked queries chart (Vertical Bar Chart)
function createQueriesChart(colors) {
    const canvas = document.getElementById('queriesChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    charts.queries = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Query Count',
                data: [],
                backgroundColor: colors.primary,
                borderColor: colors.primary,
                borderWidth: 0,
                borderRadius: 6,
                barThickness: 'flex',
                maxBarThickness: 30
            }]
        },
        options: {
            indexAxis: 'x',
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
                    displayColors: false,
                    padding: 12,
                    titleFont: {
                        size: 13,
                        weight: 'bold'
                    },
                    bodyFont: {
                        size: 12
                    },
                    callbacks: {
                        title: function(context) {
                            // Show full query text in tooltip
                            return context[0].label;
                        },
                        label: function(context) {
                            return `Asked ${context.parsed.y} times`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false,
                        drawBorder: false
                    },
                    ticks: {
                        color: colors.textSecondary,
                        font: {
                            size: 11,
                            weight: '500'
                        },
                        maxRotation: 45,
                        minRotation: 0,
                        padding: 8,
                        callback: function(value, index, ticks) {
                            // Truncate label to 25 characters with ellipsis
                            const label = this.getLabelForValue(value);
                            if (label && label.length > 25) {
                                return label.substring(0, 25) + '...';
                            }
                            return label;
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

// Create query topics distribution chart (Doughnut Chart)
function createTopicsChart(colors) {
    const canvas = document.getElementById('topicsChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    charts.topics = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: [
                    colors.primary,
                    colors.success,
                    colors.warning,
                    colors.info,
                    colors.purple,
                    '#ec4899',
                    colors.textSecondary
                ],
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
                            return `${label}: ${value.toFixed(1)}%`;
                        }
                    }
                }
            }
        }
    });
}

// Update charts with new data
function updateCharts(data) {
    // Validate data object
    if (!data || typeof data !== 'object') {
        console.error('Invalid data object passed to updateCharts:', data);
        return;
    }
    
    console.log('updateCharts called with data:', {
        has_activity: !!data.activityData,
        has_conversions: !!data.conversionsData,
        has_queries: !!data.most_asked_queries,
        has_topics: !!data.query_topics
    });
    
    // Update activity chart (if data available)
    if (charts.activity && data.activityData) {
        try {
            charts.activity.data.labels = data.activityData.labels || [];
            charts.activity.data.datasets[0].data = data.activityData.data || [];
            charts.activity.data.datasets[0].label = getActivityChartLabel(currentSource);
            charts.activity.update('active');
        } catch (e) {
            console.warn('Error updating activity chart:', e);
        }
    }
    
    // Update conversions chart (if data available)
    if (charts.conversions && data.conversionsData) {
        try {
            charts.conversions.data.labels = data.conversionsData.labels || [];
            charts.conversions.data.datasets[0].data = data.conversionsData.data || [];
            charts.conversions.data.datasets[0].backgroundColor = data.conversionsData.colors || [];
            charts.conversions.update('active');
        } catch (e) {
            console.warn('Error updating conversions chart:', e);
        }
    }
    
    // Update queries chart
    if (data.most_asked_queries && charts.queries) {
        try {
            console.log('Updating queries chart with data:', data.most_asked_queries);
            const queryLabels = data.most_asked_queries.map(q => q.query);
            const queryCounts = data.most_asked_queries.map(q => q.count);
            
            console.log('Query labels:', queryLabels);
            console.log('Query counts:', queryCounts);
            
            if (queryLabels.length > 0 && queryCounts.length > 0) {
                charts.queries.data.labels = queryLabels;
                charts.queries.data.datasets[0].data = queryCounts;
                charts.queries.update('active');
                
                // Update legend with full query text
                const legendContainer = document.getElementById('queriesLegend');
                if (legendContainer) {
                    legendContainer.innerHTML = '';
                    queryLabels.forEach((label, index) => {
                        const legendItem = document.createElement('div');
                        legendItem.style.cssText = 'display: flex; align-items: flex-start; gap: 8px; font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; line-height: 1.4;';
                        legendItem.innerHTML = `
                            <span style="font-weight: 600; color: var(--text-primary); min-width: 20px; flex-shrink: 0;">${queryCounts[index]}</span>
                            <span style="word-break: break-word; flex: 1;">${label}</span>
                        `;
                        legendContainer.appendChild(legendItem);
                    });
                }
            } else {
                console.warn('No query data available');
            }
        } catch (e) {
            console.warn('Error updating queries chart:', e);
        }
    } else {
        console.warn('Queries chart data missing or chart not initialized:', {
            hasData: !!data.most_asked_queries,
            hasChart: !!charts.queries
        });
    }
    
    // Update topics chart
    if (data.query_topics && charts.topics) {
        try {
            console.log('Updating topics chart with data:', data.query_topics);
            
            // Handle both formats: direct dict or nested with distribution property
            const topicsData = data.query_topics.distribution || data.query_topics;
            
            // Ensure topicsData is a valid object
            if (!topicsData || typeof topicsData !== 'object') {
                console.warn('Invalid topics data format:', topicsData);
                const legendContainer = document.getElementById('topicsLegend');
                if (legendContainer) {
                    legendContainer.innerHTML = '<div style="color: var(--text-secondary); font-size: 12px;">No query data available</div>';
                }
                return;
            }
            
            const topicLabels = Object.keys(topicsData);
            const topicValues = Object.values(topicsData);
            
            console.log('Topic labels:', topicLabels);
            console.log('Topic values:', topicValues);
            
            // Only update if we have data
            if (topicLabels.length > 0 && topicValues.length > 0) {
                charts.topics.data.labels = topicLabels.map(t => t.replace(/_/g, ' ').toUpperCase());
                charts.topics.data.datasets[0].data = topicValues;
                charts.topics.update('active');
                
                // Update legend
                const legendContainer = document.getElementById('topicsLegend');
                if (legendContainer) {
                    legendContainer.innerHTML = '';
                    const colors = ['#a31010', '#10b981', '#f59e0b', '#3b82f6', '#8b5cf6', '#ec4899', '#b8b8b8'];
                    topicLabels.forEach((topic, index) => {
                        const legendItem = document.createElement('div');
                        legendItem.className = 'legend-item';
                        legendItem.innerHTML = `
                            <span class="legend-dot" style="background: ${colors[index % colors.length]};"></span>
                            <span>${topic.replace(/_/g, ' ').toUpperCase()}: ${topicValues[index].toFixed(1)}%</span>
                        `;
                        legendContainer.appendChild(legendItem);
                    });
                }
            } else {
                console.warn('No topic data available');
                // Show placeholder
                const legendContainer = document.getElementById('topicsLegend');
                if (legendContainer) {
                    legendContainer.innerHTML = '<div style="color: var(--text-secondary); font-size: 12px;">No query data available for this source</div>';
                }
            }
        } catch (e) {
            console.warn('Error updating topics chart:', e);
        }
    } else {
        console.warn('Topics chart data missing or chart not initialized:', {
            hasData: !!data.query_topics,
            hasChart: !!charts.topics,
            data: data.query_topics
        });
    }

    // Update conversions chart
    if (charts.conversions && data.conversionsData) {
        charts.conversions.data.labels = data.conversionsData.labels;
        charts.conversions.data.datasets[0].data = data.conversionsData.data;
        charts.conversions.data.datasets[0].backgroundColor = data.conversionsData.colors;
        charts.conversions.update('active');
    }
}

// Update data table
function updateTable(tableData) {
    const tbody = document.getElementById('activity-table-body');
    if (!tbody) return;

    tbody.innerHTML = '';

    tableData.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>
                <div class="user-info">
                    <div class="user-avatar">${getInitials(row.user)}</div>
                    <span class="user-name">${row.user}</span>
                </div>
            </td>
            <td>${row.activity}</td>
            <td><span class="source-badge ${row.source}">${row.source.charAt(0).toUpperCase() + row.source.slice(1)}</span></td>
            <td>${row.date}</td>
            <td><span class="status-badge ${row.status}">${row.status.charAt(0).toUpperCase() + row.status.slice(1)}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

// Get user initials
function getInitials(name) {
    return name.split(' ').map(n => n[0]).join('').toUpperCase();
}

// Download chart function
function downloadChart(chartId) {
    const chart = charts[chartId.replace('Chart', '')];
    if (!chart) return;

    const url = chart.toBase64Image();
    const link = document.createElement('a');
    link.download = `${chartId}_${currentSource}_${new Date().toISOString().split('T')[0]}.png`;
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
const observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
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
window.initializeAnalytics = initializeAnalytics;
window.downloadChart = downloadChart;

console.log('Analytics JavaScript loaded successfully');

// Loading state functions
function showLoadingState() {
    const statValues = document.querySelectorAll('.stat-value');
    statValues.forEach(stat => {
        stat.style.opacity = '0.5';
        stat.textContent = 'Loading...';
    });
}

function hideLoadingState() {
    const statValues = document.querySelectorAll('.stat-value');
    statValues.forEach(stat => {
        stat.style.opacity = '1';
    });
}

function showErrorState(error) {
    const statValues = document.querySelectorAll('.stat-value');
    statValues.forEach(stat => {
        stat.textContent = 'Error';
        stat.style.color = 'var(--color-error)';
    });

    console.error('Analytics error:', error);
}

// Enhanced error handling with retry functionality
function showErrorState(error) {
    const statValues = document.querySelectorAll('.stat-value');
    statValues.forEach(stat => {
        stat.textContent = 'Error';
        stat.style.color = 'var(--color-error)';
    });

    // Show retry button
    const container = document.querySelector('.analytics-header');
    if (container && !document.querySelector('.retry-button')) {
        const retryButton = document.createElement('button');
        retryButton.className = 'retry-button action-btn primary';
        retryButton.innerHTML = '🔄 Retry';
        retryButton.onclick = () => {
            retryButton.remove();
            switchSource(currentSource);
        };
        container.appendChild(retryButton);
    }

    console.error('Analytics error:', error);
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

// Global storage for complaints to avoid JSON parsing issues
window.currentComplaints = [];

// Update complaints table
function updateComplaintsTable(complaints) {
    const tbody = document.getElementById('activity-table-body');
    if (!tbody) return;

    // Normalize complaint data - ensure all have required fields
    const normalizedComplaints = complaints.map(complaint => ({
        ...complaint,
        user: complaint.user || complaint.author || complaint.customer || 'Unknown',
        author: complaint.author || complaint.user || complaint.customer || 'Unknown',
        customer: complaint.customer || complaint.user || complaint.author || 'Unknown',
        message: complaint.message || complaint.text || complaint.complaint || '',
        date: complaint.date || complaint.created_at || complaint.timestamp || 'Unknown'
    }));

    // Store complaints globally for modal access
    window.currentComplaints = normalizedComplaints;

    tbody.innerHTML = '';

    if (normalizedComplaints.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 20px; color: var(--text-secondary);">
                    No complaints found for this source
                </td>
            </tr>
        `;
        return;
    }

    // Show only first 10 complaints in main table
    const displayComplaints = normalizedComplaints.slice(0, 10);

    displayComplaints.forEach((complaint, index) => {
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.style.transition = 'background 0.2s';
        tr.onmouseover = function() { this.style.background = 'var(--bg-tertiary)'; };
        tr.onmouseout = function() { this.style.background = 'transparent'; };
        tr.onclick = function() { openComplaintDetailByIndex(index); };

        const userName = complaint.user || complaint.author || complaint.customer || 'Unknown';
        const complaintText = complaint.message || complaint.text || complaint.complaint || 'No details';
        const complaintCategory = complaint.complaint_category || 'car_complaint';
        const severity = complaint.severity || 'low';
        
        // Get severity badge color
        const severityColors = {
            'critical': 'background: #ef4444; color: white;',
            'high': 'background: #f97316; color: white;',
            'medium': 'background: #eab308; color: white;',
            'low': 'background: #22c55e; color: white;'
        };
        
        // Get category badge color
        const categoryColors = {
            'car_complaint': 'background: #3b82f6; color: white;',
            'other_complaint': 'background: #8b5cf6; color: white;',
            'not_a_complaint': 'background: #64748b; color: white;'
        };
        
        tr.innerHTML = `
            <td>
                <div class="user-info">
                    <div class="user-avatar">${getInitials(userName)}</div>
                    <span class="user-name">${userName}</span>
                </div>
            </td>
            <td>
                <div class="complaint-text" title="${complaintText}">
                    ${complaintText.substring(0, 50)}${complaintText.length > 50 ? '...' : ''}
                </div>
            </td>
            <td>
                <span class="badge" style="${categoryColors[complaintCategory] || categoryColors['car_complaint']} padding: 4px 8px; border-radius: 4px; font-size: 12px;">
                    ${formatCategory(complaintCategory)}
                </span>
            </td>
            <td>
                <span class="badge" style="${severityColors[severity] || severityColors['low']} padding: 4px 8px; border-radius: 4px; font-size: 12px;">
                    ${severity.toUpperCase()}
                </span>
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
                <td colspan="6" style="text-align: center; padding: 20px; color: var(--color-error);">
                    Failed to load complaints data
                </td>
            </tr>
        `;
    }
}

// Helper to format category for display
function formatCategory(category) {
    if (!category || category === 'none') return 'Unclassified';
    
    // Format complaint_category values
    const categoryMap = {
        'car_complaint': 'Car Complaint',
        'other_complaint': 'Other Complaint',
        'not_a_complaint': 'Not a Complaint'
    };
    
    return categoryMap[category] || category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

// Format date for display
function formatDate(dateStr) {
    if (!dateStr || dateStr === 'Unknown') return 'Unknown';

    try {
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return dateStr;

        const month = date.getMonth() + 1;
        const day = date.getDate();
        const year = date.getFullYear();

        return `${month}/${day}/${year}`;
    } catch (e) {
        return dateStr;
    }
}

// Export complaints function
function exportComplaints() {
    // Create CSV content
    const table = document.querySelector('.data-table');
    if (!table) return;

    let csv = 'User,Complaint,Source,Date,Status\n';

    const rows = table.querySelectorAll('tbody tr');
    rows.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 5) {
            const user = cells[0].querySelector('.user-name')?.textContent || '';
            const complaint = cells[1].textContent.trim();
            const source = cells[2].textContent.trim();
            const date = cells[3].textContent.trim();
            const status = cells[4].textContent.trim();

            csv += `"${user}","${complaint}","${source}","${date}","${status}"\n`;
        }
    });

    // Download CSV
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `complaints_${currentSource}_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
}

// View all complaints function
function viewAllComplaints(timePeriod = '7d') {
    console.log('View All clicked for source:', currentSource, 'time period:', timePeriod);

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
                            All Complaints - ${currentSource.charAt(0).toUpperCase() + currentSource.slice(1)}
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
    fetch(`/api/analytics/complaints?source=${currentSource}&period=${timePeriod}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(`Found ${data.complaints.length} complaints for ${timePeriod}`);

                // Build complaints table
                const isPakWheels = currentSource === 'pakwheels';
                let tableHTML = `
                    <table style="width: 100%; border-collapse: collapse; table-layout: fixed;">
                        <thead>
                            <tr style="background: var(--bg-tertiary); border-bottom: 2px solid var(--border-color);">
                                <th style="padding: 12px; text-align: left; font-weight: 600; color: var(--text-primary); width: ${isPakWheels ? '12%' : '15%'};">User</th>
                                <th style="padding: 12px; text-align: left; font-weight: 600; color: var(--text-primary); width: ${isPakWheels ? '45%' : '50%'};">Complaint</th>
                                ${isPakWheels ? '<th style="padding: 12px; text-align: left; font-weight: 600; color: var(--text-primary); width: 13%;">Category</th>' : ''}
                                <th style="padding: 12px; text-align: left; font-weight: 600; color: var(--text-primary); width: ${isPakWheels ? '10%' : '15%'};">Source</th>
                                <th style="padding: 12px; text-align: left; font-weight: 600; color: var(--text-primary); width: 20%;">Date</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                if (data.complaints.length === 0) {
                    tableHTML += `
                        <tr>
                            <td colspan="${isPakWheels ? 5 : 4}" style="padding: 40px; text-align: center; color: var(--text-secondary);">
                                No complaints found for this period
                            </td>
                        </tr>
                    `;
                } else {
                    // Store complaints globally for modal access
                    window.currentComplaints = data.complaints;

                    data.complaints.forEach((complaint, index) => {
                        tableHTML += `
                            <tr style="border-bottom: 1px solid var(--border-color); height: auto; cursor: pointer; transition: background 0.2s;" 
                                onmouseover="this.style.background='var(--bg-tertiary)'" 
                                onmouseout="this.style.background='transparent'"
                                onclick="openComplaintDetailByIndex(${index})"
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
                                ${isPakWheels ? `
                                <td style="padding: 12px; color: var(--text-primary); word-wrap: break-word;">
                                    <span class="category-badge ${complaint.category || 'none'}">${formatCategory(complaint.category)}</span>
                                </td>
                                ` : ''}
                                <td style="padding: 12px; color: var(--text-primary); word-wrap: break-word;">
                                    <span style="
                                        background: ${complaint.source === 'pakwheels' ? 'rgba(163, 16, 16, 0.1)' : complaint.source === 'whatsapp' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(59, 130, 246, 0.1)'};
                                        color: ${complaint.source === 'pakwheels' ? 'var(--accent-color)' : complaint.source === 'whatsapp' ? 'var(--color-success)' : 'var(--color-info)'};
                                        padding: 4px 8px;
                                        border-radius: 12px;
                                        font-size: 12px;
                                        font-weight: 600;
                                        display: inline-block;
                                    ">${complaint.source.charAt(0).toUpperCase() + complaint.source.slice(1)}</span>
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

// Show notification
function showNotification(message, type = 'info') {
    // Create notification element
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

    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}


// Open complaint detail modal by index
function openComplaintDetailByIndex(index) {
    if (!window.currentComplaints || !window.currentComplaints[index]) {
        console.error('Complaint not found at index:', index);
        showNotification('Error loading complaint details', 'error');
        return;
    }

    const complaint = window.currentComplaints[index];
    console.log('Opening complaint detail:', complaint);

    const sourceLabel = complaint.source.charAt(0).toUpperCase() + complaint.source.slice(1);
    const sourceColor = complaint.source === 'pakwheels' ? 'var(--accent-color)' : complaint.source === 'whatsapp' ? 'var(--color-success)' : 'var(--color-info)';
    const sourceBg = complaint.source === 'pakwheels' ? 'rgba(163, 16, 16, 0.1)' : complaint.source === 'whatsapp' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(59, 130, 246, 0.1)';

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
                            ${sourceLabel} Complaint
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
                                <p style="margin: 4px 0 0 0; font-size: 12px; color: var(--text-secondary);">${sourceLabel} User</p>
                            </div>
                        </div>
                    </div>
                    
                    ${complaint.url && complaint.source === 'pakwheels' ? `
                    <div style="margin-bottom: 24px;">
                        <label style="display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
                            Original Post Link
                        </label>
                        <div style="
                            padding: 12px;
                            background: var(--bg-tertiary);
                            border-radius: var(--radius);
                            border: 1px solid var(--border-color);
                        ">
                            <a href="${complaint.url}/${complaint.post_number || ''}" target="_blank" rel="noopener noreferrer" style="
                                color: var(--accent-color);
                                text-decoration: none;
                                font-weight: 500;
                                word-break: break-all;
                                display: block;
                                margin-bottom: 6px;
                                transition: opacity 0.2s;
                            " onmouseover="this.style.opacity='0.8'" onmouseout="this.style.opacity='1'">
                                🔗 ${complaint.url}/${complaint.post_number || ''}
                            </a>
                            <p style="margin: 0; font-size: 12px; color: var(--text-secondary);">Click to view original post</p>
                        </div>
                    </div>
                    ` : ''}
                    
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
                    ${complaint.source === 'pakwheels' ? `
                    <div style="margin-bottom: 24px;">
                        <label style="display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
                            Category
                        </label>
                        <div style="
                            padding: 12px;
                            background: var(--bg-tertiary);
                            border-radius: var(--radius);
                            display: flex;
                            align-items: center;
                            gap: 12px;
                        ">
                            <span class="category-badge ${complaint.category || 'none'}" style="margin: 0;">
                                ${formatCategory(complaint.category)}
                            </span>
                            <span style="font-size: 12px; color: var(--text-secondary);">
                                AI-classified based on content
                            </span>
                        </div>
                    </div>
                    ` : ''}
                    
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
                                    background: ${sourceBg};
                                    color: ${sourceColor};
                                    padding: 6px 12px;
                                    border-radius: 12px;
                                    font-size: 12px;
                                    font-weight: 600;
                                    display: inline-block;
                                ">${sourceLabel}</span>
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
        window.currentComplaints = [complaint];
        openComplaintDetailByIndex(0);
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

// Generate Report function
function generateReport() {
    console.log('Generating report for source:', currentSource);

    // Create report modal
    const reportModalHTML = `
        <div id="report-modal" style="
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
                max-width: 500px;
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
                    <h2 style="margin: 0; font-size: 18px; color: var(--text-primary);">
                        Generate Report
                    </h2>
                    <button onclick="closeReportModal()" style="
                        background: none;
                        border: none;
                        font-size: 24px;
                        cursor: pointer;
                        color: var(--text-secondary);
                    ">×</button>
                </div>
                
                <div style="padding: 24px;">
                    <div style="margin-bottom: 20px;">
                        <label style="display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
                            Time Period
                        </label>
                        <select id="reportPeriod" style="
                            width: 100%;
                            padding: 10px 12px;
                            background: var(--bg-tertiary);
                            border: 1px solid var(--border-color);
                            border-radius: var(--radius);
                            color: var(--text-primary);
                            font-size: 14px;
                            cursor: pointer;
                        ">
                            <option value="7d">Last 7 Days</option>
                            <option value="1m">Last Month</option>
                            <option value="3m">Last 3 Months</option>
                            <option value="1y">Last Year</option>
                            <option value="all">All Time</option>
                        </select>
                    </div>
                    
                    <div style="margin-bottom: 20px;">
                        <label style="display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase;">
                            Format
                        </label>
                        <div style="
                            padding: 10px 12px;
                            background: var(--bg-tertiary);
                            border: 1px solid var(--border-color);
                            border-radius: var(--radius);
                            color: var(--text-primary);
                            font-size: 14px;
                        ">
                            📄 PDF (Portable Document Format)
                        </div>
                        <input type="hidden" id="reportFormat" value="pdf">
                    </div>
                    
                    <div style="
                        padding: 12px;
                        background: rgba(16, 185, 129, 0.05);
                        border-radius: var(--radius);
                        border-left: 4px solid var(--color-success);
                        margin-bottom: 20px;
                    ">
                        <p style="margin: 0; font-size: 12px; color: var(--text-secondary);">
                            <strong style="color: var(--text-primary);">Note:</strong> Report will include all comprehensive sections: Problem Statement, Fact-Based Analysis, Assumptions, Recommendations, and Objective Conclusion.
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
                    <button onclick="closeReportModal()" style="
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
                        Cancel
                    </button>
                    <button onclick="downloadReport()" style="
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
                        Download Report
                    </button>
                </div>
            </div>
        </div>
    `;

    // Add modal to page
    document.body.insertAdjacentHTML('beforeend', reportModalHTML);
}

// Close report modal
function closeReportModal() {
    const modal = document.getElementById('report-modal');
    if (modal) {
        modal.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => modal.remove(), 300);
    }
}

// Download report
function downloadReport() {
    const reportPeriod = document.getElementById('reportPeriod').value;
    const reportFormat = 'pdf';  // Always PDF
    const reportType = 'comprehensive';  // Always comprehensive report with all sections

    console.log('Downloading report:', { reportType, reportPeriod, reportFormat, source: currentSource });

    // Create download URL
    const url = `/api/analytics/report?source=${currentSource}&type=${reportType}&period=${reportPeriod}&format=${reportFormat}`;

    // Trigger download
    const link = document.createElement('a');
    link.href = url;
    link.download = `report_${currentSource}_${new Date().toISOString().split('T')[0]}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showNotification(`PDF report downloaded successfully`, 'success');
    closeReportModal();
}


// Open complaint detail modal by index
function openComplaintDetailByIndex(index) {
    if (!window.currentComplaints || !window.currentComplaints[index]) {
        console.error('Complaint not found at index:', index);
        return;
    }
    
    const complaint = window.currentComplaints[index];
    const source = currentSource || 'pakwheels';
    
    console.log('Opening complaint modal for:', complaint);
    
    // Call the modal function from analytics_new.html
    if (typeof showComplaintModal === 'function') {
        showComplaintModal(complaint, source);
    } else {
        console.error('showComplaintModal function not found');
    }
}

// Helper function to get initials from name
function getInitials(name) {
    if (!name) return '?';
    const parts = name.split(' ');
    return parts.map(p => p[0]).join('').toUpperCase().slice(0, 2);
}

// Helper function to format date
function formatDate(dateStr) {
    if (!dateStr) return 'Unknown';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch (e) {
        return dateStr;
    }
}
