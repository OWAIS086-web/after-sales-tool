// Login Page JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Initialize login page
    initLoginPage();
});

function initLoginPage() {
    // Load theme
    loadTheme();
    
    // Focus on username field
    setTimeout(() => {
        const usernameField = document.getElementById('username');
        if (usernameField) {
            usernameField.focus();
        }
    }, 100);
    
    // Add form validation
    addFormValidation();
    
    // Add keyboard shortcuts
    addKeyboardShortcuts();
}

// Theme management
function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateAuthLogo(savedTheme);
}

function updateAuthLogo(theme) {
    const authLogo = document.getElementById('authLogo');
    if (authLogo) {
        // In dark mode, use light logo for contrast (and vice versa)
        const logoFile = theme === 'dark' ? 'light-logo.svg' : 'dark-logo.svg';
        authLogo.src = `/static/images/${logoFile}`;
    }
}

// Form validation
function addFormValidation() {
    const form = document.querySelector('.auth-form');
    if (!form) return;
    
    form.addEventListener('submit', function(e) {
        const username = document.getElementById('username');
        const password = document.getElementById('password');
        
        if (!username || !password) return;
        
        const usernameValue = username.value.trim();
        const passwordValue = password.value;
        
        if (!usernameValue || !passwordValue) {
            e.preventDefault();
            showError('Please fill in all fields');
            return false;
        }
        
        // Show loading state
        const submitBtn = form.querySelector('.auth-btn');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="loading-spinner"></span>Signing In...';
            const spinner = submitBtn.querySelector('.loading-spinner');
            if (spinner) {
                spinner.style.display = 'inline-block';
            }
        }
    });
    
    // Real-time validation
    const username = document.getElementById('username');
    const password = document.getElementById('password');
    
    if (username) {
        username.addEventListener('input', function() {
            clearFieldError(this);
        });
    }
    
    if (password) {
        password.addEventListener('input', function() {
            clearFieldError(this);
        });
    }
}

function showError(message) {
    // Remove existing error
    const existingError = document.querySelector('.form-error');
    if (existingError) {
        existingError.remove();
    }
    
    // Create new error
    const errorDiv = document.createElement('div');
    errorDiv.className = 'flash-message error form-error';
    errorDiv.textContent = message;
    
    // Insert before form
    const form = document.querySelector('.auth-form');
    if (form) {
        form.parentNode.insertBefore(errorDiv, form);
    }
    
    // Remove after 5 seconds
    setTimeout(() => {
        if (errorDiv.parentNode) {
            errorDiv.remove();
        }
    }, 5000);
}

function clearFieldError(field) {
    field.classList.remove('error');
}

// Keyboard shortcuts
function addKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ctrl + / to toggle theme
        if (e.ctrlKey && e.key === '/') {
            e.preventDefault();
            toggleTheme();
        }
        
        // Enter to submit form when focused on username
        if (e.key === 'Enter' && e.target.id === 'username') {
            const password = document.getElementById('password');
            if (password) {
                password.focus();
            }
        }
    });
}

// Add input animations
function addInputAnimations() {
    const inputs = document.querySelectorAll('.form-input');
    
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
        });
        
        input.addEventListener('blur', function() {
            if (!this.value) {
                this.parentElement.classList.remove('focused');
            }
        });
        
        // Check if input has value on load
        if (input.value) {
            input.parentElement.classList.add('focused');
        }
    });
}

// Initialize animations
window.addEventListener('load', function() {
    addInputAnimations();
    
    // Add entrance animation
    const container = document.querySelector('.auth-container');
    if (container) {
        container.style.opacity = '0';
        container.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            container.style.transition = 'all 0.5s ease-out';
            container.style.opacity = '1';
            container.style.transform = 'translateY(0)';
        }, 100);
    }
});

// Add CSS for additional animations
const additionalStyles = `
    .form-group.focused .form-label {
        color: var(--primary-color);
        transform: translateY(-2px);
    }
    
    .form-input {
        transition: all 0.3s ease;
    }
    
    .form-input:focus {
        transform: translateY(-1px);
    }
    
    .auth-container {
        animation: slideIn 0.5s ease-out;
    }
    
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .loading-spinner {
        display: inline-block;
        animation: spin 1s linear infinite;
    }
`;

// Inject additional styles
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalStyles;
document.head.appendChild(styleSheet);