// Signup/Register Page JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Initialize signup page
    initSignupPage();
});

function initSignupPage() {
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
    
    // Add password strength checker
    addPasswordStrengthChecker();
    
    // Add password confirmation checker
    addPasswordConfirmationChecker();
    
    // Add username validation
    addUsernameValidation();
    
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

// Password strength checker
function addPasswordStrengthChecker() {
    const passwordInput = document.getElementById('password');
    const strengthFill = document.getElementById('strengthFill');
    const strengthText = document.getElementById('strengthText');
    
    if (!passwordInput || !strengthFill || !strengthText) return;
    
    passwordInput.addEventListener('input', function() {
        const password = this.value;
        const strength = calculatePasswordStrength(password);
        
        strengthFill.className = 'strength-fill';
        strengthText.className = 'strength-text';
        
        if (strength.score === 0) {
            strengthText.textContent = 'Enter a password';
        } else if (strength.score === 1) {
            strengthFill.classList.add('strength-weak');
            strengthText.classList.add('weak');
            strengthText.textContent = 'Weak password';
        } else if (strength.score === 2) {
            strengthFill.classList.add('strength-fair');
            strengthText.classList.add('fair');
            strengthText.textContent = 'Fair password';
        } else if (strength.score === 3) {
            strengthFill.classList.add('strength-good');
            strengthText.classList.add('good');
            strengthText.textContent = 'Good password';
        } else {
            strengthFill.classList.add('strength-strong');
            strengthText.classList.add('strong');
            strengthText.textContent = 'Strong password';
        }
    });
}

function calculatePasswordStrength(password) {
    let score = 0;
    if (password.length >= 6) score++;
    if (password.length >= 10) score++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
    if (/\d/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;
    return { score: Math.min(score, 4) };
}

// Password confirmation checker
function addPasswordConfirmationChecker() {
    const passwordInput = document.getElementById('password');
    const confirmInput = document.getElementById('confirm_password');
    const passwordMatch = document.getElementById('passwordMatch');
    
    if (!passwordInput || !confirmInput || !passwordMatch) return;
    
    function checkPasswordMatch() {
        const password = passwordInput.value;
        const confirm = confirmInput.value;
        
        if (confirm === '') {
            passwordMatch.textContent = '';
            passwordMatch.className = 'form-help';
            confirmInput.classList.remove('error');
        } else if (password === confirm) {
            passwordMatch.textContent = '✓ Passwords match';
            passwordMatch.className = 'form-help success';
            confirmInput.classList.remove('error');
        } else {
            passwordMatch.textContent = '✗ Passwords do not match';
            passwordMatch.className = 'form-help error';
            confirmInput.classList.add('error');
        }
    }
    
    passwordInput.addEventListener('input', checkPasswordMatch);
    confirmInput.addEventListener('input', checkPasswordMatch);
}

// Username validation
function addUsernameValidation() {
    const usernameInput = document.getElementById('username');
    if (!usernameInput) return;
    
    usernameInput.addEventListener('input', function() {
        const username = this.value;
        const helpText = this.parentElement.querySelector('.form-help');
        
        if (!helpText) return;
        
        if (username.length > 0 && username.length < 3) {
            helpText.textContent = 'Username too short (minimum 3 characters)';
            helpText.className = 'form-help error';
            this.classList.add('error');
        } else if (username.length > 20) {
            helpText.textContent = 'Username too long (maximum 20 characters)';
            helpText.className = 'form-help error';
            this.classList.add('error');
        } else if (username.length > 0 && !/^[a-zA-Z0-9]+$/.test(username)) {
            helpText.textContent = 'Username can only contain letters and numbers';
            helpText.className = 'form-help error';
            this.classList.add('error');
        } else {
            helpText.textContent = '3-20 characters, letters and numbers only';
            helpText.className = 'form-help';
            this.classList.remove('error');
        }
    });
}

// Form validation
function addFormValidation() {
    const form = document.getElementById('registerForm');
    if (!form) return;
    
    form.addEventListener('submit', function(e) {
        const username = document.getElementById('username').value.trim();
        const email = document.getElementById('email').value.trim();
        const password = document.getElementById('password').value;
        const confirm = document.getElementById('confirm_password').value;
        const company_id = document.getElementById('company_id').value;
        
        if (!username || !email || !password || !confirm || !company_id) {
            e.preventDefault();
            showFormError('Please fill in all fields');
            return false;
        }
        
        if (username.length < 3 || username.length > 20) {
            e.preventDefault();
            showFormError('Username must be between 3 and 20 characters');
            return false;
        }
        
        if (!/^[a-zA-Z0-9]+$/.test(username)) {
            e.preventDefault();
            showFormError('Username can only contain letters and numbers');
            return false;
        }
        
        if (password !== confirm) {
            e.preventDefault();
            showFormError('Passwords do not match');
            return false;
        }
        
        if (password.length < 6) {
            e.preventDefault();
            showFormError('Password must be at least 6 characters long');
            return false;
        }
        
        const validCompanies = ['haval', 'kia', 'toyota'];
        if (!validCompanies.includes(company_id)) {
            e.preventDefault();
            showFormError('Please select a valid company');
            return false;
        }
        
        // Show loading state
        const submitBtn = document.getElementById('submitBtn');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Creating Account...';
        }
    });
}

function showFormError(message) {
    // Create or update error message
    let errorDiv = document.querySelector('.form-error');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'flash-message error form-error';
        const form = document.querySelector('.auth-form');
        if (form) {
            form.insertBefore(errorDiv, form.firstChild);
        }
    }
    errorDiv.textContent = message;
    
    // Remove after 5 seconds
    setTimeout(() => {
        if (errorDiv.parentNode) {
            errorDiv.remove();
        }
    }, 5000);
}

// Keyboard shortcuts
function addKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ctrl + / to toggle theme
        if (e.ctrlKey && e.key === '/') {
            e.preventDefault();
            toggleTheme();
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
`;

// Inject additional styles
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalStyles;
document.head.appendChild(styleSheet);