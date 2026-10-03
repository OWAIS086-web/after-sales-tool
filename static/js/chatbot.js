/* ============================================
   CLEAN CHATBOT JAVASCRIPT - CHATGPT/GEMINI STYLE
   ============================================ */

// Suppress Chrome extension listener errors
window.addEventListener('error', function(event) {
    if (event.message && event.message.includes('listener indicated an asynchronous response')) {
        event.preventDefault();
        return true;
    }
}, true);

// Suppress unhandled promise rejections from Chrome extensions
window.addEventListener('unhandledrejection', function(event) {
    if (event.reason && event.reason.message && event.reason.message.includes('listener indicated an asynchronous response')) {
        event.preventDefault();
        return true;
    }
}, true);

// Disable frontend logging - set to false to disable all console logs
const ENABLE_FRONTEND_LOGGING = true;

// Override console methods if logging is disabled
if (!ENABLE_FRONTEND_LOGGING) {
    console.log = function() {};
    console.warn = function() {};
    console.info = function() {};
    console.debug = function() {};
}

// Global Variables
let conversationHistory = [];
let currentSessionId = null;
let thinkingMode = false;
let isTyping = false;
let currentTypingElement = null;
let userScrolled = false;
let currentMode = localStorage.getItem('selectedMode') || 'pakwheels';
let isHovering = false;
let groupOnlyMode = false;  // New: Group only mode (no bot processing)
let isGroupCreator = false;  // New: Track if user is group creator

// Timing variables
let requestStartTime = null;

// Initialize mode with permission check
function initializeMode() {
    console.log('🔧 Initializing mode with permission check...');
    
    // Get permissions
    const debugPerms = document.getElementById('debug-perms');
    let userPerms = {};
    
    if (debugPerms && debugPerms.getAttribute('data-perms')) {
        try {
            userPerms = JSON.parse(debugPerms.getAttribute('data-perms'));
            console.log('✅ Permissions loaded:', userPerms);
        } catch (e) {
            console.error('❌ Failed to parse permissions:', e);
            userPerms = {};
        }
    }
    
    // Get stored mode
    let storedMode = localStorage.getItem('selectedMode') || 'pakwheels';
    console.log('📌 Stored mode:', storedMode);
    
    // Check if stored mode is allowed
    const hasPermissionRecord = Object.keys(userPerms).length > 0;
    const storedModePermission = userPerms[storedMode];
    const isStoredModeDisabled = hasPermissionRecord && storedModePermission === false;
    
    console.log(`🔐 Checking stored mode: ${storedMode}`);
    console.log(`   - hasRecord: ${hasPermissionRecord}`);
    console.log(`   - permission: ${storedModePermission}`);
    console.log(`   - isDisabled: ${isStoredModeDisabled}`);
    
    // If stored mode is disabled, find first enabled mode
    if (isStoredModeDisabled) {
        console.log(`🚫 Stored mode ${storedMode} is disabled, finding first enabled mode...`);
        
        // Filter modes based on company
        let allModes = ['pakwheels', 'reddit', 'lucid', 'reddit_lucid', 'whatsapp', 'cross_platform', 'dealership', 'finance', 'facebook', 'supplychain', 'insights'];
        
        // For Lucid company, only show Lucid Forum and Reddit Lucid
        const userCompany = document.getElementById('debug-company')?.getAttribute('data-company') || 'haval';
        if (userCompany === 'lucid') {
            allModes = ['lucid', 'reddit_lucid'];
        }
        
        let foundMode = null;
        
        for (let mode of allModes) {
            const modePermission = userPerms[mode];
            const isModeDisabled = hasPermissionRecord && modePermission === false;
            
            if (!isModeDisabled) {
                foundMode = mode;
                console.log(`✅ Found enabled mode: ${mode}`);
                break;
            }
        }
        
        if (foundMode) {
            currentMode = foundMode;
            localStorage.setItem('selectedMode', foundMode);
            console.log(`🔄 Mode changed to: ${foundMode}`);
        } else {
            console.error('❌ No enabled modes found!');
            currentMode = 'pakwheels';
        }
    } else {
        console.log(`✅ Stored mode ${storedMode} is allowed`);
        currentMode = storedMode;
    }
    
    console.log(`🎯 Final mode: ${currentMode}`);
}
let responseStartTime = null;
let currentTimingElement = null;
let serverProcessingTime = null;  // Server-side processing time from backend

// Notification utility function
function showNotification(title, message, type = 'info', duration = 4000) {
    // Remove any existing notifications
    const existingNotifications = document.querySelectorAll('.chatbot-notification');
    existingNotifications.forEach(notif => notif.remove());

    // Create notification element
    const notification = document.createElement('div');
    notification.className = `chatbot-notification notification-${type}`;

    // Set colors based on type
    const colors = {
        'success': '#10b981',
        'error': '#ef4444',
        'warning': '#f59e0b',
        'info': '#3b82f6'
    };

    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${colors[type] || colors.info};
        color: white;
        padding: 16px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        max-width: 350px;
        animation: slideInRight 0.3s ease-out;
        font-family: var(--font-family, 'Inter', sans-serif);
    `;

    const titleEl = document.createElement('div');
    titleEl.style.cssText = 'font-weight: 600; margin-bottom: 4px; font-size: 14px;';
    titleEl.textContent = title;

    const messageEl = document.createElement('div');
    messageEl.style.cssText = 'font-size: 13px; opacity: 0.95;';
    messageEl.textContent = message;

    notification.appendChild(titleEl);
    notification.appendChild(messageEl);
    document.body.appendChild(notification);

    // Auto-remove after specified duration
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, duration);
}

// Handle OAuth callback parameters on page load
(function handleOAuthCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    const emailOAuthSuccess = urlParams.get('email_oauth_success');
    const emailOAuthError = urlParams.get('email_oauth_error');
    const userEmail = urlParams.get('email');
    const mode = urlParams.get('mode');
    
    if (emailOAuthSuccess === 'true') {
        console.log('📧 [OAuth] Success! Connected Gmail:', userEmail);
        
        // Set email mode
        if (mode === 'email') {
            currentMode = 'email';
            localStorage.setItem('selectedMode', 'email');
        }
        
        // Show success notification and status panel
        setTimeout(() => {
            showNotification(
                'Gmail Connected!',
                `✅ Successfully connected ${userEmail}`,
                'success',
                4000
            );
            
            // Show email status panel
            if (userEmail && mode === 'email') {
                showEmailStatusPanel(userEmail);
            }
        }, 500);
        
        // Clean up URL
        window.history.replaceState({}, document.title, '/');
    } else if (emailOAuthError) {
        console.error('📧 [OAuth] Error:', emailOAuthError);
        
        // Show error notification
        setTimeout(() => {
            showNotification(
                'Gmail Connection Failed',
                `Failed to connect Gmail: ${emailOAuthError}. Please try again.`,
                'error',
                6000
            );
        }, 500);
        
        // Clean up URL
        window.history.replaceState({}, document.title, '/');
    }
})();

// Add CSS animations if not already added
if (!document.getElementById('notification-animations')) {
    const style = document.createElement('style');
    style.id = 'notification-animations';
    style.textContent = `
        @keyframes slideInRight {
            from { transform: translateX(400px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOutRight {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(400px); opacity: 0; }
        }
        @keyframes loadingDots {
            0%, 20% { content: '.'; }
            40% { content: '..'; }
            60%, 100% { content: '...'; }
        }
        .loading-dots::after {
            content: '...';
            animation: loadingDots 1.5s infinite;
        }
    `;
    document.head.appendChild(style);
}

// Helper function to remove reference headers from message content
/**
 * UTILITY: Strip references and charts from markdown BEFORE rendering
 * This ensures .message-content contains ONLY the AI analysis text
 * References and charts are rendered separately from structured_data
 * 
 * This function removes:
 * - All reference section headers (###, ##, #) with "References", "Sources", etc.
 * - Reference content lists and paragraphs
 * - Image blocks (charts/graphs)
 * - Horizontal rule separators
 */
function stripReferencesAndChartsFromMarkdown(markdown) {
    if (!markdown) return markdown;
    
    let cleaned = markdown;
    
    // CRITICAL: Remove BLOCK_ID metadata lines (e.g., "BLOCK_ID=reddit_reddit_search_1lztk6i | root_author=toocoldinhere24 | date=2025-07-14")
    // This pattern matches lines starting with BLOCK_ID= followed by metadata
    cleaned = cleaned.replace(/^BLOCK_ID=.*?\|.*?date=.*?$/gm, '');

    // Remove inline BLOCK_ID references (e.g., "(BLOCK_ID=reddit_reddit_search_1kcib9d)" or "BLOCK_ID=reddit_...")
    cleaned = cleaned.replace(/\(?\s*BLOCK_ID=\S+\s*\)?/gi, '');
    
    // Remove all variations of reference sections (headers + content)
    // Pattern: ### References ... (until next ### or end)
    cleaned = cleaned.replace(/^###\s+(?:📋\s*)?(?:References|Sources|Reddit References|Reddit Lucid References|PakWheels References|WhatsApp References|Facebook References|Dealership References|Lucid References|Lucid Forum References)[\s\S]*?(?=^###|$)/gm, '');
    
    // Pattern: ## References ... (until next ## or end)
    cleaned = cleaned.replace(/^##\s+(?:📋\s*)?(?:References|Sources|Reddit References|Reddit Lucid References|PakWheels References|WhatsApp References|Facebook References|Dealership References|Lucid References|Lucid Forum References)[\s\S]*?(?=^##|$)/gm, '');
    
    // Pattern: # References ... (until next # or end)
    cleaned = cleaned.replace(/^#\s+(?:📋\s*)?(?:References|Sources|Reddit References|Reddit Lucid References|PakWheels References|WhatsApp References|Facebook References|Dealership References|Lucid References|Lucid Forum References)[\s\S]*?(?=^#|$)/gm, '');
    
    // Remove reference sections with emoji prefix (🔗 References)
    cleaned = cleaned.replace(/^🔗\s+(?:References|Sources|Reddit References|Reddit Lucid References|PakWheels References|WhatsApp References|Facebook References|Dealership References|Lucid References|Lucid Forum References)[\s\S]*?(?=^---|$)/gm, '');
    
    // Remove horizontal rule separators followed by references
    cleaned = cleaned.replace(/---\s*\n###\s+(?:📋\s*)?References[\s\S]*?---/gm, '');
    
    // Remove image blocks (charts/graphs) - ![alt](url) or ![alt][ref]
    cleaned = cleaned.replace(/!\[.*?\]\(.*?\)/g, '');
    cleaned = cleaned.replace(/!\[.*?\]\[.*?\]/g, '');
    
    // Clean up excessive whitespace (multiple blank lines)
    cleaned = cleaned.replace(/\n\s*\n\s*\n+/g, '\n\n');
    
    // CRITICAL: Ensure blank lines before lists (markdown requirement)
    // Fix: "text\n• item" -> "text\n\n• item"
    cleaned = cleaned.replace(/([^\n])\n([\s]*[•\-\*]\s)/g, '$1\n\n$2');
    
    // Trim leading/trailing whitespace
    cleaned = cleaned.trim();
    
    return cleaned;
}

/**
 * UTILITY: Fix markdown formatting issues
 * Ensures proper spacing before lists, headers, and other markdown elements
 */
function fixMarkdownFormatting(markdown) {
    if (!markdown) return markdown;
    
    let fixed = markdown;
    
    // Ensure blank line before headers (## Header)
    fixed = fixed.replace(/([^\n])\n(#{1,6}\s+)/g, '$1\n\n$2');
    
    // Ensure blank line before lists (• item, - item, * item)
    // This handles both bullet points and dashes
    fixed = fixed.replace(/([^\n])\n([\s]*[•\-\*]\s)/g, '$1\n\n$2');
    
    // Ensure blank line before numbered lists (1. item)
    fixed = fixed.replace(/([^\n])\n([\s]*\d+\.\s)/g, '$1\n\n$2');
    
    // Add blank line between consecutive bullet points for better readability
    // This ensures each bullet point is visually separated
    fixed = fixed.replace(/^([\s]*[•\-\*]\s.+)$/gm, function(match) {
        return match + '\n';
    });
    
    // Clean up excessive blank lines (more than 2)
    fixed = fixed.replace(/\n\n\n+/g, '\n\n');
    
    return fixed;
}

/**
 * SAFETY NET: Remove reference headers from rendered HTML
 * This catches any references that slip through markdown stripping
 * Only operates on .message-content divs
 */
function cleanReferenceHeadersFromContent(contentDiv) {
    if (!contentDiv) return;
    
    // Only process if this is actually a message-content div
    if (!contentDiv.classList.contains('message-content')) return;
    
    // Get all headings that might contain reference text
    const headings = contentDiv.querySelectorAll('h1, h2, h3, h4, h5, h6');
    
    headings.forEach(heading => {
        const text = heading.textContent.toLowerCase().trim();
        
        // Check if heading contains reference keywords
        if (text.includes('references') || 
            text.includes('sources') ||
            text.includes('reddit references') ||
            text.includes('pakwheels references') ||
            text.includes('whatsapp references') ||
            text.includes('facebook references') ||
            text.includes('dealership references') ||
            text.includes('lucid references') ||
            text.includes('lucid forum references')) {
            
            // Remove the heading and following content until next heading
            let nextElement = heading.nextElementSibling;
            heading.remove();
            
            // Remove following list items and paragraphs that are part of references
            while (nextElement) {
                const nextTag = nextElement.tagName.toLowerCase();
                
                // Stop at next heading
                if (nextTag.match(/^h[1-6]$/)) {
                    break;
                }
                
                // Remove lists, paragraphs, and horizontal rules
                if (nextTag === 'ul' || nextTag === 'ol' || nextTag === 'p' || nextTag === 'hr') {
                    const toRemove = nextElement;
                    nextElement = nextElement.nextElementSibling;
                    toRemove.remove();
                } else {
                    break;
                }
            }
        }
    });
    
    // Also remove any remaining image elements (charts)
    const images = contentDiv.querySelectorAll('img');
    images.forEach(img => {
        // Only remove if it looks like a chart (has certain keywords in alt or src)
        const alt = (img.alt || '').toLowerCase();
        const src = (img.src || '').toLowerCase();
        if (alt.includes('chart') || alt.includes('graph') || alt.includes('distribution') ||
            src.includes('chart') || src.includes('graph')) {
            img.remove();
        }
    });
}

// Initialize the application
function init() {
    console.log('🚀 Initializing clean chatbot...');
    
    try {
        // Store user ID in localStorage
        const userIdElement = document.querySelector('[data-user-id]');
        if (userIdElement) {
            const userId = userIdElement.getAttribute('data-user-id');
            localStorage.setItem('userId', userId);
            console.log('✅ User ID stored:', userId);
        }
        
        // Initialize session ID
        if (!currentSessionId) {
            currentSessionId = generateSessionId();
        }
        
        // Load saved mode from localStorage
        const savedMode = localStorage.getItem('selectedMode');
        if (savedMode) {
            currentMode = savedMode;
            console.log('📂 Loaded saved mode from localStorage:', currentMode);
        } else {
            console.log('📂 No saved mode, using default:', currentMode);
        }
        
        loadTheme();
        setupEventListeners();
        updateModePlaceholder();
        loadRecentChatsToSidebar();
        
        // Ensure Chat History panel is hidden and recent chats are visible on init
        const chatHistoryPanel = document.getElementById('chatHistoryPanel');
        const recentChatsSection = document.getElementById('recentChatsSection');
        if (chatHistoryPanel) {
            chatHistoryPanel.style.display = 'none';
            console.log('✅ Chat History panel hidden on init');
        }
        if (recentChatsSection) {
            recentChatsSection.style.display = 'block';
            console.log('✅ Recent chats section visible on init');
        }
        
        // Load user preferences
        loadThinkingModePreference();
        
        // Initialize auto questions
        initAutoQuestions();
        
        // Ensure UI is updated with current mode
        updateModePlaceholder();
        
        console.log('✅ Clean chatbot initialized successfully');
        console.log('🎯 Current state:', {
            mode: currentMode,
            thinkingMode: thinkingMode,
            sessionId: currentSessionId
        });
    } catch (error) {
        console.error('❌ Error during initialization:', error);
    }
}

// Setup event listeners
function setupEventListeners() {
    // Theme toggle
    const themeToggle = document.querySelector('.theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

    // Chat input
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.addEventListener('keydown', handleKeyPress);
        chatInput.addEventListener('input', function() {
            autoResize(this);
        });
    }

    // Send button
    const sendBtn = document.getElementById('sendBtn');
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }

    // Stop button
    const stopBtn = document.getElementById('stopBtn');
    if (stopBtn) {
        stopBtn.addEventListener('click', stopTyping);
    }

    // Data Source button (sidebar)
    const dataSourceBtn = document.getElementById('dataSourceBtn');
    if (dataSourceBtn) {
        dataSourceBtn.addEventListener('click', toggleDataSourcePanel);
        console.log('✅ Data source sidebar button event listener added');
    } else {
        console.warn('⚠️ Data source sidebar button not found');
    }

    // AI Mode toggle
    const aiModeToggle = document.getElementById('aiModeToggle');
    if (aiModeToggle) {
        aiModeToggle.addEventListener('click', toggleThinkingMode);
        updateAiModeButton();
    }

    // Group Only Mode toggle
    const groupOnlyModeBtn = document.getElementById('groupOnlyModeBtn');
    if (groupOnlyModeBtn) {
        groupOnlyModeBtn.addEventListener('click', toggleGroupOnlyMode);
        console.log('✅ Group only mode button event listener added');
    } else {
        console.warn('⚠️ Group only mode button not found');
    }

    // Sidebar buttons (no hide/show functionality)
    const newChatSidebarBtn = document.getElementById('newChatSidebarBtn');
    if (newChatSidebarBtn) {
        newChatSidebarBtn.addEventListener('click', newChat);
        console.log('✅ New chat sidebar button event listener added');
    } else {
        console.warn('⚠️ New chat sidebar button not found');
    }

    const clearHistorySidebarBtn = document.getElementById('clearHistorySidebarBtn');
    if (clearHistorySidebarBtn) {
        clearHistorySidebarBtn.addEventListener('click', clearAllChats);
        console.log('✅ Clear history sidebar button event listener added');
    } else {
        console.warn('⚠️ Clear history sidebar button not found');
    }

    // Clear Mode History Button (in Chat History panel)
    const clearModeHistoryBtn = document.getElementById('clearModeHistoryBtn');
    if (clearModeHistoryBtn) {
        clearModeHistoryBtn.addEventListener('click', clearModeHistory);
        console.log('✅ Clear mode history button event listener added');
    } else {
        console.warn('⚠️ Clear mode history button not found');
    }

    // Create Group Button (in Sidebar)
    const createGroupSidebarBtn = document.getElementById('createGroupSidebarBtn');
    if (createGroupSidebarBtn) {
        createGroupSidebarBtn.addEventListener('click', showCreateGroupModal);
        console.log('✅ Create group sidebar button event listener added');
    } else {
        console.warn('⚠️ Create group sidebar button not found');
    }

    // My Groups Button (in Sidebar)
    const myGroupsSidebarBtn = document.getElementById('myGroupsSidebarBtn');
    if (myGroupsSidebarBtn) {
        myGroupsSidebarBtn.addEventListener('click', toggleGroupsPanel);
        console.log('✅ My groups sidebar button event listener added');
    } else {
        console.warn('⚠️ My groups sidebar button not found');
    }

    // Quick Questions Button
    const quickQuestionsBtn = document.getElementById('quickQuestionsBtn');
    if (quickQuestionsBtn) {
        quickQuestionsBtn.addEventListener('click', toggleQuickQuestions);
        console.log('✅ Quick questions button event listener added');
    } else {
        console.warn('⚠️ Quick questions button not found');
    }
    
    // Chat History Button
    const chatHistoryBtn = document.getElementById('chatHistoryBtn');
    if (chatHistoryBtn) {
        chatHistoryBtn.addEventListener('click', toggleChatHistory);
        console.log('✅ Chat history button event listener added');
    } else {
        console.warn('⚠️ Chat history button not found');
    }

    // Hamburger Menu Button (Mobile)
    const hamburgerMenu = document.getElementById('hamburgerMenu');
    if (hamburgerMenu) {
        hamburgerMenu.addEventListener('click', toggleMobileSidebar);
        console.log('✅ Hamburger menu button event listener added');
    } else {
        console.warn('⚠️ Hamburger menu button not found');
    }

    // Sidebar Close Button (Mobile)
    const sidebarCloseBtn = document.getElementById('sidebarCloseBtn');
    if (sidebarCloseBtn) {
        sidebarCloseBtn.addEventListener('click', closeMobileSidebar);
        console.log('✅ Sidebar close button event listener added');
    } else {
        console.warn('⚠️ Sidebar close button not found');
    }

    // Sidebar Action Button (Mobile)
    const sidebarActionBtn = document.getElementById('sidebarActionBtn');
    if (sidebarActionBtn) {
        sidebarActionBtn.addEventListener('click', showCreateGroupModal);
        console.log('✅ Sidebar action button event listener added');
    } else {
        console.warn('⚠️ Sidebar action button not found');
    }

    // Custom question input - Enter key support
    const customQuestionInput = document.getElementById('customQuestionInput');
    if (customQuestionInput) {
        customQuestionInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                addCustomQuestion();
            }
        });
    }

    // Data source menu items - no longer needed with panel approach
    // setupDataSourceMenu();  // Removed - using panel instead

    // Track user scrolling
    const chatArea = document.getElementById('chatArea');
    if (chatArea) {
        chatArea.addEventListener('mouseenter', function() {
            isHovering = true;
        });
        
        chatArea.addEventListener('mouseleave', function() {
            isHovering = false;
        });
        
        chatArea.addEventListener('scroll', function() {
            const isAtBottom = chatArea.scrollHeight - chatArea.scrollTop - chatArea.clientHeight < 10;
            userScrolled = !isAtBottom;
        });
    }

    // Close dropdowns when clicking outside
    document.addEventListener('click', function(event) {
        // No longer needed - using panel instead of dropdown menu
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            // Close any open panels
            closeQuickQuestions();
            closeChatHistory();
            closeGroupsPanel();
            closeDataSourcePanel();
        }
        
        if (event.ctrlKey || event.metaKey) {
            switch(event.key) {
                case 'n':
                case 'N':
                    event.preventDefault();
                    newChat();
                    break;
            }
        }
    });
}

// Handle key press
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Auto resize textarea
function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

// Send message
function sendMessage() {
    const chatInput = document.getElementById('chatInput');
    const message = chatInput.value.trim();
    
    if (!message || isTyping) return;
    
    console.log('📤 Sending message:', message);
    console.log('🔍 Current mode:', {
        isGroupChatMode: isGroupChatMode,
        currentGroupId: currentGroupId,
        currentMode: currentMode
    });
    
    // If auto questions is active and this is a manual message, stop auto questions
    if (autoQuestionsActive && !autoQuestionsWaitingForResponse) {
        console.log('🛑 Manual message detected, stopping auto questions');
        stopAutoQuestions();
    }
    
    // Start timing
    requestStartTime = performance.now();
    responseStartTime = null;
    
    // Show stop button, hide send button
    const sendBtn = document.getElementById('sendBtn');
    const stopBtn = document.getElementById('stopBtn');
    if (sendBtn) sendBtn.style.display = 'none';
    if (stopBtn) stopBtn.style.display = 'flex';
    
    // Add user message to DOM
    addMessageToDOM(message, true);
    
    // Add to conversation history
    conversationHistory.push({
        role: 'user',
        content: message
    });
    
    // Clear input
    chatInput.value = '';
    autoResize(chatInput);
    
    // Show typing indicator
    showTypingIndicator();
    
    // Send to backend
    sendToBackend(message);
    
    // Save chat history
    saveChatHistory();
}

// Add message to DOM with enhanced styling
function addMessageToDOM(content, isUser, withTyping = false, messageTimestamp = null) {
    const messagesContainer = document.getElementById('messagesContainer');
    const welcomeScreen = document.getElementById('welcomeScreen');
    
    // Hide welcome screen and show messages
    if (welcomeScreen.style.display !== 'none') {
        welcomeScreen.style.display = 'none';
        messagesContainer.style.display = 'block';
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user' : 'bot'}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    if (withTyping && !isUser) {
        // Start with empty content for typing effect
        contentDiv.innerHTML = '';
        currentTypingElement = contentDiv;
        isTyping = true;
        
        // Mark when response started (for typing time calculation)
        responseStartTime = performance.now();
    } else {
        // Content is already cleaned by the backend, just process markdown for bot messages
        if (!isUser && typeof marked !== 'undefined') {
            // CRITICAL: Strip references and charts from markdown BEFORE rendering
            // This ensures .message-content contains ONLY the AI analysis text
            const cleanedContent = stripReferencesAndChartsFromMarkdown(content);
            const formattedContent = fixMarkdownFormatting(cleanedContent);
            contentDiv.innerHTML = marked.parse(formattedContent);
            // Safety net: remove any references that slip through
            cleanReferenceHeadersFromContent(contentDiv);
        } else {
            contentDiv.textContent = content;
        }
    }
    
    messageDiv.appendChild(contentDiv);
    
    // Add timing info for bot messages
    if (!isUser) {
        const timingDiv = document.createElement('div');
        timingDiv.className = 'message-timing';
        timingDiv.style.cssText = 'font-size: 11px; color: var(--text-secondary); margin-top: 8px; opacity: 0.7;';
        
        if (withTyping && requestStartTime) {
            // Show "Thinking..." initially
            const thinkingTime = ((performance.now() - requestStartTime) / 1000).toFixed(1);
            timingDiv.innerHTML = `⏱️ Thinking: ${thinkingTime}s`;
            currentTimingElement = timingDiv;
        }
        
        messageDiv.appendChild(timingDiv);
    }
    
    // Add timestamp with Pakistan time
    const timestampDiv = document.createElement('div');
    timestampDiv.className = 'message-timestamp';
    
    // Use provided timestamp or current time
    let displayDate;
    if (messageTimestamp) {
        try {
            displayDate = new Date(messageTimestamp);
        } catch (e) {
            console.error('Error parsing message timestamp:', messageTimestamp, e);
            displayDate = new Date();
        }
    } else {
        displayDate = new Date();
    }
    
    // Format timestamp in Pakistan timezone with date and time
    const pakistanDateTime = new Intl.DateTimeFormat('en-US', {
        timeZone: 'Asia/Karachi',
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
    }).format(displayDate);
    
    timestampDiv.textContent = pakistanDateTime;
    messageDiv.appendChild(timestampDiv);
    
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom if user hasn't scrolled up
    if (!userScrolled && !isHovering) {
        scrollToBottom();
    }
    
    return messageDiv;
}

// Show typing indicator
function showTypingIndicator() {
    const messagesContainer = document.getElementById('messagesContainer');
    
    // Remove existing typing indicator
    const existingIndicator = document.querySelector('.typing-indicator');
    if (existingIndicator) {
        existingIndicator.remove();
    }
    
    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing-indicator';
    
    // Check if we're in cross_platform mode for multi-source animation
    if (currentMode === 'cross_platform') {
        typingDiv.innerHTML = `
            <div class="multi-source-loader">
                <span class="typing-text">🔍 Searching across platforms...</span>
                <div class="sources-progress">
                    <div class="source-item" data-source="pakwheels">
                        <span class="source-icon">🔗</span>
                        <span class="source-name">PakWheels</span>
                        <span class="source-status">●</span>
                    </div>
                    <div class="source-item" data-source="whatsapp">
                        <span class="source-icon">🔗</span>
                        <span class="source-name">WhatsApp</span>
                        <span class="source-status">●</span>
                    </div>
                    <div class="source-item" data-source="reddit">
                        <span class="source-icon">🔗</span>
                        <span class="source-name">Reddit</span>
                        <span class="source-status">●</span>
                    </div>
                </div>
            </div>
        `;
        
        // Animate source items sequentially
        setTimeout(() => {
            const sourceItems = typingDiv.querySelectorAll('.source-item');
            sourceItems.forEach((item, index) => {
                setTimeout(() => {
                    item.classList.add('searching');
                }, index * 400);
            });
        }, 100);
    } else {
        typingDiv.innerHTML = `
            <span class="typing-text">AI is thinking</span>
            <div class="typing-dots">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
    }
    
    messagesContainer.appendChild(typingDiv);
    scrollToBottom();
}

// Hide typing indicator
function hideTypingIndicator() {
    const typingIndicator = document.querySelector('.typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// Send to backend
function sendToBackend(message) {
    // Ensure we have a session ID
    if (!currentSessionId) {
        currentSessionId = generateSessionId();
        console.log('🆔 Generated new session ID:', currentSessionId);
    }
    
    console.log('📤 sendToBackend called:', {
        isGroupChatMode: isGroupChatMode,
        currentGroupId: currentGroupId,
        groupOnlyMode: groupOnlyMode,
        message: message.substring(0, 50)
    });
    
    // If in group chat mode with Group Only Mode enabled, just save to group and don't process with bot
    if (isGroupChatMode && currentGroupId && groupOnlyMode) {
        console.log('👥 Group Only Mode ENABLED: Saving message to group only (no bot processing)');
        
        // For group only mode, we need to save the message without AI processing
        // This is a simple message save, not a query
        addMessageToGroup(currentGroupId, message, null);
        
        hideTypingIndicator();
        
        // Show send button, hide stop button
        const sendBtn = document.getElementById('sendBtn');
        const stopBtn = document.getElementById('stopBtn');
        if (sendBtn) sendBtn.style.display = 'flex';
        if (stopBtn) stopBtn.style.display = 'none';
        
        // Reload group messages to show the new message
        loadGroupMessages(currentGroupId);
        
        return;
    }
    
    // If in group chat mode (but Group Only Mode is disabled), send to bot (which will save to group automatically)
    if (isGroupChatMode && currentGroupId && !groupOnlyMode) {
        console.log('👥 Group Chat Mode ENABLED (Group Only Mode disabled): Sending to bot (will save to group automatically)');
        // Continue to send to bot below - the backend will save to group automatically
    }
    
    // Check if user is a member (not creator) in group chat - members can only send messages, no AI
    if (isGroupChatMode && currentGroupId && !isGroupCreator) {
        console.log('🔒 Member detected in group chat: Saving message only (no AI processing)');
        
        // For members, just save the message without AI processing
        addMessageToGroup(currentGroupId, message, null);
        
        hideTypingIndicator();
        
        // Show send button, hide stop button
        const sendBtn = document.getElementById('sendBtn');
        const stopBtn = document.getElementById('stopBtn');
        if (sendBtn) sendBtn.style.display = 'flex';
        if (stopBtn) stopBtn.style.display = 'none';
        
        // Reload group messages to show the new message
        loadGroupMessages(currentGroupId);
        
        return;
    }
    
    // Send to bot (always, unless Group Only Mode is enabled or user is a member)
    if (!groupOnlyMode && (isGroupCreator || !isGroupChatMode)) {
        console.log('🤖 Sending to bot for processing');
        console.log('💭 Current thinking mode:', thinkingMode, 'Type:', typeof thinkingMode);
        console.log('📧 [DEBUG EMAIL] currentMode at send time:', currentMode);
        console.log('📧 [DEBUG EMAIL] localStorage selectedMode:', localStorage.getItem('selectedMode'));
        
        const payload = {
            query: message,
            mode: currentMode,
            thinking: thinkingMode,
            session_id: currentSessionId,
            conversation_history: conversationHistory.slice(-10),
            group_id: isGroupChatMode ? currentGroupId : null
        };
        
        console.log('📤 PAYLOAD DETAILS:', JSON.stringify(payload, null, 2));
        console.log('📤 Sending payload to bot:', {
            query: message.substring(0, 50) + '...',
            mode: currentMode,
            modeActual: payload.mode,
            thinking: thinkingMode,
            thinking_type: typeof thinkingMode,
            session_id: currentSessionId,
            group_id: isGroupChatMode ? currentGroupId : null,
            history_length: conversationHistory.length
        });
        
        // Use group chat endpoint if in group mode, otherwise use regular bot endpoint
        const endpoint = isGroupChatMode && currentGroupId ? '/api/group-chat/query' : '/chatbot_query';
        
        console.log('🔍 FINAL CHECK BEFORE FETCH:');
        console.log('   currentMode:', currentMode);
        console.log('   payload.mode:', payload.mode);
        console.log('   localStorage selectedMode:', localStorage.getItem('selectedMode'));
        console.log('   endpoint:', endpoint);
        
        // Create abort controller for timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 120000); // 120 second timeout
        
        fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
            signal: controller.signal
        })
        .then(response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // For group chat, response is SSE stream
            if (isGroupChatMode && currentGroupId) {
                return handleGroupChatStream(response);
            } else {
                return response.json();
            }
        })
        .then(data => {
            hideTypingIndicator();
            
            // Check if response is empty or incomplete
            if (!data.answer || data.answer.trim() === '') {
                showNotification(
                    '⚠️ Empty Response',
                    'The AI did not return a complete response. Please try again.',
                    'warning'
                );
                
                const botMessageDiv = addMessageToDOM(
                    '⚠️ **No Response Received**\n\nThe language model did not return a complete answer. This can happen due to:\n\n• API timeout\n• Service interruption\n• Network issue\n\nPlease try your question again.',
                    false,
                    true
                );
                
                if (botMessageDiv) {
                    botMessageDiv.style.borderLeft = '4px solid #f59e0b';
                    botMessageDiv.style.backgroundColor = '#fffbeb';
                }
                
                return;
            }
            
            console.log('📊 Received data from backend:', {
                has_answer: !!data.answer,
                has_structured: !!data.structured,
                references_count: data.structured?.references?.length || 0,
                charts_count: data.structured?.charts?.length || 0,
                server_time: data.server_time
            });

            if (data.answer) {
                // Check if response contains error keywords
                const errorKeywords = [
                    'credit',
                    'exhausted',
                    'limit',
                    'quota',
                    'rate limit',
                    '429',
                    'insufficient',
                    'not available',
                    'temporarily unavailable'
                ];
                
                const hasErrorKeyword = errorKeywords.some(keyword => 
                    data.answer.toLowerCase().includes(keyword)
                );
                
                // Always show the original LLM response as-is
                const botMessageDiv = addMessageToDOM(data.answer, false, true);
                typeMessage(data.answer, currentTypingElement, botMessageDiv, data.structured, data.server_time);
                
                // Add to conversation history
                conversationHistory.push({
                    role: 'assistant',
                    content: data.answer
                });
                
                // Save chat history
                saveChatHistory();
                
                // Reload group messages if in group mode
                if (isGroupChatMode && currentGroupId) {
                    setTimeout(() => {
                        loadGroupMessages(currentGroupId);
                    }, 500);
                }
                
                console.log('✅ Message processed and saved to database');
            }
        })
        .catch(error => {
            console.error('❌ Error sending message:', error);
            hideTypingIndicator();
            clearTimeout(timeoutId);
            
            // Show send button, hide stop button on error
            const sendBtn = document.getElementById('sendBtn');
            const stopBtn = document.getElementById('stopBtn');
            if (sendBtn) sendBtn.style.display = 'flex';
            if (stopBtn) stopBtn.style.display = 'none';
            
            let errorTitle = '❌ Error';
            let errorMessage = 'Sorry, I encountered an error. Please try again.';
            let errorType = 'error';
            
            // Detect specific error types
            if (error.name === 'AbortError') {
                errorTitle = '⏱️ Request Timeout';
                errorMessage = 'The request took too long to complete. Please try again with a simpler question.';
                errorType = 'warning';
            } else if (error.message.includes('404')) {
                errorTitle = '🔌 Service Unavailable';
                errorMessage = 'The chat service is not available. Please check if the server is running properly.';
            } else if (error.message.includes('500')) {
                errorTitle = '⚠️ Server Error';
                errorMessage = 'The server encountered an error. Please try again in a moment.';
                errorType = 'warning';
            } else if (error.message.includes('Failed to fetch') || error.message.includes('Network')) {
                errorTitle = '🌐 Connection Error';
                errorMessage = 'Unable to connect to the server. Please check your internet connection.';
            } else if (error.message.includes('429')) {
                errorTitle = '⚠️ Rate Limited';
                errorMessage = 'Too many requests. Please wait a moment and try again.';
                errorType = 'warning';
            } else if (error.message.includes('credit') || error.message.includes('exhausted')) {
                errorTitle = '💳 API Credits Exhausted';
                errorMessage = 'The API has reached its usage limit. Please try again later.';
                errorType = 'warning';
            }
            
            // Show popup notification only
            showNotification(errorTitle, errorMessage, errorType);
            
            // Add error message to conversation history
            conversationHistory.push({
                role: 'assistant',
                content: errorMessage
            });
        });
    } else {
        console.log('⚠️ Group Only Mode is enabled - bot processing skipped');
    }
}

