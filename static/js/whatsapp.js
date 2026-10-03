// WhatsApp Dashboard JavaScript - Modern Theme

// Theme management
function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateLogo(savedTheme);
}

function updateLogo(theme) {
    const logo = document.getElementById('navLogo');
    if (logo) {
        const logoFile = theme === 'dark' ? 'light-logo.svg' : 'dark-logo.svg';
        logo.src = `/static/images/${logoFile}`;
    }
}

// Sidebar management - REMOVED
function toggleSidebar() {
    // No sidebar anymore
    console.log('Sidebar functionality removed');
}

// Filter management
function applyFilters() {
    try {
        const dateFrom = document.getElementById('dateFrom')?.value || '';
        const dateTo = document.getElementById('dateTo')?.value || '';
        const messageType = document.getElementById('messageType')?.value || 'all';
        const customerSearch = document.getElementById('customerSearch')?.value || '';
        
        if (dateFrom && dateTo && dateFrom > dateTo) {
            showNotification('Start date cannot be after end date', 'error');
            return;
        }
        
        showLoading();
        showNotification('Applying filters...', 'info');
        
        // Filter messages without page refresh
        filterMessages(dateFrom, dateTo, messageType, customerSearch);
    } catch (error) {
        console.warn('Error applying filters:', error);
        hideLoading();
        showNotification('Error applying filters', 'error');
    }
}

function applyDateFilter() {
    applyFilters();
}

function clearAllFilters() {
    try {
        // Clear all filter inputs
        const dateFrom = document.getElementById('dateFrom');
        const dateTo = document.getElementById('dateTo');
        const messageType = document.getElementById('messageType');
        const customerSearch = document.getElementById('customerSearch');
        
        if (dateFrom) dateFrom.value = '';
        if (dateTo) dateTo.value = '';
        if (messageType) messageType.value = 'all';
        if (customerSearch) customerSearch.value = '';
        
        // Show all message cards without recalculating statistics
        const messageCards = document.querySelectorAll('.message-card, .conversation-message');
        messageCards.forEach(card => {
            card.style.display = '';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        });
        
        // Reset statistics to original values
        resetStatistics();
        
        // Update empty state
        updateEmptyState(messageCards.length);
        
        showNotification('Filters cleared', 'success');
    } catch (error) {
        console.warn('Error clearing filters:', error);
        showNotification('Error clearing filters', 'error');
    }
}

