// ----- TOAST MODUL -----
const ToastManager = {
    container: null,
    
    init() {
        this.createContainer();
    },
    
    createContainer() {
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                max-width: 350px;
            `;
            document.body.appendChild(this.container);
        }
    },
    
    show(message, type = 'info', duration = 4000) {
        const toast = document.createElement('div');
        const timestamp = new Date().toLocaleTimeString();
        
        toast.className = `toast toast-${type}`;
        toast.style.cssText = `
            background: ${this.getBackgroundColor(type)};
            color: white;
            padding: 12px 16px;
            margin-bottom: 10px;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            transform: translateX(100%);
            transition: all 0.3s ease;
            animation: slideInRight 0.3s ease forwards;
            border-left: 4px solid ${this.getBorderColor(type)};
            font-size: 14px;
            line-height: 1.4;
        `;
        
        toast.innerHTML = `
            <div class="toast-content">
                <div class="toast-message">
                    <strong>${this.getIcon(type)} ${this.getTitle(type)}</strong>
                    <div>${message}</div>
                    <small style="opacity: 0.8; font-size: 12px;">${timestamp}</small>
                </div>
                <button class="toast-close" onclick="this.parentElement.parentElement.remove()" 
                        style="background: none; border: none; color: rgba(255,255,255,0.8); 
                               cursor: pointer; padding: 0 0 0 10px; font-size: 18px;">×</button>
            </div>
        `;
        
        this.container.appendChild(toast);
        
        // Auto remove
        setTimeout(() => {
            if (toast.parentNode) {
                toast.style.animation = 'slideOutRight 0.3s ease forwards';
                setTimeout(() => toast.remove(), 300);
            }
        }, duration);
        
        return toast;
    },
    
    getBackgroundColor(type) {
        const colors = {
            success: 'linear-gradient(135deg, #28a745, #20c997)',
            error: 'linear-gradient(135deg, #dc3545, #e74c3c)',
            warning: 'linear-gradient(135deg, #ffc107, #fd7e14)',
            info: 'linear-gradient(135deg, #17a2b8, #6f42c1)'
        };
        return colors[type] || colors.info;
    },
    
    getBorderColor(type) {
        const colors = {
            success: '#1e7e34',
            error: '#bd2130',
            warning: '#d39e00',
            info: '#117a8b'
        };
        return colors[type] || colors.info;
    },
    
    getIcon(type) {
        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️'
        };
        return icons[type] || icons.info;
    },
    
    getTitle(type) {
        const titles = {
            success: 'Siker',
            error: 'Hiba',
            warning: 'Figyelem',
            info: 'Információ'
        };
        return titles[type] || titles.info;
    }
};

// ----- LOADING MODUL -----
const LoadingManager = {
    overlay: null,
    
    init() {
        this.createOverlay();
    },
    
    createOverlay() {
        if (!this.overlay) {
            this.overlay = document.createElement('div');
            this.overlay.id = 'loading-overlay';
            this.overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.7);
                backdrop-filter: blur(3px);
                z-index: 9999;
                display: none;
                justify-content: center;
                align-items: center;
                flex-direction: column;
            `;
            
            this.overlay.innerHTML = `
                <div style="background: white; padding: 30px; border-radius: 15px; text-align: center; 
                           box-shadow: 0 10px 30px rgba(0,0,0,0.3); max-width: 300px;">
                    <div class="spinner" style="border: 4px solid #f3f3f3; border-top: 4px solid #007bff; 
                                             border-radius: 50%; width: 50px; height: 50px; 
                                             animation: spin 1s linear infinite; margin: 0 auto 20px;"></div>
                    <div id="loading-message" style="color: #333; font-size: 16px; font-weight: 500;">
                        Betöltés...
                    </div>
                    <div style="color: #666; font-size: 14px; margin-top: 10px;">
                        Kérjük várjon...
                    </div>
                </div>
            `;
            
            document.body.appendChild(this.overlay);
        }
    },
    
    show(message = 'Betöltés...') {
        const messageElement = this.overlay.querySelector('#loading-message');
        if (messageElement) {
            messageElement.textContent = message;
        }
        this.overlay.style.display = 'flex';
    },
    
    hide() {
        this.overlay.style.display = 'none';
    }
};