// Handle group chat SSE stream
function handleGroupChatStream(response) {
    return new Promise((resolve, reject) => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullAnswer = '';
        let buffer = '';
        
        function read() {
            reader.read().then(({ done, value }) => {
                if (done) {
                    // Check if response is incomplete
                    const incompleteIndicators = [
                        'credit',
                        'exhausted',
                        'limit',
                        'quota',
                        'rate limit',
                        '429',
                        'insufficient',
                        'not available',
                        'temporarily unavailable'
                    ];
                    
                    const isIncomplete = incompleteIndicators.some(indicator => 
                        fullAnswer.toLowerCase().includes(indicator)
                    );
                    
                    resolve({ answer: fullAnswer });
                    return;
                }
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                
                // Keep the last incomplete line in the buffer
                buffer = lines[lines.length - 1];
                
                for (let i = 0; i < lines.length - 1; i++) {
                    const line = lines[i].trim();
                    if (line.startsWith('data: ')) {
                        try {
                            const jsonStr = line.substring(6);
                            const data = JSON.parse(jsonStr);
                            
                            if (data.content && !data.done) {
                                fullAnswer += data.content;
                            } else if (data.done && data.success) {
                                // Message is complete
                                console.log('✅ Group message processed');
                            }
                        } catch (e) {
                            console.error('Error parsing SSE data:', e);
                        }
                    }
                }
                
                read();
            }).catch(reject);
        }
        
        read();
    });
}

// Type message effect - Progressive typing with real-time styling and no auto-scroll
function typeMessage(content, element, messageDiv = null, structuredData = null, serverTime = null) {
    if (!element) return;

    // Store server processing time if provided
    if (serverTime !== null && serverTime !== undefined) {
        serverProcessingTime = serverTime;
    }

    // Content is already cleaned by the backend, just process markdown
    let processedContent = content;
    
    // Fix markdown formatting BEFORE parsing
    processedContent = fixMarkdownFormatting(processedContent);
    
    if (typeof marked !== 'undefined') {
        processedContent = marked.parse(processedContent);
    }
    
    // Split content into words for word-by-word typing with styling
    const words = processedContent.split(' ');
    let currentWordIndex = 0;
    const typingSpeed = 25; // 25ms per word for smooth typing
    let lastUpdateTime = performance.now();
    
    function typeWord(currentTime) {
        if (!isTyping) {
            // Typing was stopped, complete immediately
            if (processedContent.includes('<')) {
                element.innerHTML = processedContent;
            } else {
                element.textContent = content;
            }
            
            // Update timing display
            updateTimingDisplay(true);
            
            // Show send button, hide stop button
            const sendBtn = document.getElementById('sendBtn');
            const stopBtn = document.getElementById('stopBtn');
            if (sendBtn) sendBtn.style.display = 'flex';
            if (stopBtn) stopBtn.style.display = 'none';
            return;
        }
        
        // Calculate elapsed time since last update
        const elapsed = currentTime - lastUpdateTime;
        
        if (elapsed >= typingSpeed && currentWordIndex < words.length) {
            // Build current content up to this word
            const currentContent = words.slice(0, currentWordIndex + 1).join(' ');
            
            // Apply styling immediately during typing
            if (processedContent.includes('<')) {
                // For HTML content, apply styling progressively
                element.innerHTML = currentContent;
                
                // Highlight code blocks if available during typing
                if (typeof hljs !== 'undefined') {
                    element.querySelectorAll('pre code').forEach(block => {
                        hljs.highlightElement(block);
                    });
                }
            } else {
                // For plain text, show progressively
                element.textContent = currentContent;
            }
            
            currentWordIndex++;
            lastUpdateTime = currentTime;
        }
        
        if (currentWordIndex < words.length && isTyping) {
            // Continue typing using requestAnimationFrame for better performance
            requestAnimationFrame(typeWord);
        } else {
            // Typing complete, set final content with full styling
            if (processedContent.includes('<')) {
                element.innerHTML = processedContent;
            } else {
                element.textContent = content;
            }
            
            isTyping = false;
            currentTypingElement = null;
            
            // Final highlight pass for code blocks
            if (typeof hljs !== 'undefined') {
                element.querySelectorAll('pre code').forEach(block => {
                    hljs.highlightElement(block);
                });
            }
            
            // Add references and charts AFTER typing completes
            addStructuredDataToMessage(messageDiv, structuredData);
            
            // Update timing display with final times
            updateTimingDisplay(false);
            
            // Show send button, hide stop button when typing completes
            const sendBtn = document.getElementById('sendBtn');
            const stopBtn = document.getElementById('stopBtn');
            if (sendBtn) sendBtn.style.display = 'flex';
            if (stopBtn) stopBtn.style.display = 'none';
            
            // Hook for auto questions - notify that response is complete
            onAutoQuestionResponseComplete();
            
            // Only scroll at the end if user hasn't manually scrolled
            if (!userScrolled) {
                scrollToBottom();
            }
        }
    }
    
    // Start typing animation using requestAnimationFrame
    requestAnimationFrame(typeWord);
}

// Helper function to add structured data (references and charts) to message
function addStructuredDataToMessage(messageDiv, structuredData) {
    if (!messageDiv || !structuredData) {
        console.log('⚠️ No message div or structured data to add');
        return;
    }
    
    console.log('📊 Adding structured data to message:', {
        has_references: !!structuredData.references,
        references_count: structuredData.references?.length || 0,
        has_charts: !!structuredData.charts,
        charts_count: structuredData.charts?.length || 0
    });
    
    // Add references if available
    if (structuredData.references && structuredData.references.length > 0) {
        console.log(`📚 Adding ${structuredData.references.length} references`);
        // Pass the mode from structured data if available
        const messageMode = structuredData.mode || currentMode;
        addReferencesToMessage(messageDiv, structuredData.references, messageMode);
    }
    
    // Add charts if available
    if (structuredData.charts && structuredData.charts.length > 0) {
        console.log(`📈 Adding ${structuredData.charts.length} charts`);
        addChartsToMessage(messageDiv, structuredData.charts);
    }
    
    // Scroll to bottom after adding structured data
    if (!userScrolled) {
        scrollToBottom();
    }
}

// Update timing display
function updateTimingDisplay(stopped) {
    if (!currentTimingElement) return;

    // Use server-side timing if available (accurate), otherwise fall back to client-side timing
    if (serverProcessingTime !== null && serverProcessingTime !== undefined) {
        // Display actual server processing time
        currentTimingElement.innerHTML = `⏱️ Time: ${serverProcessingTime}s`;
    } else if (requestStartTime) {
        // Fallback to client-side timing calculation (less accurate due to network latency + animation)
        const now = performance.now();
        const totalTime = ((now - requestStartTime) / 1000).toFixed(1);

        if (stopped) {
            currentTimingElement.innerHTML = `⏱️ Time: ${totalTime}s (stopped)`;
        } else {
            currentTimingElement.innerHTML = `⏱️ Time: ${totalTime}s`;
        }
    }

    // Reset timing variables
    requestStartTime = null;
    responseStartTime = null;
    currentTimingElement = null;
    serverProcessingTime = null;
}

// Stop typing
function stopTyping() {
    isTyping = false;
    
    // If auto questions is active and user manually stops, pause auto questions
    if (autoQuestionsActive && autoQuestionsWaitingForResponse) {
        console.log('🛑 User manually stopped typing during auto questions');
        // Don't fully stop, just mark as not waiting so next question can proceed
        autoQuestionsWaitingForResponse = false;
    }
    
    if (currentTypingElement) {
        // Complete the message immediately with cleaned content
        const content = conversationHistory[conversationHistory.length - 1]?.content || '';
        
        // The content is already cleaned by the backend, just apply markdown
        if (typeof marked !== 'undefined') {
            // CRITICAL: Strip references and charts from markdown BEFORE rendering
            const cleanedContent = stripReferencesAndChartsFromMarkdown(content);
            const formattedContent = fixMarkdownFormatting(cleanedContent);
            currentTypingElement.innerHTML = marked.parse(formattedContent);
            // Safety net: remove any references that slip through
            cleanReferenceHeadersFromContent(currentTypingElement);
        } else {
            currentTypingElement.textContent = content;
        }
        
        currentTypingElement = null;
    }
    
    hideTypingIndicator();
    
    // Hide stop button, show send button
    const stopBtn = document.getElementById('stopBtn');
    const sendBtn = document.getElementById('sendBtn');
    if (stopBtn) stopBtn.style.display = 'none';
    if (sendBtn) sendBtn.style.display = 'flex';
    
    // Hook for auto questions - notify that response is complete (even if stopped)
    onAutoQuestionResponseComplete();
}

// Add references to message with enhanced styling and proper filtering
function addReferencesToMessage(messageDiv, references, messageMode, isGroupChat = false) {
    if (!references || references.length === 0) return;
    
    // Check if references section already exists to prevent duplication
    const existingReferences = messageDiv.querySelector('.references-section');
    if (existingReferences) {
        console.log('⚠️ References already exist, skipping duplication');
        return;
    }
    
    // Use messageMode if provided (from structured data), otherwise use currentMode
    const modeToUse = messageMode || currentMode;
    
    // Filter references based on mode to avoid wrong source mixing
    const filteredReferences = filterReferencesByMode(references, modeToUse);
    
    if (filteredReferences.length === 0) {
        console.log('📋 No references match mode:', modeToUse);
        return;
    }
    
    // Remove duplicate references based on content
    const uniqueReferences = removeDuplicateReferences(filteredReferences);
    
    // For email mode, show all references (up to 10). For other modes, limit to 2.
    const maxReferences = modeToUse === 'email' ? 10 : 2;
    const limitedReferences = uniqueReferences.slice(0, maxReferences);
    
    if (limitedReferences.length === 0) {
        console.log('📋 No valid references to display');
        return;
    }
    
    const referencesDiv = document.createElement('div');
    referencesDiv.className = 'references-section';
    if (isGroupChat) {
        referencesDiv.classList.add('group-references');
    }
    
    const titleDiv = document.createElement('div');
    titleDiv.className = 'references-title';
    
    // Set heading based on current mode
    const modeHeadings = {
        'whatsapp': 'WhatsApp References',
        'pakwheels': 'PakWheels References', 
        'facebook': 'Facebook References',
        'dealership': 'Dealership References',
        'reddit': 'Reddit References',
        'email': 'Gmail References',
        'lucid': 'Lucid Forum References',
        'reddit_lucid': 'Reddit Lucid References',
        'insights': 'AI References'
    };
    
    titleDiv.textContent = modeHeadings[modeToUse] || 'References';
    referencesDiv.appendChild(titleDiv);
    
    limitedReferences.forEach((ref, index) => {
        const refDiv = document.createElement('div');
        refDiv.className = 'reference-item';
        refDiv.style.cursor = 'pointer';
        refDiv.title = 'Click to view full details';
        
        // Add click handler to open popup
        refDiv.addEventListener('click', () => {
            showReferencePopup(ref, index + 1, isGroupChat);
        });
        
        // Reference header with number and metadata
        const headerDiv = document.createElement('div');
        headerDiv.className = 'reference-header';
        
        // Reference number
        const numberDiv = document.createElement('div');
        numberDiv.className = 'reference-number';
        numberDiv.textContent = index + 1;
        headerDiv.appendChild(numberDiv);
        
        // Reference metadata container
        const metaDiv = document.createElement('div');
        metaDiv.className = 'reference-meta';
        
        // Check if this is an email reference
        const refType = (ref.type || ref.source || modeToUse).toLowerCase();
        const isEmailRef = refType === 'email' || refType === 'gmail';
        
        if (isEmailRef) {
            // Email-specific metadata
            if (ref.sender_name || ref.contact) {
                const senderDiv = document.createElement('div');
                senderDiv.className = 'reference-contact';
                senderDiv.textContent = ref.sender_name || ref.contact || 'Unknown Sender';
                metaDiv.appendChild(senderDiv);
            }
            
            if (ref.sender_email || ref.email) {
                const emailDiv = document.createElement('div');
                emailDiv.className = 'reference-phone';
                emailDiv.style.fontSize = '12px';
                emailDiv.textContent = ref.sender_email || ref.email;
                metaDiv.appendChild(emailDiv);
            }
            
            if (ref.date || ref.timestamp || ref.time) {
                const dateDiv = document.createElement('div');
                dateDiv.className = 'reference-date';
                const dateStr = ref.date || ref.timestamp || ref.time;
                const formattedDate = dateStr && dateStr.includes('T') ? 
                    new Date(dateStr).toLocaleDateString() : dateStr;
                dateDiv.textContent = formattedDate;
                metaDiv.appendChild(dateDiv);
            }
        } else {
            // Standard contact info for other modes
            if (ref.contact || ref.customer_name) {
                const contactDiv = document.createElement('div');
                contactDiv.className = 'reference-contact';
                contactDiv.textContent = ref.contact || ref.customer_name || 'Contact';
                metaDiv.appendChild(contactDiv);
            }
            
            // Add date if available
            if (ref.date || ref.timestamp) {
                const dateDiv = document.createElement('div');
                dateDiv.className = 'reference-date';
                const dateStr = ref.date || ref.timestamp;
                // Format date if it's a full timestamp
                const formattedDate = dateStr.includes('T') ? 
                    new Date(dateStr).toLocaleDateString() : dateStr;
                dateDiv.textContent = formattedDate;
                metaDiv.appendChild(dateDiv);
            }
            
            // Add phone if available
            if (ref.phone || ref.phone_number) {
                const phoneDiv = document.createElement('div');
                phoneDiv.className = 'reference-phone';
                phoneDiv.textContent = ref.phone || ref.phone_number;
                metaDiv.appendChild(phoneDiv);
            }
        }
        
        headerDiv.appendChild(metaDiv);
        refDiv.appendChild(headerDiv);
        
        // Reference message/content - for email show subject, otherwise show message
        if (isEmailRef && (ref.title || ref.subject)) {
            const subjectDiv = document.createElement('div');
            subjectDiv.className = 'reference-message';
            subjectDiv.style.fontWeight = '500';
            const subject = ref.title || ref.subject;
            const truncatedSubject = subject.length > 150 ? 
                subject.substring(0, 150) + '...' : subject;
            subjectDiv.textContent = '📧 ' + truncatedSubject;
            refDiv.appendChild(subjectDiv);
        } else if (ref.message || ref.content || ref.body) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'reference-message';
            const content = ref.body || ref.message || ref.content;
            // Truncate long messages
            const truncatedContent = content.length > 200 ? 
                content.substring(0, 200) + '...' : content;
            messageDiv.textContent = truncatedContent;
            refDiv.appendChild(messageDiv);
        }
        
        // Reference actions - add buttons for email mode
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'reference-actions';
        actionsDiv.style.cssText = 'display: flex; gap: 8px; margin-top: 10px;';
        
        // For email references, ALWAYS add "View Original Email" button
        if (isEmailRef) {
            console.log('📧 Adding email buttons for ref:', ref.title || ref.subject, 'email_id:', ref.email_id);
            
            // View Full Email button - opens popup with original email content
            const viewBtn = document.createElement('button');
            viewBtn.textContent = '📄 View Original Email';
            viewBtn.style.cssText = `
                padding: 8px 16px;
                background: linear-gradient(135deg, #a31010, #c41e1e);
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                box-shadow: 0 2px 8px rgba(163, 16, 16, 0.3);
                transition: transform 0.2s, box-shadow 0.2s;
            `;
            viewBtn.onmouseover = () => {
                viewBtn.style.transform = 'translateY(-2px)';
                viewBtn.style.boxShadow = '0 4px 12px rgba(163, 16, 16, 0.4)';
            };
            viewBtn.onmouseout = () => {
                viewBtn.style.transform = 'translateY(0)';
                viewBtn.style.boxShadow = '0 2px 8px rgba(163, 16, 16, 0.3)';
            };
            viewBtn.onclick = (e) => {
                e.stopPropagation(); // Prevent triggering the parent click
                showReferencePopup(ref, index + 1, isGroupChat);
            };
            actionsDiv.appendChild(viewBtn);
            
            // Open in Gmail button (if we have thread_id or email_id)
            if (ref.email_id || ref.thread_id || ref.gmail_link) {
                const gmailUrl = ref.gmail_link || `https://mail.google.com/mail/u/0/#inbox/${ref.thread_id || ref.email_id}`;
                const gmailBtn = document.createElement('a');
                gmailBtn.href = gmailUrl;
                gmailBtn.target = '_blank';
                gmailBtn.textContent = '📧 Open in Gmail';
                gmailBtn.style.cssText = `
                    padding: 8px 16px;
                    background: linear-gradient(135deg, #4285f4, #5a95f5);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 13px;
                    font-weight: 500;
                    text-decoration: none;
                    box-shadow: 0 2px 8px rgba(66, 133, 244, 0.3);
                    transition: transform 0.2s, box-shadow 0.2s;
                `;
                gmailBtn.onmouseover = () => {
                    gmailBtn.style.transform = 'translateY(-2px)';
                    gmailBtn.style.boxShadow = '0 4px 12px rgba(66, 133, 244, 0.4)';
                };
                gmailBtn.onmouseout = () => {
                    gmailBtn.style.transform = 'translateY(0)';
                    gmailBtn.style.boxShadow = '0 2px 8px rgba(66, 133, 244, 0.3)';
                };
                gmailBtn.onclick = (e) => e.stopPropagation();
                actionsDiv.appendChild(gmailBtn);
            }
        }
        
        refDiv.appendChild(actionsDiv);
        referencesDiv.appendChild(refDiv);
    });
    
    messageDiv.appendChild(referencesDiv);
    
    console.log(`✅ Added ${limitedReferences.length} styled ${modeToUse} references`);
}

// Show reference popup with full details
function showReferencePopup(ref, number, isGroupChat = false) {
    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        backdrop-filter: blur(4px);
        animation: fadeIn 0.2s ease;
    `;
    
    // Create modal content
    const modal = document.createElement('div');
    modal.style.cssText = `
        background: var(--bg-primary);
        border-radius: var(--radius-large);
        padding: 30px;
        max-width: 600px;
        width: 90%;
        max-height: 80vh;
        overflow-y: auto;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        position: relative;
        animation: slideUp 0.3s ease;
    `;
    
    // Modal header
    const header = document.createElement('div');
    header.style.cssText = `
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
        padding-bottom: 15px;
        border-bottom: 2px solid var(--border-color);
    `;
    
    const title = document.createElement('h3');
    title.style.cssText = `
        margin: 0;
        font-size: 20px;
        color: var(--text-primary);
        display: flex;
        align-items: center;
        gap: 10px;
    `;
    
    const numberBadge = document.createElement('span');
    numberBadge.style.cssText = `
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        background: var(--accent-color);
        color: white;
        border-radius: 50%;
        font-size: 14px;
        font-weight: 600;
    `;
    numberBadge.textContent = number;
    title.appendChild(numberBadge);
    
    const titleText = document.createElement('span');
    titleText.textContent = 'Reference Details';
    title.appendChild(titleText);
    
    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '✕';
    closeBtn.style.cssText = `
        background: none;
        border: none;
        font-size: 24px;
        color: var(--text-secondary);
        cursor: pointer;
        padding: 5px 10px;
        line-height: 1;
        transition: color 0.2s;
    `;
    closeBtn.onmouseover = () => closeBtn.style.color = 'var(--accent-color)';
    closeBtn.onmouseout = () => closeBtn.style.color = 'var(--text-secondary)';
    closeBtn.onclick = () => overlay.remove();
    
    header.appendChild(title);
    header.appendChild(closeBtn);
    modal.appendChild(header);
    
    // Modal body
    const body = document.createElement('div');
    body.style.cssText = `
        color: var(--text-primary);
        line-height: 1.6;
    `;
    
    // Check if this is an email reference
    const refType = (ref.type || ref.source || currentMode).toLowerCase();
    const isEmail = refType === 'email' || refType === 'gmail';
    
    // Build fields array based on type
    let fields = [];
    
    if (isEmail) {
        // Email-specific fields
        fields = [
            { label: 'From', value: ref.sender_name || ref.contact || ref.customer_name },
            { label: 'Email', value: ref.sender_email || ref.email },
            { label: 'Subject', value: ref.title || ref.subject },
            { label: 'Date', value: ref.date || ref.timestamp || ref.time }
        ];
    } else {
        // Default fields for other modes
        fields = [
            { label: 'Contact', value: ref.contact || ref.customer_name || ref.username },
            { label: 'Phone', value: ref.phone || ref.phone_number },
            { label: 'Date', value: ref.date || ref.timestamp },
            { label: 'Message Type', value: ref.message_type },
            { label: 'Post Number', value: ref.post_number || ref.id }
        ];
    }
    
    fields.forEach(field => {
        if (field.value) {
            const fieldDiv = document.createElement('div');
            fieldDiv.style.cssText = `
                margin-bottom: 12px;
                padding: 10px;
                background: var(--bg-secondary);
                border-radius: 8px;
            `;
            
            const label = document.createElement('strong');
            label.textContent = field.label + ': ';
            label.style.color = 'var(--text-secondary)';
            
            const value = document.createElement('span');
            value.textContent = field.value;
            
            fieldDiv.appendChild(label);
            fieldDiv.appendChild(value);
            body.appendChild(fieldDiv);
        }
    });
    
    // Full message / Email body
    if (ref.message || ref.content || ref.body) {
        const messageDiv = document.createElement('div');
        messageDiv.style.cssText = `
            margin-top: 20px;
            padding: 15px;
            background: var(--bg-secondary);
            border-radius: 8px;
            border-left: 4px solid var(--accent-color);
        `;
        
        const messageLabel = document.createElement('div');
        messageLabel.textContent = isEmail ? 'Email Content:' : 'Full Message:';
        messageLabel.style.cssText = `
            font-weight: 600;
            margin-bottom: 10px;
            color: var(--text-secondary);
        `;
        
        const messageText = document.createElement('div');
        messageText.textContent = ref.body || ref.message || ref.content;
        messageText.style.cssText = `
            white-space: pre-wrap;
            word-wrap: break-word;
        `;
        
        messageDiv.appendChild(messageLabel);
        messageDiv.appendChild(messageText);
        body.appendChild(messageDiv);
    }
    
// View source button - for PakWheels, Lucid Forum, Reddit, and WhatsApp (NOT in group chat)
    console.log('Reference details:', { refType, hasUrl: !!(ref.url || ref.link), isGroupChat, ref });
    
    if (!isGroupChat && (refType === 'pakwheels' || refType === 'pakwheel' || refType === 'lucid' || refType === 'reddit' || refType === 'reddit_lucid' || refType === 'whatsapp') && (ref.url || ref.link)) {
        console.log(`✅ Showing View Original Source button for ${refType}`);
        const linkBtn = document.createElement('a');
        linkBtn.href = ref.url || ref.link;
        linkBtn.target = '_blank';
        linkBtn.textContent = '🔗 View Original Source';
        linkBtn.style.cssText = `
            display: inline-block;
            margin-top: 20px;
            padding: 12px 24px;
            background: var(--accent-color);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 500;
            transition: transform 0.2s, box-shadow 0.2s;
        `;
        linkBtn.onmouseover = () => {
            linkBtn.style.transform = 'translateY(-2px)';
            linkBtn.style.boxShadow = '0 4px 12px rgba(163, 16, 16, 0.3)';
        };
        linkBtn.onmouseout = () => {
            linkBtn.style.transform = 'translateY(0)';
            linkBtn.style.boxShadow = 'none';
        };
        body.appendChild(linkBtn);
    } else if (!isGroupChat && isEmail && (ref.email_id || ref.thread_id || ref.gmail_link)) {
        // View in Gmail button for email references
        console.log('✅ Showing View in Gmail button');
        const emailBtn = document.createElement('a');
        // Use gmail_link if available, otherwise construct from thread_id/email_id
        const gmailUrl = ref.gmail_link || `https://mail.google.com/mail/u/0/#inbox/${ref.thread_id || ref.email_id}`;
        emailBtn.href = gmailUrl;
        emailBtn.target = '_blank';
        emailBtn.textContent = '📧 View in Gmail';
        emailBtn.style.cssText = `
            display: inline-block;
            margin-top: 20px;
            padding: 12px 24px;
            background: #4285f4;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 500;
            transition: transform 0.2s, box-shadow 0.2s;
        `;
        emailBtn.onmouseover = () => {
            emailBtn.style.transform = 'translateY(-2px)';
            emailBtn.style.boxShadow = '0 4px 12px rgba(66, 133, 244, 0.3)';
        };
        emailBtn.onmouseout = () => {
            emailBtn.style.transform = 'translateY(0)';
            emailBtn.style.boxShadow = 'none';
        };
        body.appendChild(emailBtn);
    } else {
        console.log('❌ Not showing button - isGroupChat:', isGroupChat, 'refType:', refType, 'hasUrl:', !!(ref.url || ref.link));
    }
    
    modal.appendChild(body);
    overlay.appendChild(modal);
    
    // Close on overlay click
    overlay.onclick = (e) => {
        if (e.target === overlay) {
            overlay.remove();
        }
    };
    
    // Close on Escape key
    const escapeHandler = (e) => {
        if (e.key === 'Escape') {
            overlay.remove();
            document.removeEventListener('keydown', escapeHandler);
        }
    };
    document.addEventListener('keydown', escapeHandler);
    
    document.body.appendChild(overlay);
}

