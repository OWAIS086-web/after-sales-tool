// Landing Page JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Initialize landing page
    initLandingPage();
    
    // Load theme and update logo
    loadTheme();
});

// Theme management
function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateLogo(savedTheme);
}

function updateLogo(theme) {
    const logo = document.getElementById('navLogo');
    if (logo) {
        // Dark theme uses light logo, light theme uses dark logo
        const logoFile = theme === 'dark' ? 'light-logo.svg' : 'dark-logo.svg';
        logo.src = `/static/images/${logoFile}`;
    }
}

// Listen for theme changes
const themeObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (mutation.type === 'attributes' && mutation.attributeName === 'data-theme') {
            const theme = document.documentElement.getAttribute('data-theme');
            updateLogo(theme);
        }
    });
});

themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme']
});

function initLandingPage() {
    // Add scroll effects
    addScrollEffects();
    
    // Add intersection observer for animations
    addIntersectionObserver();
    
    // Add smooth scrolling
    addSmoothScrolling();
    
    // Add typing effect
    addTypingEffect();
    
    // Add counter animations
    addCounterAnimations();
    
    // Add parallax effects
    addParallaxEffects();
}

// Scroll effects for navigation
function addScrollEffects() {
    const nav = document.querySelector('.antigravity-nav');
    let lastScrollY = window.scrollY;
    
    window.addEventListener('scroll', () => {
        const currentScrollY = window.scrollY;
        
        if (currentScrollY > 100) {
            nav.style.background = 'rgba(255, 255, 255, 0.98)';
            nav.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.1)';
        } else {
            nav.style.background = 'rgba(255, 255, 255, 0.95)';
            nav.style.boxShadow = '0 1px 3px rgba(0, 0, 0, 0.1)';
        }
        
        // Hide/show nav on scroll
        if (currentScrollY > lastScrollY && currentScrollY > 200) {
            nav.style.transform = 'translateY(-100%)';
        } else {
            nav.style.transform = 'translateY(0)';
        }
        
        lastScrollY = currentScrollY;
    });
    
    // Update nav background for dark theme
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'attributes' && mutation.attributeName === 'data-theme') {
                const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
                if (window.scrollY > 100) {
                    nav.style.background = isDark ? 'rgba(26, 26, 26, 0.98)' : 'rgba(255, 255, 255, 0.98)';
                } else {
                    nav.style.background = isDark ? 'rgba(26, 26, 26, 0.95)' : 'rgba(255, 255, 255, 0.95)';
                }
            }
        });
    });
    
    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-theme']
    });
}

// Intersection Observer for animations
function addIntersectionObserver() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
                
                // Special handling for different sections
                if (entry.target.classList.contains('hero-stats')) {
                    animateCounters();
                }
                
                if (entry.target.classList.contains('sentiment-chart')) {
                    animateChartBars();
                }
            }
        });
    }, observerOptions);
    
    // Observe elements
    const elementsToObserve = document.querySelectorAll(
        '.feature-card, .hero-stats, .sentiment-chart, .floating-elements, .demo-video'
    );
    elementsToObserve.forEach(el => observer.observe(el));
}

// Smooth scrolling for anchor links
function addSmoothScrolling() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                const offsetTop = target.offsetTop - 80; // Account for fixed nav
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
            }
        });
    });
}

// Typing effect for hero title
function addTypingEffect() {
    const titleElement = document.querySelector('.hero-title');
    if (!titleElement) return;
    
    const originalHTML = titleElement.innerHTML;
    const textContent = titleElement.textContent;
    
    // Clear the title initially
    titleElement.innerHTML = '';
    titleElement.style.opacity = '1';
    
    let index = 0;
    const cursor = '<span class="typing-cursor">|</span>';
    
    function typeWriter() {
        if (index < textContent.length) {
            const char = textContent.charAt(index);
            const currentText = textContent.substring(0, index + 1);
            
            // Check if we're at the gradient text part
            if (currentText.includes('Intelligent Insights')) {
                const beforeGradient = currentText.split('Intelligent Insights')[0];
                const gradientPart = 'Intelligent Insights';
                titleElement.innerHTML = beforeGradient + 
                    '<span class="gradient-text">' + gradientPart + '</span>' + cursor;
            } else {
                titleElement.innerHTML = currentText + cursor;
            }
            
            index++;
            setTimeout(typeWriter, 50);
        } else {
            // Remove cursor and set final HTML
            setTimeout(() => {
                titleElement.innerHTML = originalHTML;
            }, 1000);
        }
    }
    
    // Start typing effect after a delay
    setTimeout(typeWriter, 1500);
}

// Counter animations for hero stats
function addCounterAnimations() {
    // This will be triggered by intersection observer
}

function animateCounters() {
    const counters = document.querySelectorAll('.stat-number[data-target]');
    
    counters.forEach(counter => {
        const target = parseInt(counter.getAttribute('data-target'));
        const isPercentage = target === 95; // 95% accuracy rate
        
        if (target > 0) {
            animateNumber(counter, 0, target, 2000, isPercentage);
        }
    });
}

