// WhatsApp Customer Detail View JavaScript

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

// Filter management for detail view
function applyFilters() {
    try {
        const dateFrom = document.getElementById('dateFrom')?.value || '';
        const dateTo = document.getElementById('dateTo')?.value || '';
        const messageType = document.getElementById('messageType')?.value || 'all';
        
        if (dateFrom && dateTo && dateFrom > dateTo) {
            showNotification('Start date cannot be after end date', 'error');
            return;
        }
        
        showLoading();
        showNotification('Applying filters...', 'info');
        
        // Filter messages for this customer only
        filterCustomerMessages(dateFrom, dateTo, messageType);
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
        
        if (dateFrom) dateFrom.value = '';
        if (dateTo) dateTo.value = '';
        if (messageType) messageType.value = 'all';
        
        // Reset statistics to original values
        resetCustomerStatistics();
        
        // Apply cleared filters
        filterCustomerMessages('', '', 'all');
        showNotification('Filters cleared', 'success');
    } catch (error) {
        console.warn('Error clearing filters:', error);
        showNotification('Error clearing filters', 'error');
    }
}

// Filter messages for a specific customer
function filterCustomerMessages(dateFrom, dateTo, messageType) {
    try {
        const messageCards = document.querySelectorAll('.conversation-message');
        let visibleCount = 0;
        let totalMessages = 0;
        let totalComplaints = 0;
        let totalQueries = 0;
        
        messageCards.forEach(card => {
            let shouldShow = true;
            
            // Date filtering
            const cardDate = card.getAttribute('data-date');
            if (dateFrom && cardDate && cardDate < dateFrom) shouldShow = false;
            if (dateTo && cardDate && cardDate > dateTo) shouldShow = false;
            
            // Message type filtering
            const cardType = card.getAttribute('data-type');
            if (messageType !== 'all' && cardType !== messageType) shouldShow = false;
            
            // Apply filter with animation
            if (shouldShow) {
                visibleCount++;
                totalMessages++;
                if (cardType === 'complaint') totalComplaints++;
                if (cardType === 'query') totalQueries++;
                
                card.style.display = '';
                card.style.opacity = '0';
                card.style.transform = 'translateY(20px)';
                
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
        
        // Update statistics
        updateCustomerStatistics(totalMessages, totalComplaints, totalQueries);
        
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

// Update statistics for customer detail view
function updateCustomerStatistics(totalMessages, totalComplaints, totalQueries) {
    try {
        // Store original values if not already stored
        if (!window.originalCustomerStats) {
            window.originalCustomerStats = {
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
        
        console.log('📊 Updated customer statistics:', {
            totalMessages,
            totalComplaints,
            totalQueries
        });
    } catch (error) {
        console.warn('Error updating customer statistics:', error);
    }
}

// Reset statistics to original values
function resetCustomerStatistics() {
    try {
        if (window.originalCustomerStats) {
            const statCards = [
                { selector: '.stat-card:nth-child(1) .stat-value', value: window.originalCustomerStats.totalMessages },
                { selector: '.stat-card:nth-child(2) .stat-value', value: window.originalCustomerStats.totalComplaints },
                { selector: '.stat-card:nth-child(3) .stat-value', value: window.originalCustomerStats.totalQueries }
            ];
            
            statCards.forEach(({ selector, value }) => {
                const element = document.querySelector(selector);
                if (element) {
                    element.textContent = value;
                }
            });
            
            // Remove filtered indicator
            removeFilteredIndicator();
            
            console.log('📊 Reset customer statistics to original values');
        }
    } catch (error) {
        console.warn('Error resetting customer statistics:', error);
    }
}

// Add visual indicator that stats are filtered
function addFilteredIndicator() {
    try {
        const statCards = document.querySelectorAll('.stat-card');
        
        statCards.forEach((card, index) => {
            // Skip the phone number card (4th card)
            if (index === 3) return;
            
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

// Update empty state
function updateEmptyState(visibleCount) {
    try {
        let emptyState = document.querySelector('.empty-state');
        const conversationThread = document.querySelector('.conversation-thread');
        
        if (visibleCount === 0 && conversationThread) {
            if (!emptyState) {
                emptyState = document.createElement('div');
                emptyState.className = 'empty-state';
                emptyState.innerHTML = `
                    <div class="empty-icon">🔍</div>
                    <h3 class="empty-title">No Messages Found</h3>
                    <p class="empty-text">No messages match your current filters. Try adjusting the filters or clearing them.</p>
                `;
                conversationThread.parentNode.insertBefore(emptyState, conversationThread.nextSibling);
            }
            emptyState.style.display = 'block';
            conversationThread.style.display = 'none';
        } else {
            if (emptyState) {
                emptyState.style.display = 'none';
            }
            if (conversationThread) {
                conversationThread.style.display = 'block';
            }
        }
    } catch (error) {
        console.warn('Error updating empty state:', error);
    }
}

// Loading management
function showLoading() {
    try {
        const loadingIndicator = document.getElementById('loadingIndicator');
        if (loadingIndicator) {
            loadingIndicator.style.display = 'block';
            loadingIndicator.innerHTML = '🔄 Filtering messages...';
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

// Notification system
function showNotification(message, type = 'info') {
    try {
        // Remove existing notifications
        const existingNotifications = document.querySelectorAll('.notification');
        existingNotifications.forEach(notif => notif.remove());
        
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        
        // Set icon based on type
        let icon = 'ℹ️';
        if (type === 'success') icon = '✅';
        if (type === 'error') icon = '❌';
        if (type === 'warning') icon = '⚠️';
        
        notification.innerHTML = `
            <span class="notification-icon">${icon}</span>
            <span class="notification-message">${message}</span>
        `;
        
        notification.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            background: var(--card-bg);
            color: var(--text-primary);
            padding: 16px 24px;
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-xl);
            display: flex;
            align-items: center;
            gap: 12px;
            z-index: 10000;
            animation: slideInRight 0.3s ease;
            border-left: 4px solid ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : type === 'warning' ? '#f59e0b' : '#3b82f6'};
        `;
        
        document.body.appendChild(notification);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            notification.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    } catch (error) {
        console.warn('Error showing notification:', error);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 WhatsApp Customer Detail View initialized');
    loadTheme();
});

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeIn {
        from { opacity: 0; transform: scale(0.8); }
        to { opacity: 1; transform: scale(1); }
    }
    
    @keyframes fadeOut {
        from { opacity: 1; transform: scale(1); }
        to { opacity: 0; transform: scale(0.8); }
    }
    
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);