// Filter references by current mode to prevent wrong source mixing
function filterReferencesByMode(references, mode) {
    if (!references || !Array.isArray(references)) return [];
    
    return references.filter(ref => {
        // First check if reference has its own mode stored
        if (ref.mode) {
            const refMode = ref.mode.toLowerCase();
            const modeNormalized = mode.toLowerCase();
            
            // Match exact mode
            if (refMode === modeNormalized) return true;
            
            // Handle mode aliases
            const modeAliases = {
                'whatsapp': ['whatsapp', 'wa'],
                'pakwheels': ['pakwheels', 'pakwheel', 'pw'],
                'facebook': ['facebook', 'fb'],
                'dealership': ['dealership', 'dealer'],
                'reddit': ['reddit'],
                'reddit_lucid': ['reddit_lucid', 'reddit lucid'],
                'insights': ['insights', 'ai'],
                'email': ['email', 'gmail']
            };
            
            const aliases = modeAliases[modeNormalized] || [modeNormalized];
            return aliases.includes(refMode);
        }
        
        // Define mode aliases
        const modeAliases = {
            'whatsapp': ['whatsapp', 'wa'],
            'pakwheels': ['pakwheels', 'pakwheel', 'pw'],
            'facebook': ['facebook', 'fb'],
            'dealership': ['dealership', 'dealer'],
            'reddit': ['reddit'],
            'reddit_lucid': ['reddit_lucid', 'reddit lucid'],
            'email': ['email', 'gmail'],
            'lucid': ['lucid', 'lucid forum'],
            'insights': ['insights', 'ai']
        };
        
        const aliases = modeAliases[modeNormalized] || [modeNormalized];
        
        // Check ref.mode first
        if (ref.mode) {
            const refMode = ref.mode.toLowerCase();
            if (refMode === modeNormalized || aliases.includes(refMode)) return true;
        }
        
        // Check ref.type second
        if (ref.type) {
            const refType = ref.type.toLowerCase();
            if (refType === modeNormalized || aliases.includes(refType)) return true;
        }
        
        // Check ref.source third (for backward compatibility)
        if (ref.source) {
            const refSource = ref.source.toLowerCase();
            // Check for exact match or alias match
            if (refSource === modeNormalized || aliases.includes(refSource)) return true;
            // Also check if source contains mode name (e.g., "Lucid Forum" contains "lucid")
            if (refSource.includes(modeNormalized)) return true;
        }
        
        // If no source specified, include it (backward compatibility)
        if (!ref.mode && !ref.type && !ref.source) return true;
        
        return false;
    });
}

// Remove duplicate references based on content similarity
function removeDuplicateReferences(references) {
    if (!references || !Array.isArray(references)) return [];
    
    const uniqueRefs = [];
    const seenContent = new Set();
    
    references.forEach(ref => {
        // For email references, use email_id as unique key
        const refType = (ref.type || ref.source || '').toLowerCase();
        let contentKey;
        
        if (refType === 'email' || refType === 'gmail') {
            // Use email_id for uniqueness
            contentKey = ref.email_id || ref.thread_id || [
                (ref.title || ref.subject || '').toLowerCase().trim(),
                (ref.sender_email || '').toLowerCase().trim(),
                (ref.date || '').toLowerCase().trim()
            ].filter(Boolean).join('|');
        } else {
            // Standard deduplication for other modes
            contentKey = [
                (ref.message || ref.content || '').substring(0, 100).toLowerCase().trim(),
                (ref.contact || ref.customer_name || '').toLowerCase().trim(),
                (ref.phone || ref.phone_number || '').toLowerCase().trim(),
                (ref.date || ref.timestamp || '').toLowerCase().trim()
            ].filter(Boolean).join('|');
        }
        
        if (!seenContent.has(contentKey) && contentKey.length > 0) {
            seenContent.add(contentKey);
            uniqueRefs.push(ref);
        }
    });
    
    console.log(`🔍 Filtered ${references.length} references to ${uniqueRefs.length} unique items`);
    return uniqueRefs;
}

// Scroll to bottom
function scrollToBottom() {
    const chatArea = document.getElementById('chatArea');
    if (chatArea) {
        chatArea.scrollTop = chatArea.scrollHeight;
    }
}

// Theme functions
function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

function updateThemeIcon(theme) {
    const navLogo = document.getElementById('navLogo');
    const sidebarLogo = document.getElementById('sidebarLogo');
    
    // Update logos based on theme
    const logoSrc = theme === 'dark' 
        ? '/static/images/light-logo.svg' 
        : '/static/images/dark-logo.svg';
    
    if (navLogo) {
        navLogo.src = logoSrc;
    }
    
    if (sidebarLogo) {
        sidebarLogo.src = logoSrc;
    }
}

// Data source functions - now using panel instead of dropdown menu
// selectDataSource function remains the same as it's used by the panel

function selectDataSource(mode) {
    console.log('🔄 Selecting data source:', mode);
    console.log('📊 BEFORE - currentMode:', currentMode, 'localStorage:', localStorage.getItem('selectedMode'));
    
    // Get current permissions
    const debugPerms = document.getElementById('debug-perms');
    let userPerms = {};
    
    if (debugPerms && debugPerms.getAttribute('data-perms')) {
        try {
            userPerms = JSON.parse(debugPerms.getAttribute('data-perms'));
        } catch (e) {
            console.error('❌ Failed to parse permissions:', e);
            userPerms = {};
        }
    }
    
    // Check if user has permission for this mode
    const hasPermissionRecord = Object.keys(userPerms).length > 0;
    const permissionValue = userPerms[mode];
    const isDisabled = hasPermissionRecord && permissionValue === false;
    
    console.log(`🔐 Permission check for mode: ${mode}`);
    console.log(`   - hasRecord: ${hasPermissionRecord}`);
    console.log(`   - permission value: ${permissionValue}`);
    console.log(`   - isDisabled: ${isDisabled}`);
    
    // If user doesn't have permission, reject the selection
    if (isDisabled) {
        console.log(`🚫 ACCESS DENIED: User does not have permission for ${mode}`);
        showNotification('Access Denied', `You do not have permission to access ${mode.toUpperCase()}`, 'error');
        return;
    }
    
    console.log(`✅ ACCESS GRANTED: User has permission for ${mode}`);
    
    // If auto questions is active, stop it when changing modes
    if (autoQuestionsActive) {
        console.log('🛑 Stopping auto questions due to mode change');
        stopAutoQuestions();
    }
    
    // Check if mode is actually changing
    const modeChanged = currentMode !== mode;
    
    // Update the global variable FIRST
    currentMode = mode;
    console.log('📊 AFTER assignment - currentMode:', currentMode);
    
    // Save to localStorage immediately
    localStorage.setItem('selectedMode', mode);
    console.log('📊 AFTER localStorage - selectedMode:', localStorage.getItem('selectedMode'));
    
    updateModePlaceholder();
    
    // Handle email mode specifically - check authentication
    if (mode === 'email') {
        checkEmailAuthAndShowPanel();
    } else {
        // Remove email status panel when switching away from email mode
        const emailPanel = document.getElementById('emailStatusPanel');
        if (emailPanel) emailPanel.remove();
    }
    
    // If in group chat and user is creator, save mode to group
    if (isGroupChatMode && currentGroupId && isGroupCreator) {
        console.log('💾 Saving group mode to database:', mode);
        fetch('/api/group-chat/update-mode', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                group_id: currentGroupId,
                mode: mode
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log('✅ Group mode saved:', data);
        })
        .catch(error => {
            console.error('❌ Error saving group mode:', error);
        });
    }
    
    // If mode changed and we have an active conversation, create a new session
    if (modeChanged && conversationHistory.length > 0) {
        console.log('🔄 Mode changed from', localStorage.getItem('previousMode'), 'to', mode);
        console.log('💬 Current conversation has', conversationHistory.length, 'messages');
        console.log('🆕 Creating new session for new mode');
        
        // Save current session before switching
        saveChatHistory();
        
        // Create new session for the new mode
        createNewSession();
        
        console.log('✅ New session created for mode:', mode);
    }
    
    // Store current mode for next comparison
    localStorage.setItem('previousMode', mode);
    
    // Update quick questions for the new mode
    if (document.getElementById('quickQuestionsPanel') && 
        !document.getElementById('quickQuestionsPanel').classList.contains('hidden')) {
        updateQuickQuestionsForMode();
    }
    
    // Update chat history panel if it's open
    if (document.getElementById('chatHistoryPanel') && 
        document.getElementById('chatHistoryPanel').style.display === 'block') {
        console.log('🔄 Updating chat history panel for new mode:', mode);
        loadChatHistoryForMode();
    }
    
    // Log the current state for debugging
    console.log('✅ Data source selected FINAL:', {
        mode: currentMode,
        localStorage: localStorage.getItem('selectedMode'),
        thinking_mode: thinkingMode
    });
}

// ==================================
// EMAIL MODE FUNCTIONS
// ==================================

