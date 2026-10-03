/**
 * Settings Page - Data Collection JavaScript
 * Handles PakWheels scraping and WATI data fetching from the settings page
 */

// Initialize data collection functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeDataCollection();
});

function initializeDataCollection() {
    console.log('🔧 Initializing data collection functionality');

    // PakWheels scraping button
    const pakWheelsBtn = document.getElementById('startPakWheelsScraping');
    if (pakWheelsBtn) {
        pakWheelsBtn.addEventListener('click', startPakWheelsScraping);
    }

    // Manual PakWheels URL scraping
    const manualUrlInput = document.getElementById('manualPakWheelsUrl');
    const scrapeManualBtn = document.getElementById('scrapeManualUrl');
    if (manualUrlInput && scrapeManualBtn) {
        // Real-time validation on input
        manualUrlInput.addEventListener('input', validateManualUrl);
        // Scrape button click
        scrapeManualBtn.addEventListener('click', scrapeManualUrl);
    }

    // Reddit scraping button
    const redditBtn = document.getElementById('startRedditScraping');
    if (redditBtn) {
        redditBtn.addEventListener('click', startRedditScraping);
    }

    // Manual Reddit URL scraping
    const manualRedditUrlInput = document.getElementById('manualRedditUrl');
    const scrapeManualRedditBtn = document.getElementById('scrapeManualRedditUrl');
    if (manualRedditUrlInput && scrapeManualRedditBtn) {
        // Real-time validation on input
        manualRedditUrlInput.addEventListener('input', validateManualRedditUrl);
        // Scrape button click
        scrapeManualRedditBtn.addEventListener('click', scrapeManualRedditUrl);
    }

    // WATI fetching button
    const watiBtn = document.getElementById('startWatiFetching');
    if (watiBtn) {
        watiBtn.addEventListener('click', startWatiFetching);
    }

    // Initialize Lucid scraping
    initializeLucidScraping();

    // Update status on page load
    updateCollectionStatus();

    // Set up periodic status updates
    setInterval(updateCollectionStatus, 30000); // Update every 30 seconds
}

function startPakWheelsScraping() {
    const postsInput = document.getElementById('pakWheelsPosts');
    const posts = parseInt(postsInput.value);

    // Validate input
    if (!posts || posts < 10 || posts > 10000) {
        showToast('Please enter a valid number of posts (10-10,000)', 'error');
        return;
    }

    console.log('🚀 Starting PakWheels scraping for', posts, 'posts');

    // Disable button and show loading state
    const btn = document.getElementById('startPakWheelsScraping');
    btn.disabled = true;
    btn.innerHTML = '🔄 Starting Scraping...';

    // Update status
    updateStatusCard('pakwheelsStatus', 'Processing', 'processing');

    // Show progress popup
    showScrapingProgress('PakWheels', posts);

    // Make API call to start scraping
    fetch('/scrape_single_topic', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: new URLSearchParams({
            max_posts: posts.toString(),
            fetch_mode: 'latest'
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const count = data.posts_scraped || posts;
            updateScrapingProgress(`Successfully scraped ${count} posts!`, 'success');
            updateStatusCard('pakwheelsStatus', 'Ready', 'ready');

            // Auto-close the popup after showing success message
            setTimeout(() => {
                hideScrapingProgress();
                showToast(`PakWheels scraping completed: ${count} posts`, 'success');
            }, 2000);
        } else {
            updateScrapingProgress('Error: ' + (data.error || 'Unknown error'), 'error');
            updateStatusCard('pakwheelsStatus', 'Error', 'error');
        }
    })
    .catch(error => {
        console.error('❌ PakWheels scraping error:', error);
        updateScrapingProgress('Error: ' + error.message, 'error');
        updateStatusCard('pakwheelsStatus', 'Error', 'error');
    })
    .finally(() => {
        // Re-enable button
        btn.disabled = false;
        btn.innerHTML = '🔍 Start PakWheels Scraping';
    });
}

function startWatiFetching() {
    const daysSelect = document.getElementById('watiDays');
    const days = daysSelect.value;

    console.log('📱 Starting WATI data fetch for', days, 'days');

    // Disable button and show loading state
    const btn = document.getElementById('startWatiFetching');
    btn.disabled = true;
    btn.innerHTML = '🔄 Fetching Data...';

    // Update status
    updateStatusCard('watiStatus', 'Processing', 'processing');

    // Show progress popup
    showScrapingProgress('WATI', `${days} days`);

    // Start progress monitoring immediately
    startWatiProgressMonitoring();

    // Make API call to fetch WATI data
    fetch('/fetch_wati_data', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            period: `${days}d`
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const count = data.messages_imported || 0;
            updateScrapingProgress(`Successfully fetched ${count} WhatsApp messages!`, 'success');
            updateStatusCard('watiStatus', 'Ready', 'ready');

            // Auto-close the popup after showing success message
            setTimeout(() => {
                hideScrapingProgress();
                showToast(`WATI data fetch completed: ${count} messages`, 'success');
            }, 2000);
        } else {
            updateScrapingProgress('Error: ' + (data.error || 'Unknown error'), 'error');
            updateStatusCard('watiStatus', 'Error', 'error');
        }
    })
    .catch(error => {
        console.error('❌ WATI fetch error:', error);
        updateScrapingProgress('Error: ' + error.message, 'error');
        updateStatusCard('watiStatus', 'Error', 'error');
    })
    .finally(() => {
        // Re-enable button
        btn.disabled = false;
        btn.innerHTML = '📱 Fetch WATI Data';
    });
}