function animateNumber(element, start, end, duration, isPercentage = false) {
    const startTime = performance.now();
    
    const update = (currentTime) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Easing function
        const easeOutCubic = 1 - Math.pow(1 - progress, 3);
        const current = Math.floor(start + (end - start) * easeOutCubic);
        
        if (isPercentage) {
            element.textContent = current + '%';
        } else if (end >= 1000) {
            element.textContent = (current / 1000).toFixed(1) + 'K+';
        } else {
            element.textContent = current.toLocaleString();
        }
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    };
    
    requestAnimationFrame(update);
}

// Animate chart bars
function animateChartBars() {
    const bars = document.querySelectorAll('.chart-bar');
    bars.forEach((bar, index) => {
        setTimeout(() => {
            bar.style.animation = 'growUp 1s ease-out forwards';
        }, index * 200);
    });
}

// Parallax effects
function addParallaxEffects() {
    const floatingElements = document.querySelectorAll('.floating-element');
    const dashboardPreview = document.querySelector('.dashboard-preview');
    
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        const rate = scrolled * -0.5;
        
        // Parallax for floating elements
        floatingElements.forEach((element, index) => {
            const speed = (index + 1) * 0.3;
            element.style.transform = `translateY(${scrolled * speed}px)`;
        });
        
        // Parallax for dashboard preview
        if (dashboardPreview) {
            dashboardPreview.style.transform = `translateY(${rate * 0.2}px)`;
        }
    });
}

// Add hover effects to feature cards
document.addEventListener('DOMContentLoaded', function() {
    const featureCards = document.querySelectorAll('.feature-card');
    
    featureCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-12px)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(-8px)';
        });
    });
});

// Add click effect to demo video
document.addEventListener('DOMContentLoaded', function() {
    const videoPlaceholder = document.querySelector('.video-placeholder');
    
    if (videoPlaceholder) {
        videoPlaceholder.addEventListener('click', function() {
            // Add click animation
            this.style.transform = 'scale(0.98)';
            setTimeout(() => {
                this.style.transform = 'scale(1.02)';
            }, 150);
            
            // Here you would typically open a video modal or redirect to video
            console.log('Demo video clicked - implement video player');
        });
    }
});

// Add mouse movement effect to hero visual
function addMouseMovementEffect() {
    const heroVisual = document.querySelector('.hero-visual');
    if (!heroVisual) return;
    
    heroVisual.addEventListener('mousemove', (e) => {
        const rect = heroVisual.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        
        const deltaX = (x - centerX) / centerX;
        const deltaY = (y - centerY) / centerY;
        
        const floatingElements = heroVisual.querySelectorAll('.floating-element');
        floatingElements.forEach((element, index) => {
            const intensity = (index + 1) * 3;
            const moveX = deltaX * intensity;
            const moveY = deltaY * intensity;
            
            element.style.transform = `translate(${moveX}px, ${moveY}px)`;
        });
        
        const dashboardPreview = heroVisual.querySelector('.dashboard-preview');
        if (dashboardPreview) {
            const moveX = deltaX * 5;
            const moveY = deltaY * 5;
            dashboardPreview.style.transform = `translate(${moveX}px, ${moveY}px)`;
        }
    });
    
    heroVisual.addEventListener('mouseleave', () => {
        const floatingElements = heroVisual.querySelectorAll('.floating-element');
        floatingElements.forEach(element => {
            element.style.transform = '';
        });
        
        const dashboardPreview = heroVisual.querySelector('.dashboard-preview');
        if (dashboardPreview) {
            dashboardPreview.style.transform = '';
        }
    });
}

// Add loading animations
function addLoadingAnimations() {
    // Add stagger animation to feature cards
    const featureCards = document.querySelectorAll('.feature-card');
    featureCards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
    });
    
    // Add stagger animation to floating elements
    const floatingElements = document.querySelectorAll('.floating-element');
    floatingElements.forEach((element, index) => {
        element.style.animationDelay = `${index * 0.5}s`;
    });
}

// Initialize additional effects
window.addEventListener('load', function() {
    addMouseMovementEffect();
    addLoadingAnimations();
    
    // Add loaded class for animations
    document.body.classList.add('loaded');
});

// Add CSS for additional animations
const additionalStyles = `
    .animate-in {
        animation: slideInUp 0.8s ease-out forwards;
    }
    
    @keyframes slideInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .typing-cursor {
        animation: blink 1s infinite;
        color: var(--primary-color);
    }
    
    @keyframes blink {
        0%, 50% { opacity: 1; }
        51%, 100% { opacity: 0; }
    }
    
    .floating-element {
        will-change: transform;
        transition: transform 0.3s ease;
    }
    
    .dashboard-preview {
        will-change: transform;
        transition: transform 0.3s ease;
    }
    
    body.loaded .hero-content > * {
        animation-play-state: running;
    }
    
    .feature-card {
        animation: fadeInUp 0.8s ease-out forwards;
        opacity: 0;
    }
    
    body.loaded .feature-card {
        opacity: 1;
    }
`;

// Inject additional styles
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalStyles;
document.head.appendChild(styleSheet);