// Check Gmail authentication status and show email panel
function checkEmailAuthAndShowPanel() {
    console.log('📧 [DEBUG] checkEmailAuthAndShowPanel() called');
    console.log('📧 [DEBUG] Making fetch request to /email/config-status');
    
    fetch('/email/config-status')
        .then(response => {
            console.log('📧 [DEBUG] Response received:', {
                status: response.status,
                statusText: response.statusText,
                ok: response.ok,
                headers: Object.fromEntries(response.headers.entries())
            });
            
            if (!response.ok) {
                console.error('📧 [DEBUG] Response not OK:', response.status, response.statusText);
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('📧 [DEBUG] Email config status data:', JSON.stringify(data, null, 2));
            
            if (data.error) {
                console.error('📧 [DEBUG] Server returned error:', data.error);
                showNotification('Error', data.error, 'error');
                return;
            }
            
            if (!data.success) {
                console.error('📧 [DEBUG] Request was not successful:', data);
                showNotification('Error', data.message || 'Failed to get email configuration', 'error');
                return;
            }
            
            console.log('📧 [DEBUG] OAuth configured:', data.oauth_configured);
            console.log('📧 [DEBUG] LLM configured:', data.llm_configured);
            console.log('📧 [DEBUG] User logged in:', data.user_logged_in);
            console.log('📧 [DEBUG] Gmail authenticated:', data.gmail_authenticated);
            console.log('📧 [DEBUG] User email:', data.user_email);
            
            // Check if user is logged in to the app first
            if (!data.user_logged_in) {
                console.warn('📧 [DEBUG] User not logged in to app');
                showNotification('Login Required', 'Please log in to the app first to use Gmail features.', 'warning');
                return;
            }
            
            if (!data.oauth_configured) {
                console.warn('📧 [DEBUG] OAuth not configured');
                showNotification('Gmail Not Configured', 'Gmail OAuth is not configured. Please contact administrator.', 'warning');
                return;
            }
            
            if (!data.gmail_authenticated) {
                console.log('📧 [DEBUG] User not authenticated, showing auth modal');
                // Show authentication required modal
                showEmailAuthModal();
            } else {
                console.log('📧 [DEBUG] User authenticated with Gmail');
                console.log('📧 [DEBUG] Email mode is active, showing status panel');
                // User is authenticated, show compact status panel
                showEmailStatusPanel(data.user_email);
                
                // Update the chat input placeholder
                updateModePlaceholder();
            }
        })
        .catch(error => {
            console.error('📧 [DEBUG] Fetch error details:', {
                message: error.message,
                name: error.name,
                stack: error.stack
            });
            showNotification('Error', 'Failed to check email configuration: ' + error.message, 'error');
        });
}

// Show compact email status panel
function showEmailStatusPanel(userEmail) {
    // Remove existing panel if any
    const existingPanel = document.getElementById('emailStatusPanel');
    if (existingPanel) existingPanel.remove();
    
    const panel = document.createElement('div');
    panel.id = 'emailStatusPanel';
    panel.className = 'email-status-panel-expanded';
    panel.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        background: var(--bg-secondary, #1e1e1e);
        border-radius: 12px;
        padding: 16px;
        width: 260px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        z-index: 9999;
        border: 1px solid rgba(66, 133, 244, 0.3);
        transition: height 0.3s ease, padding 0.3s ease;
    `;
    
    panel.innerHTML = `
        <div class="panel-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="#4285F4">
                    <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
                </svg>
                <span style="color: var(--text-primary, #fff); font-size: 14px; font-weight: 600;">Gmail</span>
            </div>
            <div style="display: flex; gap: 8px;">
                <button id="minimizeEmailPanel" style="
                    background: transparent;
                    border: none;
                    color: var(--text-secondary, #aaa);
                    cursor: pointer;
                    font-size: 18px;
                    padding: 0;
                    width: 20px;
                    height: 20px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                " title="Minimize">−</button>
                <button id="closeEmailStatusPanel" style="
                    background: transparent;
                    border: none;
                    color: var(--text-secondary, #aaa);
                    cursor: pointer;
                    font-size: 18px;
                    padding: 0;
                    width: 20px;
                    height: 20px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                " title="Close">×</button>
            </div>
        </div>
        
        <div class="panel-content">
            <div style="
                padding: 10px;
                background: var(--bg-tertiary, #2a2a2a);
                border-radius: 6px;
                margin-bottom: 12px;
            ">
                <div style="color: var(--text-secondary, #aaa); font-size: 11px; margin-bottom: 4px;">Connected</div>
                <div style="
                    color: #4285F4;
                    font-size: 12px;
                    font-weight: 500;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                " title="${userEmail}">${userEmail || 'Unknown'}</div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px;">
                <div style="
                    padding: 8px;
                    background: var(--bg-tertiary, #2a2a2a);
                    border-radius: 6px;
                    text-align: center;
                ">
                    <div style="color: var(--text-secondary, #aaa); font-size: 10px; margin-bottom: 2px;">Indexed</div>
                    <div id="emailIndexedCount" style="color: #10b981; font-size: 16px; font-weight: 600;">
                        <span class="loading-dots">...</span>
                    </div>
                </div>
                <div style="
                    padding: 8px;
                    background: var(--bg-tertiary, #2a2a2a);
                    border-radius: 6px;
                    text-align: center;
                ">
                    <div style="color: var(--text-secondary, #aaa); font-size: 10px; margin-bottom: 2px;">Pending</div>
                    <div id="emailPendingCount" style="color: #f59e0b; font-size: 16px; font-weight: 600;">
                        <span class="loading-dots">...</span>
                    </div>
                </div>
            </div>
            
            <button id="syncEmailsStatusBtn" style="
                width: 100%;
                background: linear-gradient(135deg, #4285F4 0%, #34A853 100%);
                color: white;
                border: none;
                padding: 10px 12px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                cursor: pointer;
                margin-bottom: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                transition: transform 0.2s;
            " onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"/>
                </svg>
                Sync New Emails
            </button>
            
            <button id="disconnectGmailStatusBtn" style="
                width: 100%;
                background: transparent;
                color: #ef4444;
                border: 1px solid rgba(239, 68, 68, 0.3);
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
            " onmouseover="this.style.background='rgba(239, 68, 68, 0.1)'" onmouseout="this.style.background='transparent'">
                Disconnect Gmail
            </button>
        </div>
    `;
    
    document.body.appendChild(panel);
    
    // Load email stats
    loadEmailStatsForPanel();
    
    // Event listeners
    document.getElementById('minimizeEmailPanel').addEventListener('click', () => {
        toggleEmailPanelMinimize();
    });
    
    document.getElementById('closeEmailStatusPanel').addEventListener('click', () => {
        panel.remove();
    });
    
    document.getElementById('syncEmailsStatusBtn').addEventListener('click', () => {
        syncEmailsFromPanel();
    });
    
    document.getElementById('disconnectGmailStatusBtn').addEventListener('click', () => {
        if (confirm('Are you sure you want to disconnect your Gmail account?')) {
            disconnectGmail();
            panel.remove();
        }
    });
}

// Toggle email panel minimize/maximize
function toggleEmailPanelMinimize() {
    const panel = document.getElementById('emailStatusPanel');
    const content = panel.querySelector('.panel-content');
    const minimizeBtn = document.getElementById('minimizeEmailPanel');
    
    if (panel.classList.contains('email-status-panel-expanded')) {
        // Minimize
        panel.classList.remove('email-status-panel-expanded');
        panel.classList.add('email-status-panel-minimized');
        content.style.display = 'none';
        panel.style.width = '140px';
        panel.style.padding = '12px';
        minimizeBtn.textContent = '+';
        minimizeBtn.title = 'Maximize';
    } else {
        // Maximize
        panel.classList.remove('email-status-panel-minimized');
        panel.classList.add('email-status-panel-expanded');
        content.style.display = 'block';
        panel.style.width = '260px';
        panel.style.padding = '16px';
        minimizeBtn.textContent = '−';
        minimizeBtn.title = 'Minimize';
    }
}

// Load email stats for the compact panel
// Load email stats for the compact panel
function loadEmailStatsForPanel() {
    fetch('/email/count')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const indexedCount = data.indexed_emails || 0;
                const pendingCount = data.unindexed_emails || 0;
                
                const indexedEl = document.getElementById('emailIndexedCount');
                const pendingEl = document.getElementById('emailPendingCount');
                
                if (indexedEl) indexedEl.textContent = indexedCount;
                if (pendingEl) pendingEl.textContent = pendingCount;
                
                console.log('📊 Email stats loaded:', { indexed: indexedCount, pending: pendingCount });
            } else {
                console.warn('⚠️ Email stats request unsuccessful:', data);
                const indexedEl = document.getElementById('emailIndexedCount');
                const pendingEl = document.getElementById('emailPendingCount');
                
                if (indexedEl) indexedEl.textContent = '0';
                if (pendingEl) pendingEl.textContent = '0';
            }
        })
        .catch(error => {
            console.error('❌ Error loading email stats:', error);
            const indexedEl = document.getElementById('emailIndexedCount');
            const pendingEl = document.getElementById('emailPendingCount');
            
            if (indexedEl) indexedEl.textContent = '?';
            if (pendingEl) pendingEl.textContent = '?';
        });
}

// Sync emails from the compact panel
function syncEmailsFromPanel() {
    const btn = document.getElementById('syncEmailsStatusBtn');
    if (!btn) return;
    
    const originalHTML = btn.innerHTML;
    const indexedEl = document.getElementById('emailIndexedCount');
    const pendingEl = document.getElementById('emailPendingCount');
    
    // Show loading state
    btn.disabled = true;
    btn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="animation: spin 1s linear infinite;">
            <path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"/>
        </svg>
        Syncing...
    `;
    
    if (indexedEl) indexedEl.innerHTML = '<span class="loading-dots">...</span>';
    if (pendingEl) pendingEl.innerHTML = '<span class="loading-dots">...</span>';
    
    // Add spin animation
    const style = document.createElement('style');
    style.id = 'spin-animation-temp';
    style.textContent = `@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`;
    document.head.appendChild(style);
    
    console.log('🔄 Starting email sync...');
    
    fetch('/email/index', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            max_emails: 100,
            days_back: 30
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('✅ Email sync response:', data);
        
        if (data.success) {
            const indexed = data.indexed || 0;
            const skipped = data.skipped || 0;
            
            showNotification(
                'Sync Complete!', 
                `✅ Indexed ${indexed} new emails (${skipped} already indexed)`, 
                'success',
                5000
            );
            
            // Reload stats after sync
            setTimeout(() => {
                loadEmailStatsForPanel();
            }, 1000);
        } else {
            console.error('❌ Sync failed:', data.error);
            showNotification('Sync Failed', data.error || 'Failed to sync emails', 'error');
            
            // Reload stats anyway to show current state
            loadEmailStatsForPanel();
        }
    })
    .catch(error => {
        console.error('❌ Error syncing emails:', error);
        showNotification('Sync Failed', 'An error occurred while syncing emails', 'error');
        
        // Reload stats anyway
        loadEmailStatsForPanel();
    })
    .finally(() => {
        // Restore button
        btn.disabled = false;
        btn.innerHTML = originalHTML;
        
        // Remove animation style
        const tempStyle = document.getElementById('spin-animation-temp');
        if (tempStyle) tempStyle.remove();
    });
}

// Show email authentication modal
function showEmailAuthModal() {
    // Remove existing modal if any
    const existingModal = document.getElementById('emailAuthModal');
    if (existingModal) existingModal.remove();
    
    const modal = document.createElement('div');
    modal.id = 'emailAuthModal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
    `;
    
    modal.innerHTML = `
        <div style="
            background: var(--bg-secondary, #1e1e1e);
            border-radius: 12px;
            padding: 32px;
            max-width: 400px;
            width: 90%;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        ">
            <div style="font-size: 48px; margin-bottom: 16px;">📧</div>
            <h2 style="color: var(--text-primary, #fff); margin-bottom: 12px; font-size: 24px;">Connect Gmail</h2>
            <p style="color: var(--text-secondary, #aaa); margin-bottom: 24px; font-size: 14px; line-height: 1.5;">
                Connect your Gmail account to search and analyze your emails with AI.
                Your data stays private and secure.
            </p>
            <button id="connectGmailBtn" style="
                background: #4285F4;
                color: white;
                border: none;
                padding: 14px 28px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                display: inline-flex;
                align-items: center;
                gap: 10px;
                transition: background 0.2s;
            ">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
                </svg>
                Connect with Google
            </button>
            <p style="color: var(--text-tertiary, #666); margin-top: 16px; font-size: 12px;">
                We only request read-only access to your emails.
            </p>
            <button id="closeEmailAuthModal" style="
                background: transparent;
                border: 1px solid var(--border-color, #333);
                color: var(--text-secondary, #aaa);
                padding: 10px 20px;
                border-radius: 6px;
                margin-top: 16px;
                cursor: pointer;
            ">Cancel</button>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Event listeners
    document.getElementById('connectGmailBtn').addEventListener('click', () => {
        window.location.href = '/auth/gmail/connect';
    });
    
    document.getElementById('closeEmailAuthModal').addEventListener('click', () => {
        modal.remove();
    });
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
    });
}

// Show email panel with sync options
function showEmailPanel(userEmail) {
    // Remove existing panel if any
    const existingPanel = document.getElementById('emailSyncPanel');
    if (existingPanel) existingPanel.remove();
    
    const panel = document.createElement('div');
    panel.id = 'emailSyncPanel';
    panel.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        background: var(--bg-secondary, #1e1e1e);
        border-radius: 12px;
        padding: 20px;
        width: 300px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
        z-index: 9999;
        border: 1px solid var(--border-color, #333);
    `;
    
    panel.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <h3 style="color: var(--text-primary, #fff); margin: 0; font-size: 16px; display: flex; align-items: center; gap: 8px;">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="#4285F4">
                    <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
                </svg>
                Gmail Intelligence
            </h3>
            <button id="closeEmailPanel" style="
                background: transparent;
                border: none;
                color: var(--text-secondary, #aaa);
                cursor: pointer;
                font-size: 20px;
                padding: 4px;
            ">×</button>
        </div>
        
        <div style="padding: 12px; background: var(--bg-tertiary, #2a2a2a); border-radius: 8px; margin-bottom: 16px;">
            <div style="color: var(--text-secondary, #aaa); font-size: 12px; margin-bottom: 4px;">Connected as</div>
            <div style="color: var(--text-primary, #fff); font-size: 14px; font-weight: 500;">${userEmail || 'Unknown'}</div>
        </div>
        
        <div id="emailStats" style="margin-bottom: 16px;">
            <div style="color: var(--text-secondary, #aaa); font-size: 13px;">Loading email stats...</div>
        </div>
        
        <button id="syncEmailsBtn" style="
            width: 100%;
            background: linear-gradient(135deg, #4285F4 0%, #34A853 100%);
            color: white;
            border: none;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            margin-bottom: 12px;
        ">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"/>
            </svg>
            Sync New Emails
        </button>
        
        <button id="disconnectGmailBtn" style="
            width: 100%;
            background: transparent;
            color: var(--text-secondary, #aaa);
            border: 1px solid var(--border-color, #333);
            padding: 10px 16px;
            border-radius: 8px;
            font-size: 13px;
            cursor: pointer;
        ">Disconnect Gmail</button>
    `;
    
    document.body.appendChild(panel);
    
    // Load email stats
    loadEmailStats();
    
    // Event listeners
    document.getElementById('closeEmailPanel').addEventListener('click', () => {
        panel.remove();
    });
    
    document.getElementById('syncEmailsBtn').addEventListener('click', syncEmails);
    
    document.getElementById('disconnectGmailBtn').addEventListener('click', () => {
        if (confirm('Are you sure you want to disconnect Gmail?')) {
            disconnectGmail();
        }
    });
}

// Load email statistics
function loadEmailStats() {
    const statsContainer = document.getElementById('emailStats');
    if (!statsContainer) return;
    
    fetch('/email/count')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                statsContainer.innerHTML = `
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                        <div style="
                            background: var(--bg-tertiary, #2a2a2a);
                            padding: 12px;
                            border-radius: 8px;
                            text-align: center;
                        ">
                            <div style="color: #4285F4; font-size: 24px; font-weight: 700;">${data.indexed_emails || 0}</div>
                            <div style="color: var(--text-secondary, #aaa); font-size: 11px;">Indexed</div>
                        </div>
                        <div style="
                            background: var(--bg-tertiary, #2a2a2a);
                            padding: 12px;
                            border-radius: 8px;
                            text-align: center;
                        ">
                            <div style="color: #34A853; font-size: 24px; font-weight: 700;">${data.unindexed_emails || 0}</div>
                            <div style="color: var(--text-secondary, #aaa); font-size: 11px;">Pending</div>
                        </div>
                    </div>
                `;
            } else {
                statsContainer.innerHTML = `<div style="color: #f59e0b; font-size: 13px;">⚠️ ${data.error || 'Could not load stats'}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading email stats:', error);
            statsContainer.innerHTML = `<div style="color: #ef4444; font-size: 13px;">❌ Failed to load stats</div>`;
        });
}

// Sync emails to vector database
function syncEmails() {
    const btn = document.getElementById('syncEmailsBtn');
    if (!btn) return;
    
    const originalText = btn.innerHTML;
    btn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" class="spin-animation">
            <path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"/>
        </svg>
        Syncing...
    `;
    btn.disabled = true;
    
    // Add spin animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .spin-animation { animation: spin 1s linear infinite; }
    `;
    document.head.appendChild(style);
    
    fetch('/email/index', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            max_emails: 100,
            days_back: 30
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Sync Complete', `Indexed ${data.indexed || 0} new emails (${data.skipped || 0} already indexed)`, 'success');
            loadEmailStats();
        } else {
            showNotification('Sync Failed', data.error || 'Failed to sync emails', 'error');
        }
    })
    .catch(error => {
        console.error('Error syncing emails:', error);
        showNotification('Sync Failed', 'An error occurred while syncing emails', 'error');
    })
    .finally(() => {
        btn.innerHTML = originalText;
        btn.disabled = false;
        style.remove();
    });
}

// Disconnect Gmail
function disconnectGmail() {
    fetch('/auth/gmail/disconnect', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Gmail Disconnected', 'Your Gmail account has been disconnected successfully', 'info');
            
            // Remove sync panel if exists
            const panel = document.getElementById('emailSyncPanel');
            if (panel) panel.remove();
            
            // Switch to default mode (pakwheels) if currently in email mode
            if (currentMode === 'email') {
                selectDataSource('pakwheels');
                showNotification('Mode Changed', 'Switched to PakWheels mode', 'info');
            }
        } else {
            showNotification('Error', data.error || 'Failed to disconnect', 'error');
        }
    })
    .catch(error => {
        console.error('Error disconnecting Gmail:', error);
        showNotification('Error', 'Failed to disconnect Gmail', 'error');
    });
}

function updateDataSourceButton() {
    const btn = document.getElementById('dataSourceToggle');
    if (btn) {
        // Update icon based on selected mode
        const iconMap = {
            'pakwheels': 'M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11c-.66 0-1.22.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z',
            'whatsapp': 'M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893A11.821 11.821 0 0020.465 3.516',
            'facebook': 'M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z',
            'dealership': 'M3 13h2v8H3zm4-8h2v16H7zm4-2h2v18h-2zm4 4h2v14h-2zm4-4h2v18h-2z',
            'finance': 'M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z',
            'supplychain': 'M19 7h-3V6a4 4 0 0 0-8 0v1H5a1 1 0 0 0-1 1v11a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3V8a1 1 0 0 0-1-1zM10 6a2 2 0 0 1 4 0v1h-4V6zm8 13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V9h2v1a1 1 0 0 0 2 0V9h4v1a1 1 0 0 0 2 0V9h2v10z',
            'reddit': 'M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z',
            'insights': 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.94-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z',
            'cross_platform': 'M19.14 12.94c0.04-0.3 0.06-0.61 0.06-0.94c0-0.32-0.02-0.64-0.07-0.94l2.03-1.58c0.18-0.14 0.23-0.41 0.12-0.61l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39 0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4 2.81c-0.04-0.24-0.24-0.41-0.48-0.41h-3.84c-0.24 0-0.43 0.17-0.47 0.41L9.25 5.35C8.66 5.59 8.12 5.92 7.63 6.29L5.24 5.33c-0.22-0.08-0.47 0-0.59 0.22L2.74 8.87C2.62 9.08 2.66 9.34 2.86 9.48l2.03 1.58C4.84 11.36 4.8 11.69 4.8 12s0.02 0.64 0.07 0.94l-2.03 1.58c-0.18 0.14-0.23 0.41-0.12 0.61l1.92 3.32c0.12 0.22 0.37 0.29 0.59 0.22l2.39-0.96c0.5 0.38 1.03 0.7 1.62 0.94l0.36 2.54c0.05 0.24 0.24 0.41 0.48 0.41h3.84c0.24 0 0.44-0.17 0.47-0.41l0.36-2.54c0.59-0.24 1.13-0.56 1.62-0.94l2.39 0.96c0.22 0.08 0.47 0 0.59-0.22l1.92-3.32c0.12-0.22 0.07-0.47-0.12-0.61L19.14 12.94zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6s3.6 1.62 3.6 3.6S13.98 15.6 12 15.6z',
            'email': 'M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z'
        };
        
        const svgElement = btn.querySelector('svg path');
        if (svgElement && iconMap[currentMode]) {
            console.log('🎨 Updating data source icon to:', currentMode);
            try {
                // Use textContent to avoid HTML entity encoding issues
                svgElement.setAttribute('d', iconMap[currentMode]);
            } catch (error) {
                console.error('❌ Error updating SVG path:', error);
                // Fallback: recreate the entire SVG
                const svg = btn.querySelector('svg');
                if (svg) {
                    svg.innerHTML = `<path d="${iconMap[currentMode]}" fill="currentColor"/>`;
                }
            }
        } else {
            console.warn('⚠️ Could not update data source icon:', {
                svgElement: !!svgElement,
                currentMode: currentMode,
                hasIcon: !!iconMap[currentMode]
            });
        }
        
        if (currentMode) {
            btn.classList.add('active');
            console.log('✅ Data source button activated for mode:', currentMode);
        } else {
            btn.classList.remove('active');
            console.log('🔄 Data source button deactivated (no mode selected)');
        }
    } else {
        console.error('❌ Data source button not found in DOM');
    }
}

function updateDataSourceMenu() {
    // No longer needed - using panel instead of menu
    console.log('🔄 Data source menu update skipped (using panel instead)');
}

function updateModePlaceholder() {
    const chatInput = document.getElementById('chatInput');
    const modeDescription = document.getElementById('modeDescription');
    
    const modeInfo = {
        'pakwheels': {
            placeholder: 'Pakwheel Mode Activate',
            description: 'Analyzing PakWheels forum discussions'
        },
        'whatsapp': {
            placeholder: 'Whatsapp Mode Activate.',
            description: 'Analyzing WhatsApp support conversations'
        },
        'facebook': {
            placeholder: 'Facebook Mode Activate',
            description: 'Analyzing Facebook page interactions'
        },
        'dealership': {
            placeholder: 'Dealership Mode Activate',
            description: 'Analyzing dealership information'
        },
        'finance': {
            placeholder: 'Finance Mode Activate',
            description: 'Analyzing finance and banking information'
        },
        'supplychain': {
            placeholder: 'Supply Chain Mode Activate ',
            description: 'Analyzing supply chain operations'
        },
        'reddit': {
            placeholder: 'Reddit Mode Activate',
            description: 'Analyzing Reddit community discussions'
        },
        'lucid': {
            placeholder: 'Lucid Forum Mode Activate',
            description: 'Analyzing Lucid Forum owner discussions'
        },
        'reddit_lucid': {
            placeholder: 'Reddit Lucid Mode Activate',
            description: 'Analyzing Reddit Lucid community discussions'
        },
        'cross_platform': {
            placeholder: 'Cross Platform Mode Activate',
            description: '🔍 Multi-Source Intelligence: PakWheels • WhatsApp • Reddit • Lucid Forum'
        },
        'email': {
            placeholder: 'Ask questions about your emails...',
            description: '📧 Gmail Intelligence: Search and analyze your emails'
        },
        'insights': {
            placeholder: 'Ask me anything...',
            description: 'AI-powered insights and analysis'
        }
    };
    
    const info = modeInfo[currentMode] || modeInfo['pakwheels'];
    
    if (chatInput) {
        chatInput.placeholder = info.placeholder;
    }
    
    if (modeDescription) {
        let description = info.description;
        
        // Add thinking mode indicator
        if (thinkingMode) {
            description += ' • Thinking mode enabled';
        }
        
        // Add data availability warning for PakWheels if needed
        if (currentMode === 'pakwheels') {
            description += ' • Note: Limited PakWheels data available';
        }
        
        modeDescription.textContent = description;
    }
}

// AI Mode functions
function toggleThinkingMode() {
    thinkingMode = !thinkingMode;
    localStorage.setItem('thinkingMode', String(thinkingMode));
    updateAiModeButton();
    updateModePlaceholder(); // Update description to show thinking mode status
    
    console.log('💭 Thinking mode toggled:', thinkingMode);
}

function updateAiModeButton() {
    const btn = document.getElementById('aiModeToggle');
    if (btn) {
        if (thinkingMode) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    }
}

function loadThinkingModePreference() {
    const savedThinkingMode = localStorage.getItem('thinkingMode');
    if (savedThinkingMode !== null) {
        thinkingMode = savedThinkingMode === 'true';
        console.log('💭 Loaded thinking mode preference:', thinkingMode);
        updateAiModeButton();
    } else {
        console.log('💭 No saved thinking mode preference, using default: false');
        thinkingMode = false;
    }
}

// Group Only Mode functions
function toggleGroupOnlyMode() {
    if (!isGroupChatMode) {
        showNotification('Info', 'Group Only Mode is only available in group chats', 'info');
        return;
    }
    
    groupOnlyMode = !groupOnlyMode;
    localStorage.setItem('groupOnlyMode', groupOnlyMode);
    updateGroupOnlyModeButton();
    
    const modeText = groupOnlyMode ? 'enabled' : 'disabled';
    showNotification('Group Mode', `Group Only Mode ${modeText}. Messages will ${groupOnlyMode ? 'only go to group members' : 'be processed by bot'}.`, 'info');
    
    console.log('👥 Group Only Mode:', groupOnlyMode);
}

function updateGroupOnlyModeButton() {
    const btn = document.getElementById('groupOnlyModeBtn');
    if (btn) {
        if (groupOnlyMode) {
            btn.classList.add('active');
            btn.style.opacity = '1';
        } else {
            btn.classList.remove('active');
            btn.style.opacity = '0.6';
        }
    }
}

function loadGroupOnlyModePreference() {
    const savedGroupOnlyMode = localStorage.getItem('groupOnlyMode');
    if (savedGroupOnlyMode !== null) {
        groupOnlyMode = savedGroupOnlyMode === 'true';
        updateGroupOnlyModeButton();
    }
}

// Sidebar functions (simplified - no hide/show)
function loadRecentChatsToSidebar() {
    console.log('📂 Loading recent chats to sidebar...');
    
    const recentChatsList = document.getElementById('recentChatsSidebarList');
    if (!recentChatsList) {
        console.error('❌ Recent chats list element not found!');
        return;
    }
    
    // Show loading state
    recentChatsList.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-secondary); font-size: 13px;">Loading conversations...</div>';
    
    // Fetch from existing backend endpoint
    fetch('/api/chat/sessions')
        .then(response => {
            console.log('📡 Sessions response status:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('📊 Sessions data received:', data);
            displayRecentChatsInSidebar(data.sessions || []);
        })
        .catch(error => {
            console.error('❌ Error loading recent chats:', error);
            recentChatsList.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-secondary); font-size: 13px;">Error loading conversations</div>';
        });
    }

function displayRecentChatsInSidebar(sessions) {
    console.log('📋 Displaying recent chats in sidebar:', sessions.length, 'sessions');
    console.log('📊 Sessions data:', sessions);
    
    const recentChatsList = document.getElementById('recentChatsSidebarList');
    if (!recentChatsList) {
        console.error('❌ Recent chats list element not found!');
        return;
    }
    
    if (sessions.length === 0) {
        recentChatsList.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-secondary); font-size: 13px;">No recent conversations</div>';
        return;
    }
    
    // Create chat items with better ChatGPT-style formatting
    // Display all sessions (no limit) so users can see complete history
    recentChatsList.innerHTML = sessions.map((session, index) => {
        console.log(`📝 Processing session ${index + 1}:`, {
            session_id: session.session_id,
            mode: session.mode,
            first_query: session.first_query,
            message_count: session.message_count,
            last_updated: session.last_updated
        });
        
        // Create a better title from the first query
        let chatTitle = 'New conversation';
        if (session.first_query && session.first_query.length > 0) {
            // Clean and format the title
            chatTitle = session.first_query
                .replace(/[^\w\s]/g, '') // Remove special characters
                .trim()
                .split(' ')
                .slice(0, 6) // Take first 6 words
                .join(' ');
            
            if (session.first_query.split(' ').length > 6) {
                chatTitle += '...';
            }
        }
        
        // Format timestamp in Pakistan timezone
        let timeDisplay = 'Recently';
        if (session.last_updated) {
            try {
                const date = new Date(session.last_updated);
                const now = new Date();
                
                // Convert both to Pakistan timezone for comparison
                const pakistanNow = new Date(now.toLocaleString("en-US", {timeZone: "Asia/Karachi"}));
                const pakistanDate = new Date(date.toLocaleString("en-US", {timeZone: "Asia/Karachi"}));
                
                const diffMs = pakistanNow - pakistanDate;
                const diffMinutes = Math.floor(diffMs / (1000 * 60));
                const diffHours = Math.floor(diffMinutes / 60);
                const diffDays = Math.floor(diffHours / 24);
                
                if (diffMinutes < 1) {
                    timeDisplay = 'Just now';
                } else if (diffMinutes < 60) {
                    timeDisplay = `${diffMinutes}m ago`;
                } else if (diffHours < 24) {
                    timeDisplay = `${diffHours}h ago`;
                } else if (diffDays < 7) {
                    timeDisplay = `${diffDays}d ago`;
                } else {
                    // Show date in Pakistan timezone
                    timeDisplay = new Intl.DateTimeFormat('en-US', {
                        timeZone: 'Asia/Karachi',
                        month: 'short',
                        day: 'numeric'
                    }).format(date);
                }
            } catch (e) {
                console.warn('Error formatting timestamp:', e);
                timeDisplay = 'Recently';
            }
        }
        
        // Get mode display name and SVG icon
        const modeConfig = {
            'whatsapp': { 
                name: 'WhatsApp',
                icon: 'M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893A11.821 11.821 0 0020.465 3.516'
            },
            'pakwheels': { 
                name: 'PakWheels',
                icon: 'M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11c-.66 0-1.22.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z'
            },
            'facebook': { 
                name: 'Facebook',
                icon: 'M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14l4 4V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z'
            },
            'facebook_beta': { 
                name: 'Facebook',
                icon: 'M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z'
            },
            'dealership': { 
                name: 'Dealership',
                icon: 'M3 13h2v8H3zm4-8h2v16H7zm4-2h2v18h-2zm4 4h2v14h-2zm4-4h2v18h-2z'
            },
            'reddit': { 
                name: 'Reddit',
                icon: 'M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z'
            },
            'cross_platform': { 
                name: 'Cross-Platform',
                icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm3.5-9c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-7 0c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5 7.67 11 8.5 11zm3.5 6.5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z'
            },
            'email': {
                name: 'Gmail',
                icon: 'M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z'
            },
            'insights': { 
                name: 'Insights',
                icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.94-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z'
            }
        };
        
        const mode = modeConfig[session.mode] || { 
            name: session.mode, 
            icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.94-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z'
        };
        
        return `
            <div class="recent-chat-item" data-session-id="${session.session_id}">
                <div class="chat-header">
                    <div class="chat-title">${chatTitle}</div>
                    <div class="chat-time">${timeDisplay}</div>
                </div>
                <div class="chat-meta">
                    <span class="chat-mode">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="display: inline-block; vertical-align: middle; margin-right: 4px;">
                            <path d="${mode.icon}"/>
                        </svg>
                        ${mode.name}
                    </span>
                    <span class="chat-count">${session.message_count || 0} msgs</span>
                </div>
            </div>
        `;
    }).join('');
    
    // Add click event listeners to all chat items
    const chatItems = recentChatsList.querySelectorAll('.recent-chat-item');
    console.log('🔗 Adding click handlers to', chatItems.length, 'chat items');
    
    chatItems.forEach((item, index) => {
        const sessionId = item.getAttribute('data-session-id');
        console.log(`📌 Setting up click handler for item ${index + 1}:`, sessionId);
        
        item.addEventListener('click', function() {
            console.log('🖱️ Chat item clicked, loading session:', sessionId);
            loadChatFromSidebar(sessionId);
        });
        
        // Add hover effect
        item.style.cursor = 'pointer';
    });
    
    console.log('✅ Recent chats loaded with enhanced ChatGPT-style formatting');
}

function loadChatFromSidebar(sessionId, modeParam) {
    console.log('📂 Loading chat from sidebar, session ID:', sessionId, 'mode:', modeParam);
    
    if (!sessionId) {
        console.error('❌ No session ID provided to loadChatFromSidebar');
        return;
    }
    
    // Reset buttons to initial state when loading old chat
    const sendBtn = document.getElementById('sendBtn');
    const stopBtn = document.getElementById('stopBtn');
    if (sendBtn) sendBtn.style.display = 'flex';
    if (stopBtn) stopBtn.style.display = 'none';
    
    // Show loading state
    const messagesContainer = document.getElementById('messagesContainer');
    const welcomeScreen = document.getElementById('welcomeScreen');
    
    if (messagesContainer) {
        messagesContainer.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-secondary);">Loading conversation...</div>';
        messagesContainer.style.display = 'block';
        welcomeScreen.style.display = 'none';
    }
    
    // Determine the mode to use
    let modeToUse = modeParam;
    
    // If mode not provided as parameter, try to extract from sidebar
    if (!modeToUse) {
        const sessionItem = document.querySelector(`[data-session-id="${sessionId}"]`);
        if (sessionItem) {
            const modeSpan = sessionItem.querySelector('.chat-mode');
            if (modeSpan) {
                const modeText = modeSpan.textContent.trim().toLowerCase();
                const modeMap = {
                    'whatsapp': 'whatsapp',
                    'pakwheels': 'pakwheels',
                    'facebook': 'facebook',
                    'dealership': 'dealership',
                    'reddit': 'reddit',
                    'insights': 'insights'
                };
                modeToUse = modeMap[modeText] || modeText;
                console.log('🎯 Mode detected from UI:', modeToUse);
            }
        }
    }
    
    // Normalize mode
    if (modeToUse) {
        modeToUse = modeToUse.toLowerCase().trim();
    }
    
    console.log('🔄 Loading history with mode:', modeToUse);
    
    // Load conversation history with mode parameter
    const historyUrl = modeToUse 
        ? `/api/chat/history/${sessionId}?mode=${modeToUse}`
        : `/api/chat/history/${sessionId}`;
    
    console.log('📡 Fetching from URL:', historyUrl);
    
    fetch(historyUrl)
        .then(response => {
            console.log('📡 Chat history response status:', response.status);
            console.log('📡 Response headers:', response.headers);
            if (!response.ok) {
                return response.text().then(text => {
                    console.error('❌ Error response body:', text);
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('📊 Chat history data received:', data);
            console.log('📊 Data keys:', Object.keys(data));
            
            // Check both 'messages' and 'history' for compatibility
            const messages = data.messages || data.history || [];
            console.log('� Messages array:', messages);
            
            if (messages && Array.isArray(messages) && messages.length > 0) {
                console.log('💬 Loading', messages.length, 'messages');
                console.log('📝 First few messages:', messages.slice(0, 4));
                
                // IMPORTANT: Switch to the correct mode FIRST before loading messages
                if (data.mode) {
                    console.log('🎯 Auto-switching to mode:', data.mode);
                    selectDataSource(data.mode);
                }
                
                // Clear current conversation
                conversationHistory = [];
                
                if (messagesContainer) {
                    messagesContainer.innerHTML = '';
                    messagesContainer.style.display = 'block';
                }
                if (welcomeScreen) {
                    welcomeScreen.style.display = 'none';
                }
                
                // Load messages
                messages.forEach((msg, index) => {
                    console.log(`📝 Loading message ${index + 1}:`, {
                        role: msg.role,
                        content_length: (msg.content || '').length,
                        has_structured: !!msg.structured,
                        timestamp: msg.timestamp,
                        content_preview: (msg.content || '').substring(0, 100) + '...'
                    });
                    
                    if (msg.role && msg.content) {
                        // Clean old bot messages to remove references section and process chart code blocks
                        let cleanContent = msg.content;
                        if (msg.role === 'assistant') {
                            // Remove chart definitions from old messages (raw text format)
                            cleanContent = cleanContent.replace(/```chart[\s\S]*?```/g, '');
                            cleanContent = cleanContent.replace(/type:\s*\w+\s*\n?\s*title:\s*[^\n]+?\s*\n?\s*data:\s*\{[^}]+\}/g, '');
                            cleanContent = cleanContent.replace(/type:\s*\w+\s+title:\s*[^\n]+?\s+data:\s*\{[^}]+\}/g, '');
                            cleanContent = cleanContent.replace(/type:\s*bar\s*title:\s*[^\n]*\n?[^\n]*data:\s*\{[^}]+\}/g, '');
                            
                            // Remove references section from old bot messages
                            cleanContent = cleanContent.replace(/---\s*\n### 📋 References[\s\S]*?---/g, '');
                            cleanContent = cleanContent.replace(/📋 References[\s\S]*$/g, '');
                            cleanContent = cleanContent.replace(/\n\s*\n\s*\n+/g, '\n\n').trim();
                        }
                        
                        // Pass the actual message timestamp to addMessageToDOM
                        const messageDiv = addMessageToDOM(cleanContent, msg.role === 'user', false, msg.timestamp);
                        
                        // Process structured data if available (charts and references)
                        if (msg.role === 'assistant' && msg.structured && messageDiv) {
                            console.log('📊 Processing structured data for message:', msg.structured);
                            
                            // Render charts if available
                            if (msg.structured.charts && msg.structured.charts.length > 0) {
                                console.log(`📈 Rendering ${msg.structured.charts.length} charts`);
                                addChartsToMessage(messageDiv, msg.structured.charts);
                            }
                            
                            // Render references if available
                            if (msg.structured.references && msg.structured.references.length > 0) {
                                console.log(`📚 Rendering ${msg.structured.references.length} references`);
                                // Pass the mode from structured data if available
                                const messageMode = msg.structured.mode || currentMode;
                                addReferencesToMessage(messageDiv, msg.structured.references, messageMode);
                            }
                        } else if (msg.role === 'assistant' && messageDiv) {
                            // Fallback: Process any chart code blocks in old messages after DOM creation
                            processChartCodeBlocks(messageDiv);
                        }
                        
                        conversationHistory.push({
                            role: msg.role,
                            content: cleanContent
                        });
                    } else {
                        console.warn('⚠️ Invalid message format:', msg);
                    }
                });
                
                // Update session
                currentSessionId = sessionId;
                console.log('🔄 Updated current session ID to:', currentSessionId);
                
                // Update data source mode if available
                if (data.mode) {
                    console.log('🎯 Switching to mode:', data.mode);
                    selectDataSource(data.mode);
                }
                
                scrollToBottom();
                
                // Update active state in sidebar
                document.querySelectorAll('.recent-chat-item').forEach(item => {
                    item.classList.remove('active');
                    if (item.getAttribute('data-session-id') === sessionId) {
                        item.classList.add('active');
                        console.log('✅ Marked chat item as active:', sessionId);
                    }
                });
                
                console.log('✅ Chat loaded successfully');
            } else {
                console.warn('⚠️ No messages found in response:', data);
                if (messagesContainer) {
                    messagesContainer.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-secondary);">No messages found in this conversation.</div>';
                }
            }
        })
        .catch(error => {
            console.error('❌ Error loading chat history:', error);
            if (messagesContainer) {
                messagesContainer.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-secondary);">Error loading conversation. Please try again.</div>';
            }
        });
}

// Chat management functions
function newChat() {
    console.log('🆕 Starting new chat...');
    
    // Exit group mode if active
    if (isGroupChatMode) {
        console.log('👥 Exiting group chat mode');
        isGroupChatMode = false;
        currentGroupId = null;
        currentGroupName = null;
        groupOnlyMode = false;
        
        // Stop message polling
        stopGroupMessagePolling();
        
        // Hide group details header
        const detailsHeader = document.getElementById('groupDetailsHeader');
        if (detailsHeader) {
            detailsHeader.remove();
        }
        
        // Show mode selector again (was hidden for group members)
        const dataSourceToggle = document.getElementById('dataSourceToggle');
        if (dataSourceToggle) {
            dataSourceToggle.style.display = 'flex';
            console.log('🔓 Mode selector shown again');
        }
        
        // Hide Group Only Mode button
        const groupOnlyModeBtn = document.getElementById('groupOnlyModeBtn');
        if (groupOnlyModeBtn) {
            groupOnlyModeBtn.style.display = 'none';
        }
        
        // Hide AI Mode button (show only for group creators)
        const aiModeToggle = document.getElementById('aiModeToggle');
        if (aiModeToggle) {
            aiModeToggle.style.display = 'flex';
            console.log('🔓 AI Mode button shown again');
        }
    }
    
    // Stop auto questions if active
    if (autoQuestionsActive) {
        console.log('🛑 Stopping auto questions for new chat');
        stopAutoQuestions();
    }
    
    // Clear messages container for new chat
    const messagesContainer = document.getElementById('messagesContainer');
    if (messagesContainer) {
        messagesContainer.innerHTML = '';
        console.log('🗑️ Messages cleared');
    }
    
    // Clear conversation history
    conversationHistory = [];
    console.log('📝 Conversation history cleared');
    
    // Create new session
    createNewSession();
    
    console.log('✅ New chat started with session:', currentSessionId);
}

function clearAllChats() {
    console.log('🗑️ Clear all chats requested');
    
    if (confirm('Are you sure you want to clear all chat history?')) {
        console.log('✅ User confirmed, clearing chat history...');
        
        fetch('/api/chat/clear', { 
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        })
            .then(response => {
                console.log('📡 Clear history response status:', response.status);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('📊 Clear history response:', data);
                
                if (data.success) {
                    console.log('✅ Chat history cleared successfully');
                    
                    // Clear local storage
                    localStorage.removeItem('chatHistory');
                    
                    // Reload sidebar
                    loadRecentChatsToSidebar();
                    
                    // Start new chat
                    newChat();
                    
                    console.log('🔄 UI updated after clearing history');
                } else {
                    console.error('❌ Clear history failed:', data.error || 'Unknown error');
                    alert('Failed to clear chat history. Please try again.');
                }
            })
            .catch(error => {
                console.error('❌ Error clearing chat history:', error);
                alert('Error clearing chat history: ' + error.message);
            });
    } else {
        console.log('❌ User cancelled clear history operation');
    }
}

// Clear history for current mode only
function clearModeHistory() {
    console.log('🗑️ Clear mode history requested for mode:', currentMode);
    
    const modeNames = {
        'pakwheels': 'PakWheels',
        'whatsapp': 'WhatsApp',
        'facebook': 'Facebook',
        'dealership': 'Dealership',
        'reddit': 'Reddit',
        'insights': 'Insights'
    };
    
    const modeName = modeNames[currentMode] || currentMode.toUpperCase();
    
    if (confirm(`Are you sure you want to clear all ${modeName} chat history? This cannot be undone.`)) {
        console.log('✅ User confirmed, clearing mode history for:', currentMode);
        
        fetch('/api/chat/clear', { 
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                mode: currentMode
            })
        })
            .then(response => {
                console.log('📡 Clear mode history response status:', response.status);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('📊 Clear mode history response:', data);
                
                if (data.success) {
                    console.log(`✅ ${modeName} chat history cleared successfully`);
                    
                    // Reload chat history panel to show updated list
                    loadChatHistoryForMode();
                    
                    // Start new chat for this mode
                    newChat();
                    
                    showNotification('Success', `${modeName} history cleared`, 'success');
                    console.log('🔄 UI updated after clearing mode history');
                } else {
                    console.error('❌ Clear mode history failed:', data.error || 'Unknown error');
                    showNotification('Error', 'Failed to clear history. Please try again.', 'error');
                }
            })
            .catch(error => {
                console.error('❌ Error clearing mode history:', error);
                showNotification('Error', 'Error clearing history: ' + error.message, 'error');
            });
    } else {
        console.log('❌ User cancelled clear mode history operation');
    }
}

function saveChatHistory() {
    // Chat history is automatically saved by the backend in /chatbot_query endpoint
    // But we can also refresh the sidebar to show the latest chat
    console.log('💾 Chat history automatically saved by backend');
    
    // Refresh the sidebar to show the latest chat after a small delay
    if (conversationHistory.length > 0) {
        setTimeout(() => {
            loadRecentChatsToSidebar();
        }, 1000); // Increased delay to ensure backend has processed the save
    }
}

// Enhanced function to create a new session with proper database integration
function createNewSession() {
    // Generate a new session ID
    currentSessionId = generateSessionId();
    
    // Clear conversation history
    conversationHistory = [];
    
    // Reset buttons to initial state
    const sendBtn = document.getElementById('sendBtn');
    const stopBtn = document.getElementById('stopBtn');
    if (sendBtn) sendBtn.style.display = 'flex';
    if (stopBtn) stopBtn.style.display = 'none';
    
    // Update UI
    const messagesContainer = document.getElementById('messagesContainer');
    const welcomeScreen = document.getElementById('welcomeScreen');
    
    if (messagesContainer) {
        messagesContainer.innerHTML = '';
        messagesContainer.style.display = 'none';
    }
    
    if (welcomeScreen) {
        welcomeScreen.style.display = 'flex';
    }
    
    // Clear input
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.value = '';
        autoResize(chatInput);
    }
    
    // Remove active state from all chat items
    document.querySelectorAll('.recent-chat-item').forEach(item => {
        item.classList.remove('active');
    });
    
    console.log('🆕 New session created:', currentSessionId);
    
    // Optionally save the new session to backend
    return currentSessionId;
}

function generateSessionId() {
    return 'chat_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Test function for debugging data source functionality
window.testDataSource = function() {
    console.log('🧪 Testing data source functionality...');
    
    // Test 1: Check if elements exist
    const dataSourceToggle = document.getElementById('dataSourceToggle');
    const dataSourceMenu = document.getElementById('dataSourceMenu');
    const menuItems = document.querySelectorAll('.menu-item[data-mode]');
    
    console.log('📋 Element check:', {
        dataSourceToggle: !!dataSourceToggle,
        dataSourceMenu: !!dataSourceMenu,
        menuItemsCount: menuItems.length
    });
    
    // Test 2: List all available modes
    const modes = [];
    menuItems.forEach(item => {
        modes.push(item.getAttribute('data-mode'));
    });
    console.log('🎯 Available modes:', modes);
    
    // Test 3: Current state
    console.log('📊 Current state:', {
        currentMode: currentMode,
        thinkingMode: thinkingMode,
        buttonActive: dataSourceToggle?.classList.contains('active'),
        sessionId: currentSessionId
    });
    
    // Test 4: Test backend connectivity
    console.log('🔌 Testing backend connectivity...');
    fetch('/api/chat/sessions')
        .then(response => {
            console.log('✅ Backend connection successful:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('📊 Backend response:', data);
        })
        .catch(error => {
            console.error('❌ Backend connection failed:', error);
        });
    
    // Test 5: Try switching to each mode
    modes.forEach((mode, index) => {
        setTimeout(() => {
            console.log(`🔄 Testing mode switch to: ${mode}`);
            selectDataSource(mode);
        }, index * 1000);
    });
    
    return {
        elementsFound: !!dataSourceToggle && !!dataSourceMenu,
        modesAvailable: modes,
        currentMode: currentMode,
        backendEndpoint: '/chatbot_query'
    };
};

// Test function to debug chat history loading
window.testChatHistoryAPI = function() {
    console.log('🧪 Testing chat history API endpoints...');
    
    // Test 1: Get chat sessions
    console.log('📋 Testing /api/chat/sessions...');
    fetch('/api/chat/sessions')
        .then(response => {
            console.log('📡 Sessions API response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('📊 Sessions API data:', data);
            
            if (data.success && data.sessions && data.sessions.length > 0) {
                const firstSession = data.sessions[0];
                console.log('🎯 Testing first session:', firstSession.session_id);
                
                // Test 2: Get specific session history
                return fetch(`/api/chat/history/${firstSession.session_id}`);
            } else {
                console.log('⚠️ No sessions found');
                return null;
            }
        })
        .then(response => {
            if (response) {
                console.log('📡 History API response status:', response.status);
                return response.json();
            }
            return null;
        })
        .then(data => {
            if (data) {
                console.log('📊 History API data:', data);
                
                // Test the actual loading function
                if (data.success && (data.messages || data.history)) {
                    console.log('✅ API working, testing UI loading...');
                    const messages = data.messages || data.history;
                    console.log('💬 Messages to load:', messages.length);
                    messages.forEach((msg, i) => {
                        console.log(`Message ${i + 1}:`, {
                            role: msg.role,
                            content_preview: (msg.content || '').substring(0, 50) + '...'
                        });
                    });
                }
            }
        })
        .catch(error => {
            console.error('❌ API test failed:', error);
        });
    
    return 'Chat history API test started - check console for results';
};

// Test function to manually load a specific session
window.testLoadSession = function(sessionId) {
    if (!sessionId) {
        console.log('📋 Available sessions:');
        fetch('/api/chat/sessions')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.sessions) {
                    data.sessions.forEach((session, i) => {
                        console.log(`${i + 1}. Session: ${session.session_id} (${session.mode}) - "${session.first_query}"`);
                    });
                    console.log('💡 Use testLoadSession("session_id") to load a specific session');
                }
            });
        return;
    }
    
    console.log('🔄 Loading session:', sessionId);
    loadChatFromSidebar(sessionId);
    return `Loading session ${sessionId}...`;
};

// Test function for fast typing animation
window.testTyping = function() {
    console.log('⚡ Testing fast typing animation...');
    
    const testMessage = `# Fast Typing Test

This is a test of the new **fast line-by-line typing animation**.

## Features:
- Line-by-line typing instead of character-by-character
- Much faster animation (50ms per line vs 20ms per character)
- Better visual flow for longer messages
- Supports **markdown formatting**

### Code Example:
\`\`\`javascript
function fastTyping() {
    console.log("This types much faster!");
}
\`\`\`

> This should appear smoothly and quickly!

The typing animation is now optimized for better user experience.`;

    // Add the test message
    const botMessageDiv = addMessageToDOM(testMessage, false, true);
    typeMessage(testMessage, currentTypingElement);
    
    return 'Fast typing test started! Watch the message appear line by line.';
};

// Comprehensive test function for all chatbot functionality
window.testChatbotFunctionality = function() {
    console.log('🧪 Running comprehensive chatbot functionality test...');
    
    const results = {
        elements: {},
        functionality: {},
        backend: {},
        errors: []
    };
    
    // Test 1: Check all critical elements exist
    console.log('📋 Testing element existence...');
    const criticalElements = {
        'dataSourceToggle': document.getElementById('dataSourceToggle'),
        'dataSourceMenu': document.getElementById('dataSourceMenu'),
        'aiModeToggle': document.getElementById('aiModeToggle'),
        'chatInput': document.getElementById('chatInput'),
        'sendBtn': document.getElementById('sendBtn'),
        'chatSidebar': document.getElementById('chatSidebar'),
        'recentChatsSidebarList': document.getElementById('recentChatsSidebarList'),
        'newChatSidebarBtn': document.getElementById('newChatSidebarBtn'),
        'clearHistorySidebarBtn': document.getElementById('clearHistorySidebarBtn'),
        'messagesContainer': document.getElementById('messagesContainer'),
        'welcomeScreen': document.getElementById('welcomeScreen')
    };
    
    Object.entries(criticalElements).forEach(([name, element]) => {
        results.elements[name] = !!element;
        if (!element) {
            results.errors.push(`Missing element: ${name}`);
        }
    });
    
    // Test 2: Check data source menu items
    console.log('🎯 Testing data source menu items...');
    const menuItems = document.querySelectorAll('.menu-item[data-mode]');
    results.functionality.menuItemsCount = menuItems.length;
    
    const expectedModes = ['pakwheels', 'whatsapp', 'facebook', 'dealership', 'reddit', 'lucid', 'insights'];
    const foundModes = Array.from(menuItems).map(item => item.getAttribute('data-mode'));
    results.functionality.availableModes = foundModes;
    results.functionality.missingModes = expectedModes.filter(mode => !foundModes.includes(mode));
    
    // Test 3: Check current state
    console.log('📊 Testing current state...');
    results.functionality.currentMode = currentMode;
    results.functionality.thinkingMode = thinkingMode;
    results.functionality.sessionId = currentSessionId;
    
    // Test 4: Test data source button functionality
    console.log('🔄 Testing data source button...');
    try {
        const originalMode = currentMode;
        selectDataSource('whatsapp');
        results.functionality.dataSourceSwitching = (currentMode === 'whatsapp');
        selectDataSource(originalMode); // Restore original mode
    } catch (error) {
        results.errors.push(`Data source switching error: ${error.message}`);
        results.functionality.dataSourceSwitching = false;
    }
    
    // Test 5: Test recent chat items
    console.log('💬 Testing recent chat items...');
    const chatItems = document.querySelectorAll('.recent-chat-item');
    results.functionality.recentChatItemsCount = chatItems.length;
    
    let clickHandlersWorking = 0;
    chatItems.forEach((item, index) => {
        if (item.onclick || item.addEventListener) {
            clickHandlersWorking++;
        }
    });
    results.functionality.chatItemsWithHandlers = clickHandlersWorking;
    
    // Test 6: Test backend connectivity
    console.log('🔌 Testing backend connectivity...');
    const backendTests = [
        { endpoint: '/api/chat/sessions', description: 'Chat sessions' },
        { endpoint: '/chatbot_query', description: 'Chat query', method: 'POST' }
    ];
    
    Promise.all(backendTests.map(test => {
        const options = test.method === 'POST' ? {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: 'test', mode: 'pakwheels' })
        } : {};
        
        return fetch(test.endpoint, options)
            .then(response => ({
                endpoint: test.endpoint,
                status: response.status,
                ok: response.ok,
                description: test.description
            }))
            .catch(error => ({
                endpoint: test.endpoint,
                status: 'ERROR',
                ok: false,
                error: error.message,
                description: test.description
            }));
    })).then(backendResults => {
        results.backend = backendResults.reduce((acc, result) => {
            acc[result.endpoint] = {
                status: result.status,
                ok: result.ok,
                description: result.description,
                error: result.error
            };
            return acc;
        }, {});
        
        // Log final results
        console.log('✅ Comprehensive test completed!');
        console.table(results.elements);
        console.table(results.functionality);
        console.table(results.backend);
        
        if (results.errors.length > 0) {
            console.error('❌ Errors found:', results.errors);
        }
        
        // Summary
        const elementsWorking = Object.values(results.elements).filter(Boolean).length;
        const totalElements = Object.keys(results.elements).length;
        const backendWorking = Object.values(results.backend).filter(b => b.ok).length;
        const totalBackend = Object.keys(results.backend).length;
        
        console.log(`📊 Test Summary:
        - Elements: ${elementsWorking}/${totalElements} working
        - Menu Items: ${results.functionality.menuItemsCount} found
        - Chat Items: ${results.functionality.recentChatItemsCount} with ${results.functionality.chatItemsWithHandlers} handlers
        - Backend: ${backendWorking}/${totalBackend} endpoints working
        - Errors: ${results.errors.length}`);
        
        return results;
    });
    
    return results;
};

// Quick fix function for common issues
window.fixChatbotIssues = function() {
    console.log('🔧 Running chatbot issue fixes...');
    
    // Fix 1: Ensure event listeners are attached
    setupEventListeners();
    
    // Fix 2: Reload recent chats
    loadRecentChatsToSidebar();
    
    // Fix 3: Update UI state
    updateModePlaceholder();
    updateAiModeButton();
    
    // Fix 4: Ensure proper mode is set
    if (!currentMode) {
        currentMode = 'pakwheels';
        localStorage.setItem('selectedMode', currentMode);
    }
    
    console.log('✅ Issue fixes applied');
    return 'Chatbot issues fixed. Try testing functionality again.';
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 DOM Content Loaded, initializing chatbot...');
    
    // Small delay to ensure all elements are rendered
    setTimeout(() => {
        // Initialize mode with permission check FIRST
        initializeMode();
        
        init();
        
        // Additional setup after initialization
        setTimeout(() => {
            console.log('🔧 Running post-initialization setup...');
            
            // Ensure all event listeners are properly attached
            setupEventListeners();
            
            // Load recent chats
            loadRecentChatsToSidebar();
            
            // Update UI state
            updateModePlaceholder();
            
            console.log('✅ Post-initialization setup complete');
        }, 500);
    }, 100);
});

// Process chart code blocks in old messages and convert them to visual charts
function processChartCodeBlocks(messageDiv) {
    if (!messageDiv) return;
    
    // Find all code blocks with language-chart class
    const chartCodeBlocks = messageDiv.querySelectorAll('pre code.language-chart');
    
    chartCodeBlocks.forEach(codeBlock => {
        try {
            const chartDefinition = codeBlock.textContent.trim();
            
            // Parse the chart definition
            const lines = chartDefinition.split('\n');
            let chartType = 'bar';
            let chartTitle = 'Chart';
            let chartData = {};
            
            lines.forEach(line => {
                line = line.trim();
                if (line.startsWith('type:')) {
                    chartType = line.split(':', 2)[1].trim();
                } else if (line.startsWith('title:')) {
                    chartTitle = line.split(':', 2)[1].trim();
                } else if (line.startsWith('data:')) {
                    try {
                        const dataStr = line.split(':', 2)[1].trim();
                        chartData = JSON.parse(dataStr);
                    } catch (e) {
                        console.error('Error parsing chart data:', e);
                    }
                }
            });
            
            // Create chart object
            const chart = {
                type: chartType,
                title: chartTitle,
                data: chartData
            };
            
            // Remove the code block
            const preElement = codeBlock.closest('pre');
            if (preElement) {
                preElement.remove();
            }
            
            // Add the chart to the message
            addChartsToMessage(messageDiv, [chart]);
            
        } catch (error) {
            console.error('Error processing chart code block:', error);
            // If processing fails, just remove the code block to avoid showing raw HTML
            const preElement = codeBlock.closest('pre');
            if (preElement) {
                preElement.remove();
            }
        }
    });
}

// Add charts to message with Chart.js rendering
function addChartsToMessage(messageDiv, charts) {
    if (!charts || charts.length === 0) return;
    
    // Check if Chart.js is available
    if (typeof Chart === 'undefined') {
        console.error('❌ Chart.js is not loaded, cannot render charts');
        return;
    }
    
    // Check if charts section already exists to prevent duplication
    const existingChartsSection = messageDiv.querySelector('.charts-section');
    if (existingChartsSection) {
        console.log('⚠️ Charts already exist in message, skipping duplication');
        return;
    }
    
    // Create charts section container
    const chartsSection = document.createElement('div');
    chartsSection.className = 'charts-section';
    
    // Track rendered chart titles to avoid duplicates within this message
    const renderedChartTitles = new Set();
    
    charts.forEach((chartData, index) => {
        try {
            // Skip duplicate charts based on title and data
            const chartKey = `${chartData.title || 'Chart'}_${JSON.stringify(chartData.data)}`;
            if (renderedChartTitles.has(chartKey)) {
                console.log(`⚠️ Skipping duplicate chart: ${chartData.title}`);
                return;
            }
            renderedChartTitles.add(chartKey);
            
            // Create chart container
            const chartContainer = document.createElement('div');
            chartContainer.className = 'chart-container';
            chartContainer.style.cssText = `
                margin: 20px 0;
                padding: 20px;
                background: var(--bg-secondary);
                border-radius: var(--radius-large);
                border: 1px solid var(--border-color);
                box-shadow: var(--shadow-light);
                width: 100%;
                box-sizing: border-box;
                overflow: hidden;
            `;
            
            // Chart title
            if (chartData.title) {
                const titleDiv = document.createElement('div');
                titleDiv.className = 'chart-title';
                titleDiv.textContent = chartData.title;
                titleDiv.style.cssText = `
                    font-size: 16px;
                    font-weight: 600;
                    margin-bottom: 15px;
                    color: var(--text-primary);
                    text-align: center;
                `;
                chartContainer.appendChild(titleDiv);
            }
            
            // Create wrapper for canvas to control sizing
            const canvasWrapper = document.createElement('div');
            canvasWrapper.style.cssText = `
                position: relative;
                width: 100%;
                height: 300px;
                overflow: hidden;
            `;
            
            // Canvas for chart
            const canvas = document.createElement('canvas');
            canvas.id = `chart-${Date.now()}-${index}`;
            canvas.style.cssText = `
                max-width: 100%;
                width: 100% !important;
                height: 100% !important;
                display: block;
            `;
            canvasWrapper.appendChild(canvas);
            chartContainer.appendChild(canvasWrapper);
            
            // Prepare chart configuration
            const ctx = canvas.getContext('2d');
            const labels = Object.keys(chartData.data);
            const values = Object.values(chartData.data);
            
            // Use doughnut chart for better visualization
            const chartType = 'doughnut';
            
            console.log(`📊 Rendering chart: ${chartData.title}`, {
                type: 'doughnut',
                labels: labels,
                values: values
            });
            
            // Color schemes
            const colorSchemes = {
                bar: {
                    backgroundColor: [
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(255, 99, 132, 0.8)',
                        'rgba(255, 205, 86, 0.8)',
                        'rgba(75, 192, 192, 0.8)',
                        'rgba(153, 102, 255, 0.8)',
                        'rgba(255, 159, 64, 0.8)'
                    ],
                    borderColor: [
                        'rgba(54, 162, 235, 1)',
                        'rgba(255, 99, 132, 1)',
                        'rgba(255, 205, 86, 1)',
                        'rgba(75, 192, 192, 1)',
                        'rgba(153, 102, 255, 1)',
                        'rgba(255, 159, 64, 1)'
                    ]
                },
                pie: {
                    backgroundColor: [
                        '#FF6384',
                        '#36A2EB',
                        '#FFCE56',
                        '#4BC0C0',
                        '#9966FF',
                        '#FF9F40'
                    ]
                }
            };
            
            const colors = colorSchemes[chartType] || colorSchemes.bar;
            
            // Chart configuration - Doughnut Chart
            // Check if mobile view
            const isMobile = window.innerWidth <= 767;
            
            const config = {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        label: chartData.title || 'Data',
                        data: values,
                        backgroundColor: [
                            '#3B82F6',  // Blue
                            '#EF4444',  // Red
                            '#FBBF24',  // Amber
                            '#10B981',  // Green
                            '#8B5CF6',  // Purple
                            '#F97316',  // Orange
                            '#EC4899',  // Pink
                            '#06B6D4'   // Cyan
                        ],
                        borderColor: getComputedStyle(document.documentElement).getPropertyValue('--bg-primary').trim(),
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    layout: {
                        padding: 10
                    },
                    plugins: {
                        legend: {
                            display: !isMobile,
                            position: 'bottom',
                            labels: {
                                color: getComputedStyle(document.documentElement).getPropertyValue('--text-primary').trim(),
                                padding: 15,
                                font: {
                                    size: 12
                                },
                                usePointStyle: true,
                                pointStyle: 'circle'
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: '#fff',
                            bodyColor: '#fff',
                            borderColor: '#333',
                            borderWidth: 1,
                            padding: 10,
                            displayColors: true,
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((value / total) * 100).toFixed(1);
                                    return label + ': ' + value + ' (' + percentage + '%)';
                                }
                            }
                        }
                    }
                }
            };
            new Chart(ctx, config);
            
            // Add to charts section
            chartsSection.appendChild(chartContainer);
            
            console.log(`✅ Rendered ${chartType} chart: ${chartData.title}`);
            
        } catch (error) {
            console.error('❌ Error rendering chart:', error);
            
            // Fallback: show chart data as text
            const fallbackDiv = document.createElement('div');
            fallbackDiv.className = 'chart-fallback';
            fallbackDiv.style.cssText = `
                margin: 20px 0;
                padding: 15px;
                background: var(--message-bg);
                border-radius: 8px;
                border-left: 4px solid #ff6b6b;
            `;
            
            let fallbackContent = `<strong>📊 ${chartData.title || 'Chart Data'}</strong><br><br>`;
            Object.entries(chartData.data).forEach(([key, value]) => {
                fallbackContent += `• ${key}: ${value}<br>`;
            });
            
            fallbackDiv.innerHTML = fallbackContent;
            chartsSection.appendChild(fallbackDiv);
        }
    });
    
    // Only add charts section if it has content
    if (chartsSection.children.length > 0) {
        messageDiv.appendChild(chartsSection);
        console.log(`✅ Added ${chartsSection.children.length} unique charts to message`);
    }
}

// Grok Activation Functionality
document.addEventListener('DOMContentLoaded', function() {
    const grokBtn = document.getElementById('grokActivateBtn');
    let grokActive = false;
    
    if (grokBtn) {
        grokBtn.addEventListener('click', function() {
            grokActive = !grokActive;
            
            if (grokActive) {
                // Activate Grok mode
                grokBtn.classList.add('active');
                grokBtn.title = 'Grok AI Activated - Click to deactivate';
                
                // Show activation notification
                showNotification('🚀 Grok AI Activated! Enhanced AI capabilities enabled.', 'success');
                
                // Add visual indicator to chat
                const chatArea = document.getElementById('chatArea');
                if (chatArea) {
                    chatArea.classList.add('grok-mode');
                }
                
                // Update mode description
                const modeDescription = document.getElementById('modeDescription');
                if (modeDescription) {
                    modeDescription.textContent = 'Grok AI is active - Enhanced reasoning and analysis enabled.';
                    modeDescription.style.color = '#c1121f';
                }
                
            } else {
                // Deactivate Grok mode
                grokBtn.classList.remove('active');
                grokBtn.title = 'Activate Grok AI';
                
                // Show deactivation notification
                showNotification('Grok AI deactivated. Standard AI mode restored.', 'info');
                
                // Remove visual indicator
                const chatArea = document.getElementById('chatArea');
                if (chatArea) {
                    chatArea.classList.remove('grok-mode');
                }
                
                // Reset mode description
                const modeDescription = document.getElementById('modeDescription');
                if (modeDescription) {
                    modeDescription.textContent = 'Enterprise AI can make mistakes. Check important info.';
                    modeDescription.style.color = '';
                }
            }
            
            // Store Grok state in localStorage
            localStorage.setItem('grokActive', grokActive);
        });
        
        // Restore Grok state on page load
        const savedGrokState = localStorage.getItem('grokActive');
        if (savedGrokState === 'true') {
            grokBtn.click();
        }
    }
});

// Add Grok mode visual effects to chat area
function addGrokModeStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .chat-area.grok-mode {
            border: 2px solid rgba(193, 18, 31, 0.3);
            box-shadow: 0 0 20px rgba(193, 18, 31, 0.1);
        }
        
        .chat-area.grok-mode::before {
            content: '🚀 GROK AI ACTIVE';
            position: absolute;
            top: 10px;
            right: 20px;
            background: linear-gradient(135deg, #c1121f 0%, #ff4d4d 50%, #8f0d0d 100%);
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            z-index: 10;
            animation: grokIndicator 3s infinite;
        }
        
        @keyframes grokIndicator {
            0%, 100% { opacity: 0.8; }
            50% { opacity: 1; }
        }
    `;
    document.head.appendChild(style);
}

// Initialize Grok mode styles
addGrokModeStyles();

// ============================================
// QUICK QUESTIONS FUNCTIONALITY - LEFT SIDEBAR
// ============================================

// Toggle quick questions panel in left sidebar
function toggleQuickQuestions() {
    const panel = document.getElementById('quickQuestionsPanel');
    const recentChatsSection = document.getElementById('recentChatsSection');
    
    if (!panel || !recentChatsSection) return;
    
    const isVisible = panel.style.display === 'block';
    
    if (isVisible) {
        closeQuickQuestions();
    } else {
        // Show panel, hide recent chats
        panel.style.display = 'block';
        recentChatsSection.style.display = 'none';
        
        // Update questions based on current mode
        updateQuickQuestionsForMode();
        
        // Load custom questions
        loadCustomQuestions();
        
        console.log('📋 Quick questions panel opened for mode:', currentMode);
    }
}

// Close quick questions panel
function closeQuickQuestions() {
    const panel = document.getElementById('quickQuestionsPanel');
    const recentChatsSection = document.getElementById('recentChatsSection');
    
    if (panel) {
        panel.style.display = 'none';
    }
    if (recentChatsSection) {
        recentChatsSection.style.display = 'block';
    }
}

// Toggle chat history panel in left sidebar
function toggleChatHistory() {
    const panel = document.getElementById('chatHistoryPanel');
    const recentChatsSection = document.getElementById('recentChatsSection');
    
    if (!panel || !recentChatsSection) return;
    
    const isVisible = panel.style.display === 'block';
    
    if (isVisible) {
        closeChatHistory();
    } else {
        // Show panel, hide recent chats
        panel.style.display = 'block';
        recentChatsSection.style.display = 'none';
        
        // Load chat history for current mode
        loadChatHistoryForMode();
        
        console.log('📂 Chat history panel opened for mode:', currentMode);
    }
}

// Close chat history panel
function closeChatHistory() {
    const panel = document.getElementById('chatHistoryPanel');
    const recentChatsSection = document.getElementById('recentChatsSection');
    
    if (panel) {
        panel.style.display = 'none';
    }
    if (recentChatsSection) {
        recentChatsSection.style.display = 'block';
    }
    
    console.log('📂 Chat history panel closed, recent chats shown');
}

// Toggle groups panel in left sidebar
function toggleGroupsPanel() {
    const panel = document.getElementById('groupsPanel');
    const recentChatsSection = document.getElementById('recentChatsSection');
    
    if (!panel || !recentChatsSection) return;
    
    const isVisible = panel.style.display === 'block';
    
    if (isVisible) {
        closeGroupsPanel();
    } else {
        // Show panel, hide recent chats
        panel.style.display = 'block';
        recentChatsSection.style.display = 'none';
        
        // Load groups
        loadUserGroups();
        
        console.log('👥 Groups panel opened');
    }
}

// Close groups panel
function closeGroupsPanel() {
    const panel = document.getElementById('groupsPanel');
    const recentChatsSection = document.getElementById('recentChatsSection');
    
    if (panel) {
        panel.style.display = 'none';
    }
    if (recentChatsSection) {
        recentChatsSection.style.display = 'block';
    }
    
    console.log('👥 Groups panel closed, recent chats shown');
}

// Toggle data source panel in left sidebar
function toggleDataSourcePanel() {
    const panel = document.getElementById('dataSourcePanel');
    const recentChatsSection = document.getElementById('recentChatsSection');
    
    if (!panel || !recentChatsSection) return;
    
    const isVisible = panel.style.display === 'block';
    
    if (isVisible) {
        closeDataSourcePanel();
    } else {
        // Show panel, hide recent chats
        panel.style.display = 'block';
        recentChatsSection.style.display = 'none';
        
        // Load data sources
        loadDataSourcesToPanel();
        
        console.log('📊 Data source panel opened');
    }
}

// Close data source panel
function closeDataSourcePanel() {
    const panel = document.getElementById('dataSourcePanel');
    const recentChatsSection = document.getElementById('recentChatsSection');
    
    if (panel) {
        panel.style.display = 'none';
    }
    if (recentChatsSection) {
        recentChatsSection.style.display = 'block';
    }
    
    console.log('📊 Data source panel closed, recent chats shown');
}

// Load and display data sources in panel
// Load and display data sources in panel
function loadDataSourcesToPanel() {
    const dataSourceList = document.getElementById('dataSourceList');
    if (!dataSourceList) return;
    
    // Clear existing items
    dataSourceList.innerHTML = '<p style="padding: 12px; color: var(--text-secondary);">Loading data sources...</p>';
    
    // Get permissions from the debug element first
    const debugPerms = document.getElementById('debug-perms');
    let userPerms = {};
    
    if (debugPerms && debugPerms.getAttribute('data-perms')) {
        try {
            const permsStr = debugPerms.getAttribute('data-perms');
            console.log('📋 Raw permissions string:', permsStr);
            userPerms = JSON.parse(permsStr);
            console.log('✅ Permissions loaded from debug element:', userPerms);
            console.log('📊 Permissions JSON:', JSON.stringify(userPerms, null, 2));
            renderDataSources(userPerms);
            return;
        } catch (e) {
            console.error('❌ Failed to parse permissions from debug element:', e);
        }
    }
    
    // Fallback: fetch permissions from API
    console.log('📡 Fetching permissions from API...');
    fetch('/api/user/permissions')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('✅ Permissions fetched from API:', data.permissions);
                userPerms = data.permissions;
                renderDataSources(userPerms);
            } else {
                console.error('❌ API error:', data.error);
                renderDataSources({});
            }
        })
        .catch(error => {
            console.error('❌ Failed to fetch permissions:', error);
            renderDataSources({});
        });
}

// Render data sources based on permissions
function renderDataSources(userPerms) {
    const dataSourceList = document.getElementById('dataSourceList');
    if (!dataSourceList) return;
    
    // Get user's company from debug element
    const debugCompanyEl = document.getElementById('debug-company');
    const userCompany = debugCompanyEl ? debugCompanyEl.getAttribute('data-company') : 'haval';
    
    // Define all data sources with their display names
    const allDataSources = {
        'pakwheels': { display_name: 'PakWheels' },
        'reddit': { display_name: 'Reddit' },
        'lucid': { display_name: 'Lucid Forum' },
        'reddit_lucid': { display_name: 'Reddit Lucid' },
        'whatsapp': { display_name: 'WhatsApp' },
        'cross_platform': { display_name: 'Cross Platform' },
        'dealership': { display_name: 'Dealership' },
        'finance': { display_name: 'Finance' },
        'facebook': { display_name: 'Facebook' },
        'supplychain': { display_name: 'Supply Chain' },
        'insights': { display_name: 'AI Insights' }
    };
    
    console.log('📊 User permissions object:', userPerms);
    console.log('📊 User company:', userCompany);
    console.log('📊 All available sources:', Object.keys(allDataSources));
    console.log('📊 Has permission records:', Object.keys(userPerms).length > 0);
    
    // Clear the loading message
    dataSourceList.innerHTML = '';
    
    let visibleCount = 0;
    
    // Create buttons for each data source
    Object.entries(allDataSources).forEach(([mode, config]) => {
        const label = config.display_name || mode;
        
        // Filter data sources based on company
        if (userCompany === 'lucid') {
            // Lucid users only see: DMS, Lucid Forum, Reddit Lucid, and AI Insights
            if (!['dealership', 'lucid', 'reddit_lucid', 'insights'].includes(mode)) {
                console.log(`🚫 HIDING data source for Lucid user: ${mode}`);
                return;
            }
        }
        
        // Check if user has permission for this source
        const hasPermissionRecord = Object.keys(userPerms).length > 0;
        const permissionValue = userPerms[mode];
        const isDisabled = hasPermissionRecord && permissionValue === false;
        const isActive = mode === currentMode;
        
        console.log(`📌 Source: ${mode}`);
        console.log(`   - hasRecord: ${hasPermissionRecord}`);
        console.log(`   - permission value: ${permissionValue}`);
        console.log(`   - permission value type: ${typeof permissionValue}`);
        console.log(`   - isDisabled: ${isDisabled}`);
        console.log(`   - isActive: ${isActive}`);
        
        // Skip disabled sources - don't show them at all
        if (isDisabled) {
            console.log(`🚫 HIDING data source: ${mode} (permission=${permissionValue})`);
            return;
        }
        
        visibleCount++;
        console.log(`✅ SHOWING data source: ${mode}`);
        
        const button = document.createElement('button');
        button.className = `default-question-item ${isActive ? 'active' : ''}`;
        button.style.cssText = `
            padding: 12px;
            margin: 8px 0;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            background: ${isActive ? 'var(--accent-color)' : 'var(--bg-secondary)'};
            color: ${isActive ? 'white' : 'var(--text-primary)'};
            cursor: pointer;
            opacity: 1;
            transition: all 0.2s ease;
            text-align: left;
            font-weight: ${isActive ? '600' : '500'};
            width: 100%;
        `;
        
        button.textContent = label;
        button.setAttribute('data-mode', mode);
        
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('🖱️ Data source button clicked:', mode);
            console.log('📊 Before selection - currentMode:', currentMode);
            
            selectDataSource(mode);
            
            console.log('📊 After selection - currentMode:', currentMode);
            console.log('📊 localStorage selectedMode:', localStorage.getItem('selectedMode'));
            
            // Close panel after a brief delay to ensure selection is processed
            setTimeout(() => {
                closeDataSourcePanel();
            }, 100);
        });
        
        button.addEventListener('mouseover', function() {
            if (!isActive) {
                this.style.background = 'var(--bg-tertiary)';
            }
        });
        
        button.addEventListener('mouseout', function() {
            if (!isActive) {
                this.style.background = 'var(--bg-secondary)';
            }
        });
        
        dataSourceList.appendChild(button);
    });
    
    if (visibleCount === 0) {
        dataSourceList.innerHTML = '<p style="padding: 12px; color: var(--text-secondary);">No data sources available</p>';
    }
    
    console.log(`✅ Data sources rendered: ${visibleCount} visible, currentMode: ${currentMode}`);
}

// Load and display chat history for current mode
function loadChatHistoryForMode() {
    const historyList = document.getElementById('chatHistoryList');
    const historyTitle = document.getElementById('historyModeTitle');
    const historyIcon = document.getElementById('historyModeIcon');
    
    if (!historyList || !historyTitle) return;
    
    console.log('📂 Loading chat history for mode:', currentMode);
    
    // Update title and icon based on current mode
    const modeConfig = {
        'pakwheels': { icon: '', title: 'PakWheels History' },
        'whatsapp': { icon: '', title: 'WhatsApp History' },
        'facebook': { icon: '', title: 'Facebook History' },
        'dealership': { icon: '', title: 'Dealership History' },
        'reddit': { icon: '', title: 'Reddit History' },
        'cross_platform': { icon: '', title: 'Cross-Platform History'},
        'email': { icon: '📧', title: 'Gmail History' },
        'insights': { icon: '', title: 'Insights History' }
    };
    
    const config = modeConfig[currentMode] || { icon: '📋', title: 'History' };
    
    // Use SVG icon if available, otherwise use emoji
    if (config.svgIcon && historyIcon) {
        // Create SVG element for cross_platform
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', '20');
        svg.setAttribute('height', '20');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('fill', 'currentColor');
        
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', config.svgIcon);
        
        svg.appendChild(path);
        historyIcon.innerHTML = '';
        historyIcon.appendChild(svg);
    } else {
        historyIcon.textContent = config.icon;
    }
    
    historyTitle.textContent = config.title;
    
    // Fetch sessions for current mode
    fetch('/api/chat/sessions')
        .then(response => response.json())
        .then(data => {
            const sessions = data.sessions || [];
            console.log('📊 All sessions from API:', sessions);
            console.log('🎯 Current mode:', currentMode);
            
            // Filter sessions for current mode (case-insensitive comparison)
            const modeSpecificSessions = sessions.filter(s => {
                const sessionMode = (s.mode || '').toLowerCase().trim();
                const currentModeNorm = (currentMode || '').toLowerCase().trim();
                return sessionMode === currentModeNorm;
            });
            
            console.log(`✅ Filtered ${modeSpecificSessions.length} sessions for mode ${currentMode}`);
            
            // Clear history list
            historyList.innerHTML = '';
            
            if (modeSpecificSessions.length === 0) {
                historyList.innerHTML = `<p style="color: var(--text-secondary); font-size: 12px; padding: 8px;">No ${config.title.toLowerCase()} yet</p>`;
                return;
            }
            
            // Show all sessions for current mode in card format
            modeSpecificSessions.forEach(session => {
                const item = document.createElement('button');
                item.className = 'question-item';  // Use same styling as quick questions
                
                // Create title from first query
                let title = 'New conversation';
                if (session.first_query && session.first_query.length > 0) {
                    title = session.first_query
                        .replace(/[^\w\s]/g, '')
                        .trim()
                        .split(' ')
                        .slice(0, 6)
                        .join(' ');
                    
                    if (session.first_query.split(' ').length > 6) {
                        title += '...';
                    }
                }
                
                // Format time
                let timeDisplay = 'Recently';
                if (session.last_updated) {
                    try {
                        // Parse ISO string correctly - this handles timezone properly
                        const date = new Date(session.last_updated);
                        const now = new Date();
                        
                        // Calculate difference in milliseconds
                        const diffMs = now.getTime() - date.getTime();
                        const diffMinutes = Math.floor(diffMs / (1000 * 60));
                        const diffHours = Math.floor(diffMinutes / 60);
                        const diffDays = Math.floor(diffHours / 24);
                        
                        if (diffMinutes < 1) {
                            timeDisplay = 'Just now';
                        } else if (diffMinutes < 60) {
                            timeDisplay = `${diffMinutes}m ago`;
                        } else if (diffHours < 24) {
                            timeDisplay = `${diffHours}h ago`;
                        } else if (diffDays < 7) {
                            timeDisplay = `${diffDays}d ago`;
                        } else {
                            // For older dates, show the actual date
                            const options = { month: 'short', day: 'numeric' };
                            timeDisplay = date.toLocaleDateString('en-US', options);
                        }
                    } catch (e) {
                        console.error('Error parsing timestamp:', session.last_updated, e);
                        timeDisplay = 'Recently';
                    }
                }
                
                // Create HTML content with title, time, mode, and message count
                item.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
                        <div style="flex: 1;">
                            <div style="font-weight: 500; color: var(--text-primary); margin-bottom: 4px;">${title}</div>
                            <div style="font-size: 12px; color: var(--text-secondary); display: flex; gap: 12px;">
                                <span>${config.icon} ${config.title.split(' ')[0]}</span>
                                <span>${session.message_count || 0} msgs</span>
                            </div>
                        </div>
                        <div style="font-size: 11px; color: var(--text-secondary); white-space: nowrap;">${timeDisplay}</div>
                    </div>
                `;
                
                item.onclick = () => {
                    closeChatHistory();
                    // Pass both session ID and mode to ensure correct filtering
                    loadChatFromSidebar(session.session_id, session.mode);
                };
                
                historyList.appendChild(item);
            });
        })
        .catch(error => {
            console.error('Error loading chat history:', error);
            historyList.innerHTML = '<p style="color: var(--text-secondary); font-size: 12px; padding: 8px;">Error loading history</p>';
        });
}

// Update quick questions based on current mode
function updateQuickQuestionsForMode() {
    // Update heading based on current mode
    updateQuestionsHeading();
    
    // Load default questions for current mode
    loadDefaultQuestions();
}

// Update the questions heading based on current mode
function updateQuestionsHeading() {
    const headingElement = document.getElementById('questionsHeading');
    if (!headingElement) return;
    
    // Clear existing content
    headingElement.innerHTML = '';
    
    // Create icon and text elements
    const iconElement = document.createElement('svg');
    iconElement.setAttribute('width', '16');
    iconElement.setAttribute('height', '16');
    iconElement.setAttribute('viewBox', '0 0 24 24');
    iconElement.setAttribute('fill', 'currentColor');
    iconElement.style.marginRight = '8px';
    
    const textElement = document.createElement('span');
    
    // Define mode-specific icons and text
    const modeConfig = {
        'pakwheels': {
            icon: 'M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11c-.66 0-1.22.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z',
            text: 'PakWheels Questions'
        },
        'whatsapp': {
            icon: 'M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893A11.821 11.821 0 0020.465 3.516',
            text: 'WhatsApp Questions'
        },
        'dealership': {
            icon: 'M3 13h2v8H3zm4-8h2v16H7zm4-2h2v18h-2zm4 4h2v14h-2zm4-4h2v18h-2z',
            text: 'Dealership Questions'
        },
        'facebook': {
            icon: 'M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z',
            text: 'Facebook Questions'
        },
        'cross_platform': {
            icon: 'M19.14 12.94c0.04-0.3 0.06-0.61 0.06-0.94c0-0.32-0.02-0.64-0.07-0.94l2.03-1.58c0.18-0.14 0.23-0.41 0.12-0.61l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39 0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4 2.81c-0.04-0.24-0.24-0.41-0.48-0.41h-3.84c-0.24 0-0.43 0.17-0.47 0.41L9.25 5.35C8.66 5.59 8.12 5.92 7.63 6.29L5.24 5.33c-0.22-0.08-0.47 0-0.59 0.22L2.74 8.87C2.62 9.08 2.66 9.34 2.86 9.48l2.03 1.58C4.84 11.36 4.8 11.69 4.8 12s0.02 0.64 0.07 0.94l-2.03 1.58c-0.18 0.14-0.23 0.41-0.12 0.61l1.92 3.32c0.12 0.22 0.37 0.29 0.59 0.22l2.39-0.96c0.5 0.38 1.03 0.7 1.62 0.94l0.36 2.54c0.05 0.24 0.24 0.41 0.48 0.41h3.84c0.24 0 0.44-0.17 0.47-0.41l0.36-2.54c0.59-0.24 1.13-0.56 1.62-0.94l2.39 0.96c0.22 0.08 0.47 0 0.59-0.22l1.92-3.32c0.12-0.22 0.07-0.47-0.12-0.61L19.14 12.94zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6s3.6 1.62 3.6 3.6S13.98 15.6 12 15.6z',
            text: 'Cross-Platform Questions'
        },
        'finance': {
            icon: 'M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z',
            text: 'Finance Questions'
        },
        'supplychain': {
            icon: 'M19 7h-3V6a4 4 0 0 0-8 0v1H5a1 1 0 0 0-1 1v11a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3V8a1 1 0 0 0-1-1zM10 6a2 2 0 0 1 4 0v1h-4V6zm8 13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V9h2v1a1 1 0 0 0 2 0V9h4v1a1 1 0 0 0 2 0V9h2v10z',
            text: 'Supply Chain Questions'
        },
        'reddit': {
            icon: 'M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z',
            text: 'Reddit Questions'
        },
        'cross_platform': {
            icon: 'M19.14 12.94c0.04-0.3 0.06-0.61 0.06-0.94c0-0.32-0.02-0.64-0.07-0.94l2.03-1.58c0.18-0.14 0.23-0.41 0.12-0.61l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39 0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4 2.81c-0.04-0.24-0.24-0.41-0.48-0.41h-3.84c-0.24 0-0.43 0.17-0.47 0.41L9.25 5.35C8.66 5.59 8.12 5.92 7.63 6.29L5.24 5.33c-0.22-0.08-0.47 0-0.59 0.22L2.74 8.87C2.62 9.08 2.66 9.34 2.86 9.48l2.03 1.58C4.84 11.36 4.8 11.69 4.8 12s0.02 0.64 0.07 0.94l-2.03 1.58c-0.18 0.14-0.23 0.41-0.12 0.61l1.92 3.32c0.12 0.22 0.37 0.29 0.59 0.22l2.39-0.96c0.5 0.38 1.03 0.7 1.62 0.94l0.36 2.54c0.05 0.24 0.24 0.41 0.48 0.41h3.84c0.24 0 0.44-0.17 0.47-0.41l0.36-2.54c0.59-0.24 1.13-0.56 1.62-0.94l2.39 0.96c0.22 0.08 0.47 0 0.59-0.22l1.92-3.32c0.12-0.22 0.07-0.47-0.12-0.61L19.14 12.94zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6s3.6 1.62 3.6 3.6S13.98 15.6 12 15.6z',
            text: 'Cross-Platform Questions'
        },
        'email': {
            icon: 'M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z',
            text: 'Gmail Questions'
        },
        'insights': {
            icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.94-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z',
            text: 'AI Insights Questions'
        }
    };
    
    // Get config for current mode or use default
    const config = modeConfig[currentMode] || {
        icon: 'M4 6h16v2H4zm0 5h16v2H4zm0 5h16v2H4z', // Default list icon
        text: 'Quick Questions'
    };
    
    // Create path element for the icon
    const pathElement = document.createElement('path');
    pathElement.setAttribute('d', config.icon);
    iconElement.appendChild(pathElement);
    
    // Set text content
    textElement.textContent = config.text;
    
    // Append icon and text to heading
    headingElement.appendChild(iconElement);
    headingElement.appendChild(textElement);
    
    console.log(`✅ Updated heading for mode ${currentMode}: ${config.text}`);
}

// Load default questions from JSON config for current mode
function loadDefaultQuestions() {
    const defaultQuestionsList = document.getElementById('defaultQuestionsList');
    if (!defaultQuestionsList) return;
    
    // Show loading state
    defaultQuestionsList.innerHTML = '<div class="loading-questions">Loading questions...</div>';
    
    // Fetch default questions from the enhanced API (which includes both default and user questions)
    fetch(`/api/quick-questions/list?mode=${currentMode}&limit=20`)
        .then(response => {
            console.log(`[QuickQ] API response status: ${response.status} for mode: ${currentMode}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log(`[QuickQ] API response data:`, data);
            
            defaultQuestionsList.innerHTML = '';
            
            // Check if API returned an error
            if (!data.success) {
                console.log(`[QuickQ] API returned success=false for mode: ${currentMode}`);
                console.log(`[QuickQ] Error: ${data.error}`);
                defaultQuestionsList.innerHTML = '<p style="color: var(--text-secondary); font-size: 12px; padding: 8px;">Error loading questions</p>';
                return;
            }
            
            if (!data.questions || data.questions.length === 0) {
                console.log(`[QuickQ] No questions in response for mode: ${currentMode}`);
                console.log(`[QuickQ] Response keys:`, Object.keys(data));
                defaultQuestionsList.innerHTML = '<p style="color: var(--text-secondary); font-size: 12px; padding: 8px;">No questions available for this mode</p>';
                return;
            }
            
            console.log(`[QuickQ] Total questions in response: ${data.questions.length}`);
            
            // Filter to show only default questions in the main section
            const defaultQuestions = data.questions.filter(q => q.is_default);
            
            console.log(`[QuickQ] Default questions after filtering: ${defaultQuestions.length}`);
            
            if (defaultQuestions.length === 0) {
                console.log(`[QuickQ] No default questions found for mode: ${currentMode}`);
                defaultQuestionsList.innerHTML = '<p style="color: var(--text-secondary); font-size: 12px; padding: 8px;">No default questions available</p>';
                return;
            }
            
            // Display default questions (limit to first 10 for main section)
            defaultQuestions.slice(0, 10).forEach((q, index) => {
                const questionBtn = document.createElement('button');
                questionBtn.className = 'question-item default-question-item';
                questionBtn.textContent = q.question;
                questionBtn.onclick = function() {
                    askQuestion(this);
                };
                
                // Add visual indicator for default questions
                questionBtn.style.borderLeft = '3px solid var(--primary-color)';
                questionBtn.title = 'Default question';
                
                defaultQuestionsList.appendChild(questionBtn);
            });
            
            console.log(`✅ Loaded ${defaultQuestions.length} default questions for mode: ${currentMode}`);
        })
        .catch(error => {
            console.error('❌ Error loading default questions:', error);
            console.error('[QuickQ] Error details:', error.message);
            defaultQuestionsList.innerHTML = '<p style="color: var(--text-secondary); font-size: 12px; padding: 8px;">Error loading questions</p>';
        });
}

// Ask a question from the quick questions list
function askQuestion(button) {
    const question = button.textContent.trim();
    const chatInput = document.getElementById('chatInput');
    
    if (chatInput && question) {
        chatInput.value = question;
        autoResize(chatInput);
        
        // Close the panel
        closeQuickQuestions();
        
        // Focus on input
        chatInput.focus();
        
        console.log('📝 Question selected:', question);
    }
}

// Add custom question and save to server
function addCustomQuestion() {
    const input = document.getElementById('customQuestionInput');
    if (!input) return;
    
    const question = input.value.trim();
    
    if (!question) {
        alert('Please enter a question');
        return;
    }
    
    // Save to server
    fetch('/api/quick-questions/add', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            question: question,
            mode: currentMode
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Clear input
            input.value = '';
            
            // Reload custom questions display
            loadCustomQuestions();
            
            console.log('✅ Custom question added:', question);
        } else {
            alert('Failed to save question: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('❌ Error saving question:', error);
        alert('Failed to save question. Please try again.');
    });
}

// Load custom questions from server
function loadCustomQuestions() {
    const customQuestionsList = document.getElementById('customQuestionsList');
    if (!customQuestionsList) return;
    
    // Fetch from server with limit of 100 questions
    fetch(`/api/quick-questions/list?mode=${currentMode}&limit=100`)
        .then(response => response.json())
        .then(data => {
            // Clear existing
            customQuestionsList.innerHTML = '';
            
            if (!data.questions || data.questions.length === 0) {
                customQuestionsList.innerHTML = '<p style="color: var(--text-secondary); font-size: 12px; padding: 8px;">No questions available</p>';
                return;
            }
            
            // Add summary info
            const summaryDiv = document.createElement('div');
            summaryDiv.className = 'questions-summary';
            summaryDiv.innerHTML = `
                <div style="font-size: 11px; color: var(--text-secondary); padding: 4px 8px; border-bottom: 1px solid var(--border-color);">
                    📊 ${data.total_count} total • ${data.default_count} default • ${data.user_count} custom
                </div>
            `;
            customQuestionsList.appendChild(summaryDiv);
            
            // Display questions (both default and user)
            data.questions.forEach((q, index) => {
                const questionDiv = document.createElement('div');
                questionDiv.className = `custom-question-item ${q.is_default ? 'default-question' : 'user-question'}`;
                
                const questionBtn = document.createElement('button');
                questionBtn.className = 'question-item';
                questionBtn.textContent = q.question;
                questionBtn.onclick = function() {
                    askQuestion(this);
                };
                
                // Add indicator for default vs user questions
                if (q.is_default) {
                    questionBtn.style.background = 'var(--bg-tertiary)';
                    questionBtn.style.borderLeft = '3px solid var(--primary-color)';
                }
                
                const actionsDiv = document.createElement('div');
                actionsDiv.className = 'custom-question-actions';
                
                // Only show edit/delete for user questions that belong to current user
                if (q.can_edit || q.can_delete) {
                    // Edit button
                    if (q.can_edit) {
                        const editBtn = document.createElement('button');
                        editBtn.className = 'edit-question-btn';
                        editBtn.innerHTML = '✏️';
                        editBtn.title = 'Edit question';
                        editBtn.onclick = function(e) {
                            e.stopPropagation();
                            editCustomQuestion(q.id, q.question);
                        };
                        actionsDiv.appendChild(editBtn);
                    }
                    
                    // Delete button
                    if (q.can_delete) {
                        const deleteBtn = document.createElement('button');
                        deleteBtn.className = 'delete-question-btn';
                        deleteBtn.innerHTML = '🗑️';
                        deleteBtn.title = 'Delete question';
                        deleteBtn.onclick = function(e) {
                            e.stopPropagation();
                            deleteCustomQuestion(q.id);
                        };
                        actionsDiv.appendChild(deleteBtn);
                    }
                } else if (q.is_default) {
                    // Add default indicator
                    const defaultIndicator = document.createElement('span');
                    defaultIndicator.className = 'default-indicator';
                    defaultIndicator.innerHTML = '🔒';
                    defaultIndicator.title = 'Default question';
                    defaultIndicator.style.color = 'var(--text-secondary)';
                    defaultIndicator.style.fontSize = '12px';
                    actionsDiv.appendChild(defaultIndicator);
                }
                
                questionDiv.appendChild(questionBtn);
                questionDiv.appendChild(actionsDiv);
                customQuestionsList.appendChild(questionDiv);
            });
        })
        .catch(error => {
            console.error('❌ Error loading questions:', error);
            customQuestionsList.innerHTML = '<p style="color: var(--text-secondary); font-size: 12px; padding: 8px;">Error loading questions</p>';
        });
}

// Edit custom question - inline editing
function editCustomQuestion(questionId, currentText) {
    // Find the question item in the DOM
    const customQuestionsList = document.getElementById('customQuestionsList');
    if (!customQuestionsList) return;
    
    const items = customQuestionsList.querySelectorAll('.custom-question-item');
    let targetItem = null;
    
    for (let item of items) {
        const btn = item.querySelector('.question-item');
        if (btn && btn.textContent === currentText) {
            targetItem = item;
            break;
        }
    }
    
    if (!targetItem) return;
    
    // Get the question button
    const questionBtn = targetItem.querySelector('.question-item');
    const actionsDiv = targetItem.querySelector('.custom-question-actions');
    
    // Hide the button and actions
    questionBtn.style.display = 'none';
    actionsDiv.style.display = 'none';
    
    // Create edit input
    const editInput = document.createElement('input');
    editInput.type = 'text';
    editInput.value = currentText;
    editInput.className = 'edit-question-input';
    
    // Create save/cancel buttons
    const editActions = document.createElement('div');
    editActions.className = 'edit-question-actions';
    
    const saveBtn = document.createElement('button');
    saveBtn.innerHTML = '✓';
    saveBtn.title = 'Save';
    saveBtn.className = 'save-edit-btn';
    
    const cancelBtn = document.createElement('button');
    cancelBtn.innerHTML = '✕';
    cancelBtn.title = 'Cancel';
    cancelBtn.className = 'cancel-edit-btn';
    
    // Cancel edit function
    const cancelEdit = () => {
        editInput.remove();
        editActions.remove();
        questionBtn.style.display = 'block';
        actionsDiv.style.display = 'flex';
    };
    
    // Save edit function
    const saveEdit = () => {
        const newText = editInput.value.trim();
        
        if (!newText || newText === currentText) {
            cancelEdit();
            return;
        }
        
        // Show loading state
        saveBtn.innerHTML = '⏳';
        saveBtn.disabled = true;
        cancelBtn.disabled = true;
        
        fetch('/api/quick-questions/edit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                id: questionId,
                question: newText
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                loadCustomQuestions();
                console.log('✅ Question updated');
            } else {
                alert('Failed to update question: ' + (data.error || 'Unknown error'));
                cancelEdit();
            }
        })
        .catch(error => {
            console.error('❌ Error updating question:', error);
            alert('Failed to update question. Please try again.');
            cancelEdit();
        });
    };
    
    // Event listeners
    saveBtn.onclick = saveEdit;
    cancelBtn.onclick = cancelEdit;
    
    editInput.onkeydown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            saveEdit();
        } else if (e.key === 'Escape') {
            e.preventDefault();
            cancelEdit();
        }
    };
    
    // Add to DOM
    editActions.appendChild(saveBtn);
    editActions.appendChild(cancelBtn);
    
    targetItem.insertBefore(editInput, questionBtn);
    targetItem.insertBefore(editActions, questionBtn);
    
    // Focus the input
    editInput.focus();
    editInput.select();
}

// Delete custom question
function deleteCustomQuestion(questionId) {
    if (!confirm('Are you sure you want to delete this question?')) {
        return;
    }
    
    fetch('/api/quick-questions/delete', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            id: questionId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            loadCustomQuestions();
            console.log('🗑️ Question deleted');
        } else {
            alert('Failed to delete question: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('❌ Error deleting question:', error);
        alert('Failed to delete question. Please try again.');
    });
}

// Make functions globally available
window.askQuestion = askQuestion;
window.addCustomQuestion = addCustomQuestion;
window.closeQuickQuestions = closeQuickQuestions;
window.closeChatHistory = closeChatHistory;
window.closeGroupsPanel = closeGroupsPanel;
window.closeDataSourcePanel = closeDataSourcePanel;

// ============================================
// AUTO QUESTIONS FUNCTIONALITY
// ============================================

// Auto questions state
let autoQuestionsActive = false;
let autoQuestionsQueue = [];
let autoQuestionsCurrentIndex = 0;
let autoQuestionsWaitingForResponse = false;

// Initialize auto questions button
function initAutoQuestions() {
    const autoQuestionBtn = document.getElementById('autoQuestionBtn');
    if (autoQuestionBtn) {
        autoQuestionBtn.addEventListener('click', toggleAutoQuestions);
        console.log('✅ Auto questions button event listener added');
    } else {
        console.warn('⚠️ Auto questions button not found');
    }
}

// Toggle auto questions mode
function toggleAutoQuestions() {
    if (autoQuestionsActive) {
        stopAutoQuestions();
    } else {
        // Safety check: don't start if currently typing
        if (isTyping) {
            alert('Please wait for the current response to complete before starting auto questions.');
            return;
        }
        startAutoQuestions();
    }
}

// Start auto questions sequence
function startAutoQuestions() {
    console.log('🚀 Starting auto questions for mode:', currentMode);
    
    // Get random questions for current mode
    fetch(`/api/quick-questions/list?mode=${currentMode}&limit=100`)
        .then(response => response.json())
        .then(data => {
            if (!data.questions || data.questions.length === 0) {
                alert('No questions available for this mode');
                return;
            }
            
            // Get all questions (both default and custom)
            const allQuestions = data.questions.map(q => q.question);
            
            // Shuffle and select 5 random questions
            const shuffled = [...allQuestions].sort(() => 0.5 - Math.random());
            autoQuestionsQueue = shuffled.slice(0, 5);
            
            if (autoQuestionsQueue.length === 0) {
                alert('No questions available for auto mode');
                return;
            }
            
            // Start the sequence
            autoQuestionsActive = true;
            autoQuestionsCurrentIndex = 0;
            autoQuestionsWaitingForResponse = false;
            
            updateAutoQuestionButton();
            showAutoQuestionsIndicator();
            
            console.log('📋 Auto questions queue:', autoQuestionsQueue);
            
            // Send first question
            sendNextAutoQuestion();
        })
        .catch(error => {
            console.error('❌ Error loading questions for auto mode:', error);
            alert('Failed to load questions for auto mode');
        });
}

// Stop auto questions sequence
function stopAutoQuestions() {
    console.log('⏹️ Stopping auto questions');
    
    autoQuestionsActive = false;
    autoQuestionsQueue = [];
    autoQuestionsCurrentIndex = 0;
    autoQuestionsWaitingForResponse = false;
    
    updateAutoQuestionButton();
    hideAutoQuestionsIndicator();
}

// Send next question in the auto sequence
function sendNextAutoQuestion() {
    if (!autoQuestionsActive || autoQuestionsCurrentIndex >= autoQuestionsQueue.length) {
        // Sequence complete
        console.log('✅ Auto questions sequence completed');
        stopAutoQuestions();
        return;
    }
    
    if (autoQuestionsWaitingForResponse) {
        console.log('⏳ Still waiting for previous response, skipping...');
        return;
    }
    
    // Safety check: don't send if already typing or user is actively using chat
    if (isTyping) {
        console.log('⏳ System is typing, delaying auto question...');
        setTimeout(() => sendNextAutoQuestion(), 1000);
        return;
    }
    
    const question = autoQuestionsQueue[autoQuestionsCurrentIndex];
    console.log(`📤 Sending auto question ${autoQuestionsCurrentIndex + 1}/5: ${question}`);
    
    // Set the question in the input
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.value = question;
        autoResize(chatInput);
        
        // Mark as waiting for response
        autoQuestionsWaitingForResponse = true;
        
        // Send the message
        sendMessage();
        
        // Move to next question
        autoQuestionsCurrentIndex++;
        
        updateAutoQuestionButton();
    }
}

// Update auto question button appearance
function updateAutoQuestionButton() {
    const autoQuestionBtn = document.getElementById('autoQuestionBtn');
    const autoQuestionBtnText = document.getElementById('autoQuestionBtnText');
    
    if (!autoQuestionBtn || !autoQuestionBtnText) return;
    
    if (autoQuestionsActive) {
        autoQuestionBtn.classList.remove('secondary');
        autoQuestionBtn.classList.add('primary');
        autoQuestionBtn.style.background = 'var(--accent-color)';
        autoQuestionBtn.style.color = 'white';
        
        if (autoQuestionsWaitingForResponse) {
            autoQuestionBtnText.textContent = `Stop Auto (${autoQuestionsCurrentIndex}/5) ⏳`;
        } else {
            autoQuestionBtnText.textContent = `Stop Auto (${autoQuestionsCurrentIndex}/5)`;
        }
        
        // Update SVG to stop icon
        const svg = autoQuestionBtn.querySelector('svg path');
        if (svg) {
            svg.setAttribute('d', 'M6 6h12v12H6z'); // Stop/square icon
        }
    } else {
        autoQuestionBtn.classList.remove('primary');
        autoQuestionBtn.classList.add('secondary');
        autoQuestionBtn.style.background = '';
        autoQuestionBtn.style.color = '';
        autoQuestionBtnText.textContent = 'Auto Questions';
        
        // Update SVG to play icon
        const svg = autoQuestionBtn.querySelector('svg path');
        if (svg) {
            svg.setAttribute('d', 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z'); // Play/check icon
        }
    }
}

// Hook into the existing message sending system to detect when responses complete
function onAutoQuestionResponseComplete() {
    if (autoQuestionsActive && autoQuestionsWaitingForResponse) {
        console.log('✅ Auto question response completed, preparing next question...');
        autoQuestionsWaitingForResponse = false;
        
        // Wait a bit before sending next question for better UX
        setTimeout(() => {
            if (autoQuestionsActive) {
                sendNextAutoQuestion();
            }
        }, 2000); // 2 second delay between questions
    }
}

// Make auto questions functions globally available
window.toggleAutoQuestions = toggleAutoQuestions;
window.startAutoQuestions = startAutoQuestions;
window.stopAutoQuestions = stopAutoQuestions;

// Show auto questions indicator in chat area
function showAutoQuestionsIndicator() {
    // Remove existing indicator
    hideAutoQuestionsIndicator();
    
    const messagesContainer = document.getElementById('messagesContainer');
    if (!messagesContainer) return;
    
    const indicator = document.createElement('div');
    indicator.id = 'autoQuestionsIndicator';
    indicator.className = 'auto-questions-indicator';
    
    // Show the queue of questions
    const queuePreview = autoQuestionsQueue.slice(0, 3).map((q, i) => 
        `${i + 1}. ${q.length > 50 ? q.substring(0, 50) + '...' : q}`
    ).join('<br>');
    
    indicator.innerHTML = `
        <div class="indicator-content">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
            <div class="indicator-text">
                <div><strong>Auto Questions Active (${currentMode.toUpperCase()})</strong></div>
                <div style="font-size: 12px; opacity: 0.9; margin-top: 4px;">
                    Next questions:<br>${queuePreview}
                    ${autoQuestionsQueue.length > 3 ? '<br>+ ' + (autoQuestionsQueue.length - 3) + ' more...' : ''}
                </div>
            </div>
            <button onclick="stopAutoQuestions()" class="stop-auto-btn">Stop</button>
        </div>
    `;
    
    messagesContainer.appendChild(indicator);
    scrollToBottom();
}

// Hide auto questions indicator
function hideAutoQuestionsIndicator() {
    const indicator = document.getElementById('autoQuestionsIndicator');
    if (indicator) {
        indicator.remove();
    }
}

// ============================================================================
// MOBILE SIDEBAR TOGGLE - Hamburger Menu
// ============================================================================

// Toggle mobile sidebar visibility
function toggleMobileSidebar() {
    const sidebar = document.getElementById('chatSidebar');
    const hamburgerMenu = document.getElementById('hamburgerMenu');
    
    if (!sidebar || !hamburgerMenu) {
        console.warn('⚠️ Sidebar or hamburger menu not found');
        console.log('Sidebar:', sidebar);
        console.log('Hamburger:', hamburgerMenu);
        return;
    }
    
    // Toggle sidebar visibility
    const isOpen = sidebar.classList.contains('mobile-open');
    
    console.log('📱 Before toggle - isOpen:', isOpen);
    console.log('📱 Sidebar classes:', sidebar.className);
    
    if (isOpen) {
        // Close sidebar
        sidebar.classList.remove('mobile-open');
        hamburgerMenu.classList.remove('active');
        console.log('📱 Mobile sidebar closed');
        console.log('📱 After close - classes:', sidebar.className);
    } else {
        // Open sidebar
        sidebar.classList.add('mobile-open');
        hamburgerMenu.classList.add('active');
        console.log('📱 Mobile sidebar opened');
        console.log('📱 After open - classes:', sidebar.className);
        console.log('📱 Sidebar computed style:', window.getComputedStyle(sidebar).transform);
    }
}

// Close mobile sidebar when a panel is opened
function closeMobileSidebar() {
    const sidebar = document.getElementById('chatSidebar');
    const hamburgerMenu = document.getElementById('hamburgerMenu');
    
    if (sidebar && hamburgerMenu) {
        sidebar.classList.remove('mobile-open');
        hamburgerMenu.classList.remove('active');
        console.log('📱 Mobile sidebar closed via closeMobileSidebar');
    }
}

// Add click handler to close sidebar when clicking backdrop (on mobile)
document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('chatSidebar');
    if (sidebar) {
        sidebar.addEventListener('click', function(e) {
            // Only close if clicking on the backdrop (::after pseudo-element area)
            // Check if click is outside the sidebar content
            if (e.target === sidebar) {
                closeMobileSidebar();
            }
        });
    }
});

// ============================================================================
// GROUP CHAT FUNCTIONALITY - Simple Group Sharing
// ============================================================================

// Show Create Group Modal
function showCreateGroupModal() {
    console.log('🔧 Opening Create Group modal');
    
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        backdrop-filter: blur(4px);
    `;
    
    const modal = document.createElement('div');
    modal.style.cssText = `
        background: var(--bg-primary);
        border-radius: 12px;
        padding: 30px;
        max-width: 500px;
        width: 90%;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        animation: slideUp 0.3s ease;
        max-height: 90vh;
        overflow-y: auto;
    `;
    
    modal.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid var(--border-color);">
            <h3 style="margin: 0; font-size: 20px; color: var(--text-primary);">Create Group Chat</h3>
            <button onclick="this.closest('[data-overlay]').remove()" style="background: none; border: none; font-size: 24px; color: var(--text-secondary); cursor: pointer; padding: 5px 10px;">✕</button>
        </div>
        
        <div style="margin-bottom: 20px;">
            <label style="display: block; margin-bottom: 8px; color: var(--text-secondary); font-weight: 500;">Group Name</label>
            <input type="text" id="groupNameInput" placeholder="Enter group name..." style="width: 100%; padding: 10px 12px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--bg-secondary); color: var(--text-primary); font-family: inherit; box-sizing: border-box;">
        </div>
        
        <div style="margin-bottom: 20px;">
            <label style="display: block; margin-bottom: 8px; color: var(--text-secondary); font-weight: 500;">Select Users to Invite</label>
            <div id="userDropdownContainer" style="position: relative; margin-bottom: 10px;">
                <button id="userDropdownBtn" style="width: 100%; padding: 10px 12px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--bg-secondary); color: var(--text-primary); font-family: inherit; box-sizing: border-box; text-align: left; cursor: pointer; display: flex; justify-content: space-between; align-items: center;">
                    <span>Select users...</span>
                    <span style="font-size: 12px;">▼</span>
                </button>
                <div id="userDropdownMenu" style="position: absolute; top: 100%; left: 0; right: 0; background: var(--bg-secondary); border: 1px solid var(--border-color); border-top: none; border-radius: 0 0 8px 8px; max-height: 200px; overflow-y: auto; display: none; z-index: 1001; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                    <div id="userList" style="padding: 8px 0;">
                        <!-- Users will be loaded here -->
                    </div>
                </div>
            </div>
            <div id="selectedUsersDisplay" style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px;">
                <!-- Selected users will be shown as tags here -->
            </div>
            <div style="font-size: 12px; color: var(--text-secondary);">Or add emails manually:</div>
            <textarea id="groupMembersInput" placeholder="user1@example.com, user2@example.com..." style="width: 100%; padding: 10px 12px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--bg-secondary); color: var(--text-primary); font-family: inherit; box-sizing: border-box; min-height: 60px; resize: vertical; margin-top: 8px;"></textarea>
        </div>
        
        <div style="display: flex; gap: 10px; justify-content: flex-end;">
            <button onclick="this.closest('[data-overlay]').remove()" style="padding: 10px 20px; border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); border-radius: 8px; cursor: pointer; font-weight: 500;">Cancel</button>
            <button onclick="createGroupChat()" style="padding: 10px 20px; background: var(--accent-color); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 500;">Create & Share</button>
        </div>
    `;
    
    overlay.setAttribute('data-overlay', 'true');
    overlay.appendChild(modal);
    
    overlay.onclick = (e) => {
        if (e.target === overlay) {
            overlay.remove();
        }
    };
    
    document.body.appendChild(overlay);
    
    // Focus on group name input
    setTimeout(() => {
        document.getElementById('groupNameInput').focus();
    }, 100);
    
    // Load users for dropdown
    loadUsersForInvite();
    
    // Setup dropdown toggle
    const dropdownBtn = document.getElementById('userDropdownBtn');
    const dropdownMenu = document.getElementById('userDropdownMenu');
    
    dropdownBtn.addEventListener('click', () => {
        dropdownMenu.style.display = dropdownMenu.style.display === 'none' ? 'block' : 'none';
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#userDropdownContainer')) {
            dropdownMenu.style.display = 'none';
        }
    });
}

// Create Group Chat
function createGroupChat() {
    const groupName = document.getElementById('groupNameInput').value.trim();
    const manualEmails = document.getElementById('groupMembersInput').value.trim();
    
    if (!groupName) {
        showNotification('Error', 'Please enter a group name', 'error');
        return;
    }
    
    // Combine selected users and manual emails
    let members = selectedUsersForGroup.map(u => u.email);
    
    if (manualEmails) {
        const manualList = manualEmails.split(',').map(m => m.trim()).filter(m => m);
        members = [...new Set([...members, ...manualList])]; // Remove duplicates
    }
    
    if (members.length === 0) {
        showNotification('Error', 'Please select or add at least one member', 'error');
        return;
    }
    
    console.log('👥 Creating group chat:', {
        name: groupName,
        members: members,
        sessionId: currentSessionId
    });
    
    // Send to backend
    fetch('/create_group_chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            group_name: groupName,
            members: members,
            session_id: currentSessionId,
            mode: currentMode
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            console.log('✅ Group created:', data.group_id);
            showNotification('Success', `Group "${groupName}" created and invitations sent!`, 'success');
            
            // Close modal
            const overlay = document.querySelector('[data-overlay]');
            if (overlay) {
                overlay.remove();
            }
            
            // Reset selected users
            selectedUsersForGroup = [];
            
            // Auto-open groups list and select the new group
            setTimeout(() => {
                loadUserGroups();
                setTimeout(() => {
                    selectGroupChat(data.group_id, groupName, currentSessionId);
                    closeGroupsPanel();
                }, 500);
            }, 300);
        } else {
            showNotification('Error', data.error || 'Failed to create group', 'error');
        }
    })
    .catch(error => {
        console.error('❌ Error creating group:', error);
        showNotification('Error', 'Failed to create group chat: ' + error.message, 'error');
    });
}

// Show Group Info
function showGroupInfo(groupName, members, groupId) {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        backdrop-filter: blur(4px);
    `;
    
    const modal = document.createElement('div');
    modal.style.cssText = `
        background: var(--bg-primary);
        border-radius: 12px;
        padding: 30px;
        max-width: 500px;
        width: 90%;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        animation: slideUp 0.3s ease;
        text-align: center;
    `;
    
    modal.innerHTML = `
        <div style="font-size: 40px; margin-bottom: 15px;">✅</div>
        <h3 style="margin: 0 0 10px 0; font-size: 20px; color: var(--text-primary);">Group Created!</h3>
        <p style="color: var(--text-secondary); margin: 0 0 20px 0;">
            Group "<strong>${groupName}</strong>" has been created.<br>
            Invitations sent to ${members.length} member(s).
        </p>
        <div style="background: var(--bg-secondary); padding: 15px; border-radius: 8px; margin-bottom: 20px; text-align: left;">
            <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 10px;">Members:</div>
            ${members.map(m => `<div style="color: var(--text-secondary); font-size: 14px; margin-bottom: 5px;">• ${m}</div>`).join('')}
        </div>
        <p style="color: var(--text-secondary); font-size: 13px; margin: 0 0 20px 0;">
            All members will see the same chat and can work together on this conversation.
        </p>
        <button onclick="closeGroupInfoAndSelectGroup('${groupId}', '${groupName}')" style="padding: 10px 30px; background: var(--accent-color); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 500;">Open Group</button>
    `;
    
    overlay.setAttribute('data-overlay', 'true');
    overlay.appendChild(modal);
    
    overlay.onclick = (e) => {
        if (e.target === overlay) {
            overlay.remove();
            loadUserGroups();  // Reload groups when modal closes
        }
    };
    
    document.body.appendChild(overlay);
}

// Close group info and select the group
function closeGroupInfoAndSelectGroup(groupId, groupName) {
    const overlay = document.querySelector('[data-overlay]');
    if (overlay) {
        overlay.remove();
    }
    
    // Reload groups and select the new one
    loadUserGroups();
    
    // Select the group after a short delay to ensure it's loaded
    setTimeout(() => {
        selectGroupChat(groupId, groupName, null);
    }, 500);
}

// Global variables for group chat
let currentGroupId = null;
let currentGroupName = null;
let selectedUsersForGroup = [];
let isGroupChatMode = false;

// Load user groups and display in panel
function loadUserGroups() {
    console.log('👥 Loading user groups...');
    
    fetch('/api/group-chat/user-groups', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('📊 Groups response:', data);
        
        // Handle both response formats
        const groups = data.groups || [];
        
        if (groups.length > 0) {
            console.log(`✅ Loaded ${groups.length} groups`);
            displayGroupsInPanel(groups);
        } else {
            console.log('📭 No groups found');
            displayGroupsInPanel([]);
        }
    })
    .catch(error => {
        console.error('❌ Error loading groups:', error);
        displayGroupsInPanel([]);
    });
}

// Display groups in panel
function displayGroupsInPanel(groups) {
    const groupsList = document.getElementById('groupsList');
    if (!groupsList) return;
    
    console.log('📋 Displaying', groups.length, 'groups in panel');
    
    if (groups.length === 0) {
        groupsList.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-secondary); font-size: 13px;">No groups yet. Create one to get started!</div>';
        return;
    }
    
    groupsList.innerHTML = '';
    
    // Add each group
    groups.forEach(group => {
        const groupItem = document.createElement('div');
        groupItem.style.cssText = `
            padding: 12px 16px;
            margin: 8px 0;
            background: var(--bg-secondary);
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            border-left: 3px solid var(--accent-color);
        `;
        
        groupItem.innerHTML = `
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 16px;">👥</span>
                <div style="flex: 1; min-width: 0;">
                    <div style="font-weight: 500; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        ${group.name}
                    </div>
                    <div style="font-size: 12px; color: var(--text-secondary);">
                        <span id="members-${group.id}">Loading members...</span>
                    </div>
                </div>
            </div>
        `;
        
        groupItem.addEventListener('mouseenter', function() {
            this.style.backgroundColor = 'var(--bg-tertiary)';
        });
        
        groupItem.addEventListener('mouseleave', function() {
            this.style.backgroundColor = 'var(--bg-secondary)';
        });
        
        groupItem.addEventListener('click', function() {
            console.log('🖱️ Group clicked:', group.id, group.name);
            closeGroupsPanel();
            selectGroupChat(group.id, group.name, group.session_id);
        });
        
        groupsList.appendChild(groupItem);
        
        // Load and display member count
        loadGroupMemberCount(group.id);
    });
    
    console.log('✅ Groups displayed in panel');
}

// Load and display group member count
function loadGroupMemberCount(groupId) {
    fetch(`/api/group-chat/info?group_id=${groupId}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.members) {
            const memberCount = data.members.length;
            const memberNames = data.members
                .map(m => m.email || m.username || 'Unknown')
                .slice(0, 2)
                .join(', ');
            
            const membersEl = document.getElementById(`members-${groupId}`);
            if (membersEl) {
                const displayText = memberCount === 1 
                    ? '1 member' 
                    : `${memberCount} members`;
                membersEl.textContent = displayText;
                membersEl.title = `Members: ${data.members.map(m => m.email || m.username || 'Unknown').join(', ')}`;
            }
            
            console.log(`✅ Loaded ${memberCount} members for group ${groupId}`);
        }
    })
    .catch(error => {
        console.error('❌ Error loading group members:', error);
        const membersEl = document.getElementById(`members-${groupId}`);
        if (membersEl) {
            membersEl.textContent = 'Group Chat';
        }
    });
}

// Select a group chat
function selectGroupChat(groupId, groupName, sessionId) {
    console.log('👥 Selecting group chat:', groupId, groupName);
    
    // Save current chat history before switching
    saveChatHistory();
    
    // Set group mode
    isGroupChatMode = true;
    currentGroupId = groupId;
    currentGroupName = groupName;
    currentSessionId = sessionId || generateSessionId();
    
    // Clear conversation history
    conversationHistory = [];
    
    // Fetch group info to check if user is creator
    fetch(`/api/group-chat/info?group_id=${groupId}`)
        .then(response => response.json())
        .then(data => {
            const isCreator = data.is_creator;
            isGroupCreator = isCreator;  // Set global variable
            console.log(`👤 User is creator: ${isCreator}`, data);
            
            // Load group's mode setting
            if (data.mode) {
                currentMode = data.mode;
                localStorage.setItem('selectedMode', currentMode);
                updateModePlaceholder();
                console.log(`� Loaded group mode: ${currentMode}`);
            }
            
            // Show all mode selector ONLY for creator
            const dataSourceToggle = document.getElementById('dataSourceToggle');
            if (dataSourceToggle) {
                dataSourceToggle.style.display = isCreator ? 'block' : 'none';
                console.log(`� Mode selector ${isCreator ? 'shown for creator' : 'hidden for member'}`);
            }
            
            // Show thinking mode toggle ONLY for creator
            const aiModeToggle = document.getElementById('aiModeToggle');
            if (aiModeToggle) {
                aiModeToggle.style.display = isCreator ? 'block' : 'none';
                console.log(`💭 Thinking mode toggle ${isCreator ? 'shown for creator' : 'hidden for member'}`);
            }
            
            // Show group only mode button ONLY for creator
            const groupOnlyModeBtn = document.getElementById('groupOnlyModeBtn');
            if (groupOnlyModeBtn) {
                groupOnlyModeBtn.style.display = isCreator ? 'block' : 'none';
                if (isCreator) {
                    loadGroupOnlyModePreference();
                }
                console.log(`👥 Group only mode button ${isCreator ? 'shown for creator' : 'hidden for member'}`);
            }
            
            // Send button always visible for all members
            const sendBtn = document.getElementById('sendBtn');
            if (sendBtn) {
                sendBtn.style.display = 'block';
                console.log('✉️ Send button shown for all members');
            }
        })
        .catch(error => {
            console.error('❌ Error fetching group info:', error);
            isGroupCreator = false;  // Default to member if fetch fails
            // Default to hiding all controls except send button if fetch fails
            const dataSourceToggle = document.getElementById('dataSourceToggle');
            if (dataSourceToggle) dataSourceToggle.style.display = 'none';
            const aiModeToggle = document.getElementById('aiModeToggle');
            if (aiModeToggle) aiModeToggle.style.display = 'none';
            const groupOnlyModeBtn = document.getElementById('groupOnlyModeBtn');
            if (groupOnlyModeBtn) groupOnlyModeBtn.style.display = 'none';
            const sendBtn = document.getElementById('sendBtn');
            if (sendBtn) sendBtn.style.display = 'block';
        });
    
    // Update input placeholder
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.placeholder = `Message in ${groupName}...`;
    }
    
    // Load group messages
    loadGroupMessages(groupId);
    
    // Load and display group details
    loadAndDisplayGroupDetails(groupId, groupName);
    
    // Update UI
    const messagesContainer = document.getElementById('messagesContainer');
    const welcomeScreen = document.getElementById('welcomeScreen');
    
    if (welcomeScreen) {
        welcomeScreen.innerHTML = `
            <div class="welcome-content">
                
            </div>
        `;
        welcomeScreen.style.display = 'flex';
    }
    
    if (messagesContainer) {
        messagesContainer.innerHTML = '';
        messagesContainer.style.display = 'none';
    }
    
    // Start polling for new messages
    startGroupMessagePolling(groupId);
    
    console.log('✅ Group chat selected:', groupName);
}

// Load group messages
function loadGroupMessages(groupId) {
    console.log('📥 Loading group messages for:', groupId);
    
    fetch(`/api/group-chat/messages?group_id=${groupId}&limit=100`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.messages) {
            console.log(`✅ Loaded ${data.messages.length} group messages`);
            displayGroupMessages(data.messages);
        }
    })
    .catch(error => {
        console.error('❌ Error loading group messages:', error);
    });
}

// Display group messages
function displayGroupMessages(messages) {
    const messagesContainer = document.getElementById('messagesContainer');
    const welcomeScreen = document.getElementById('welcomeScreen');
    
    console.log('📊 Displaying group messages:', messages.length);
    
    if (!messagesContainer) {
        console.error('❌ Messages container not found');
        return;
    }
    
    if (messages.length === 0) {
        console.log('📭 No messages in group');
        if (welcomeScreen) {
            welcomeScreen.style.display = 'block';
        }
        messagesContainer.style.display = 'none';
        return;
    }
    
    // Hide welcome screen and show messages
    if (welcomeScreen) {
        welcomeScreen.style.display = 'none';
    }
    messagesContainer.style.display = 'block';
    messagesContainer.innerHTML = '';
    
    const currentUserId = getCurrentUserId();
    console.log('👤 Current user ID:', currentUserId);
    
    // Display each message
    messages.forEach((msg, index) => {
        console.log(`📝 Message ${index + 1}:`, {
            sender_id: msg.sender_id,
            sender_name: msg.sender_name,
            isCurrentUser: msg.sender_id === currentUserId
        });
        
        const isCurrentUser = msg.sender_id === currentUserId;
        
        // Check if message contains both user query and AI response (combined format)
        if (msg.message.includes('**User:**') && msg.message.includes('**AI Response:**')) {
            // Parse the combined message into separate parts
            const userMatch = msg.message.match(/\*\*User:\*\*\s*([\s\S]*?)(?=\n\n\*\*AI Response:\*\*|\n\*\*AI Response:\*\*)/);
            const aiMatch = msg.message.match(/\*\*AI Response:\*\*\s*([\s\S]*?)$/);
            
            if (userMatch && aiMatch) {
                const userQuery = userMatch[1].trim();
                const aiResponse = aiMatch[1].trim();
                
                // Display user message
                const userMessageDiv = document.createElement('div');
                userMessageDiv.className = 'message user';
                userMessageDiv.setAttribute('data-message-id', msg.id + '-user');
                
                const userContentDiv = document.createElement('div');
                userContentDiv.className = 'message-content';
                userContentDiv.textContent = userQuery;
                userMessageDiv.appendChild(userContentDiv);
                
                // Add sender info
                const userSenderDiv = document.createElement('div');
                userSenderDiv.style.cssText = 'font-size: 11px; color: var(--text-secondary); margin-top: 4px; opacity: 0.7; text-align: right;';
                userSenderDiv.textContent = `From: ${msg.sender_name}`;
                userMessageDiv.appendChild(userSenderDiv);
                
                // Add timestamp
                const userTimestampDiv = document.createElement('div');
                userTimestampDiv.className = 'message-timestamp';
                userTimestampDiv.textContent = formatGroupMessageTime(msg.created_at);
                userMessageDiv.appendChild(userTimestampDiv);
                
                messagesContainer.appendChild(userMessageDiv);
                
                // Display AI response message
                const aiMessageDiv = document.createElement('div');
                aiMessageDiv.className = 'message bot';
                aiMessageDiv.setAttribute('data-message-id', msg.id + '-ai');
                
                // Create a wrapper for content and metadata
                const aiContentWrapper = document.createElement('div');
                aiContentWrapper.style.cssText = 'width: 100%;';
                
                const aiContentDiv = document.createElement('div');
                aiContentDiv.className = 'message-content';
                
                if (typeof marked !== 'undefined') {
                    aiContentDiv.innerHTML = marked.parse(aiResponse);
                    // Clean up any reference headers that might still be in the content
                    cleanReferenceHeadersFromContent(aiContentDiv);
                } else {
                    aiContentDiv.textContent = aiResponse;
                }
                
                aiContentWrapper.appendChild(aiContentDiv);
                
                // Add sender info for AI
                const aiSenderDiv = document.createElement('div');
                aiSenderDiv.style.cssText = 'font-size: 11px; color: var(--text-secondary); margin-top: 4px; opacity: 0.7;';
                aiSenderDiv.textContent = 'AI Response';
                aiContentWrapper.appendChild(aiSenderDiv);
                
                // Add timestamp
                const aiTimestampDiv = document.createElement('div');
                aiTimestampDiv.className = 'message-timestamp';
                aiTimestampDiv.textContent = formatGroupMessageTime(msg.created_at);
                aiContentWrapper.appendChild(aiTimestampDiv);
                
                aiMessageDiv.appendChild(aiContentWrapper);
                
                messagesContainer.appendChild(aiMessageDiv);
                
                // Add structured data (references and charts) if available - SAME AS NORMAL CHAT
                console.log('📊 Group message structured_data:', {
                    has_structured_data: !!msg.structured_data,
                    structured_data_type: typeof msg.structured_data,
                    structured_data_value: msg.structured_data
                });
                
                if (msg.structured_data) {
                    try {
                        const structuredData = typeof msg.structured_data === 'string' 
                            ? JSON.parse(msg.structured_data) 
                            : msg.structured_data;
                        
                        console.log('✅ Parsed structured data:', {
                            has_references: !!structuredData.references,
                            references_count: structuredData.references?.length || 0,
                            has_charts: !!structuredData.charts,
                            charts_count: structuredData.charts?.length || 0
                        });
                        
                        // Add references if available - add to aiMessageDiv like normal chat
                        if (structuredData.references && structuredData.references.length > 0) {
                            console.log(`📚 Adding ${structuredData.references.length} references to group message`);
                            const messageMode = structuredData.mode || currentMode;
                            addReferencesToMessage(aiMessageDiv, structuredData.references, messageMode, true);
                        }
                        
                        // Add charts if available - add to aiMessageDiv like normal chat
                        if (structuredData.charts && structuredData.charts.length > 0) {
                            console.log(`📈 Adding ${structuredData.charts.length} charts to group message`);
                            addChartsToMessage(aiMessageDiv, structuredData.charts);
                        }
                    } catch (e) {
                        console.log('⚠️ Could not parse structured data:', e);
                    }
                }
            } else {
                // Fallback: display as single message if parsing fails
                displaySingleGroupMessage(messagesContainer, msg, isCurrentUser, currentUserId);
            }
        } else {
            // Display as single message (member message without AI response)
            const isCurrentUser = msg.sender_id === currentUserId;
            
            if (isCurrentUser) {
                // Display as user message
                const userMessageDiv = document.createElement('div');
                userMessageDiv.className = 'message user';
                userMessageDiv.setAttribute('data-message-id', msg.id);
                
                const userContentDiv = document.createElement('div');
                userContentDiv.className = 'message-content';
                userContentDiv.textContent = msg.message;
                userMessageDiv.appendChild(userContentDiv);
                
                // Add sender info
                const userSenderDiv = document.createElement('div');
                userSenderDiv.style.cssText = 'font-size: 11px; color: var(--text-secondary); margin-top: 4px; opacity: 0.7; text-align: right;';
                userSenderDiv.textContent = `From: ${msg.sender_name}`;
                userMessageDiv.appendChild(userSenderDiv);
                
                // Add timestamp
                const userTimestampDiv = document.createElement('div');
                userTimestampDiv.className = 'message-timestamp';
                userTimestampDiv.textContent = formatGroupMessageTime(msg.created_at);
                userMessageDiv.appendChild(userTimestampDiv);
                
                messagesContainer.appendChild(userMessageDiv);
            } else {
                // Display as bot/other message
                displaySingleGroupMessage(messagesContainer, msg, isCurrentUser, currentUserId);
            }
        }
    });
    
    console.log('✅ All messages displayed');
    scrollToBottom();
}

// Helper function to display a single group message
function displaySingleGroupMessage(container, msg, isCurrentUser, currentUserId) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isCurrentUser ? 'user' : 'bot'}`;
    messageDiv.setAttribute('data-message-id', msg.id);
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    if (typeof marked !== 'undefined') {
        contentDiv.innerHTML = marked.parse(msg.message);
        // Clean up any reference headers that might still be in the content
        cleanReferenceHeadersFromContent(contentDiv);
    } else {
        contentDiv.textContent = msg.message;
    }
    
    messageDiv.appendChild(contentDiv);
    
    // Add sender info for ALL group messages (both user and bot/AI)
    const senderDiv = document.createElement('div');
    senderDiv.style.cssText = 'font-size: 11px; color: var(--text-secondary); margin-top: 4px; opacity: 0.7;';
    senderDiv.textContent = `From: ${msg.sender_name}`;
    messageDiv.appendChild(senderDiv);
    
    // Add timestamp
    const timestampDiv = document.createElement('div');
    timestampDiv.className = 'message-timestamp';
    timestampDiv.textContent = formatGroupMessageTime(msg.created_at);
    messageDiv.appendChild(timestampDiv);
    
    container.appendChild(messageDiv);
}

// Format group message time
function formatGroupMessageTime(timestamp) {
    try {
        const date = new Date(timestamp);
        return new Intl.DateTimeFormat('en-US', {
            timeZone: 'Asia/Karachi',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        }).format(date);
    } catch (e) {
        return 'Recently';
    }
}

// Add message to group (for group-only mode)
function addMessageToGroup(groupId, message, response) {
    console.log('💬 Adding message to group:', groupId);
    
    fetch('/api/group-chat/add-message', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            group_id: groupId,
            message: message,
            response: response
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('✅ Message added to group');
        } else {
            console.error('❌ Failed to add message:', data.error);
        }
    })
    .catch(error => {
        console.error('❌ Error adding message to group:', error);
    });
}

// Load and display group details at top
function loadAndDisplayGroupDetails(groupId, groupName) {
    console.log('📋 Loading group details for:', groupId);
    
    fetch(`/api/group-chat/info?group_id=${groupId}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.members) {
            const isCreator = data.is_creator || false;
            console.log('👤 Group info loaded - is_creator:', isCreator);
            displayGroupDetailsHeader(groupId, groupName, data.members, isCreator);
        }
    })
    .catch(error => {
        console.error('❌ Error loading group details:', error);
    });
}

// Display group details header
function displayGroupDetailsHeader(groupId, groupName, members, isCreator = false) {
    let detailsHeader = document.getElementById('groupDetailsHeader');
    
    // Create header if it doesn't exist
    if (!detailsHeader) {
        detailsHeader = document.createElement('div');
        detailsHeader.id = 'groupDetailsHeader';
        const chatArea = document.getElementById('chatArea');
        if (chatArea) {
            chatArea.insertBefore(detailsHeader, chatArea.firstChild);
            console.log('✅ Group header element created and inserted into chatArea');
        } else {
            console.error('❌ chatArea element not found!');
            return;
        }
    }
    
    const memberCount = members.length;
    
    detailsHeader.style.cssText = `
        padding: 16px 24px;
        background: var(--bg-secondary);
        border-bottom: 1px solid var(--border-color);
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 16px;
        flex-shrink: 0;
        width: 100%;
        box-sizing: border-box;
        z-index: 50;
        flex-direction: column;
    `;
    
    // Build buttons HTML based on is_creator
    let buttonsHTML = '';
    
    if (isCreator) {
        // Creator has all buttons
        buttonsHTML = `
            <div style="position: relative;">
                <button id="inviteUserBtn" style="padding: 8px 12px; border-radius: 6px; background: var(--accent-color); color: white; border: none; cursor: pointer; font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 6px; transition: all 0.2s; white-space: nowrap;">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M15 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm-9-2c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3zm0 4c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm9 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>
                    </svg>
                    <span>Invite</span>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style="margin-left: 4px;">
                        <path d="M7 10l5 5 5-5z"/>
                    </svg>
                </button>
                <div id="inviteDropdown" style="position: absolute; top: 100%; right: 0; background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); display: none; z-index: 1000; min-width: 200px; margin-top: 4px;">
                    <button id="inviteNewUserBtn" style="width: 100%; padding: 10px 16px; text-align: left; border: none; background: transparent; color: var(--text-primary); cursor: pointer; font-size: 13px; transition: background 0.2s; border-bottom: 1px solid var(--border-color);">
                        ➕ Invite New User
                    </button>
                    <button id="removeUserBtn" style="width: 100%; padding: 10px 16px; text-align: left; border: none; background: transparent; color: var(--text-primary); cursor: pointer; font-size: 13px; transition: background 0.2s;">
                        ➖ Remove User
                    </button>
                </div>
            </div>
            <button id="deleteGroupBtn" style="padding: 8px 12px; border-radius: 6px; background: var(--accent-color); color: white; border: none; cursor: pointer; font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 6px; transition: all 0.2s; white-space: nowrap;" title="Delete this group">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-9l-1 1H5v2h14V4z"/>
                </svg>
                <span>Delete</span>
            </button>
            <button id="clearConversationBtn" style="padding: 8px 12px; border-radius: 6px; background: var(--accent-color); color: white; border: none; cursor: pointer; font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 6px; transition: all 0.2s; white-space: nowrap;" title="Clear all messages in this group">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V5h14v14zm-2-7h-8v2h8v-2z"/>
                </svg>
                <span>Clear</span>
            </button>
            <button id="closeGroupBtn" style="padding: 8px 12px; border-radius: 6px; background: var(--accent-color); color: white; border: none; cursor: pointer; font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 6px; transition: all 0.2s; white-space: nowrap;" title="Close group and return to chat">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12 19 6.41z"/>
                </svg>
                <span>Close</span>
            </button>
        `;
    } else {
        // Members have only send button (no buttons in header)
        // Just show close button to exit group
        buttonsHTML = `
            <button id="closeGroupBtn" style="padding: 8px 12px; border-radius: 6px; background: var(--accent-color); color: white; border: none; cursor: pointer; font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 6px; transition: all 0.2s; white-space: nowrap;" title="Close group and return to chat">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12 19 6.41z"/>
                </svg>
                <span>Close</span>
            </button>
        `;
    }
    
    detailsHeader.innerHTML = `
        <div style="width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 0; display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 20px; flex-shrink: 0;">👥</span>
                <div style="flex: 1; min-width: 0;">
                    <div style="font-weight: 600; color: var(--text-primary); font-size: 16px; margin-bottom: 4px;">
                        ${groupName}
                    </div>
                    <div style="font-size: 12px; color: var(--text-secondary); display: flex; align-items: center; gap: 8px;">
                        <span>${memberCount} member${memberCount !== 1 ? 's' : ''}</span>
                        <span style="color: var(--border-color);">•</span>
                        <span style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            ${members.map(m => m.username || m.email?.split('@')[0] || 'Unknown').join(', ')}
                        </span>
                    </div>
                </div>
            </div>
            <div style="display: flex; gap: 8px; align-items: center; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; width: 100%;">
                ${buttonsHTML}
            </div>
        </div>
    `;
    
    // Setup event listeners only if creator
    if (isCreator) {
        // Invite dropdown toggle
        const inviteBtn = detailsHeader.querySelector('#inviteUserBtn');
        const inviteDropdown = detailsHeader.querySelector('#inviteDropdown');
        const inviteNewUserBtn = detailsHeader.querySelector('#inviteNewUserBtn');
        const removeUserBtn = detailsHeader.querySelector('#removeUserBtn');
        
        if (inviteBtn && inviteDropdown) {
            inviteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                inviteDropdown.style.display = inviteDropdown.style.display === 'none' ? 'block' : 'none';
            });
            
            inviteBtn.addEventListener('mouseenter', () => {
                inviteBtn.style.background = 'var(--accent-hover, #8f0d0d)';
            });
            
            inviteBtn.addEventListener('mouseleave', () => {
                inviteBtn.style.background = 'var(--accent-color)';
            });
        }
        
        // Invite new user option
        if (inviteNewUserBtn) {
            inviteNewUserBtn.addEventListener('click', () => {
                console.log('📧 Invite new user clicked');
                if (inviteDropdown) inviteDropdown.style.display = 'none';
                showInviteUserModal(groupId, groupName);
            });
            
            inviteNewUserBtn.addEventListener('mouseenter', () => {
                inviteNewUserBtn.style.background = 'var(--bg-secondary)';
            });
            
            inviteNewUserBtn.addEventListener('mouseleave', () => {
                inviteNewUserBtn.style.background = 'transparent';
            });
        }
        
        // Remove user option
        if (removeUserBtn) {
            removeUserBtn.addEventListener('click', () => {
                console.log('➖ Remove user clicked');
                if (inviteDropdown) inviteDropdown.style.display = 'none';
                showRemoveUserModal(groupId, groupName, members);
            });
            
            removeUserBtn.addEventListener('mouseenter', () => {
                removeUserBtn.style.background = 'var(--bg-secondary)';
            });
            
            removeUserBtn.addEventListener('mouseleave', () => {
                removeUserBtn.style.background = 'transparent';
            });
        }
        
        // Delete button listener
        const deleteBtn = detailsHeader.querySelector('#deleteGroupBtn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => {
                console.log('🗑️ Delete button clicked');
                showDeleteGroupConfirmation(groupId, groupName);
            });
            
            deleteBtn.addEventListener('mouseenter', () => {
                deleteBtn.style.background = '#b91c1c';
            });
            
            deleteBtn.addEventListener('mouseleave', () => {
                deleteBtn.style.background = '#dc2626';
            });
        }
        
        // Clear conversation button listener
        const clearBtn = detailsHeader.querySelector('#clearConversationBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                console.log('🧹 Clear conversation button clicked');
                showClearConversationConfirmation(groupId, groupName);
            });
            
            clearBtn.addEventListener('mouseenter', () => {
                clearBtn.style.background = '#b91c1c';
            });
            
            clearBtn.addEventListener('mouseleave', () => {
                clearBtn.style.background = '#b91c1c';
            });
        }
        
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (inviteDropdown && !inviteBtn.contains(e.target) && !inviteDropdown.contains(e.target)) {
                inviteDropdown.style.display = 'none';
            }
        });
        
        console.log('✅ Group details header displayed (Creator mode) with', memberCount, 'members');
    } else {
        // Member mode - only close button
        console.log('✅ Group details header displayed (Member mode) with', memberCount, 'members');
    }
    
    // Close group button listener (available for both creator and members)
    const closeBtn = detailsHeader.querySelector('#closeGroupBtn');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            console.log('❌ Close group button clicked - returning to chat');
            closeGroupAndReturnToChat();
        });
        
        closeBtn.addEventListener('mouseenter', () => {
            closeBtn.style.background = '#b91c1c';
        });
        
        closeBtn.addEventListener('mouseleave', () => {
            closeBtn.style.background = 'var(--accent-color)';
        });
    }
}

// Show invite user modal
function showInviteUserModal(groupId, groupName) {
    console.log('📧 Opening invite user modal for group:', groupId);
    
    const overlay = document.createElement('div');
    overlay.style.cssText = `
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
    `;
    overlay.setAttribute('data-overlay', 'true');
    
    const modal = document.createElement('div');
    modal.style.cssText = `
        background: var(--bg-primary);
        border-radius: 12px;
        padding: 24px;
        max-width: 450px;
        width: 90%;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        max-height: 80vh;
        overflow-y: auto;
    `;
    
    modal.innerHTML = `
        <div style="margin-bottom: 24px;">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                <span style="font-size: 24px;">👥</span>
                <div>
                    <h2 style="margin: 0; color: var(--text-primary); font-size: 18px;">Invite to ${groupName}</h2>
                    <p style="margin: 4px 0 0 0; color: var(--text-secondary); font-size: 13px;">Add new members to this group</p>
                </div>
            </div>
        </div>
        
        <div style="margin-bottom: 20px; padding: 12px; background: var(--bg-secondary); border-radius: 8px;">
            <label style="display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px;">📧 Email Address</label>
            <input 
                type="email" 
                id="inviteEmailInput" 
                placeholder="user@example.com"
                style="
                    width: 100%;
                    padding: 10px 12px;
                    border: 1px solid var(--border-color);
                    border-radius: 6px;
                    background: var(--bg-tertiary);
                    color: var(--text-primary);
                    font-size: 14px;
                    box-sizing: border-box;
                    transition: border-color 0.2s;
                "
            />
        </div>
        
        <div id="inviteStatus" style="margin-bottom: 16px; padding: 12px; background: var(--bg-secondary); border-radius: 8px; display: none; font-size: 13px;"></div>
        
        <div style="display: flex; gap: 12px; justify-content: flex-end;">
            <button id="cancelInviteBtn" style="padding: 10px 16px; border-radius: 6px; background: var(--bg-tertiary); color: var(--text-primary); border: 1px solid var(--border-color); cursor: pointer; font-size: 14px; font-weight: 500; transition: background 0.2s;">
                Cancel
            </button>
            <button id="confirmInviteBtn" style="padding: 10px 16px; border-radius: 6px; background: var(--accent-color); color: white; border: none; cursor: pointer; font-size: 14px; font-weight: 500; transition: background 0.2s;">
                Send Invite
            </button>
        </div>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    const emailInput = modal.querySelector('#inviteEmailInput');
    const cancelBtn = modal.querySelector('#cancelInviteBtn');
    const confirmBtn = modal.querySelector('#confirmInviteBtn');
    const statusDiv = modal.querySelector('#inviteStatus');
    
    // Focus on input
    emailInput.focus();
    
    // Cancel button
    cancelBtn.addEventListener('click', () => {
        overlay.remove();
    });
    
    cancelBtn.addEventListener('mouseenter', () => {
        cancelBtn.style.background = 'var(--bg-secondary)';
    });
    
    cancelBtn.addEventListener('mouseleave', () => {
        cancelBtn.style.background = 'var(--bg-tertiary)';
    });
    
    // Confirm button
    confirmBtn.addEventListener('click', () => {
        const email = emailInput.value.trim();
        if (!email) {
            showNotification('Error', 'Please enter an email address', 'error');
            return;
        }
        
        if (!email.includes('@')) {
            showNotification('Error', 'Please enter a valid email address', 'error');
            return;
        }
        
        // Show loading state
        confirmBtn.disabled = true;
        confirmBtn.textContent = 'Sending...';
        statusDiv.style.display = 'block';
        statusDiv.innerHTML = '⏳ Sending invitation...';
        statusDiv.style.color = 'var(--text-secondary)';
        
        // Send invite to backend
        fetch('/api/group-chat/invite-user', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                group_id: groupId,
                user_id: null,
                email: email
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                statusDiv.innerHTML = '✅ Invitation sent successfully!';
                statusDiv.style.color = 'var(--success-color, #10b981)';
                showNotification('Success', `Invitation sent to ${email}`, 'success');
                
                setTimeout(() => {
                    overlay.remove();
                    // Reload group details
                    loadAndDisplayGroupDetails(groupId, groupName);
                }, 1500);
            } else {
                statusDiv.innerHTML = '❌ ' + (data.error || 'Failed to invite user');
                statusDiv.style.color = 'var(--error-color, #ef4444)';
                confirmBtn.disabled = false;
                confirmBtn.textContent = 'Send Invite';
                showNotification('Error', data.error || 'Failed to invite user', 'error');
            }
        })
        .catch(error => {
            console.error('❌ Error inviting user:', error);
            statusDiv.innerHTML = '❌ Error: ' + error.message;
            statusDiv.style.color = 'var(--error-color, #ef4444)';
            confirmBtn.disabled = false;
            confirmBtn.textContent = 'Send Invite';
            showNotification('Error', 'Failed to invite user', 'error');
        });
    });
    
    confirmBtn.addEventListener('mouseenter', () => {
        if (!confirmBtn.disabled) {
            confirmBtn.style.background = 'rgba(220, 38, 38, 0.9)';
        }
    });
    
    confirmBtn.addEventListener('mouseleave', () => {
        if (!confirmBtn.disabled) {
            confirmBtn.style.background = 'var(--accent-color)';
        }
    });
    
    // Enter key to send
    emailInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !confirmBtn.disabled) {
            confirmBtn.click();
        }
    });
    
    // Close on overlay click
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            overlay.remove();
        }
    });
}