function updateStatusCard(statusId, text, type) {
    const statusEl = document.getElementById(statusId);
    if (statusEl) {
        statusEl.textContent = text;
        statusEl.className = `status-value ${type}`;
    }
}

function updateCollectionStatus() {
    // Check pipeline status
    fetch('/api/pipeline-status')
        .then(response => response.json())
        .then(data => {
            const status = data.status || 'unknown';
            let statusText = 'Unknown';
            let statusType = 'error';
            
            switch (status) {
                case 'ready':
                    statusText = 'Ready';
                    statusType = 'ready';
                    break;
                case 'processing':
                case 'enriching':
                case 'indexing':
                    statusText = 'Processing';
                    statusType = 'processing';
                    break;
                case 'error':
                case 'failed':
                    statusText = 'Error';
                    statusType = 'error';
                    break;
                default:
                    statusText = status.charAt(0).toUpperCase() + status.slice(1);
                    statusType = 'processing';
            }
            
            updateStatusCard('pipelineStatus', statusText, statusType);
        })
        .catch(error => {
            console.error('Error checking pipeline status:', error);
            updateStatusCard('pipelineStatus', 'Error', 'error');
        });
}

// Progress Popup Functions
function showScrapingProgress(source, count) {
    // Remove any existing progress popup
    const existingPopup = document.getElementById('scrapingProgressPopup');
    if (existingPopup) {
        existingPopup.remove();
    }
    
    // Create progress popup
    const progressPopup = document.createElement('div');
    progressPopup.id = 'scrapingProgressPopup';
    progressPopup.className = 'scraping-popup active';
    progressPopup.style.zIndex = '3000';
    
    progressPopup.innerHTML = `
        <div class="popup-content">
            <div class="popup-header">
                <div class="popup-icon ${source.toLowerCase()}">🚀</div>
                <div class="popup-title">Collecting ${source} Data</div>
            </div>
            <div class="popup-body">
                <div class="progress-container">
                    <div class="progress-status" id="progressStatus">
                        Starting data collection for ${count}...
                    </div>
                    <div class="progress-bar-container">
                        <div class="progress-bar" id="progressBar">
                            <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="popup-actions">
                <button class="popup-btn popup-btn-cancel" onclick="hideScrapingProgress()" disabled>
                    Processing...
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(progressPopup);
}

function updateScrapingProgress(message, type = 'info') {
    const statusEl = document.getElementById('progressStatus');

    if (statusEl) {
        statusEl.textContent = message;
        statusEl.className = `progress-status ${type}`;
    }

    if (type === 'success') {
        // Update close button for success states
        const closeBtn = document.querySelector('#scrapingProgressPopup .popup-btn-cancel');
        if (closeBtn) {
            closeBtn.textContent = 'Close';
            closeBtn.disabled = false;
            closeBtn.onclick = () => {
                hideScrapingProgress();
            };
        }
    } else if (type === 'error') {
        // Enable close button for errors
        const closeBtn = document.querySelector('#scrapingProgressPopup .popup-btn-cancel');
        if (closeBtn) {
            closeBtn.textContent = 'Close';
            closeBtn.disabled = false;
            closeBtn.onclick = () => {
                hideScrapingProgress();
            };
        }
    }
}

function hideScrapingProgress() {
    const progressPopup = document.getElementById('scrapingProgressPopup');
    if (progressPopup) {
        progressPopup.remove();
    }
}

function updateProgressBar(percentage) {
    const progressFill = document.getElementById('progressFill');
    if (progressFill) {
        progressFill.style.width = `${Math.min(percentage, 100)}%`;
    }
}

// Monitor WATI progress by checking logs
function startWatiProgressMonitoring() {
    let checkCount = 0;
    const maxChecks = 200; // 10 minutes max (3 second intervals)
    
    const checkProgress = () => {
        checkCount++;
        
        // Try to get progress from a logs endpoint (if available)
        fetch('/api/wati/progress')
            .then(response => {
                if (response.ok) {
                    return response.json();
                } else {
                    throw new Error('Progress endpoint not available');
                }
            })
            .then(data => {
                if (data.status === 'processing' && data.progress) {
                    const { current, total, contact_name, contact_phone } = data.progress;
                    updateScrapingProgress(
                        `Processing ${current}/${total}: ${contact_name} (${contact_phone})`, 
                        'info'
                    );
                    
                    // Update progress bar
                    if (total > 0) {
                        const percentage = Math.round((current / total) * 90); // Max 90% until complete
                        updateProgressBar(percentage);
                    }
                    
                    // Continue monitoring
                    if (checkCount < maxChecks) {
                        setTimeout(checkProgress, 3000); // Check every 3 seconds
                    }
                } else if (data.status === 'completed') {
                    // Process completed
                    updateScrapingProgress('WATI data fetch completed!', 'success');
                    updateProgressBar(100);
                } else if (data.status === 'error') {
                    updateScrapingProgress('WATI fetch encountered an error', 'error');
                }
            })
            .catch(error => {
                // Progress endpoint not available, continue with basic monitoring
                if (checkCount < maxChecks) {
                    setTimeout(checkProgress, 5000); // Check every 5 seconds
                }
            });
    };
    
    // Start monitoring after a short delay
    setTimeout(checkProgress, 2000);
}

function startEngineMonitoring() {
    updateScrapingProgress('Starting AI pipeline processing...', 'info');
    updateStatusCard('pipelineStatus', 'Processing', 'processing');
    
    let checkCount = 0;
    const maxChecks = 120; // 10 minutes max (5 second intervals)
    
    const checkEngine = () => {
        checkCount++;
        
        fetch('/api/pipeline-status')
            .then(response => response.json())
            .then(data => {
                const status = data.status || 'unknown';
                
                if (status === 'completed' || status === 'ready') {
                    // Pipeline completed successfully
                    updateScrapingProgress('✅ AI Pipeline completed successfully!', 'success');
                    updateStatusCard('pipelineStatus', 'Ready', 'ready');
                    updateProgressBar(100);
                    
                    // Show completion message and auto-close
                    setTimeout(() => {
                        updateScrapingProgress('🎉 Process complete! Data is now available.', 'success');
                        
                        // Close popup after showing completion message
                        setTimeout(() => {
                            hideScrapingProgress();
                            showToast('Data processing completed successfully!');
                        }, 2000);
                    }, 1000);
                    
                } else if (status === 'processing') {
                    // Still processing
                    updateScrapingProgress(`🔄 Processing data... (${checkCount}/${maxChecks})`, 'info');
                    setTimeout(checkEngine, 5000); // Check every 5 seconds during processing
                    
                } else if (status === 'enriching') {
                    updateScrapingProgress(`🤖 Enriching data with AI analysis... (${checkCount}/${maxChecks})`, 'info');
                    setTimeout(checkEngine, 5000);
                    
                } else if (status === 'indexing') {
                    updateScrapingProgress(`📚 Building vector database... (${checkCount}/${maxChecks})`, 'info');
                    setTimeout(checkEngine, 5000);
                    
                } else if (status === 'error' || status === 'failed') {
                    updateScrapingProgress('❌ AI pipeline encountered an error', 'error');
                    updateStatusCard('pipelineStatus', 'Error', 'error');
                    
                } else if (checkCount >= maxChecks) {
                    updateScrapingProgress('⏰ Pipeline taking longer than expected. Check logs for details.', 'error');
                    updateStatusCard('pipelineStatus', 'Error', 'error');
                    
                } else {
                    // Continue monitoring with unknown status
                    updateScrapingProgress(`⏳ AI engine status: ${status}... (${checkCount}/${maxChecks})`, 'info');
                    setTimeout(checkEngine, 5000); // Check every 5 seconds for unknown status
                }
            })
            .catch(error => {
                console.error('Error checking pipeline status:', error);
                if (checkCount < maxChecks) {
                    updateScrapingProgress(`🔍 Checking pipeline status... (${checkCount}/${maxChecks})`, 'info');
                    setTimeout(checkEngine, 5000);
                } else {
                    updateScrapingProgress('❌ Could not check pipeline status. Please check manually.', 'error');
                    updateStatusCard('pipelineStatus', 'Error', 'error');
                }
            });
    };
    
    // Start monitoring after a short delay
    setTimeout(checkEngine, 2000);
}

// Toast notification function
function showToast(message, type = 'info') {
    // Remove existing toast
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }
    
    // Create toast
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    // Style the toast
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#6366f1'};
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 10000;
        font-weight: 500;
        max-width: 400px;
        word-wrap: break-word;
        animation: slideInRight 0.3s ease;
    `;
    
    document.body.appendChild(toast);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (toast.parentNode) {
            toast.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }
    }, 5000);
}