// ----- API MODUL -----
const ApiManager = {
    async post(url, data) {
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(data)
            });
            
            return await response.json();
        } catch (error) {
            console.error('API hiba:', error);
            throw error;
        }
    },
    
    async get(url) {
        try {
            const response = await fetch(url, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            return await response.json();
        } catch (error) {
            console.error('API hiba:', error);
            throw error;
        }
    }
};

// ----- RATING MODUL -----
const RatingManager = {
    ratings: {},
    
    async submitRating(recipeId, rating) {
        try {
            LoadingManager.show('Értékelés mentése...');
            
            const response = await ApiManager.post('/rate_recipe', {
                recipe_id: recipeId,
                rating: rating
            });
            
            if (response.success) {
                // Sikeres mentés után frissítjük a helyi adatokat
                this.ratings[recipeId] = rating;
                this.markCardAsSelected(recipeId);
                
                ToastManager.show(`Recept értékelve: ${rating}/5 ${'⭐'.repeat(rating)}`, 'success');
                
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
        } finally {
            LoadingManager.hide();
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
        
        const searchUrl = new URL('/search', window.location.origin);
        searchUrl.searchParams.set('q', query);
        
        window.location.href = searchUrl.toString();
    }
};

// ----- ANALYTICS MODUL -----
const AnalyticsManager = {
    async loadDashboard() {
        try {
            LoadingManager.show('Analytics adatok betöltése...');
            
            const response = await ApiManager.get('/api/analytics');
            
            if (response.success) {
                return response.data;
            } else {
                throw new Error('Analytics adatok betöltése sikertelen');
            }
            
        } catch (error) {
            console.error('Analytics hiba:', error);
            ToastManager.show('Analytics adatok betöltése sikertelen', 'error');
            return null;
        } finally {
            LoadingManager.hide();
        }
    },
    
    createLearningCurveChart(containerId, data) {
        // Chart.js vagy egyéb chart library használata itt
        console.log('Learning curve chart létrehozása:', containerId, data);
    }
};

// ----- UTILITY MODUL -----
const Utils = {
    formatDate(date) {
        return new Date(date).toLocaleDateString('hu-HU');
    },
    
    formatTime(date) {
        return new Date(date).toLocaleTimeString('hu-HU');
    },
    
    getUrlParameter(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
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
    }
};

// ----- GLOBÁLIS FÜGGVÉNYEK (Template kompatibilitás) -----
function showToast(message, type = 'info') {
    ToastManager.show(message, type);
}

function showLoading(message = 'Betöltés...') {
    LoadingManager.show(message);
}

function hideLoading() {
    LoadingManager.hide();
}

async function rateRecipe(recipeId, rating) {
    return await RatingManager.submitRating(recipeId, rating);
}

async function advanceToNextRound() {
    return await NavigationManager.nextRound();
}

async function completeStudy() {
    return await NavigationManager.completeStudy();
}

function searchRecipes() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        NavigationManager.search(searchInput.value);
    }
}

function showResults() {
    window.location.href = '/results';
}