// Message polling for real-time updates
let groupMessagePollingInterval = null;
let lastMessageTimestamp = null;

function startGroupMessagePolling(groupId) {
    console.log('🔄 Starting message polling for group:', groupId);
    
    // Clear existing polling
    if (groupMessagePollingInterval) {
        clearInterval(groupMessagePollingInterval);
    }
    
    // Poll every 2 seconds for real-time updates (reduced from 500ms to avoid excessive refreshing)
    groupMessagePollingInterval = setInterval(() => {
        if (isGroupChatMode && currentGroupId === groupId) {
            checkForNewMessages(groupId);
        }
    }, 2000);
}

function stopGroupMessagePolling() {
    if (groupMessagePollingInterval) {
        clearInterval(groupMessagePollingInterval);
        groupMessagePollingInterval = null;
        console.log('🛑 Stopped message polling');
    }
}

function checkForNewMessages(groupId) {
    fetch(`/api/group-chat/messages?group_id=${groupId}&limit=100`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.messages && data.messages.length > 0) {
            const messagesContainer = document.getElementById('messagesContainer');
            if (!messagesContainer) return;
            
            // Get all currently displayed message IDs (excluding the -user and -ai suffixes)
            const displayedMessages = messagesContainer.querySelectorAll('[data-message-id]');
            const displayedIds = new Set();
            displayedMessages.forEach(msg => {
                const id = msg.getAttribute('data-message-id');
                // Extract base ID (remove -user or -ai suffix if present)
                const baseId = id.replace(/-user$|-ai$/, '');
                displayedIds.add(baseId);
            });
            
            // Check if there are new messages
            let hasNewMessages = false;
            data.messages.forEach(msg => {
                if (!displayedIds.has(msg.id)) {
                    hasNewMessages = true;
                }
            });
            
            if (hasNewMessages) {
                console.log('📬 New messages detected, refreshing...');
                displayGroupMessages(data.messages);
            }
        }
    })
    .catch(error => {
        // Silently fail on polling errors
        console.debug('Polling check failed:', error);
    });
}