// Add CSS animations for toast
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// ============================================================================
// REDDIT SCRAPING FUNCTIONS
// ============================================================================

function startRedditScraping() {
    const postsInput = document.getElementById('redditPosts');
    const posts = parseInt(postsInput.value);

    // Validate input
    if (!posts || posts < 10 || posts > 10000) {
        showToast('Please enter a valid number of posts (10-10,000)', 'error');
        return;
    }

    console.log('🚀 Starting Reddit scraping for', posts, 'posts');

    // Disable button and show loading state
    const btn = document.getElementById('startRedditScraping');
    btn.disabled = true;
    btn.innerHTML = '🔄 Starting Scraping...';

    // Update status
    updateStatusCard('redditStatus', 'Processing', 'processing');

    // Show progress popup
    showScrapingProgress('Reddit', posts);

    // Make API call to start scraping
    fetch('/scrape_reddit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: new URLSearchParams({
            max_posts: posts.toString(),
            fetch_mode: 'latest'
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const count = data.posts_scraped || posts;
            updateScrapingProgress(`Successfully scraped ${count} posts!`, 'success');
            updateStatusCard('redditStatus', 'Ready', 'ready');

            // Auto-close the popup after showing success message
            setTimeout(() => {
                hideScrapingProgress();
                showToast(`Reddit scraping completed: ${count} posts`, 'success');
            }, 2000);
        } else {
            updateScrapingProgress('Error: ' + (data.error || 'Unknown error'), 'error');
            updateStatusCard('redditStatus', 'Error', 'error');
        }
    })
    .catch(error => {
        console.error('❌ Reddit scraping error:', error);
        updateScrapingProgress('Error: ' + error.message, 'error');
        updateStatusCard('redditStatus', 'Error', 'error');
    })
    .finally(() => {
        // Re-enable button
        btn.disabled = false;
        btn.innerHTML = '🔍 Start Reddit Scraping';
    });
}