// Új globális függvény a gomb állapot ellenőrzésére
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
    
    // ✅ ÚJ: Favicon hiba javítása (404 elkerülése)
    const favicon = document.querySelector('link[rel="icon"]');
    if (!favicon) {
        const newFavicon = document.createElement('link');
        newFavicon.rel = 'icon';
        newFavicon.type = 'image/x-icon';
        newFavicon.href = '/static/images/favicon.ico';
        document.head.appendChild(newFavicon);
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
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
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
    
    /* ✅ ÚJ: Csillag és gomb stílusok */
    .star-rating .star {
        cursor: pointer;
        color: #ddd;
        font-size: 20px;
        transition: color 0.2s ease;
        display: inline-block;
        margin: 0 2px;
    }
    
    .star-rating .star:hover,
    .star-rating .star.active {
        color: #ffc107;
        text-shadow: 0 0 5px rgba(255, 193, 7, 0.5);
    }
    
    .submit-rating-btn.disabled {
        opacity: 0.6;
        cursor: not-allowed;
        background-color: #6c757d;
    }
    
    .submit-rating-btn.enabled {
        opacity: 1;
        cursor: pointer;
        background-color: #28a745;
        animation: glow 0.5s ease-in-out;
    }
    
    @keyframes glow {
        0% { box-shadow: 0 0 5px rgba(40, 167, 69, 0.5); }
        50% { box-shadow: 0 0 15px rgba(40, 167, 69, 0.8); }
        100% { box-shadow: 0 0 5px rgba(40, 167, 69, 0.5); }
    }
    
    .recipe-card.selected {
        border: 2px solid #28a745;
        box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);
        transform: translateY(-2px);
        transition: all 0.3s ease;
    }
`;
document.head.appendChild(style);

// ------- ✅ ÚJ: CSILLAG ÉRTÉKELÉS MODUL -------
// Csillag értékelés kezelése
function initStarRating() {
    document.querySelectorAll('.star-rating').forEach(rating => {
        const stars = rating.querySelectorAll('.star');
        let currentRating = 0;
        
        stars.forEach((star, index) => {
            star.addEventListener('click', async () => {
                currentRating = index + 1;
                updateStarsVisual(stars, currentRating);
                
                // Gomb aktiválása
                const recipeCard = rating.closest('.recipe-card');
                enableSubmitButton(recipeCard);
                
                // ✅ AZONNAL mentjük az értékelést
                const recipeId = recipeCard.dataset.recipeId;
                if (recipeId) {
                    const success = await RatingManager.submitRating(recipeId, currentRating);
                    if (success) {
                        // Template updateUI hívása is
                        if (window.updateUI) {
                            window.updateUI();
                        }
                        checkAndUpdateMainButton();
                    }
                }
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

// Image error handling (placeholder képek javítása)
function handleImageError(img) {
    img.src = '/static/images/placeholder.jpg';
    img.onerror = null; // Prevent infinite loop
}

// Template compatibility - globális függvények kiegészítése
window.initStarRating = initStarRating;
window.handleImageError = handleImageError;
window.checkAndUpdateMainButton = checkAndUpdateMainButton;

// ✅ ÚJ: updateUI függvény a template kompatibilitáshoz
window.updateUI = function() {
    const ratedCount = Object.keys(RatingManager.ratings).length;
    const requiredRatings = parseInt(document.getElementById('requiredRatings')?.value || 3);
    const currentRound = parseInt(document.getElementById('currentRound')?.value || 1);
    const maxRounds = parseInt(document.getElementById('maxRounds')?.value || 3);
    
    const canProceed = ratedCount >= requiredRatings;
    
    // Gomb állapotának frissítése
    const nextBtn = document.getElementById('nextRoundBtn') || document.getElementById('completeStudyBtn');
    if (nextBtn) {
        nextBtn.disabled = !canProceed;
        
        if (canProceed) {
            nextBtn.innerHTML = currentRound < maxRounds ?
                '<i class="fas fa-arrow-right"></i> Következő Kör' :
                '<i class="fas fa-flag-checkered"></i> Tanulmány Befejezése';
        } else {
            nextBtn.innerHTML = `<i class="fas fa-hourglass-half"></i> ${ratedCount}/${requiredRatings} Értékelés`;
        }
    }
    
    // Státusz frissítése
    const statusElement = document.getElementById('ratingStatus');
    if (statusElement) {
        statusElement.textContent = `${ratedCount} / ${requiredRatings} recept értékelve`;
    }
};