// Get current user ID (from page data or session)
function getCurrentUserId() {
    // Try to get from page data
    const userIdElement = document.querySelector('[data-user-id]');
    if (userIdElement) {
        const userId = parseInt(userIdElement.getAttribute('data-user-id'));
        console.log('✅ Got user ID from page data:', userId);
        return userId;
    }
    
    // Try to get from localStorage
    const storedUserId = localStorage.getItem('userId');
    if (storedUserId) {
        const userId = parseInt(storedUserId);
        console.log('✅ Got user ID from localStorage:', userId);
        return userId;
    }
    
    console.warn('⚠️ Could not get user ID');
    return null;
}

// Load users for group invite dropdown
function loadUsersForInvite() {
    console.log('📥 Loading users for group invite');
    
    fetch('/api/users/invite-list', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success && data.users) {
            console.log(`✅ Loaded ${data.users.length} users for invite`);
            populateUserDropdown(data.users);
        } else {
            console.warn('⚠️ No users returned from API');
        }
    })
    .catch(error => {
        console.error('❌ Error loading users for invite:', error);
        showNotification('Warning', 'Could not load user list. You can still add emails manually.', 'warning');
    });
}

// Populate user dropdown
function populateUserDropdown(users) {
    const userList = document.getElementById('userList');
    if (!userList) return;
    
    userList.innerHTML = '';
    
    users.forEach(user => {
        const userItem = document.createElement('div');
        userItem.style.cssText = `
            padding: 10px 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
            border-bottom: 1px solid var(--border-color);
            transition: background-color 0.2s;
        `;
        
        userItem.innerHTML = `
            <input type="checkbox" id="user_${user.id}" value="${user.email}" style="cursor: pointer;">
            <label for="user_${user.id}" style="flex: 1; cursor: pointer; margin: 0;">
                <div style="font-weight: 500; color: var(--text-primary);">${user.username}</div>
                <div style="font-size: 12px; color: var(--text-secondary);">${user.email}</div>
            </label>
        `;
        
        userItem.addEventListener('mouseenter', () => {
            userItem.style.backgroundColor = 'var(--bg-tertiary)';
        });
        
        userItem.addEventListener('mouseleave', () => {
            userItem.style.backgroundColor = 'transparent';
        });
        
        const checkbox = userItem.querySelector('input[type="checkbox"]');
        checkbox.addEventListener('change', () => {
            updateSelectedUsers();
        });
        
        userList.appendChild(userItem);
    });
}

