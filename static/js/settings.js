// Settings Page JavaScript - Modern Theme

// Global variables
let pendingChanges = {};
let restartNeeded = false;

// Theme management
function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateLogo(savedTheme);
    updateThemeSelector(savedTheme);
}

// Toggle sidebar on mobile
function toggleSidebar() {
    const sidebar = document.querySelector('.settings-sidebar');
    if (sidebar) {
        sidebar.classList.toggle('open');
    }
}

function selectTheme(theme) {
    // Update the theme
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    
    // Update logo
    updateLogo(theme);
    
    // Update theme selector UI
    updateThemeSelector(theme);
    
    // Show notification
    showNotification(`Theme changed to ${theme} mode`, 'success');
}

function updateThemeSelector(theme) {
    // Update active state on theme options
    const themeOptions = document.querySelectorAll('.theme-option');
    themeOptions.forEach(option => {
        if (option.getAttribute('data-theme') === theme) {
            option.classList.add('active');
        } else {
            option.classList.remove('active');
        }
    });
}

function updateLogo(theme) {
    const logo = document.getElementById('navLogo');
    if (logo) {
        const logoFile = theme === 'dark' ? 'light-logo.svg' : 'dark-logo.svg';
        logo.src = `/static/images/${logoFile}`;
    }
}

// Section management
function showSection(sectionName) {
    try {
        console.log('=== showSection called ===');
        console.log('Section name:', sectionName);

        // Save the active tab to localStorage
        localStorage.setItem('activeSettingsTab', sectionName);

        // Hide all sections
        const allSections = document.querySelectorAll('.content-section');
        console.log('Total sections found:', allSections.length);

        allSections.forEach(section => {
            section.classList.remove('active');
            console.log('Hiding section:', section.id);
        });

        // Remove active class from all sidebar items
        const allItems = document.querySelectorAll('.sidebar-item');
        allItems.forEach(item => {
            item.classList.remove('active');
        });

        // Show selected section
        const targetSectionId = sectionName + '-section';
        const targetSection = document.getElementById(targetSectionId);

        console.log('Looking for section:', targetSectionId);
        console.log('Target section found:', targetSection ? 'YES' : 'NO');

        if (targetSection) {
            targetSection.classList.add('active');
            console.log('Activated section:', targetSectionId);

            // Scroll to top of section (only if triggered by user click)
            if (typeof event !== 'undefined' && event) {
                targetSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        } else {
            console.error('Section not found:', targetSectionId);
            return; // Don't show error notification, just return silently
        }

        // Mark the corresponding sidebar item as active
        const sidebarItems = document.querySelectorAll('.sidebar-item');
        sidebarItems.forEach(item => {
            const itemSection = item.getAttribute('data-section');
            if (itemSection === sectionName) {
                item.classList.add('active');
            }
        });

        // Load logs if logs section is shown
        if (sectionName === 'logs' && typeof loadLogsList === 'function') {
            setTimeout(() => loadLogsList(), 100);
        }

        console.log('=== showSection complete ===');
    } catch (error) {
        console.error('Error in showSection:', error);
        // Don't show notification for expected undefined event errors
    }
}

// Toggle setting with animation feedback
function toggleSetting(element, settingName) {
    try {
        element.classList.toggle('active');
        const isActive = element.classList.contains('active');
        
        // Store the change
        pendingChanges[settingName] = isActive;
        
        // Check if restart is needed
        if (element.hasAttribute('data-restart')) {
            restartNeeded = true;
            const restartWarning = document.getElementById('restart-warning');
            if (restartWarning) {
                restartWarning.classList.add('show');
            }
        }
        
        console.log('Setting changed:', settingName, '=', isActive);
        
        // Add visual feedback with animation
        element.style.transform = 'scale(1.05)';
        setTimeout(() => {
            element.style.transform = '';
        }, 150);
        
        // Show notification for immediate feedback
        const statusText = isActive ? 'enabled' : 'disabled';
        showNotification(`${settingName.replace('_', ' ')} ${statusText}`, 'success');
    } catch (error) {
        console.warn('Error toggling setting:', error);
        showNotification('Error updating setting', 'error');
    }
}

// Save all settings
function saveAllSettings() {
    try {
        // Collect all input values
        document.querySelectorAll('.setting-input').forEach(input => {
            if (input.value !== input.defaultValue) {
                pendingChanges[input.id] = input.value;
                
                if (input.hasAttribute('data-restart')) {
                    restartNeeded = true;
                    const restartWarning = document.getElementById('restart-warning');
                    if (restartWarning) {
                        restartWarning.classList.add('show');
                    }
                }
            }
        });

        if (Object.keys(pendingChanges).length === 0) {
            showNotification('No changes to save', 'warning');
            return;
        }

        // Show loading state
        const saveButton = document.querySelector('.btn-primary');
        const originalText = saveButton.innerHTML;
        saveButton.innerHTML = '🔄 Saving...';
        saveButton.disabled = true;

        showNotification('Saving settings...', 'info');

        // Send changes to server
        fetch('/update_settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(pendingChanges)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('Settings saved successfully!', 'success');
                pendingChanges = {};
                
                if (data.restart_needed) {
                    const restartWarning = document.getElementById('restart-warning');
                    if (restartWarning) {
                        restartWarning.classList.add('show');
                    }
                }
            } else {
                showNotification('Error saving settings: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error saving settings', 'error');
        })
        .finally(() => {
            // Restore button state
            saveButton.innerHTML = originalText;
            saveButton.disabled = false;
        });
    } catch (error) {
        console.warn('Error saving settings:', error);
        showNotification('Error saving settings', 'error');
    }
}