function filterMessages(dateFrom, dateTo, messageType, customerSearch) {
    try {
        const messageCards = document.querySelectorAll('.message-card, .conversation-message');
        let visibleCount = 0;
        let totalMessages = 0;
        let totalComplaints = 0;
        let totalQueries = 0;
        let uniqueCustomers = new Set();
        
        // Check if we're on the detail view (conversation-message) or main view (message-card)
        const isDetailView = document.querySelector('.conversation-message') !== null;
        
        messageCards.forEach(card => {
            let shouldShow = true;
            
            // Date filtering
            const cardDate = card.getAttribute('data-date');
            if (dateFrom && cardDate && cardDate < dateFrom) shouldShow = false;
            if (dateTo && cardDate && cardDate > dateTo) shouldShow = false;
            
            // Message type filtering
            const cardType = card.getAttribute('data-type');
            if (messageType !== 'all' && cardType !== messageType) shouldShow = false;
            
            // Customer search filtering (only for main view)
            if (!isDetailView) {
                const cardCustomer = card.getAttribute('data-customer') || '';
                if (customerSearch && !cardCustomer.toLowerCase().includes(customerSearch.toLowerCase())) shouldShow = false;
            }
            
            // Apply filter with animation
            if (shouldShow) {
                visibleCount++;
                card.style.display = '';
                card.style.opacity = '0';
                card.style.transform = 'translateY(20px)';
                
                // Count statistics based on view type
                if (isDetailView) {
                    // Detail view: count individual messages
                    totalMessages++;
                    if (cardType === 'complaint') totalComplaints++;
                    if (cardType === 'query') totalQueries++;
                } else {
                    // Main view: count from card data
                    const customerName = card.getAttribute('data-customer');
                    if (customerName) {
                        uniqueCustomers.add(customerName);
                    }
                    
                    // Count messages from the card
                    const messageCountText = card.querySelector('.customer-info + div')?.textContent || '';
                    const messageMatch = messageCountText.match(/(\d+)\s+message/);
                    if (messageMatch) {
                        const count = parseInt(messageMatch[1]);
                        totalMessages += count;
                    }
                    
                    // Count complaints and queries from badges
                    const complaintBadge = card.querySelector('.message-type-badge.complaint');
                    const queryBadge = card.querySelector('.message-type-badge.query');
                    
                    if (complaintBadge) {
                        const complaintMatch = complaintBadge.textContent.match(/(\d+)/);
                        if (complaintMatch) {
                            totalComplaints += parseInt(complaintMatch[1]);
                        }
                    }
                    
                    if (queryBadge) {
                        const queryMatch = queryBadge.textContent.match(/(\d+)/);
                        if (queryMatch) {
                            totalQueries += parseInt(queryMatch[1]);
                        }
                    }
                }
                
                setTimeout(() => {
                    card.style.transition = 'all 0.3s ease';
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                }, 100);
            } else {
                card.style.transition = 'all 0.3s ease';
                card.style.opacity = '0';
                card.style.transform = 'translateY(-20px)';
                
                setTimeout(() => {
                    card.style.display = 'none';
                }, 300);
            }
        });
        
        // Update statistics based on view type
        if (isDetailView) {
            updateDetailViewStatistics(totalMessages, totalComplaints, totalQueries);
        } else {
            updateFilteredStatistics(totalMessages, totalComplaints, totalQueries, uniqueCustomers.size);
        }
        
        // Update empty state
        updateEmptyState(visibleCount);
        hideLoading();
        
        if (visibleCount === 0) {
            showNotification('No messages match the current filters', 'warning');
        } else {
            showNotification(`Showing ${visibleCount} message${visibleCount > 1 ? 's' : ''}`, 'success');
        }
    } catch (error) {
        console.warn('Error filtering messages:', error);
        hideLoading();
        showNotification('Error filtering messages', 'error');
    }
}

// Update statistics for detail view (customer-specific page)
function updateDetailViewStatistics(totalMessages, totalComplaints, totalQueries) {
    try {
        // Store original values if not already stored
        if (!window.originalDetailStats) {
            window.originalDetailStats = {
                totalMessages: document.querySelector('.stat-card:nth-child(1) .stat-value')?.textContent || '0',
                totalComplaints: document.querySelector('.stat-card:nth-child(2) .stat-value')?.textContent || '0',
                totalQueries: document.querySelector('.stat-card:nth-child(3) .stat-value')?.textContent || '0'
            };
        }
        
        // Update stat cards with animation (only first 3 cards, 4th is phone number)
        const statCards = [
            { selector: '.stat-card:nth-child(1) .stat-value', value: totalMessages },
            { selector: '.stat-card:nth-child(2) .stat-value', value: totalComplaints },
            { selector: '.stat-card:nth-child(3) .stat-value', value: totalQueries }
        ];
        
        statCards.forEach(({ selector, value }) => {
            const element = document.querySelector(selector);
            if (element) {
                // Add animation
                element.style.transition = 'all 0.3s ease';
                element.style.transform = 'scale(1.1)';
                element.style.color = 'var(--accent-color)';
                
                // Update value
                setTimeout(() => {
                    element.textContent = value;
                    element.style.transform = 'scale(1)';
                }, 150);
                
                // Reset color after animation
                setTimeout(() => {
                    element.style.color = '';
                }, 600);
            }
        });
        
        // Add filtered indicator to stat cards
        addFilteredIndicator();
        
        console.log('📊 Updated detail view statistics:', {
            totalMessages,
            totalComplaints,
            totalQueries
        });
    } catch (error) {
        console.warn('Error updating detail view statistics:', error);
    }
}