// ============================================================================
// Manual URL Scraping Functions
// ============================================================================

function validateManualUrl() {
    const urlInput = document.getElementById('manualPakWheelsUrl');
    const messageDiv = document.getElementById('urlValidationMessage');
    const scrapeBtn = document.getElementById('scrapeManualUrl');

    const url = urlInput.value.trim();

    // Empty URL - clear validation
    if (!url) {
        messageDiv.textContent = '';
        messageDiv.style.color = '';
        urlInput.style.borderColor = '';
        scrapeBtn.disabled = false;
        return;
    }

    // Validate URL format
    const pattern = /^https:\/\/www\.pakwheels\.com\/forums\/t\/[a-z0-9\-]+\/\d+$/;
    const hasPostNumber = /\/\d+\/\d+$/.test(url);

    if (!url.startsWith('https://www.pakwheels.com/forums/t/')) {
        messageDiv.textContent = '❌ URL must start with https://www.pakwheels.com/forums/t/';
        messageDiv.style.color = '#e74c3c';
        urlInput.style.borderColor = '#e74c3c';
        scrapeBtn.disabled = true;
        return;
    }

    if (hasPostNumber) {
        messageDiv.textContent = '❌ Remove specific post numbers (e.g., /972). Use the base thread URL only.';
        messageDiv.style.color = '#e74c3c';
        urlInput.style.borderColor = '#e74c3c';
        scrapeBtn.disabled = true;
        return;
    }

    if (!pattern.test(url)) {
        messageDiv.textContent = '❌ Invalid format. Expected: https://www.pakwheels.com/forums/t/topic-name/123456';
        messageDiv.style.color = '#e74c3c';
        urlInput.style.borderColor = '#e74c3c';
        scrapeBtn.disabled = true;
        return;
    }

    // Valid URL
    messageDiv.textContent = '✅ Valid URL format';
    messageDiv.style.color = '#27ae60';
    urlInput.style.borderColor = '#27ae60';
    scrapeBtn.disabled = false;
}

function scrapeManualUrl() {
    const urlInput = document.getElementById('manualPakWheelsUrl');
    const scrapeBtn = document.getElementById('scrapeManualUrl');
    const postsInput = document.getElementById('pakWheelsPosts');

    const url = urlInput.value.trim();
    const posts = parseInt(postsInput.value);

    // Validate URL
    if (!url) {
        showToast('Please enter a PakWheels URL', 'error');
        return;
    }

    // Validate posts count
    if (!posts || posts < 10 || posts > 10000) {
        showToast('Please set a valid number of posts (10-10,000) above', 'error');
        return;
    }

    console.log('🚀 Starting manual URL scraping:', url);

    // Disable button and show loading state
    scrapeBtn.disabled = true;
    scrapeBtn.innerHTML = '⏳ Scraping...';

    // Prepare form data
    const formData = new FormData();
    formData.append('manual_url', url);
    formData.append('max_posts', posts);
    formData.append('fetch_mode', 'latest');

    // Start scraping
    fetch('/scrape_manual_url', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('✅ Manual URL scraping completed:', data);
            showToast(`Successfully scraped ${data.posts_scraped} posts in ${data.elapsed_time}s`, 'success');
            showToast('Pipeline processing completed. You can now ask questions!', 'success');

            // Clear input after successful scrape
            urlInput.value = '';
            document.getElementById('urlValidationMessage').textContent = '';
            urlInput.style.borderColor = '';

            // Update status
            updateCollectionStatus();
        } else {
            console.error('❌ Manual URL scraping failed:', data.error);

            // Handle specific error types
            if (data.validation_error) {
                showToast('Validation Error: ' + data.error, 'error');
            } else if (data.already_scraped) {
                showToast('This URL has already been scraped', 'warning');
            } else {
                showToast('Scraping failed: ' + data.error, 'error');
            }
        }
    })
    .catch(error => {
        console.error('❌ Manual URL scraping error:', error);
        showToast('Error: ' + error.message, 'error');
    })
    .finally(() => {
        // Re-enable button
        scrapeBtn.disabled = false;
        scrapeBtn.innerHTML = '🚀 Scrape URL';
    });
}