// Restart server
function restartServer() {
    try {
        if (confirm('Are you sure you want to restart the server? This will disconnect all users.')) {
            const restartButton = event.target;
            const originalText = restartButton.innerHTML;
            restartButton.innerHTML = '🔄 Restarting...';
            restartButton.disabled = true;

            fetch('/restart_server', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotification('Server restart initiated. The page will reload automatically.', 'success');
                    setTimeout(() => {
                        window.location.reload();
                    }, 3000);
                } else {
                    showNotification('Error restarting server: ' + data.error, 'error');
                    restartButton.innerHTML = originalText;
                    restartButton.disabled = false;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Error restarting server', 'error');
                restartButton.innerHTML = originalText;
                restartButton.disabled = false;
            });
        }
    } catch (error) {
        console.warn('Error restarting server:', error);
        showNotification('Error restarting server', 'error');
    }
}

// Export settings
function exportSettings() {
    try {
        const exportButton = event.target;
        const originalText = exportButton.innerHTML;
        exportButton.innerHTML = '📤 Exporting...';
        exportButton.disabled = true;

        showNotification('Exporting settings...', 'info');

        fetch('/export_settings')
        .then(response => response.json())
        .then(data => {
            const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'haval_settings_' + new Date().toISOString().split('T')[0] + '.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            showNotification('Settings exported successfully!', 'success');
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error exporting settings', 'error');
        })
        .finally(() => {
            exportButton.innerHTML = originalText;
            exportButton.disabled = false;
        });
    } catch (error) {
        console.warn('Error exporting settings:', error);
        showNotification('Error exporting settings', 'error');
    }
}

// Import settings
function importSettings(input) {
    try {
        const file = input.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('config_file', file);

        showNotification('Importing settings...', 'info');

        fetch('/import_settings', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (response.ok) {
                showNotification('Settings imported successfully! The page will reload.', 'success');
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            } else {
                showNotification('Error importing settings', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error importing settings', 'error');
        });
    } catch (error) {
        console.warn('Error importing settings:', error);
        showNotification('Error importing settings', 'error');
    }
}

// Reset settings
function resetSettings() {
    try {
        if (confirm('Are you sure you want to reset all settings to defaults? This cannot be undone.')) {
            const resetButton = event.target;
            const originalText = resetButton.innerHTML;
            resetButton.innerHTML = '🔄 Resetting...';
            resetButton.disabled = true;

            fetch('/reset_settings', {
                method: 'POST'
            })
            .then(response => {
                if (response.ok) {
                    showNotification('Settings reset to defaults! The page will reload.', 'success');
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                } else {
                    showNotification('Error resetting settings', 'error');
                    resetButton.innerHTML = originalText;
                    resetButton.disabled = false;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Error resetting settings', 'error');
                resetButton.innerHTML = originalText;
                resetButton.disabled = false;
            });
        }
    } catch (error) {
        console.warn('Error resetting settings:', error);
        showNotification('Error resetting settings', 'error');
    }
}

// Show notification system (same as WhatsApp and Analysis)
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
        default: return 'linear-gradient(135deg, #6366f1, #8b5cf6)'; // Settings purple theme
    }
}