// Update selected users display
function updateSelectedUsers() {
    const checkboxes = document.querySelectorAll('#userList input[type="checkbox"]:checked');
    selectedUsersForGroup = Array.from(checkboxes).map(cb => ({
        email: cb.value,
        id: cb.id.replace('user_', '')
    }));
    
    const displayContainer = document.getElementById('selectedUsersDisplay');
    if (!displayContainer) return;
    
    displayContainer.innerHTML = '';
    
    selectedUsersForGroup.forEach(user => {
        const tag = document.createElement('div');
        tag.style.cssText = `
            background: var(--accent-color);
            color: white;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 8px;
        `;
        
        tag.innerHTML = `
            <span>${user.email}</span>
            <button onclick="removeSelectedUser('${user.email}')" style="background: none; border: none; color: white; cursor: pointer; font-size: 16px; padding: 0; line-height: 1;">×</button>
        `;
        
        displayContainer.appendChild(tag);
    });
    
    console.log(`✅ Selected ${selectedUsersForGroup.length} users`);
}

// Remove selected user
function removeSelectedUser(email) {
    const checkbox = document.querySelector(`#userList input[value="${email}"]`);
    if (checkbox) {
        checkbox.checked = false;
        updateSelectedUsers();
    }
}


// ============================================================================
// GROUP CHAT HELPER FUNCTIONS - Backend Integration
// ============================================================================