// ============================================================================
// MANUAL REDDIT URL SCRAPING FUNCTIONS
// ============================================================================

function validateManualRedditUrl() {
    const urlInput = document.getElementById('manualRedditUrl');
    const messageDiv = document.getElementById('redditUrlValidationMessage');
    const scrapeBtn = document.getElementById('scrapeManualRedditUrl');

    const url = urlInput.value.trim();

    // Empty URL - clear validation
    if (!url) {
        messageDiv.textContent = '';
        messageDiv.style.color = '';
        urlInput.style.borderColor = '';
        scrapeBtn.disabled = false;
        return;
    }

    // Validate Reddit URL formats
    const subredditPattern = /^r\/[a-zA-Z0-9_]+$/;
    const subredditUrlPattern = /^https?:\/\/(www\.)?reddit\.com\/r\/[a-zA-Z0-9_]+\/?$/;
    const postUrlPattern = /^https?:\/\/(www\.)?reddit\.com\/r\/[a-zA-Z0-9_]+\/comments\/[a-zA-Z0-9_]+/;

    if (!url.startsWith('https://www.reddit.com/r/') && !url.startsWith('https://reddit.com/r/') && !subredditPattern.test(url)) {
        messageDiv.textContent = '❌ URL must be a Reddit URL (r/subreddit or https://reddit.com/r/...)';
        messageDiv.style.color = '#e74c3c';
        urlInput.style.borderColor = '#e74c3c';
        scrapeBtn.disabled = true;
        return;
    }

    if (subredditPattern.test(url) || subredditUrlPattern.test(url) || postUrlPattern.test(url)) {
        // Valid Reddit URL
        messageDiv.textContent = '✅ Valid Reddit URL format';
        messageDiv.style.color = '#27ae60';
        urlInput.style.borderColor = '#27ae60';
        scrapeBtn.disabled = false;
    } else {
        messageDiv.textContent = '❌ Invalid format. Expected: r/subreddit or https://reddit.com/r/subreddit/...';
        messageDiv.style.color = '#e74c3c';
        urlInput.style.borderColor = '#e74c3c';
        scrapeBtn.disabled = true;
    }
}

function scrapeManualRedditUrl() {
    const urlInput = document.getElementById('manualRedditUrl');
    const scrapeBtn = document.getElementById('scrapeManualRedditUrl');
    const postsInput = document.getElementById('redditPosts');

    const url = urlInput.value.trim();
    const posts = parseInt(postsInput.value);

    // Validate URL
    if (!url) {
        showToast('Please enter a Reddit URL', 'error');
        return;
    }

    // Validate posts count
    if (!posts || posts < 10 || posts > 10000) {
        showToast('Please set a valid number of posts (10-10,000) above', 'error');
        return;
    }

    console.log('🚀 Starting manual Reddit URL scraping:', url);

    // Disable button and show loading state
    scrapeBtn.disabled = true;
    scrapeBtn.innerHTML = '⏳ Scraping...';

    // Prepare form data
    const formData = new FormData();
    formData.append('manual_url', url);
    formData.append('max_posts', posts);
    formData.append('fetch_mode', 'latest');

    // Start scraping
    fetch('/scrape_manual_reddit_url', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('✅ Manual Reddit URL scraping completed:', data);
            showToast(`Successfully scraped ${data.posts_scraped} posts in ${data.elapsed_time}s`, 'success');
            showToast('Pipeline processing completed. You can now ask questions!', 'success');

            // Clear input after successful scrape
            urlInput.value = '';
            document.getElementById('redditUrlValidationMessage').textContent = '';
            urlInput.style.borderColor = '';

            // Update status
            updateCollectionStatus();
        } else {
            console.error('❌ Manual Reddit URL scraping failed:', data.error);

            // Handle specific error types
            if (data.validation_error) {
                showToast('Validation Error: ' + data.error, 'error');
            } else if (data.already_scraped) {
                showToast('This URL has already been scraped', 'warning');
            } else {
                showToast('Scraping failed: ' + data.error, 'error');
            }
        }
    })
    .catch(error => {
        console.error('❌ Manual Reddit URL scraping error:', error);
        showToast('Error: ' + error.message, 'error');
    })
    .finally(() => {
        // Re-enable button
        scrapeBtn.disabled = false;
        scrapeBtn.innerHTML = '🚀 Scrape URL';
    });
}


// ============================================================================
// LUCID FORUM SCRAPING FUNCTIONS
// ============================================================================