// Add notification animations to CSS if not already added
if (!document.getElementById('settings-notification-styles')) {
    const notificationStyles = document.createElement('style');
    notificationStyles.id = 'settings-notification-styles';
    notificationStyles.textContent = `
        @keyframes slideInRight {
            from { opacity: 0; transform: translateX(100px); }
            to { opacity: 1; transform: translateX(0); }
        }
        @keyframes slideOutRight {
            from { opacity: 1; transform: translateX(0); }
            to { opacity: 0; transform: translateX(100px); }
        }
    `;
    document.head.appendChild(notificationStyles);
}

// Update compression level display
function updateCompressionLevel() {
    try {
        const compressionLevel = document.getElementById('compression_level');
        const compressionDisplay = document.getElementById('compression_level_display');
        
        if (compressionLevel && compressionDisplay) {
            compressionLevel.addEventListener('input', function() {
                compressionDisplay.textContent = this.value;
            });
        }
    } catch (error) {
        console.warn('Error updating compression level:', error);
    }
}

// Auto-save on input change
function initializeAutoSave() {
    try {
        document.querySelectorAll('.setting-input').forEach(input => {
            input.addEventListener('change', function() {
                pendingChanges[this.id] = this.value;
                
                if (this.hasAttribute('data-restart')) {
                    restartNeeded = true;
                    const restartWarning = document.getElementById('restart-warning');
                    if (restartWarning) {
                        restartWarning.classList.add('show');
                    }
                }
                
                // Visual feedback
                this.style.borderColor = 'var(--primary-color)';
                setTimeout(() => {
                    this.style.borderColor = '';
                }, 1000);
            });
        });
    } catch (error) {
        console.warn('Error initializing auto-save:', error);
    }
}

// Keyboard shortcuts
function initializeKeyboardShortcuts() {
    try {
        document.addEventListener('keydown', (event) => {
            // Ctrl/Cmd + S to save
            if ((event.ctrlKey || event.metaKey) && event.key === 's') {
                event.preventDefault();
                saveAllSettings();
            }
            
            // Ctrl/Cmd + E to export
            if ((event.ctrlKey || event.metaKey) && event.key === 'e') {
                event.preventDefault();
                exportSettings();
            }
            
            // Escape to close any modals or reset focus
            if (event.key === 'Escape') {
                document.activeElement.blur();
            }
        });
    } catch (error) {
        console.warn('Error initializing keyboard shortcuts:', error);
    }
}