function updateEmptyState(visibleCount) {
    try {
        let emptyState = document.querySelector('.empty-state');
        const messagesGrid = document.querySelector('.messages-grid, .conversation-thread');
        
        if (visibleCount === 0 && messagesGrid) {
            if (!emptyState) {
                emptyState = document.createElement('div');
                emptyState.className = 'empty-state';
                emptyState.innerHTML = `
                    <div class="empty-icon">🔍</div>
                    <h3 class="empty-title">No Messages Found</h3>
                    <p class="empty-text">No messages match your current filters. Try adjusting the filters or clearing them.</p>
                `;
                messagesGrid.parentNode.appendChild(emptyState);
            }
            emptyState.style.display = 'block';
        } else if (emptyState) {
            emptyState.style.display = 'none';
        }
    } catch (error) {
        console.warn('Error updating empty state:', error);
    }
}

// Update statistics based on filtered results
function updateFilteredStatistics(totalMessages, totalComplaints, totalQueries, uniqueCustomers) {
    try {
        // Store original values if not already stored
        if (!window.originalStats) {
            window.originalStats = {
                totalMessages: document.querySelector('.stat-card:nth-child(1) .stat-value')?.textContent || '0',
                totalComplaints: document.querySelector('.stat-card:nth-child(2) .stat-value')?.textContent || '0',
                totalQueries: document.querySelector('.stat-card:nth-child(3) .stat-value')?.textContent || '0',
                uniqueCustomers: document.querySelector('.stat-card:nth-child(4) .stat-value')?.textContent || '0'
            };
        }
        
        // Update stat cards with animation
        const statCards = [
            { selector: '.stat-card:nth-child(1) .stat-value', value: totalMessages },
            { selector: '.stat-card:nth-child(2) .stat-value', value: totalComplaints },
            { selector: '.stat-card:nth-child(3) .stat-value', value: totalQueries },
            { selector: '.stat-card:nth-child(4) .stat-value', value: uniqueCustomers }
        ];
        
        statCards.forEach(({ selector, value }) => {
            const element = document.querySelector(selector);
            if (element) {
                // Add animation
                element.style.transition = 'all 0.3s ease';
                element.style.transform = 'scale(1.1)';
                element.style.color = 'var(--accent-color)';
                
                // Update value
                setTimeout(() => {
                    element.textContent = value;
                    element.style.transform = 'scale(1)';
                }, 150);
                
                // Reset color after animation
                setTimeout(() => {
                    element.style.color = '';
                }, 600);
            }
        });
        
        // Add filtered indicator to stat cards
        addFilteredIndicator();
        
        console.log('📊 Updated statistics:', {
            totalMessages,
            totalComplaints,
            totalQueries,
            uniqueCustomers
        });
    } catch (error) {
        console.warn('Error updating filtered statistics:', error);
    }
}

// Add visual indicator that stats are filtered
function addFilteredIndicator() {
    try {
        const statCards = document.querySelectorAll('.stat-card');
        
        statCards.forEach(card => {
            // Remove existing indicator
            const existingIndicator = card.querySelector('.filtered-indicator');
            if (existingIndicator) {
                existingIndicator.remove();
            }
            
            // Add new indicator
            const indicator = document.createElement('div');
            indicator.className = 'filtered-indicator';
            indicator.innerHTML = '🔍 Filtered';
            indicator.style.cssText = `
                position: absolute;
                top: 8px;
                right: 8px;
                background: var(--accent-color);
                color: white;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 10px;
                font-weight: 600;
                z-index: 10;
                animation: fadeIn 0.3s ease;
            `;
            
            card.style.position = 'relative';
            card.appendChild(indicator);
        });
    } catch (error) {
        console.warn('Error adding filtered indicator:', error);
    }
}

// Remove filtered indicator
function removeFilteredIndicator() {
    try {
        const indicators = document.querySelectorAll('.filtered-indicator');
        indicators.forEach(indicator => {
            indicator.style.animation = 'fadeOut 0.3s ease';
            setTimeout(() => indicator.remove(), 300);
        });
    } catch (error) {
        console.warn('Error removing filtered indicator:', error);
    }
}