function initializeLucidScraping() {
    console.log('🔧 Initializing Lucid forum scraping functionality');

    // Lucid scraping button
    const lucidBtn = document.getElementById('startLucidScraping');
    if (lucidBtn) {
        lucidBtn.addEventListener('click', startLucidScraping);
    }

    // Manual Lucid URL scraping
    const manualLucidUrlInput = document.getElementById('manualLucidUrl');
    const scrapeManualLucidBtn = document.getElementById('scrapeManualLucidUrl');
    if (manualLucidUrlInput && scrapeManualLucidBtn) {
        // Real-time validation on input
        manualLucidUrlInput.addEventListener('input', validateManualLucidUrl);
        // Scrape button click
        scrapeManualLucidBtn.addEventListener('click', scrapeManualLucidUrl);
    }
}

function startLucidScraping() {
    const baseUrlInput = document.getElementById('lucidBaseUrl');
    const maxThreadsInput = document.getElementById('lucidMaxThreads');
    const maxPostsInput = document.getElementById('lucidMaxPosts');

    const baseUrl = baseUrlInput.value.trim();
    const maxThreads = parseInt(maxThreadsInput.value);
    const maxPosts = parseInt(maxPostsInput.value);

    // Validate inputs
    if (!baseUrl) {
        showToast('Please enter a Lucid forum URL', 'error');
        return;
    }

    if (!maxThreads || maxThreads < 1 || maxThreads > 1000) {
        showToast('Please enter a valid number of threads (1-1,000)', 'error');
        return;
    }

    if (!maxPosts || maxPosts < 10 || maxPosts > 10000) {
        showToast('Please enter a valid number of posts per thread (10-10,000)', 'error');
        return;
    }

    console.log('🚀 Starting Lucid forum scraping:', {
        baseUrl,
        maxThreads,
        maxPosts
    });

    // Disable button and show loading state
    const btn = document.getElementById('startLucidScraping');
    btn.disabled = true;
    btn.innerHTML = '🔄 Starting Scraping...';

    // Show progress popup
    showScrapingProgress('Lucid Forum', `${maxThreads} threads`);

    // Make API call to start scraping
    fetch('/scrape_lucid', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: new URLSearchParams({
            base_url: baseUrl,
            max_threads: maxThreads.toString(),
            max_posts: maxPosts.toString()
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const postsCount = data.posts_scraped || (maxThreads * maxPosts);
            
            updateScrapingProgress(`Successfully scraped ${postsCount} posts! Processing with AI...`, 'success');
            
            // Start monitoring pipeline
            setTimeout(() => {
                startEngineMonitoring();
            }, 1000);
        } else {
            updateScrapingProgress('Error: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('❌ Lucid forum scraping error:', error);
        updateScrapingProgress('Error: ' + error.message, 'error');
    })
    .finally(() => {
        // Re-enable button
        btn.disabled = false;
        btn.innerHTML = '🚀 Start Scraping';
    });
}

function validateManualLucidUrl() {
    const urlInput = document.getElementById('manualLucidUrl');
    const messageDiv = document.getElementById('lucidUrlValidationMessage');
    const scrapeBtn = document.getElementById('scrapeManualLucidUrl');

    const url = urlInput.value.trim();

    // Empty URL - clear validation
    if (!url) {
        messageDiv.textContent = '';
        messageDiv.style.color = '';
        urlInput.style.borderColor = '';
        scrapeBtn.disabled = false;
        return;
    }

    // Validate Lucid URL format
    const lucidPattern = /^https:\/\/lucidowners\.com\/threads\/[a-z0-9\-]+/i;

    if (!url.startsWith('https://lucidowners.com/threads/')) {
        messageDiv.textContent = '❌ URL must start with https://lucidowners.com/threads/';
        messageDiv.style.color = '#e74c3c';
        urlInput.style.borderColor = '#e74c3c';
        scrapeBtn.disabled = true;
        return;
    }

    if (!lucidPattern.test(url)) {
        messageDiv.textContent = '❌ Invalid format. Expected: https://lucidowners.com/threads/thread-name';
        messageDiv.style.color = '#e74c3c';
        urlInput.style.borderColor = '#e74c3c';
        scrapeBtn.disabled = true;
        return;
    }

    // Valid URL
    messageDiv.textContent = '✅ Valid Lucid thread URL';
    messageDiv.style.color = '#27ae60';
    urlInput.style.borderColor = '#27ae60';
    scrapeBtn.disabled = false;
}

function scrapeManualLucidUrl() {
    const urlInput = document.getElementById('manualLucidUrl');
    const maxPostsInput = document.getElementById('manualLucidMaxPosts');
    const scrapeBtn = document.getElementById('scrapeManualLucidUrl');

    const url = urlInput.value.trim();
    const maxPosts = parseInt(maxPostsInput.value);

    // Validate URL
    if (!url) {
        showToast('Please enter a Lucid thread URL', 'error');
        return;
    }

    // Validate posts count
    if (!maxPosts || maxPosts < 10 || maxPosts > 10000) {
        showToast('Please set a valid number of posts (10-10,000)', 'error');
        return;
    }

    console.log('🚀 Starting manual Lucid URL scraping:', url);

    // Disable button and show loading state
    scrapeBtn.disabled = true;
    scrapeBtn.innerHTML = '⏳ Scraping...';

    // Prepare form data
    const formData = new FormData();
    formData.append('thread_url', url);
    formData.append('max_posts', maxPosts);

    // Start scraping
    fetch('/scrape_lucid_thread', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('✅ Manual Lucid URL scraping completed:', data);
            showToast(`Successfully scraped ${data.posts_scraped} posts in ${data.elapsed_time}s`, 'success');
            showToast('Pipeline processing completed. You can now ask questions!', 'success');

            // Clear input after successful scrape
            urlInput.value = '';
            maxPostsInput.value = '50';
            document.getElementById('lucidUrlValidationMessage').textContent = '';
            urlInput.style.borderColor = '';

            // Update status
            updateCollectionStatus();
        } else {
            console.error('❌ Manual Lucid URL scraping failed:', data.error);

            // Handle specific error types
            if (data.validation_error) {
                showToast('Validation Error: ' + data.error, 'error');
            } else if (data.already_scraped) {
                showToast('This thread has already been scraped', 'warning');
            } else {
                showToast('Scraping failed: ' + data.error, 'error');
            }
        }
    })
    .catch(error => {
        console.error('❌ Manual Lucid URL scraping error:', error);
        showToast('Error: ' + error.message, 'error');
    })
    .finally(() => {
        // Re-enable button
        scrapeBtn.disabled = false;
        scrapeBtn.innerHTML = '🚀 Scrape Thread';
    });
}