// Validate settings
function validateSettings() {
    try {
        const serverPort = document.getElementById('server_port');
        const sessionTimeout = document.getElementById('session_timeout');
        const cacheTimeout = document.getElementById('cache_timeout');
        
        if (serverPort) {
            serverPort.addEventListener('input', function() {
                const port = parseInt(this.value);
                if (port < 1 || port > 65535) {
                    this.setCustomValidity('Port must be between 1 and 65535');
                } else {
                    this.setCustomValidity('');
                }
            });
        }
        
        if (sessionTimeout) {
            sessionTimeout.addEventListener('input', function() {
                const timeout = parseInt(this.value);
                if (timeout < 300 || timeout > 86400) {
                    this.setCustomValidity('Session timeout must be between 300 and 86400 seconds');
                } else {
                    this.setCustomValidity('');
                }
            });
        }
        
        if (cacheTimeout) {
            cacheTimeout.addEventListener('input', function() {
                const timeout = parseInt(this.value);
                if (timeout < 60 || timeout > 3600) {
                    this.setCustomValidity('Cache timeout must be between 60 and 3600 seconds');
                } else {
                    this.setCustomValidity('');
                }
            });
        }
    } catch (error) {
        console.warn('Error validating settings:', error);
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

function goToWhatsApp() {
    window.location.href = '/view_whatsapp';
}

// Error handling
function handleError(error, context = 'Unknown') {
    console.warn(`Settings Error (${context}):`, error);
    showNotification(`Something went wrong in ${context}. Please try again.`, 'error');
}

// ============================================
// LOGGING MANAGEMENT FUNCTIONS
// ============================================

// Initialize logging management
function initializeLoggingManagement() {
    try {
        // Auto-refresh log status every 30 seconds
        setInterval(refreshLogStatus, 30000);
        
        console.log('Logging management initialized');
    } catch (error) {
        handleError(error, 'Logging Management Initialization');
    }
}

// Update individual logger level
function updateLoggerLevel(selectElement) {
    try {
        const loggerName = selectElement.getAttribute('data-logger');
        const level = selectElement.value;
        
        // Add loading state
        selectElement.disabled = true;
        selectElement.style.opacity = '0.6';
        
        showNotification(`Updating ${loggerName || 'root'} logger level...`, 'info');
        
        fetch('/api/set_logger_level', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                logger_name: loggerName,
                level: level
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, 'success');
                
                // Add visual feedback
                const loggerItem = selectElement.closest('.logger-item');
                if (loggerItem) {
                    loggerItem.classList.add('log-update-animation');
                    setTimeout(() => {
                        loggerItem.classList.remove('log-update-animation');
                    }, 500);
                }
            } else {
                showNotification('Error updating logger level: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error updating logger level', 'error');
        })
        .finally(() => {
            // Restore element state
            selectElement.disabled = false;
            selectElement.style.opacity = '';
        });
    } catch (error) {
        handleError(error, 'Logger Level Update');
    }
}

// Rotate log files
function rotateLogFiles() {
    try {
        const rotateButton = event.target;
        const originalText = rotateButton.innerHTML;
        rotateButton.innerHTML = '🔄 Rotating...';
        rotateButton.disabled = true;
        
        showNotification('Rotating log files...', 'info');
        
        fetch('/api/rotate_logs', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, 'success');
                refreshLogStatus(); // Refresh the log files list
            } else {
                showNotification('Error rotating logs: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error rotating logs', 'error');
        })
        .finally(() => {
            rotateButton.innerHTML = originalText;
            rotateButton.disabled = false;
        });
    } catch (error) {
        handleError(error, 'Log Rotation');
    }
}

// Cleanup old log files
function cleanupLogFiles() {
    try {
        const days = prompt('Enter number of days to keep (default: 30):', '30');
        if (days === null) return; // User cancelled
        
        const daysToKeep = parseInt(days) || 30;
        if (daysToKeep < 1) {
            showNotification('Days must be at least 1', 'error');
            return;
        }
        
        const cleanupButton = event.target;
        const originalText = cleanupButton.innerHTML;
        cleanupButton.innerHTML = '🧹 Cleaning...';
        cleanupButton.disabled = true;
        
        showNotification(`Cleaning up logs older than ${daysToKeep} days...`, 'info');
        
        fetch(`/api/cleanup_logs?days=${daysToKeep}`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, 'success');
                refreshLogStatus(); // Refresh the log files list
            } else {
                showNotification('Error cleaning up logs: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error cleaning up logs', 'error');
        })
        .finally(() => {
            cleanupButton.innerHTML = originalText;
            cleanupButton.disabled = false;
        });
    } catch (error) {
        handleError(error, 'Log Cleanup');
    }
}