// Reset statistics to original values
function resetStatistics() {
    try {
        // Check if we're on detail view or main view
        const isDetailView = document.querySelector('.conversation-message') !== null;
        
        if (isDetailView && window.originalDetailStats) {
            // Reset detail view stats (only 3 cards)
            const statCards = [
                { selector: '.stat-card:nth-child(1) .stat-value', value: window.originalDetailStats.totalMessages },
                { selector: '.stat-card:nth-child(2) .stat-value', value: window.originalDetailStats.totalComplaints },
                { selector: '.stat-card:nth-child(3) .stat-value', value: window.originalDetailStats.totalQueries }
            ];
            
            statCards.forEach(({ selector, value }) => {
                const element = document.querySelector(selector);
                if (element) {
                    element.textContent = value;
                }
            });
            
            console.log('📊 Reset detail view statistics to original values');
        } else if (!isDetailView && window.originalStats) {
            // Reset main view stats (4 cards)
            const statCards = [
                { selector: '.stat-card:nth-child(1) .stat-value', value: window.originalStats.totalMessages },
                { selector: '.stat-card:nth-child(2) .stat-value', value: window.originalStats.totalComplaints },
                { selector: '.stat-card:nth-child(3) .stat-value', value: window.originalStats.totalQueries },
                { selector: '.stat-card:nth-child(4) .stat-value', value: window.originalStats.uniqueCustomers }
            ];
            
            statCards.forEach(({ selector, value }) => {
                const element = document.querySelector(selector);
                if (element) {
                    element.textContent = value;
                }
            });
            
            console.log('📊 Reset main view statistics to original values');
        }
        
        // Remove filtered indicator
        removeFilteredIndicator();
    } catch (error) {
        console.warn('Error resetting statistics:', error);
    }
}

// Loading management
function showLoading() {
    try {
        const loadingIndicator = document.getElementById('loadingIndicator');
        if (loadingIndicator) {
            loadingIndicator.style.display = 'block';
            loadingIndicator.innerHTML = '🔄 Loading WhatsApp messages...';
        }
    } catch (error) {
        console.warn('Error showing loading indicator:', error);
    }
}

function hideLoading() {
    try {
        const loadingIndicator = document.getElementById('loadingIndicator');
        if (loadingIndicator) {
            loadingIndicator.style.display = 'none';
        }
    } catch (error) {
        console.warn('Error hiding loading indicator:', error);
    }
}

// Navigation functions
function logout() {
    if (confirm('Are you sure you want to logout?')) {
        window.location.href = '/logout';
    }
}

function goToAnalytics() {
    window.location.href = '/analysis';
}

function goToChatbot() {
    window.location.href = '/chatbot_advanced';
}

// Message card interactions
function highlightMessageCard(card) {
    try {
        card.style.transform = 'translateY(-12px) scale(1.03)';
        card.style.boxShadow = '0 25px 50px rgba(37, 211, 102, 0.4)';
    } catch (error) {
        console.warn('Error highlighting message card:', error);
    }
}

function resetMessageCard(card) {
    try {
        card.style.transform = '';
        card.style.boxShadow = '';
    } catch (error) {
        console.warn('Error resetting message card:', error);
    }
}

// Search functionality
function searchMessages(query) {
    try {
        const messageCards = document.querySelectorAll('.message-card');
        const searchQuery = query.toLowerCase();
        
        messageCards.forEach(card => {
            const customerName = card.querySelector('.customer-name')?.textContent.toLowerCase() || '';
            const messageContent = card.querySelector('.preview-message')?.textContent.toLowerCase() || '';
            
            const matches = customerName.includes(searchQuery) || messageContent.includes(searchQuery);
            
            if (matches || searchQuery === '') {
                card.style.display = 'block';
                card.style.opacity = '1';
            } else {
                card.style.display = 'none';
                card.style.opacity = '0';
            }
        });
        
        // Update results count
        const visibleCards = document.querySelectorAll('.message-card[style*="display: block"], .message-card:not([style*="display: none"])');
        updateSearchResults(visibleCards.length);
    } catch (error) {
        console.warn('Error searching messages:', error);
    }
}