// Reddit Lucid Scraping Functions
function initializeRedditLucidScraping() {
    const startBtn = document.getElementById('startRedditLucidScraping');
    if (startBtn) {
        startBtn.addEventListener('click', startRedditLucidScraping);
    }

    // Manual URL scraping
    const manualUrlInput = document.getElementById('manualRedditLucidUrl');
    const scrapeManualBtn = document.getElementById('scrapeManualRedditLucidUrl');
    
    if (manualUrlInput) {
        manualUrlInput.addEventListener('input', validateManualRedditLucidUrl);
    }
    
    if (scrapeManualBtn) {
        scrapeManualBtn.addEventListener('click', scrapeManualRedditLucidUrl);
    }
}

function startRedditLucidScraping() {
    const postsInput = document.getElementById('redditLucidPosts');
    const delayInput = document.getElementById('redditLucidDelay');
    const startBtn = document.getElementById('startRedditLucidScraping');
    const progressDiv = document.getElementById('redditLucidScrapingProgress');

    const maxPosts = parseInt(postsInput.value);
    const delay = parseInt(delayInput.value);

    // Validate inputs
    if (!maxPosts || maxPosts < 10 || maxPosts > 10000) {
        showToast('Please set a valid number of posts (10-10,000)', 'error');
        return;
    }

    if (!delay || delay < 1 || delay > 60) {
        showToast('Please set a valid delay (1-60 seconds)', 'error');
        return;
    }

    console.log('🚀 Starting Reddit Lucid scraping:', { maxPosts, delay });

    // Disable button and show progress
    startBtn.disabled = true;
    startBtn.innerHTML = '⏳ Scraping...';
    progressDiv.style.display = 'block';

    // Prepare form data
    const formData = new FormData();
    formData.append('max_posts', maxPosts);
    formData.append('delay', delay);

    // Start scraping
    fetch('/scrape_reddit_lucid', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('✅ Reddit Lucid scraping completed:', data);
            
            // Show detailed results
            let message = `Successfully scraped ${data.posts_scraped} posts in ${data.elapsed_time}s\n`;
            message += `Saved: ${data.posts_saved} | Duplicates: ${data.posts_skipped}`;
            
            showToast(message, 'success');
            showToast('Pipeline processing started. Data will be indexed automatically.', 'success');

            // Show subreddit details
            if (data.subreddits_processed && data.subreddits_processed.length > 0) {
                data.subreddits_processed.forEach(sub => {
                    console.log(`  ${sub.subreddit}: ${sub.posts_found} found, ${sub.posts_saved} saved`);
                });
            }

            // Update progress bar
            updateRedditLucidProgress(100, 'Completed!');

            // Reset inputs
            postsInput.value = '100';
            delayInput.value = '5';

            // Update status
            updateCollectionStatus();

            // Hide progress after 3 seconds
            setTimeout(() => {
                progressDiv.style.display = 'none';
            }, 3000);
        } else {
            console.error('❌ Reddit Lucid scraping failed:', data.error);
            showToast('Scraping failed: ' + data.error, 'error');
            updateRedditLucidProgress(0, 'Failed');
        }
    })
    .catch(error => {
        console.error('❌ Reddit Lucid scraping error:', error);
        showToast('Error: ' + error.message, 'error');
        updateRedditLucidProgress(0, 'Error');
    })
    .finally(() => {
        // Re-enable button
        startBtn.disabled = false;
        startBtn.innerHTML = '🚀 Start Scraping';
    });
}