/**
 * Create a new group chat with members
 * @param {string} groupName - Name of the group
 * @param {array} members - Array of member emails or user IDs
 * @param {string} sessionId - Current session ID
 * @param {string} mode - Data source mode (pakwheels, reddit, etc.)
 */
function createGroupChatAPI(groupName, members, sessionId, mode = currentMode) {
    console.log('📤 Creating group chat via API:', {
        groupName: groupName,
        memberCount: members.length,
        mode: mode
    });
    
    return fetch('/create_group_chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            group_name: groupName,
            members: members,
            session_id: sessionId,
            mode: mode
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('✅ Group created successfully:', data);
        return data;
    })
    .catch(error => {
        console.error('❌ Error creating group:', error);
        throw error;
    });
}

/**
 * Add a participant to an existing group
 * @param {string} groupId - Group ID
 * @param {number} userId - User ID to add
 */
function addParticipantToGroupAPI(groupId, userId) {
    console.log('📤 Adding participant to group:', {
        groupId: groupId,
        userId: userId
    });
    
    return fetch('/api/group-chat/invite-user', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            group_id: groupId,
            user_id: userId
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('✅ Participant added successfully:', data);
        return data;
    })
    .catch(error => {
        console.error('❌ Error adding participant:', error);
        throw error;
    });
}

/**
 * Remove a participant from a group
 * @param {string} groupId - Group ID
 * @param {number} userId - User ID to remove
 */
function removeParticipantFromGroupAPI(groupId, userId) {
    console.log('📤 Removing participant from group:', {
        groupId: groupId,
        userId: userId
    });
    
    return fetch('/api/group-chat/remove', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            group_id: groupId,
            user_id: userId
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('✅ Participant removed successfully:', data);
        return data;
    })
    .catch(error => {
        console.error('❌ Error removing participant:', error);
        throw error;
    });
}

/**
 * Get group chat message history
 * @param {string} groupId - Group ID
 * @param {number} limit - Max messages to retrieve (default: 100)
 */
function getGroupChatHistoryAPI(groupId, limit = 100) {
    console.log('📥 Fetching group chat history:', {
        groupId: groupId,
        limit: limit
    });
    
    return fetch(`/api/group-chat/messages?group_id=${groupId}&limit=${limit}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('✅ Group chat history retrieved:', {
            messageCount: data.messages?.length || 0
        });
        return data;
    })
    .catch(error => {
        console.error('❌ Error fetching group chat history:', error);
        throw error;
    });
}

/**
 * Send a message to group chat
 * @param {string} groupId - Group ID
 * @param {string} query - User message
 * @param {string} mode - Data source mode
 * @param {boolean} thinking - Whether thinking mode is enabled
 */
function sendMessageToGroupAPI(groupId, query, mode = currentMode, thinking = thinkingMode) {
    console.log('📤 Sending message to group:', {
        groupId: groupId,
        queryLength: query.length,
        mode: mode,
        thinking: thinking
    });
    
    return fetch('/api/group-chat/message/send', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            group_id: groupId,
            query: query,
            mode: mode,
            thinking: thinking
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('✅ Message sent to group successfully');
        return data;
    })
    .catch(error => {
        console.error('❌ Error sending message to group:', error);
        throw error;
    });
}

/**
 * Get all groups for current user
 */
function getUserGroupChatsAPI() {
    console.log('📥 Fetching user group chats');
    
    return fetch('/api/group-chat/user-groups', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('✅ User group chats retrieved:', {
            groupCount: data.groups?.length || 0
        });
        return data;
    })
    .catch(error => {
        console.error('❌ Error fetching user group chats:', error);
        throw error;
    });
}

/**
 * Delete a group chat
 * @param {string} groupId - Group ID to delete
 */
function deleteGroupChatAPI(groupId) {
    console.log('📤 Deleting group chat:', groupId);
    
    return fetch('/api/group-chat/delete', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            group_id: groupId
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('✅ Group chat deleted successfully');
        return data;
    })
    .catch(error => {
        console.error('❌ Error deleting group chat:', error);
        throw error;
    });
}

/**
 * Get detailed group chat information
 * @param {string} groupId - Group ID
 */
function getGroupChatInfoAPI(groupId) {
    console.log('📥 Fetching group chat info:', groupId);
    
    return fetch(`/api/group-chat/info?group_id=${groupId}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('✅ Group chat info retrieved:', {
            groupName: data.name,
            memberCount: data.member_count || 0
        });
        return data;
    })
    .catch(error => {
        console.error('❌ Error fetching group chat info:', error);
        throw error;
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ Group chat API functions loaded');
});


// Close group and return to chat
function closeGroupAndReturnToChat() {
    console.log('❌ Closing group and returning to chat');
    
    // Exit group chat mode
    isGroupChatMode = false;
    currentGroupId = null;
    currentGroupName = null;
    
    // Hide group details header
    const detailsHeader = document.getElementById('groupDetailsHeader');
    if (detailsHeader) {
        detailsHeader.remove();
    }
    
    // Clear messages
    const messagesContainer = document.getElementById('messagesContainer');
    if (messagesContainer) {
        messagesContainer.innerHTML = '';
        messagesContainer.style.display = 'none';
    }
    
    // Show welcome screen
    const welcomeScreen = document.getElementById('welcomeScreen');
    if (welcomeScreen) {
        welcomeScreen.innerHTML = `
            <div class="welcome-content">
                <h1 class="welcome-title">Welcome to Chat</h1>
                <p class="welcome-subtitle">Select a data source and start chatting</p>
            </div>
        `;
        welcomeScreen.style.display = 'flex';
    }
    
    // Stop polling
    if (groupMessagePollingInterval) {
        clearInterval(groupMessagePollingInterval);
        groupMessagePollingInterval = null;
    }
    
    // Hide group only mode button
    const groupOnlyModeBtn = document.getElementById('groupOnlyModeBtn');
    if (groupOnlyModeBtn) {
        groupOnlyModeBtn.style.display = 'none';
    }
    
    console.log('✅ Returned to chat');
}

// Show clear conversation confirmation dialog
function showClearConversationConfirmation(groupId, groupName) {
    console.log('🧹 Showing clear conversation confirmation for:', groupName);
    
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.6);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
    `;
    overlay.setAttribute('data-overlay', 'true');
    
    const modal = document.createElement('div');
    modal.style.cssText = `
        background: var(--bg-primary);
        border-radius: 12px;
        padding: 32px;
        max-width: 450px;
        width: 90%;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
        border: 1px solid var(--border-color);
        text-align: center;
    `;
    
    modal.innerHTML = `
        <div style="margin-bottom: 20px;">
            <span style="font-size: 48px; display: block; margin-bottom: 12px;">🧹</span>
            <h2 style="margin: 0 0 8px 0; font-size: 20px; font-weight: 600; color: var(--text-primary);">Clear Conversation</h2>
            <p style="margin: 0; color: var(--text-secondary); font-size: 14px;">This action cannot be undone</p>
        </div>
        
        <p style="margin: 0 0 20px 0; color: var(--text-secondary); font-size: 14px; line-height: 1.6;">
            Are you sure you want to clear all messages in <strong>"${groupName}"</strong>? All conversation history will be permanently deleted.
        </p>
        
        <div style="display: flex; gap: 12px; justify-content: center;">
            <button id="cancelClearBtn" style="padding: 10px 20px; border-radius: 6px; background: var(--bg-tertiary); color: var(--text-primary); border: 1px solid var(--border-color); cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.2s; min-width: 100px;">
                Cancel
            </button>
            <button id="confirmClearBtn" style="padding: 10px 20px; border-radius: 6px; background: #f59e0b; color: white; border: none; cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.2s; min-width: 100px;">
                Clear All
            </button>
        </div>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    // Cancel button
    const cancelBtn = modal.querySelector('#cancelClearBtn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            overlay.remove();
        });
        
        cancelBtn.addEventListener('mouseenter', () => {
            cancelBtn.style.background = 'var(--bg-secondary)';
        });
        
        cancelBtn.addEventListener('mouseleave', () => {
            cancelBtn.style.background = 'var(--bg-tertiary)';
        });
    }
    
    // Confirm button
    const confirmBtn = modal.querySelector('#confirmClearBtn');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => {
            clearGroupConversation(groupId, groupName);
            overlay.remove();
        });
        
        confirmBtn.addEventListener('mouseenter', () => {
            confirmBtn.style.background = '#d97706';
        });
        
        confirmBtn.addEventListener('mouseleave', () => {
            confirmBtn.style.background = '#f59e0b';
        });
    }
    
    // Close on overlay click
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            overlay.remove();
        }
    });
}

// Clear group conversation
function clearGroupConversation(groupId, groupName) {
    console.log('🧹 Clearing conversation for group:', groupId);
    
    fetch('/api/group-chat/clear', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            group_id: groupId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('✅ Conversation cleared successfully');
            showNotification('Success', `All messages in "${groupName}" have been cleared`, 'success');
            
            // Clear messages from UI
            const messagesContainer = document.getElementById('messagesContainer');
            if (messagesContainer) {
                messagesContainer.innerHTML = '';
                messagesContainer.style.display = 'none';
            }
            
            // Show welcome screen
            const welcomeScreen = document.getElementById('welcomeScreen');
            if (welcomeScreen) {
                welcomeScreen.innerHTML = `
                    <div class="welcome-content">
                        <h1 class="welcome-title">👥 ${groupName}</h1>
                        <p class="welcome-subtitle">Group Chat - All members can see this conversation</p>
                    </div>
                `;
                welcomeScreen.style.display = 'flex';
            }
        } else {
            showNotification('Error', data.error || 'Failed to clear conversation', 'error');
        }
    })
    .catch(error => {
        console.error('❌ Error clearing conversation:', error);
        showNotification('Error', 'Failed to clear conversation', 'error');
    });
}

// Show delete group confirmation dialog (centered)
function showDeleteGroupConfirmation(groupId, groupName) {
    console.log('🗑️ Showing delete group confirmation for:', groupName);
    
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.6);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
    `;
    overlay.setAttribute('data-overlay', 'true');
    
    const modal = document.createElement('div');
    modal.style.cssText = `
        background: var(--bg-primary);
        border-radius: 12px;
        padding: 32px;
        max-width: 450px;
        width: 90%;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
        border: 1px solid var(--border-color);
        text-align: center;
    `;
    
    modal.innerHTML = `
        <div style="margin-bottom: 20px;">
            <span style="font-size: 48px; display: block; margin-bottom: 12px;">🗑️</span>
            <h2 style="margin: 0 0 8px 0; font-size: 20px; font-weight: 600; color: var(--text-primary);">Delete Group</h2>
            <p style="margin: 0; color: var(--text-secondary); font-size: 14px;">This action cannot be undone</p>
        </div>
        
        <p style="margin: 0 0 20px 0; color: var(--text-secondary); font-size: 14px; line-height: 1.6;">
            Are you sure you want to permanently delete the group <strong>"${groupName}"</strong>? All messages and member information will be lost.
        </p>
        
        <div style="display: flex; gap: 12px; justify-content: center;">
            <button id="cancelDeleteBtn" style="padding: 10px 20px; border-radius: 6px; background: var(--bg-tertiary); color: var(--text-primary); border: 1px solid var(--border-color); cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.2s; min-width: 100px;">
                Cancel
            </button>
            <button id="confirmDeleteBtn" style="padding: 10px 20px; border-radius: 6px; background: #dc2626; color: white; border: none; cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.2s; min-width: 100px;">
                Delete Group
            </button>
        </div>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    // Cancel button
    const cancelBtn = modal.querySelector('#cancelDeleteBtn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            overlay.remove();
        });
        
        cancelBtn.addEventListener('mouseenter', () => {
            cancelBtn.style.background = 'var(--bg-secondary)';
        });
        
        cancelBtn.addEventListener('mouseleave', () => {
            cancelBtn.style.background = 'var(--bg-tertiary)';
        });
    }
    
    // Confirm button
    const confirmBtn = modal.querySelector('#confirmDeleteBtn');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => {
            deleteGroupChat(groupId, groupName);
            overlay.remove();
        });
        
        confirmBtn.addEventListener('mouseenter', () => {
            confirmBtn.style.background = '#b91c1c';
        });
        
        confirmBtn.addEventListener('mouseleave', () => {
            confirmBtn.style.background = '#dc2626';
        });
    }
    
    // Close on overlay click
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            overlay.remove();
        }
    });
}

// Delete group chat
function deleteGroupChat(groupId, groupName) {
    console.log('🗑️ Deleting group chat:', groupId);
    
    deleteGroupChatAPI(groupId)
        .then(data => {
            console.log('✅ Group deleted successfully');
            showNotification('Success', `Group "${groupName}" has been deleted`, 'success');
            
            // Exit group chat mode
            isGroupChatMode = false;
            currentGroupId = null;
            currentGroupName = null;
            
            // Hide group details header
            const detailsHeader = document.getElementById('groupDetailsHeader');
            if (detailsHeader) {
                detailsHeader.remove();
            }
            
            // Clear messages
            const messagesContainer = document.getElementById('messagesContainer');
            if (messagesContainer) {
                messagesContainer.innerHTML = '';
                messagesContainer.style.display = 'none';
            }
            
            // Show welcome screen
            const welcomeScreen = document.getElementById('welcomeScreen');
            if (welcomeScreen) {
                welcomeScreen.innerHTML = `
                    <div class="welcome-content">
                        <h1 class="welcome-title">Welcome to Chat</h1>
                        <p class="welcome-subtitle">Select a data source and start chatting</p>
                    </div>
                `;
                welcomeScreen.style.display = 'flex';
            }
            
            // Stop polling
            if (groupMessagePollingInterval) {
                clearInterval(groupMessagePollingInterval);
                groupMessagePollingInterval = null;
            }
            
            // Reload groups list
            loadUserGroups();
        })
        .catch(error => {
            console.error('❌ Error deleting group:', error);
            showNotification('Error', 'Failed to delete group', 'error');
        });
}

// Show remove user modal
function showRemoveUserModal(groupId, groupName, members) {
    console.log('➖ Opening remove user modal for group:', groupId);
    
    const overlay = document.createElement('div');
    overlay.style.cssText = `
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
    `;
    overlay.setAttribute('data-overlay', 'true');
    
    const modal = document.createElement('div');
    modal.style.cssText = `
        background: var(--bg-primary);
        border-radius: 12px;
        padding: 24px;
        max-width: 450px;
        width: 90%;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        max-height: 80vh;
        overflow-y: auto;
    `;
    
    modal.innerHTML = `
        <div style="margin-bottom: 24px;">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                <span style="font-size: 24px;">➖</span>
                <div>
                    <h2 style="margin: 0; color: var(--text-primary); font-size: 18px;">Remove User</h2>
                    <p style="margin: 4px 0 0 0; color: var(--text-secondary); font-size: 13px;">Select a member to remove</p>
                </div>
            </div>
        </div>
        
        <div id="membersList" style="margin-bottom: 20px; max-height: 300px; overflow-y: auto;">
            ${members.map(m => {
                // Use user_id if available, otherwise use email as identifier
                const identifier = m.user_id || m.email;
                return `
                    <div style="padding: 12px; background: var(--bg-secondary); border-radius: 6px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
                        <div>
                            <div style="font-weight: 500; color: var(--text-primary); font-size: 14px;">${m.username || m.email || 'Unknown'}</div>
                            <div style="font-size: 12px; color: var(--text-secondary);">${m.email || 'No email'}</div>
                        </div>
                        <button class="removeUserOption" data-user-id="${identifier}" data-email="${m.email || ''}" style="padding: 6px 12px; border-radius: 4px; background: #ef4444; color: white; border: none; cursor: pointer; font-size: 12px; font-weight: 500; transition: background 0.2s;">
                            Remove
                        </button>
                    </div>
                `;
            }).join('')}
        </div>
        
        <div style="display: flex; gap: 12px; justify-content: flex-end;">
            <button id="cancelRemoveBtn" style="padding: 10px 16px; border-radius: 6px; background: var(--bg-tertiary); color: var(--text-primary); border: 1px solid var(--border-color); cursor: pointer; font-size: 14px; font-weight: 500; transition: background 0.2s;">
                Cancel
            </button>
        </div>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    // Cancel button
    const cancelBtn = modal.querySelector('#cancelRemoveBtn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            overlay.remove();
        });
        
        cancelBtn.addEventListener('mouseenter', () => {
            cancelBtn.style.background = 'var(--bg-secondary)';
        });
        
        cancelBtn.addEventListener('mouseleave', () => {
            cancelBtn.style.background = 'var(--bg-tertiary)';
        });
    }
    
    // Remove user buttons
    const removeButtons = modal.querySelectorAll('.removeUserOption');
    removeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const userId = btn.getAttribute('data-user-id');
            if (userId && userId !== 'null') {
                removeUserFromGroup(groupId, userId, groupName);
                overlay.remove();
            } else {
                showNotification('Error', 'Cannot remove this user', 'error');
            }
        });
        
        btn.addEventListener('mouseenter', () => {
            btn.style.background = '#dc2626';
        });
        
        btn.addEventListener('mouseleave', () => {
            btn.style.background = '#ef4444';
        });
    });
    
    // Close on overlay click
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            overlay.remove();
        }
    });
}

// Remove user from group
function removeUserFromGroup(groupId, userId, groupName) {
    console.log('➖ Removing user from group:', groupId, userId);
    
    // userId can be either a user_id (number) or an email (string)
    // If it looks like an email, send it as email, otherwise as user_id
    const isEmail = userId && userId.includes('@');
    
    const payload = {
        group_id: groupId
    };
    
    if (isEmail) {
        payload.email = userId;
    } else {
        payload.user_id = userId;
    }
    
    fetch('/api/group-chat/remove', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('✅ User removed successfully');
            showNotification('Success', 'User removed from group', 'success');
            // Reload group details
            loadAndDisplayGroupDetails(groupId, groupName);
        } else {
            showNotification('Error', data.error || 'Failed to remove user', 'error');
        }
    })
    .catch(error => {
        console.error('❌ Error removing user:', error);
        showNotification('Error', 'Failed to remove user', 'error');
    });
}