function updateSearchResults(count) {
    try {
        let resultsElement = document.getElementById('searchResults');
        
        if (!resultsElement) {
            resultsElement = document.createElement('div');
            resultsElement.id = 'searchResults';
            resultsElement.style.cssText = `
                text-align: center;
                padding: 16px;
                color: var(--text-secondary);
                font-size: 14px;
                font-weight: 500;
            `;
            
            const messagesGrid = document.querySelector('.messages-grid');
            if (messagesGrid) {
                messagesGrid.parentNode.insertBefore(resultsElement, messagesGrid);
            }
        }
        
        if (count === 0) {
            resultsElement.textContent = '🔍 No messages found matching your search';
            resultsElement.style.display = 'block';
        } else {
            resultsElement.style.display = 'none';
        }
    } catch (error) {
        console.warn('Error updating search results:', error);
    }
}

// Real-time updates
function startRealTimeUpdates() {
    try {
        // Check for new messages every 30 seconds
        setInterval(() => {
            checkForNewMessages();
        }, 30000);
    } catch (error) {
        console.warn('Error starting real-time updates:', error);
    }
}

function checkForNewMessages() {
    try {
        fetch('/api/whatsapp/check-updates')
            .then(response => response.json())
            .then(data => {
                if (data.hasNewMessages) {
                    showNewMessageNotification(data.newCount);
                }
            })
            .catch(error => {
                console.warn('Error checking for new messages:', error);
            });
    } catch (error) {
        console.warn('Error in checkForNewMessages:', error);
    }
}

// Show notification
function showNotification(message, type = 'info') {
    try {
        // Remove existing notifications
        const existingNotifications = document.querySelectorAll('.notification');
        existingNotifications.forEach(notif => notif.remove());
        
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.style.cssText = `
            position: fixed;
            top: 90px;
            right: 20px;
            background: ${getNotificationColor(type)};
            color: white;
            padding: 12px 20px;
            border-radius: 12px;
            box-shadow: var(--shadow-lg);
            z-index: 1001;
            font-weight: 600;
            font-size: 14px;
            max-width: 300px;
            animation: slideInRight 0.3s ease;
        `;
        
        notification.textContent = message;
        document.body.appendChild(notification);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.animation = 'slideOutRight 0.3s ease';
                setTimeout(() => notification.remove(), 300);
            }
        }, 3000);
    } catch (error) {
        console.warn('Error showing notification:', error);
    }
}

function getNotificationColor(type) {
    switch (type) {
        case 'success': return 'linear-gradient(135deg, #10b981, #059669)';
        case 'error': return 'linear-gradient(135deg, #ef4444, #dc2626)';
        case 'warning': return 'linear-gradient(135deg, #f59e0b, #d97706)';
        default: return 'linear-gradient(135deg, #25d366, #128c7e)';
    }
}

// Add notification animations to CSS
const notificationStyles = document.createElement('style');
notificationStyles.textContent = `
    @keyframes slideInRight {
        from { opacity: 0; transform: translateX(100px); }
        to { opacity: 1; transform: translateX(0); }
    }
    @keyframes slideOutRight {
        from { opacity: 1; transform: translateX(0); }
        to { opacity: 0; transform: translateX(100px); }
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: scale(0.8); }
        to { opacity: 1; transform: scale(1); }
    }
    @keyframes fadeOut {
        from { opacity: 1; transform: scale(1); }
        to { opacity: 0; transform: scale(0.8); }
    }
`;
document.head.appendChild(notificationStyles);

// Statistics updates
function updateStatistics() {
    try {
        fetch('/api/whatsapp/stats')
            .then(response => response.json())
            .then(stats => {
                // Update stat values
                const statElements = {
                    'total_messages': document.querySelector('.stat-value:not(.complaint):not(.query)'),
                    'total_complaints': document.querySelector('.stat-value.complaint'),
                    'total_queries': document.querySelector('.stat-value.query')
                };
                
                Object.entries(statElements).forEach(([key, element]) => {
                    if (element && stats[key] !== undefined) {
                        element.textContent = stats[key];
                        
                        // Add animation
                        element.style.transform = 'scale(1.1)';
                        setTimeout(() => {
                            element.style.transform = 'scale(1)';
                        }, 200);
                    }
                });
            })
            .catch(error => {
                console.warn('Error updating statistics:', error);
            });
    } catch (error) {
        console.warn('Error in updateStatistics:', error);
    }
}