function updateRedditLucidProgress(percentage, text) {
    const progressBar = document.getElementById('redditLucidProgressBar');
    const progressText = document.getElementById('redditLucidProgressText');
    const progressPercent = document.getElementById('redditLucidProgressPercent');

    if (progressBar) {
        progressBar.style.width = percentage + '%';
    }
    if (progressText) {
        progressText.textContent = text;
    }
    if (progressPercent) {
        progressPercent.textContent = percentage + '%';
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeRedditLucidScraping();
});


// Manual Reddit Lucid URL Validation
function validateManualRedditLucidUrl() {
    const urlInput = document.getElementById('manualRedditLucidUrl');
    const messageDiv = document.getElementById('redditLucidUrlValidationMessage');
    const url = urlInput.value.trim();

    if (!url) {
        messageDiv.textContent = '';
        messageDiv.style.color = '';
        urlInput.style.borderColor = '';
        return;
    }

    // Check if it's a valid Reddit URL
    const isValidRedditUrl = /^https?:\/\/(www\.)?reddit\.com\/r\/lucidmotors\/comments\/|^https?:\/\/(www\.)?reddit\.com\/r\/LUCID\/comments\//.test(url);

    if (isValidRedditUrl) {
        messageDiv.textContent = '✅ Valid Reddit Lucid URL';
        messageDiv.style.color = 'var(--success-color, #10b981)';
        urlInput.style.borderColor = 'var(--success-color, #10b981)';
    } else {
        messageDiv.textContent = '❌ Invalid URL. Use: https://www.reddit.com/r/lucidmotors/comments/... or https://www.reddit.com/r/LUCID/comments/...';
        messageDiv.style.color = 'var(--error-color, #ef4444)';
        urlInput.style.borderColor = 'var(--error-color, #ef4444)';
    }
}

// Manual Reddit Lucid URL Scraping
function scrapeManualRedditLucidUrl() {
    const urlInput = document.getElementById('manualRedditLucidUrl');
    const maxPostsInput = document.getElementById('manualRedditLucidMaxPosts');
    const scrapeBtn = document.getElementById('scrapeManualRedditLucidUrl');
    const messageDiv = document.getElementById('redditLucidUrlValidationMessage');

    const url = urlInput.value.trim();
    const maxPosts = parseInt(maxPostsInput.value);

    // Validate URL
    if (!url) {
        showToast('Please enter a Reddit URL', 'error');
        return;
    }

    const isValidRedditUrl = /^https?:\/\/(www\.)?reddit\.com\/r\/lucidmotors\/comments\/|^https?:\/\/(www\.)?reddit\.com\/r\/LUCID\/comments\//.test(url);
    
    if (!isValidRedditUrl) {
        showToast('Invalid Reddit URL. Use: https://www.reddit.com/r/lucidmotors/comments/... or https://www.reddit.com/r/LUCID/comments/...', 'error');
        return;
    }

    // Validate posts count
    if (!maxPosts || maxPosts < 1 || maxPosts > 1000) {
        showToast('Please set a valid number of posts (1-1,000)', 'error');
        return;
    }

    console.log('🚀 Starting manual Reddit Lucid URL scraping:', url);

    // Disable button and show loading state
    scrapeBtn.disabled = true;
    scrapeBtn.innerHTML = '⏳ Scraping...';

    // Prepare form data
    const formData = new FormData();
    formData.append('post_url', url);
    formData.append('max_posts', maxPosts);

    // Start scraping
    fetch('/scrape_reddit_lucid_manual', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('✅ Manual Reddit Lucid URL scraping completed:', data);
            showToast(`Successfully scraped ${data.posts_scraped} posts in ${data.elapsed_time}s`, 'success');
            showToast('Pipeline processing started. Data will be indexed automatically.', 'success');

            // Clear input after successful scrape
            urlInput.value = '';
            maxPostsInput.value = '50';
            messageDiv.textContent = '';
            messageDiv.style.color = '';
            urlInput.style.borderColor = '';

            // Update status
            updateCollectionStatus();
        } else {
            console.error('❌ Manual Reddit Lucid URL scraping failed:', data.error);

            // Handle specific error types
            if (data.validation_error) {
                showToast('Validation Error: ' + data.error, 'error');
            } else if (data.already_scraped) {
                showToast('This post has already been scraped', 'warning');
            } else {
                showToast('Scraping failed: ' + data.error, 'error');
            }
        }
    })
    .catch(error => {
        console.error('❌ Manual Reddit Lucid URL scraping error:', error);
        showToast('Error: ' + error.message, 'error');
    })
    .finally(() => {
        // Re-enable button
        scrapeBtn.disabled = false;
        scrapeBtn.innerHTML = '🚀 Scrape URL';
    });
}
