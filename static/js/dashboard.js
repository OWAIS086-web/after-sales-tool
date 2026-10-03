// Dashboard JavaScript

// Disable frontend logging - set to false to disable all console logs
const ENABLE_FRONTEND_LOGGING = false;

// Override console methods if logging is disabled
if (!ENABLE_FRONTEND_LOGGING) {
    console.log = function() {};
    console.warn = function() {};
    console.info = function() {};
    console.debug = function() {};
}

document.addEventListener('DOMContentLoaded', function() {
    // Initialize dashboard
    initDashboard();
});

function initDashboard() {
    // Add scroll effects
    addScrollEffects();
    
    // Add intersection observer for animations
    addIntersectionObserver();
    
    // Add particle effects
    addParticleEffects();
    
    // Add smooth scrolling
    addSmoothScrolling();
}

// Scroll effects for navigation
function addScrollEffects() {
    const nav = document.querySelector('.dashboard-nav');
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
                
                // Special handling for stats
                if (entry.target.classList.contains('stats-section')) {
                    animateStats();
                }
            }
        });
    }, observerOptions);
    
    // Observe elements
    const elementsToObserve = document.querySelectorAll('.feature-card, .stat-item, .stats-section');
    elementsToObserve.forEach(el => observer.observe(el));
}

// Animate statistics numbers
function animateStats() {
    const statNumbers = document.querySelectorAll('.stat-number');
    
    statNumbers.forEach(stat => {
        const finalValue = stat.textContent;
        const numericValue = parseInt(finalValue.replace(/,/g, '')) || 0;
        
        if (numericValue > 0) {
            animateNumber(stat, 0, numericValue, 2000);
        }
    });
}

function animateNumber(element, start, end, duration) {
    const startTime = performance.now();
    const isPercentage = element.textContent.includes('%');
    const isDecimal = element.textContent.includes('.');
    
    const update = (currentTime) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Easing function
        const easeOutCubic = 1 - Math.pow(1 - progress, 3);
        const current = Math.floor(start + (end - start) * easeOutCubic);
        
        if (isPercentage) {
            element.textContent = current + '%';
        } else if (isDecimal) {
            element.textContent = (current / 10).toFixed(1);
        } else {
            element.textContent = current.toLocaleString();
        }
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    };
    
    requestAnimationFrame(update);
}

// Add particle effects to hero section
function addParticleEffects() {
    const heroSection = document.querySelector('.hero-section');
    if (!heroSection) return;
    
    // Create particles container
    const particlesContainer = document.createElement('div');
    particlesContainer.className = 'particles-container';
    particlesContainer.style.cssText = `
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        overflow: hidden;
        z-index: 0;
    `;
    
    heroSection.appendChild(particlesContainer);
    
    // Create particles
    for (let i = 0; i < 50; i++) {
        createParticle(particlesContainer);
    }
}

function createParticle(container) {
    const particle = document.createElement('div');
    particle.className = 'particle';
    
    const size = Math.random() * 4 + 2;
    const x = Math.random() * 100;
    const y = Math.random() * 100;
    const duration = Math.random() * 20 + 10;
    const delay = Math.random() * 5;
    
    particle.style.cssText = `
        position: absolute;
        width: ${size}px;
        height: ${size}px;
        background: var(--primary-color);
        border-radius: 50%;
        left: ${x}%;
        top: ${y}%;
        opacity: 0.1;
        animation: float ${duration}s ease-in-out infinite ${delay}s;
    `;
    
    container.appendChild(particle);
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

// Add hover effects to floating cards
document.addEventListener('DOMContentLoaded', function() {
    const floatingCards = document.querySelectorAll('.floating-card');
    
    floatingCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-10px) scale(1.05)';
            this.style.boxShadow = '0 20px 40px rgba(0, 0, 0, 0.2)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = '';
            this.style.boxShadow = '';
        });
    });
});

// Add typing effect to hero title
function addTypingEffect() {
    const titleElement = document.querySelector('.hero-title');
    if (!titleElement) return;
    
    const originalText = titleElement.innerHTML;
    const gradientTextElement = titleElement.querySelector('.gradient-text');
    const gradientText = gradientTextElement ? gradientTextElement.textContent : '';
    
    // Split text into parts
    const beforeGradient = originalText.split('<span class="gradient-text">')[0];
    const afterGradient = originalText.split('</span>')[1] || '';
    
    titleElement.innerHTML = '';
    
    let index = 0;
    const fullText = beforeGradient + gradientText + afterGradient;
    
    function typeWriter() {
        if (index < beforeGradient.length) {
            titleElement.innerHTML += fullText.charAt(index);
        } else if (index < beforeGradient.length + gradientText.length) {
            if (index === beforeGradient.length) {
                titleElement.innerHTML += '<span class="gradient-text">';
            }
            titleElement.innerHTML += fullText.charAt(index);
            if (index === beforeGradient.length + gradientText.length - 1) {
                titleElement.innerHTML += '</span>';
            }
        } else {
            titleElement.innerHTML += fullText.charAt(index);
        }
        
        index++;
        
        if (index < fullText.length) {
            setTimeout(typeWriter, 50);
        }
    }
    
    // Start typing effect after a delay
    setTimeout(typeWriter, 1000);
}

// Add parallax effect to hero section
function addParallaxEffect() {
    const heroSection = document.querySelector('.hero-section');
    if (!heroSection) return;
    
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        const parallaxSpeed = 0.5;
        
        heroSection.style.transform = `translateY(${scrolled * parallaxSpeed}px)`;
    });
}

// Add mouse movement effect to floating cards
function addMouseMovementEffect() {
    const heroAnimation = document.querySelector('.hero-animation');
    if (!heroAnimation) return;
    
    heroAnimation.addEventListener('mousemove', (e) => {
        const rect = heroAnimation.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        
        const deltaX = (x - centerX) / centerX;
        const deltaY = (y - centerY) / centerY;
        
        const floatingCards = heroAnimation.querySelectorAll('.floating-card');
        floatingCards.forEach((card, index) => {
            const intensity = (index + 1) * 5;
            const moveX = deltaX * intensity;
            const moveY = deltaY * intensity;
            
            card.style.transform = `translate(${moveX}px, ${moveY}px)`;
        });
    });
    
    heroAnimation.addEventListener('mouseleave', () => {
        const floatingCards = heroAnimation.querySelectorAll('.floating-card');
        floatingCards.forEach(card => {
            card.style.transform = '';
        });
    });
}

// Initialize additional effects
window.addEventListener('load', function() {
    addParallaxEffect();
    addMouseMovementEffect();
    
    // Add loading animation
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
    
    .particle {
        will-change: transform;
    }
    
    body.loaded .hero-content > * {
        animation-play-state: running;
    }
    
    .floating-card {
        will-change: transform;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    .hero-section {
        will-change: transform;
    }
`;

// Inject additional styles
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalStyles;
document.head.appendChild(styleSheet);