// Refresh log status
function refreshLogStatus() {
    try {
        const refreshButton = document.querySelector('[onclick="refreshLogStatus()"]');
        if (refreshButton) {
            const originalText = refreshButton.innerHTML;
            refreshButton.innerHTML = '📊 Refreshing...';
            refreshButton.disabled = true;
        }
        
        fetch('/api/logging_status')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateLogFilesList(data.log_files);
                updateLogLevelsDisplay(data.log_levels);
                showNotification('Log status refreshed', 'success');
            } else {
                showNotification('Error refreshing log status: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error refreshing log status', 'error');
        })
        .finally(() => {
            if (refreshButton) {
                refreshButton.innerHTML = '📊 Refresh Status';
                refreshButton.disabled = false;
            }
        });
    } catch (error) {
        handleError(error, 'Log Status Refresh');
    }
}

// Update log files list
function updateLogFilesList(logFiles) {
    try {
        const logFilesList = document.getElementById('logFilesList');
        if (!logFilesList || !logFiles) return;
        
        logFilesList.innerHTML = '';
        
        Object.entries(logFiles).forEach(([filename, info]) => {
            const logFileItem = document.createElement('div');
            logFileItem.className = 'log-file-item';
            
            logFileItem.innerHTML = `
                <div class="log-file-info">
                    <div class="log-file-name">${filename}</div>
                    <div class="log-file-details">
                        ${info.exists ? 
                            `Size: ${info.size_mb} MB | Modified: ${info.modified.substring(0, 19)}` : 
                            'File not found'
                        }
                    </div>
                </div>
                <div class="log-file-actions">
                    ${info.exists ? 
                        `<button class="btn btn-sm btn-secondary" onclick="downloadLogFile('${filename}')">
                            📥 Download
                        </button>` : 
                        ''
                    }
                </div>
            `;
            
            logFilesList.appendChild(logFileItem);
        });
    } catch (error) {
        handleError(error, 'Log Files List Update');
    }
}

// Update log levels display
function updateLogLevelsDisplay(logLevels) {
    try {
        if (!logLevels) return;
        
        Object.entries(logLevels).forEach(([loggerName, level]) => {
            const selectElement = document.querySelector(`[data-logger="${loggerName}"]`);
            if (selectElement && selectElement.value !== level) {
                selectElement.value = level;
                
                // Add visual feedback for change
                const loggerItem = selectElement.closest('.logger-item');
                if (loggerItem) {
                    loggerItem.classList.add('log-update-animation');
                    setTimeout(() => {
                        loggerItem.classList.remove('log-update-animation');
                    }, 500);
                }
            }
        });
    } catch (error) {
        handleError(error, 'Log Levels Display Update');
    }
}

// Download log file
function downloadLogFile(filename) {
    try {
        const downloadButton = event.target;
        const originalText = downloadButton.innerHTML;
        downloadButton.innerHTML = '📥 Downloading...';
        downloadButton.disabled = true;
        
        showNotification(`Downloading ${filename}...`, 'info');
        
        // Create a temporary link to download the file
        const downloadUrl = `/api/download_log?filename=${encodeURIComponent(filename)}`;
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        showNotification(`${filename} download started`, 'success');
        
        // Restore button after a short delay
        setTimeout(() => {
            downloadButton.innerHTML = originalText;
            downloadButton.disabled = false;
        }, 1000);
        
    } catch (error) {
        handleError(error, 'Log File Download');
        
        // Restore button on error
        const downloadButton = event.target;
        if (downloadButton) {
            downloadButton.innerHTML = '📥 Download';
            downloadButton.disabled = false;
        }
    }
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

// Initialize everything when DOM is ready
function initializeSettings() {
    try {
        loadTheme();
        updateCompressionLevel();
        initializeAutoSave();
        initializeKeyboardShortcuts();
        validateSettings();
        initializeLoggingManagement();

        // Restore active tab from localStorage
        const savedTab = localStorage.getItem('activeSettingsTab');
        if (savedTab) {
            console.log('Restoring saved tab:', savedTab);
            showSection(savedTab);
        }

        // Remove any existing flash messages after 10 seconds
        setTimeout(() => {
            const flashMessages = document.querySelectorAll('.flash-message');
            flashMessages.forEach(msg => {
                if (msg.parentNode) {
                    msg.remove();
                }
            });
        }, 10000);

        console.log('Settings page initialized successfully');
    } catch (error) {
        handleError(error, 'Initialization');
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeSettings);
} else {
    initializeSettings();
}