// Keyboard shortcuts
function initializeKeyboardShortcuts() {
    try {
        document.addEventListener('keydown', (event) => {
            // Ctrl/Cmd + K for search
            if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
                event.preventDefault();
                const searchInput = document.querySelector('input[name="customer"]');
                if (searchInput) {
                    searchInput.focus();
                }
            }
            
            // Escape to close sidebar on mobile
            if (event.key === 'Escape') {
                const sidebar = document.getElementById('sidebar');
                if (sidebar && !sidebar.classList.contains('collapsed')) {
                    toggleSidebar();
                }
            }
            
            // Ctrl/Cmd + R to refresh
            if ((event.ctrlKey || event.metaKey) && event.key === 'r') {
                event.preventDefault();
                window.location.reload();
            }
        });
    } catch (error) {
        console.warn('Error initializing keyboard shortcuts:', error);
    }
}

// Error handling
function handleError(error, context = 'Unknown') {
    console.warn(`WhatsApp Dashboard Error (${context}):`, error);
    
    // Show user-friendly error message
    const errorElement = document.createElement('div');
    errorElement.style.cssText = `
        position: fixed;
        top: 90px;
        right: 20px;
        background: #ef4444;
        color: white;
        padding: 12px 20px;
        border-radius: 12px;
        box-shadow: var(--shadow-lg);
        z-index: 1001;
        font-weight: 600;
        max-width: 300px;
    `;
    
    errorElement.innerHTML = `⚠️ Something went wrong. Please refresh the page.`;
    document.body.appendChild(errorElement);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (errorElement.parentNode) {
            errorElement.remove();
        }
    }, 5000);
}

// Suppress external script errors
window.addEventListener('error', function(e) {
    // Suppress errors from external scripts/extensions
    if (e.filename && (
        e.filename.includes('giveFreely') || 
        e.filename.includes('content-script') ||
        e.filename.includes('extension')
    )) {
        e.preventDefault();
        return true;
    }
});

// Initialize responsive behavior - REMOVED (no sidebar)
function initializeResponsive() {
    // No sidebar to manage anymore
    console.log('WhatsApp pages now use full-width layout');
}

// Initialize everything when DOM is ready
function initializeWhatsAppDashboard() {
    try {
        loadTheme();
        hideLoading();
        initializeKeyboardShortcuts();
        initializeResponsive();
        
        // Start real-time updates if not in development
        if (window.location.hostname !== 'localhost') {
            startRealTimeUpdates();
        }
        
        // Update statistics immediately and then every 5 minutes
        updateStatistics();
        setInterval(updateStatistics, 300000);
        
        // Add event listeners to message cards
        const messageCards = document.querySelectorAll('.message-card');
        messageCards.forEach(card => {
            card.addEventListener('mouseenter', () => highlightMessageCard(card));
            card.addEventListener('mouseleave', () => resetMessageCard(card));
        });
        
        // Add search functionality to customer input
        const customerInput = document.querySelector('input[name="customer"]');
        if (customerInput) {
            customerInput.addEventListener('input', (e) => {
                searchMessages(e.target.value);
            });
        }
        
        console.log('WhatsApp Dashboard initialized successfully');
    } catch (error) {
        handleError(error, 'Initialization');
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeWhatsAppDashboard);
} else {
    initializeWhatsAppDashboard();
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
    
    conversationsList.innerHTML = conversations.map(conv => `
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
                ${conv.message_types.map(type => `
                    <span class="conversation-type-badge ${type}">${type === 'complaint' ? '❗' : type === 'query' ? '❓' : '💬'} ${type}</span>
                `).join('')}
            </div>
        </a>
    `).join('');
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

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadTheme();
    
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
