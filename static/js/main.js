// ===== GREENREC MODULÁRIS JAVASCRIPT =====

/**
 * GreenRec JavaScript Utilities
 * Moduláris felépítés toast, loading, analytics funkcionalitással
 */

// ----- GLOBÁLIS VÁLTOZÓK -----
window.GreenRec = {
    config: {
        toastDuration: 4000,
        animationDuration: 300,
        apiTimeout: 10000
    },
    state: {
        isLoading: false,
        toastCounter: 0
    }
};

// ----- TOAST NOTIFIKÁCIÓK MODUL -----
const ToastManager = {
    container: null,
    
    init() {
        // Toast container létrehozása ha nincs
        this.container = document.getElementById('toast-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        }
    },
    
    show(message, type = 'info', duration = null) {
        this.init();
        
        const toast = this.createToast(message, type);
        this.container.appendChild(toast);
        
        // Automatikus eltüntetés
        const hideTimeout = duration || window.GreenRec.config.toastDuration;
        setTimeout(() => {
            this.hide(toast);
        }, hideTimeout);
        
        return toast;
    },
    
    createToast(message, type) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.dataset.toastId = ++window.GreenRec.state.toastCounter;
        
        // Icon mapping
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };
        
        toast.innerHTML = `
            <div class="toast-content">
                <i class="${icons[type] || icons.info}"></i>
                <span class="toast-message">${message}</span>
                <button class="toast-close" onclick="ToastManager.hide(this.parentElement.parentElement)">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        // Klikk az egész toast-ra bezárja
        toast.addEventListener('click', (e) => {
            if (e.target === toast || e.target.classList.contains('toast-content')) {
                this.hide(toast);
            }
        });
        
        return toast;
    },
    
    hide(toast) {
        if (!toast || !toast.parentElement) return;
        
        toast.style.animation = 'slideOutRight 0.3s ease forwards';
        setTimeout(() => {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 300);
    },
    
    clear() {
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
};

// ----- LOADING OVERLAY MODUL -----
const LoadingManager = {
    overlay: null,
    
    init() {
        this.overlay = document.getElementById('loading-overlay');
        if (!this.overlay) {
            this.overlay = document.createElement('div');
            this.overlay.id = 'loading-overlay';
            this.overlay.className = 'loading-overlay';
            this.overlay.style.display = 'none';
            this.overlay.innerHTML = `
                <div class="loading-spinner">
                    <i class="fas fa-spinner fa-spin"></i>
                    <p>Betöltés...</p>
                </div>
            `;
            document.body.appendChild(this.overlay);
        }
    },
    
    show(message = 'Betöltés...') {
        this.init();
        
        const messageElement = this.overlay.querySelector('p');
        if (messageElement) {
            messageElement.textContent = message;
        }
        
        this.overlay.style.display = 'flex';
        window.GreenRec.state.isLoading = true;
        
        // Timeout védelem
        setTimeout(() => {
            if (window.GreenRec.state.isLoading) {
                this.hide();
                ToastManager.show('A művelet túl sokáig tart. Próbálja újra.', 'warning');
            }
        }, window.GreenRec.config.apiTimeout);
    },
    
    hide() {
        if (this.overlay) {
            this.overlay.style.display = 'none';
            window.GreenRec.state.isLoading = false;
        }
    }
};

// ----- API KOMMUNIKÁCIÓ MODUL -----
const ApiManager = {
    async request(url, options = {}) {
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            timeout: window.GreenRec.config.apiTimeout
        };
        
        const config = { ...defaultOptions, ...options };
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), config.timeout);
            
            const response = await fetch(url, {
                ...config,
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            } else {
                return await response.text();
            }
            
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error('A kérés túllépte az időkorlátot');
            }
            throw error;
        }
    },
    
    async get(url) {
        return this.request(url);
    },
    
    async post(url, data) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
};

// ----- RECIPE RATING MODUL -----
const RatingManager = {
    ratings: {},
    
    async rateRecipe(recipeId, rating, roundNumber) {
        try {
            // Lokális tárolás
            this.ratings[recipeId] = rating;
            
            // UI frissítése
            this.updateStars(recipeId, rating);
            this.markCardAsSelected(recipeId);
            
            // Szerver kérés
            const response = await ApiManager.post('/rate', {
                recipe_id: recipeId,
                rating: rating,
                round_number: roundNumber
            });
            
            if (response.success) {
                ToastManager.show(`Értékelés mentve! ${'⭐'.repeat(rating)}`, 'success');
                
                // UI státusz frissítése
                this.updateRatingStatus(response);
                
                return true;
            } else {
                throw new Error(response.error || 'Ismeretlen hiba');
            }
            
        } catch (error) {
            console.error('Rating hiba:', error);
            ToastManager.show('Hiba az értékelés mentése során', 'error');
            
            // Visszaállítás hiba esetén
            delete this.ratings[recipeId];
            this.updateStars(recipeId, 0);
            this.unmarkCard(recipeId);
            
            return false;
        }
    },
    
    updateStars(recipeId, rating) {
        const starsContainer = document.querySelector(`[data-recipe-id="${recipeId}"]`);
        if (!starsContainer) return;
        
        const stars = starsContainer.querySelectorAll('.star');
        stars.forEach((star, index) => {
            star.classList.toggle('active', index < rating);
        });
    },
    
    markCardAsSelected(recipeId) {
        const card = document.querySelector(`[data-recipe-id="${recipeId}"]`);
        if (card) {
            card.classList.add('selected');
        }
    },
    
    unmarkCard(recipeId) {
        const card = document.querySelector(`[data-recipe-id="${recipeId}"]`);
        if (card) {
            card.classList.remove('selected');
        }
    },
    
    updateRatingStatus(response) {
        // Gomb állapot frissítése
        const nextBtn = document.getElementById('nextRoundBtn') || 
                       document.getElementById('completeStudyBtn');
        
        if (nextBtn && response.can_proceed !== undefined) {
            nextBtn.disabled = !response.can_proceed;
            
            const ratedCount = response.rated_count || 0;
            const required = response.required_ratings || 3;
            
            if (response.can_proceed) {
                const isLastRound = document.getElementById('maxRounds') && 
                                   parseInt(document.getElementById('currentRound').value) >= 
                                   parseInt(document.getElementById('maxRounds').value);
                
                nextBtn.innerHTML = isLastRound ? 
                    '<i class="fas fa-flag-checkered"></i> Tanulmány Befejezése' :
                    '<i class="fas fa-arrow-right"></i> Következő Kör';
            } else {
                nextBtn.innerHTML = `<i class="fas fa-hourglass-half"></i> ${ratedCount}/${required} Értékelés`;
            }
        }
        
        // Státusz szöveg frissítése
        const statusElement = document.getElementById('ratingStatus');
        if (statusElement && response.rated_count !== undefined) {
            const required = response.required_ratings || 3;
            statusElement.textContent = `${response.rated_count} / ${required} recept értékelve`;
        }
    },
    
    getRatedCount() {
        return Object.keys(this.ratings).length;
    }
};

// ----- NAVIGATION MODUL -----
const NavigationManager = {
    async nextRound() {
        try {
            LoadingManager.show('Következő kör betöltése...');
            
            const response = await ApiManager.post('/next_round', {});
            
            if (response.success) {
                ToastManager.show('Következő kör betöltése...', 'success');
                
                setTimeout(() => {
                    window.location.href = response.redirect_url || '/';
                }, 1000);
                
                return true;
            } else {
                throw new Error(response.error || 'Nem lehet a következő körre lépni');
            }
            
        } catch (error) {
            console.error('Következő kör hiba:', error);
            ToastManager.show(error.message, 'error');
            return false;
        } finally {
            LoadingManager.hide();
        }
    },
    
    async completeStudy() {
        try {
            LoadingManager.show('Tanulmány befejezése...');
            
            const response = await ApiManager.post('/next_round', {});
            
            if (response.success) {
                ToastManager.show('Tanulmány befejezve! Eredmények betöltése...', 'success');
                
                setTimeout(() => {
                    window.location.href = '/results';
                }, 1500);
                
                return true;
            } else {
                throw new Error(response.error || 'Hiba a tanulmány befejezésében');
            }
            
        } catch (error) {
            console.error('Tanulmány befejezési hiba:', error);
            ToastManager.show(error.message, 'error');
            return false;
        } finally {
            LoadingManager.hide();
        }
    },
    
    search(query) {
        if (!query || query.length < 2) {
            ToastManager.show('Legalább 2 karakter szükséges a kereséshez!', 'warning');
            return;
        }
        
        LoadingManager.show('Keresés...');
        window.location.href = `/search?q=${encodeURIComponent(query)}`;
    }
};

// ----- ANALYTICS MODUL -----
const AnalyticsManager = {
    async loadDashboard() {
        try {
            const data = await ApiManager.get('/api/dashboard');
            return data;
        } catch (error) {
            console.error('Dashboard betöltési hiba:', error);
            ToastManager.show('Hiba a dashboard betöltésekor', 'error');
            return null;
        }
    },
    
    createLearningCurveChart(canvasId, data) {
        const ctx = document.getElementById(canvasId);
        if (!ctx || !window.Chart) return null;
        
        return new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.rounds || [1, 2, 3],
                datasets: [
                    {
                        label: 'A Csoport',
                        data: data.group_A || [0.25, 0.35, 0.40],
                        borderColor: '#1976d2',
                        backgroundColor: 'rgba(25, 118, 210, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'B Csoport',
                        data: data.group_B || [0.35, 0.50, 0.56],
                        borderColor: '#388e3c',
                        backgroundColor: 'rgba(56, 142, 60, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'C Csoport',
                        data: data.group_C || [0.45, 0.65, 0.72],
                        borderColor: '#f57c00',
                        backgroundColor: 'rgba(245, 124, 0, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Az Ön teljesítménye',
                        data: data.current_user || [0, 0, 0],
                        borderColor: '#e91e63',
                        backgroundColor: 'rgba(233, 30, 99, 0.1)',
                        borderWidth: 3,
                        tension: 0.4,
                        borderDash: [5, 5]
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Tanulási Görbék - F1 Score Fejlődése'
                    },
                    legend: {
                        display: true,
                        position: 'bottom'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 1,
                        title: {
                            display: true,
                            text: 'F1 Score'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Tanulási Kör'
                        }
                    }
                }
            }
        });
    }
};

// ----- UTILITY FUNKCIÓK -----
const Utils = {
    formatNumber(num, decimals = 2) {
        return Number(num).toFixed(decimals);
    },
    
    formatPercentage(num) {
        return `${(num * 100).toFixed(1)}%`;
    },
    
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    throttle(func, limit) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },
    
    validateRating(rating) {
        const num = parseInt(rating);
        return num >= 1 && num <= 5;
    },
    
    getUrlParameter(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
    }
};

// ----- GLOBÁLIS FÜGGVÉNYEK (TEMPLATE COMPATIBILITY) -----
window.showToast = (message, type) => ToastManager.show(message, type);
window.showLoading = (message) => LoadingManager.show(message);
window.hideLoading = () => LoadingManager.hide();

// Template-ben használt függvények
window.rateRecipe = async (event, recipeId, rating) => {
    event.stopPropagation();
    
    if (!Utils.validateRating(rating)) {
        ToastManager.show('Érvénytelen értékelés!', 'error');
        return;
    }
    
    const roundNumber = parseInt(document.getElementById('currentRound')?.value || 1);
    await RatingManager.rateRecipe(recipeId, rating, roundNumber);
};

window.selectRecipe = (card) => {
    if (!card.classList.contains('selected')) {
        card.classList.add('selected');
    }
};

window.advanceToNextRound = () => NavigationManager.nextRound();
window.completeStudy = () => NavigationManager.completeStudy();
window.showResults = () => window.location.href = '/results';

window.handleSearchKeypress = (event) => {
    if (event.key === 'Enter') {
        const query = event.target.value.trim();
        NavigationManager.search(query);
    }
};

window.performSearch = () => {
    const input = document.getElementById('searchInput');
    if (input) {
        const query = input.value.trim();
        NavigationManager.search(query);
    }
};

// ----- INICIALIZÁLÁS -----
document.addEventListener('DOMContentLoaded', function() {
    // Toast manager inicializálása
    ToastManager.init();
    
    // Loading manager inicializálása
    LoadingManager.init();
    
    // ✅ ÚJ: Csillag értékelés inicializálása
    initStarRating();
    
    // Existing ratings betöltése a DOM-ból
    document.querySelectorAll('.star.active').forEach(star => {
        const container = star.closest('[data-recipe-id]');
        const recipeId = container?.dataset.recipeId;
        const rating = parseInt(star.dataset.rating);
        
        if (recipeId && rating) {
            RatingManager.ratings[recipeId] = rating;
        }
    });
    
    // Keresőmező auto-focus
    const searchInput = document.getElementById('searchInput');
    if (searchInput && Utils.getUrlParameter('q')) {
        searchInput.value = Utils.getUrlParameter('q');
    }
    
    // Analytics oldal specifikus inicializálás
    if (window.location.pathname === '/analytics') {
        AnalyticsManager.loadDashboard().then(data => {
            if (data && data.metrics && data.metrics.learning_curves) {
                AnalyticsManager.createLearningCurveChart(
                    'learningCurveChart', 
                    data.metrics.learning_curves
                );
            }
        });
    }
    
    // Console információ (fejlesztői célokra)
    console.log('🌱 GreenRec JavaScript modulok betöltve');
    console.log('Elérhető modulok:', {
        Toast: ToastManager,
        Loading: LoadingManager,
        Api: ApiManager,
        Rating: RatingManager,
        Navigation: NavigationManager,
        Analytics: AnalyticsManager,
        Utils: Utils
    });
});

// ----- CSS ANIMÁCIÓK KIEGÉSZÍTÉSE -----
const style = document.createElement('style');
style.textContent = `
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
    
    .toast-content {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .toast-message {
        flex: 1;
    }
    
    .toast-close {
        background: none;
        border: none;
        color: #666;
        cursor: pointer;
        padding: 5px;
        border-radius: 3px;
        transition: background-color 0.2s;
    }
    
    .toast-close:hover {
        background-color: rgba(0,0,0,0.1);
    }
    
    /* ✅ ÚJ CSS - Értékelés gombok */
    .submit-rating-btn.disabled {
        background: #CCCCCC;
        color: #666666;
        cursor: not-allowed;
        opacity: 0.6;
    }

    .submit-rating-btn.enabled {
        background: #4CAF50;
        color: white;
        cursor: pointer;
        opacity: 1;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(76, 175, 80, 0.3);
    }

    .submit-rating-btn.enabled:hover {
        background: #45a049;
        transform: translateY(-3px);
        box-shadow: 0 6px 16px rgba(76, 175, 80, 0.4);
    }

    /* Csillagok aktív állapota */
    .star.active {
        color: #FFD700;
        transform: scale(1.1);
    }

    .star:hover {
        color: #FFD700;
        transform: scale(1.2);
        transition: all 0.2s ease;
    }
`;
document.head.appendChild(style);

// ----- ✅ ÚJ: CSILLAG ÉRTÉKELÉS MODUL -----
function initStarRating() {
    document.querySelectorAll('.star-rating').forEach(rating => {
        const stars = rating.querySelectorAll('.star');
        let currentRating = 0;
        
        stars.forEach((star, index) => {
            star.addEventListener('click', () => {
                currentRating = index + 1;
                updateStarsVisual(stars, currentRating);
                enableSubmitButton(rating.closest('.recipe-card'));
            });
            
            star.addEventListener('mouseover', () => {
                updateStarsVisual(stars, index + 1);
            });
        });
        
        rating.addEventListener('mouseleave', () => {
            updateStarsVisual(stars, currentRating);
        });
    });
}

function updateStarsVisual(stars, rating) {
    stars.forEach((star, index) => {
        star.classList.toggle('active', index < rating);
    });
}

function enableSubmitButton(recipeCard) {
    const submitBtn = recipeCard?.querySelector('.submit-rating-btn');
    if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.classList.remove('disabled');
        submitBtn.classList.add('enabled');
    }
    
    // ✅ FŐ GOMB FRISSÍTÉSE
    checkAndUpdateMainButton();
}

function checkAndUpdateMainButton() {
    const ratedCount = Object.keys(RatingManager.ratings).length;
    const requiredRatings = 3;
    
    const nextBtn = document.getElementById('nextRoundBtn') || 
                   document.getElementById('completeStudyBtn');
    
    if (nextBtn) {
        const canProceed = ratedCount >= requiredRatings;
        nextBtn.disabled = !canProceed;
        
        if (canProceed) {
            nextBtn.innerHTML = '<i class="fas fa-arrow-right"></i> Következő Kör';
        } else {
            nextBtn.innerHTML = `<i class="fas fa-hourglass-half"></i> ${ratedCount}/${requiredRatings} Értékelés`;
        }
    }
    
    // Státusz szöveg frissítése
    const statusElement = document.getElementById('ratingStatus');
    if (statusElement) {
        statusElement.textContent = `${ratedCount} / ${requiredRatings} recept értékelve`;
    }
}

function handleImageError(img) {
    img.src = '/static/images/placeholder.jpg';
    img.onerror = null; // Prevent infinite loop
}

// Template compatibility - globális függvények kiegészítése
window.initStarRating = initStarRating;
window.handleImageError = handleImageError;
