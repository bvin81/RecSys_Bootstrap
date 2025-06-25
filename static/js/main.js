// static/js/main.js
/**
 * GreenRec - Main JavaScript
 * ========================
 * Modern JavaScript for interactive sustainability-focused recipe recommendations
 */

// Global application state
const GreenRec = {
    config: {
        apiEndpoints: {
            search: '/api/search',
            rate: '/api/rate',
            analytics: '/api/analytics',
            dashboard: '/analytics/dashboard-data',
            nextRound: '/api/next-round'
        },
        debounceDelay: 300,
        animationDuration: 300,
        chartColors: {
            primary: '#2d7d32',
            success: '#4caf50',
            warning: '#ff9800',
            error: '#d32f2f',
            info: '#1976d2'
        }
    },
    state: {
        currentRatings: {},
        isLoading: false,
        searchTimeout: null,
        charts: {}
    },
    
    // Initialize application
    init() {
        console.log('🌱 GreenRec initializing...');
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Initialize components
        this.initializeComponents();
        
        // Setup mobile menu
        this.setupMobileMenu();
        
        // Initialize charts if on analytics page
        if (document.querySelector('.chart-container')) {
            this.initializeCharts();
        }
        
        console.log('✅ GreenRec initialized successfully');
    },
    
    // Setup all event listeners
    setupEventListeners() {
        // Star rating system
        this.setupStarRating();
        
        // Search functionality
        this.setupSearch();
        
        // Next round button
        this.setupNextRound();
        
        // Flash message close buttons
        this.setupFlashMessages();
        
        // Keyboard navigation
        this.setupKeyboardNavigation();
        
        // Performance monitoring
        this.setupPerformanceMonitoring();
    },
    
    // Initialize UI components
    initializeComponents() {
        // Animate recipe cards on load
        this.animateRecipeCards();
        
        // Setup tooltips
        this.setupTooltips();
        
        // Initialize progress bars
        this.updateProgressBars();
        
        // Setup lazy loading for images
        this.setupLazyLoading();
    },
    
    // Mobile menu functionality
    setupMobileMenu() {
        const mobileToggle = document.querySelector('.mobile-menu-toggle');
        const navMenu = document.querySelector('.nav-menu');
        
        if (mobileToggle && navMenu) {
            mobileToggle.addEventListener('click', () => {
                navMenu.classList.toggle('active');
                mobileToggle.classList.toggle('active');
                
                // Animate hamburger lines
                const lines = mobileToggle.querySelectorAll('.hamburger-line');
                lines.forEach((line, index) => {
                    line.style.transform = navMenu.classList.contains('active') 
                        ? `rotate(${index === 0 ? 45 : index === 1 ? 0 : -45}deg) translate(${index === 1 ? '10px' : '0'}, ${index === 1 ? '0' : index === 0 ? '6px' : '-6px'})`
                        : 'none';
                    line.style.opacity = index === 1 && navMenu.classList.contains('active') ? '0' : '1';
                });
            });
            
            // Close menu when clicking outside
            document.addEventListener('click', (e) => {
                if (!mobileToggle.contains(e.target) && !navMenu.contains(e.target)) {
                    navMenu.classList.remove('active');
                    mobileToggle.classList.remove('active');
                }
            });
        }
    },
    
    // Star rating system
    setupStarRating() {
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('star')) {
                const recipeId = e.target.dataset.recipeId;
                const rating = parseInt(e.target.dataset.rating);
                
                this.handleStarRating(recipeId, rating, e.target);
            }
        });
        
        // Hover effects for stars
        document.addEventListener('mouseover', (e) => {
            if (e.target.classList.contains('star')) {
                const rating = parseInt(e.target.dataset.rating);
                const recipeId = e.target.dataset.recipeId;
                this.highlightStars(recipeId, rating, true);
            }
        });
        
        document.addEventListener('mouseout', (e) => {
            if (e.target.classList.contains('star')) {
                const recipeId = e.target.dataset.recipeId;
                const currentRating = this.state.currentRatings[recipeId] || 0;
                this.highlightStars(recipeId, currentRating, false);
            }
        });
    },
    
    // Handle star rating click
    handleStarRating(recipeId, rating, starElement) {
        console.log(`⭐ Rating recipe ${recipeId} with ${rating} stars`);
        
        // Update UI immediately
        this.state.currentRatings[recipeId] = rating;
        this.highlightStars(recipeId, rating, false);
        
        // Show loading state
        this.showLoading(`Értékelés mentése...`);
        
        // Send rating to server
        this.submitRating(recipeId, rating)
            .then(response => {
                console.log('✅ Rating saved successfully');
                this.showFlashMessage('Értékelés elmentve!', 'success');
                
                // Update progress if available
                this.updateRatingProgress();
                
                // Check if all 6 recipes are rated
                this.checkRoundCompletion();
            })
            .catch(error => {
                console.error('❌ Rating save failed:', error);
                this.showFlashMessage('Értékelés mentése sikertelen', 'error');
                
                // Revert UI state
                delete this.state.currentRatings[recipeId];
                this.highlightStars(recipeId, 0, false);
            })
            .finally(() => {
                this.hideLoading();
            });
    },
    
    // Highlight stars up to rating
    highlightStars(recipeId, rating, isHover) {
        const stars = document.querySelectorAll(`[data-recipe-id="${recipeId}"].star`);
        
        stars.forEach((star, index) => {
            const starRating = index + 1;
            
            if (starRating <= rating) {
                star.classList.add('active');
                star.style.color = '#ffd700';
                star.style.transform = isHover ? 'scale(1.1)' : 'scale(1)';
            } else {
                star.classList.remove('active');
                star.style.color = '#e0e0e0';
                star.style.transform = 'scale(1)';
            }
        });
    },
    
    // Submit rating to server
    async submitRating(recipeId, rating) {
        try {
            const response = await fetch(this.config.apiEndpoints.rate, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    recipe_id: recipeId,
                    rating: rating,
                    timestamp: new Date().toISOString()
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status !== 'success') {
                throw new Error(data.message || 'Unknown error');
            }
            
            return data;
        } catch (error) {
            console.error('Rating submission error:', error);
            throw error;
        }
    },
    
    // Search functionality
    setupSearch() {
        const searchInput = document.querySelector('.search-input');
        const searchButton = document.querySelector('.search-button');
        
        if (searchInput) {
            // Debounced search on input
            searchInput.addEventListener('input', (e) => {
                clearTimeout(this.state.searchTimeout);
                this.state.searchTimeout = setTimeout(() => {
                    this.performSearch(e.target.value);
                }, this.config.debounceDelay);
            });
            
            // Search on Enter key
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    clearTimeout(this.state.searchTimeout);
                    this.performSearch(e.target.value);
                }
            });
        }
        
        if (searchButton) {
            searchButton.addEventListener('click', (e) => {
                e.preventDefault();
                const query = searchInput ? searchInput.value : '';
                this.performSearch(query);
            });
        }
    },
    
    // Perform search
    async performSearch(query) {
        if (!query.trim()) {
            console.log('Empty search query');
            return;
        }
        
        console.log(`🔍 Searching for: "${query}"`);
        
        this.showLoading('Keresés...');
        
        try {
            const response = await fetch(`${this.config.apiEndpoints.search}?q=${encodeURIComponent(query)}`, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (!response.ok) {
                throw new Error(`Search failed: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.displaySearchResults(data.recipes);
                this.showFlashMessage(`${data.recipes.length} recept találat`, 'info');
            } else {
                throw new Error(data.message || 'Search failed');
            }
            
        } catch (error) {
            console.error('❌ Search error:', error);
            this.showFlashMessage('Keresési hiba történt', 'error');
        } finally {
            this.hideLoading();
        }
    },
    
    // Display search results
    displaySearchResults(recipes) {
        const resultsContainer = document.querySelector('.recipe-grid');
        
        if (!resultsContainer) {
            console.warn('No results container found');
            return;
        }
        
        // Clear existing results
        resultsContainer.innerHTML = '';
        
        if (recipes.length === 0) {
            resultsContainer.innerHTML = `
                <div class="no-results">
                    <h3>Nincs találat</h3>
                    <p>Próbáljon meg más keresési kifejezést.</p>
                </div>
            `;
            return;
        }
        
        // Create recipe cards
        recipes.forEach(recipe => {
            const recipeCard = this.createRecipeCard(recipe);
            resultsContainer.appendChild(recipeCard);
        });
        
        // Animate new cards
        this.animateRecipeCards();
    },
    
    // Create recipe card element
    createRecipeCard(recipe) {
        const card = document.createElement('div');
        card.className = 'recipe-card fade-in';
        
        card.innerHTML = `
            <div class="recipe-image-container">
                <img src="${recipe.image || '/static/images/default-recipe.jpg'}" 
                     alt="${recipe.name}" 
                     class="recipe-image"
                     loading="lazy">
                <div class="recommendation-badge">
                    ${recipe.composite_score ? Math.round(recipe.composite_score) : 'N/A'}
                </div>
            </div>
            
            <div class="recipe-content">
                <h3 class="recipe-title">${recipe.name}</h3>
                <p class="recipe-description">${recipe.description || 'Nincs leírás elérhető'}</p>
                
                <div class="recipe-metrics">
                    <div class="metric-item">
                        <span class="metric-icon">🌍</span>
                        <span class="metric-value">${recipe.ESI_final ? Math.round(recipe.ESI_final) : 'N/A'}</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-icon">💚</span>
                        <span class="metric-value">${recipe.HSI ? Math.round(recipe.HSI) : 'N/A'}</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-icon">👤</span>
                        <span class="metric-value">${recipe.PPI ? Math.round(recipe.PPI) : 'N/A'}</span>
                    </div>
                </div>
                
                <div class="composite-score">
                    Kompozit: ${recipe.composite_score ? Math.round(recipe.composite_score) : 'N/A'}
                </div>
                
                <div class="star-rating">
                    ${[1, 2, 3, 4, 5].map(rating => `
                        <span class="star" 
                              data-recipe-id="${recipe.id}" 
                              data-rating="${rating}">⭐</span>
                    `).join('')}
                </div>
                
                ${recipe.categories ? `
                    <div class="category-tags">
                        ${recipe.categories.split(',').slice(0, 3).map(cat => 
                            `<span class="category-tag">${cat.trim()}</span>`
                        ).join('')}
                    </div>
                ` : ''}
            </div>
        `;
        
        return card;
    },
    
    // Next round functionality
    setupNextRound() {
        const nextRoundBtn = document.querySelector('.next-round-btn');
        
        if (nextRoundBtn) {
            nextRoundBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.startNextRound();
            });
        }
    },
    
    // Start next learning round
    async startNextRound() {
        console.log('🔄 Starting next learning round...');
        
        this.showLoading('Következő kör indítása...');
        
        try {
            const response = await fetch(this.config.apiEndpoints.nextRound, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (!response.ok) {
                throw new Error(`Next round failed: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.showFlashMessage('Új kör elkezdődött!', 'success');
                
                // Reload page to show new recommendations
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                throw new Error(data.message || 'Next round failed');
            }
            
        } catch (error) {
            console.error('❌ Next round error:', error);
            this.showFlashMessage('Következő kör indítása sikertelen', 'error');
        } finally {
            this.hideLoading();
        }
    },
    
    // Flash messages
    setupFlashMessages() {
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('flash-close')) {
                const message = e.target.closest('.flash-message');
                if (message) {
                    message.style.animation = 'slideOutRight 0.3s ease-in';
                    setTimeout(() => message.remove(), 300);
                }
            }
        });
        
        // Auto-hide flash messages after 5 seconds
        document.querySelectorAll('.flash-message').forEach(message => {
            setTimeout(() => {
                if (message.parentNode) {
                    message.style.animation = 'slideOutRight 0.3s ease-in';
                    setTimeout(() => message.remove(), 300);
                }
            }, 5000);
        });
    },
    
    // Show flash message
    showFlashMessage(text, type = 'info') {
        const container = document.querySelector('.flash-messages') || this.createFlashContainer();
        
        const message = document.createElement('div');
        message.className = `flash-message flash-${type}`;
        
        const icon = {
            'success': 'check-circle',
            'error': 'exclamation-triangle', 
            'warning': 'exclamation-triangle',
            'info': 'info-circle'
        }[type] || 'info-circle';
        
        message.innerHTML = `
            <i class="fas fa-${icon}"></i>
            <span class="flash-text">${text}</span>
            <button class="flash-close">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        container.appendChild(message);
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (message.parentNode) {
                message.style.animation = 'slideOutRight 0.3s ease-in';
                setTimeout(() => message.remove(), 300);
            }
        }, 5000);
    },
    
    // Create flash messages container
    createFlashContainer() {
        const container = document.createElement('div');
        container.className = 'flash-messages';
        document.body.appendChild(container);
        return container;
    },
    
    // Loading overlay
    showLoading(text = 'Betöltés...') {
        this.state.isLoading = true;
        
        let overlay = document.getElementById('loading-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'loading-overlay';
            overlay.className = 'loading-overlay';
            overlay.innerHTML = `
                <div class="loading-content">
                    <div class="loading-spinner">
                        <i class="fas fa-leaf spinning"></i>
                    </div>
                    <p class="loading-text">${text}</p>
                </div>
            `;
            document.body.appendChild(overlay);
        } else {
            overlay.querySelector('.loading-text').textContent = text;
        }
        
        overlay.classList.remove('hidden');
    },
    
    hideLoading() {
        this.state.isLoading = false;
        
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('hidden');
        }
    },
    
    // Animate recipe cards
    animateRecipeCards() {
        const cards = document.querySelectorAll('.recipe-card');
        
        cards.forEach((card, index) => {
            // Add staggered animation delay
            card.style.animationDelay = `${index * 100}ms`;
            card.classList.add('fade-in');
        });
    },
    
    // Update progress bars
    updateProgressBars() {
        document.querySelectorAll('.progress-bar').forEach(bar => {
            const fill = bar.querySelector('.progress-fill');
            const value = fill.dataset.value || 0;
            
            // Animate progress fill
            setTimeout(() => {
                fill.style.width = `${value}%`;
            }, 100);
        });
    },
    
    // Update rating progress
    updateRatingProgress() {
        const ratedCount = Object.keys(this.state.currentRatings).length;
        const totalCount = 6;
        const percentage = (ratedCount / totalCount) * 100;
        
        const progressBar = document.querySelector('.rating-progress .progress-fill');
        if (progressBar) {
            progressBar.style.width = `${percentage}%`;
        }
        
        const progressText = document.querySelector('.rating-progress-text');
        if (progressText) {
            progressText.textContent = `${ratedCount}/${totalCount} recept értékelve`;
        }
    },
    
    // Check if round is complete
    checkRoundCompletion() {
        const ratedCount = Object.keys(this.state.currentRatings).length;
        
        if (ratedCount >= 6) {
            const nextRoundBtn = document.querySelector('.next-round-btn');
            if (nextRoundBtn) {
                nextRoundBtn.disabled = false;
                nextRoundBtn.classList.remove('hidden');
                
                this.showFlashMessage('Mind a 6 recept értékelve! Indíthat következő kört.', 'success');
            }
        }
    },
    
    // Charts initialization
    initializeCharts() {
        console.log('📊 Initializing charts...');
        
        // Learning curves chart
        this.initializeLearningCurvesChart();
        
        // Group comparison chart  
        this.initializeGroupComparisonChart();
        
        // Metrics overview chart
        this.initializeMetricsChart();
    },
    
    // Learning curves chart
    async initializeLearningCurvesChart() {
        const canvas = document.getElementById('learningCurvesChart');
        if (!canvas) return;
        
        try {
            const response = await fetch('/api/learning-curves');
            const data = await response.json();
            
            if (data.status === 'success') {
                const ctx = canvas.getContext('2d');
                
                this.state.charts.learningCurves = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: data.rounds || [1, 2, 3, 4, 5],
                        datasets: [
                            {
                                label: 'Csoport A (Baseline)',
                                data: data.group_a || [0.2, 0.25, 0.3, 0.32, 0.35],
                                borderColor: this.config.chartColors.error,
                                backgroundColor: this.config.chartColors.error + '20',
                                tension: 0.4
                            },
                            {
                                label: 'Csoport B (Collaborative)',
                                data: data.group_b || [0.2, 0.35, 0.45, 0.52, 0.58],
                                borderColor: this.config.chartColors.warning,
                                backgroundColor: this.config.chartColors.warning + '20',
                                tension: 0.4
                            },
                            {
                                label: 'Csoport C (Hybrid)',
                                data: data.group_c || [0.2, 0.45, 0.6, 0.7, 0.78],
                                borderColor: this.config.chartColors.success,
                                backgroundColor: this.config.chartColors.success + '20',
                                tension: 0.4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            title: {
                                display: true,
                                text: 'Tanulási Görbék - F1-Score Fejlődése'
                            },
                            legend: {
                                position: 'top'
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 1,
                                title: {
                                    display: true,
                                    text: 'F1-Score'
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: 'Tanulási Kör'
                                }
                            }
                        },
                        animation: {
                            duration: 2000,
                            easing: 'easeInOutQuart'
                        }
                    }
                });
            }
        } catch (error) {
            console.error('❌ Learning curves chart error:', error);
        }
    },
    
    // Group comparison chart
    async initializeGroupComparisonChart() {
        const canvas = document.getElementById('groupComparisonChart');
        if (!canvas) return;
        
        try {
            const response = await fetch('/api/group-comparison');
            const data = await response.json();
            
            if (data.status === 'success') {
                const ctx = canvas.getContext('2d');
                
                this.state.charts.groupComparison = new Chart(ctx, {
                    type: 'radar',
                    data: {
                        labels: [
                            'Precision@10',
                            'Recall@10', 
                            'F1-Score',
                            'Diverzitás',
                            'Elégedettség',
                            'Fenntarthatóság'
                        ],
                        datasets: [
                            {
                                label: 'Csoport A',
                                data: [
                                    data.group_a?.precision || 0.3,
                                    data.group_a?.recall || 0.25,
                                    data.group_a?.f1_score || 0.35,
                                    data.group_a?.diversity || 0.4,
                                    data.group_a?.satisfaction || 0.6,
                                    data.group_a?.sustainability || 0.5
                                ],
                                borderColor: this.config.chartColors.error,
                                backgroundColor: this.config.chartColors.error + '20'
                            },
                            {
                                label: 'Csoport B',
                                data: [
                                    data.group_b?.precision || 0.5,
                                    data.group_b?.recall || 0.45,
                                    data.group_b?.f1_score || 0.58,
                                    data.group_b?.diversity || 0.6,
                                    data.group_b?.satisfaction || 0.7,
                                    data.group_b?.sustainability || 0.65
                                ],
                                borderColor: this.config.chartColors.warning,
                                backgroundColor: this.config.chartColors.warning + '20'
                            },
                            {
                                label: 'Csoport C',
                                data: [
                                    data.group_c?.precision || 0.7,
                                    data.group_c?.recall || 0.65,
                                    data.group_c?.f1_score || 0.78,
                                    data.group_c?.diversity || 0.8,
                                    data.group_c?.satisfaction || 0.85,
                                    data.group_c?.sustainability || 0.82
                                ],
                                borderColor: this.config.chartColors.success,
                                backgroundColor: this.config.chartColors.success + '20'
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            title: {
                                display: true,
                                text: 'Csoportok Összehasonlítása'
                            }
                        },
                        scales: {
                            r: {
                                beginAtZero: true,
                                max: 1
                            }
                        },
                        animation: {
                            duration: 2000,
                            easing: 'easeInOutQuart'
                        }
                    }
                });
            }
        } catch (error) {
            console.error('❌ Group comparison chart error:', error);
        }
    },
    
    // Metrics overview chart
    async initializeMetricsChart() {
        const canvas = document.getElementById('metricsChart');
        if (!canvas) return;
        
        try {
            const response = await fetch('/api/metrics-overview');
            const data = await response.json();
            
            if (data.status === 'success') {
                const ctx = canvas.getContext('2d');
                
                this.state.charts.metrics = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Kiváló (4-5⭐)', 'Jó (3⭐)', 'Közepes (2⭐)', 'Gyenge (1⭐)'],
                        datasets: [{
                            data: [
                                data.ratings?.excellent || 35,
                                data.ratings?.good || 40,
                                data.ratings?.average || 20,
                                data.ratings?.poor || 5
                            ],
                            backgroundColor: [
                                this.config.chartColors.success,
                                this.config.chartColors.primary,
                                this.config.chartColors.warning,
                                this.config.chartColors.error
                            ]
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            title: {
                                display: true,
                                text: 'Értékelések Megoszlása'
                            },
                            legend: {
                                position: 'bottom'
                            }
                        },
                        animation: {
                            duration: 2000,
                            easing: 'easeInOutQuart'
                        }
                    }
                });
            }
        } catch (error) {
            console.error('❌ Metrics chart error:', error);
        }
    },
    
    // Keyboard navigation
    setupKeyboardNavigation() {
        document.addEventListener('keydown', (e) => {
            // ESC key closes mobile menu
            if (e.key === 'Escape') {
                const navMenu = document.querySelector('.nav-menu');
                if (navMenu && navMenu.classList.contains('active')) {
                    navMenu.classList.remove('active');
                }
                
                // Hide loading overlay
                if (this.state.isLoading) {
                    this.hideLoading();
                }
            }
            
            // Enter key on star ratings
            if (e.key === 'Enter' && e.target.classList.contains('star')) {
                e.target.click();
            }
        });
    },
    
    // Setup tooltips
    setupTooltips() {
        // Simple tooltip implementation
        document.querySelectorAll('[data-tooltip]').forEach(element => {
            element.addEventListener('mouseenter', (e) => {
                const tooltip = document.createElement('div');
                tooltip.className = 'tooltip';
                tooltip.textContent = e.target.dataset.tooltip;
                tooltip.style.position = 'absolute';
                tooltip.style.background = 'rgba(0,0,0,0.8)';
                tooltip.style.color = 'white';
                tooltip.style.padding = '4px 8px';
                tooltip.style.borderRadius = '4px';
                tooltip.style.fontSize = '12px';
                tooltip.style.zIndex = '9999';
                tooltip.style.pointerEvents = 'none';
                
                document.body.appendChild(tooltip);
                
                const rect = e.target.getBoundingClientRect();
                tooltip.style.top = (rect.top - tooltip.offsetHeight - 5) + 'px';
                tooltip.style.left = (rect.left + rect.width / 2 - tooltip.offsetWidth / 2) + 'px';
                
                e.target._tooltip = tooltip;
            });
            
            element.addEventListener('mouseleave', (e) => {
                if (e.target._tooltip) {
                    e.target._tooltip.remove();
                    delete e.target._tooltip;
                }
            });
        });
    },
    
    // Lazy loading for images
    setupLazyLoading() {
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                            img.classList.remove('lazy');
                            observer.unobserve(img);
                        }
                    }
                });
            });
            
            document.querySelectorAll('img[data-src]').forEach(img => {
                img.classList.add('lazy');
                imageObserver.observe(img);
            });
        }
    },
    
    // Performance monitoring
    setupPerformanceMonitoring() {
        // Page load performance
        window.addEventListener('load', () => {
            if ('performance' in window) {
                const loadTime = performance.timing.loadEventEnd - performance.timing.navigationStart;
                console.log(`🚀 Teljes betöltési idő: ${loadTime}ms`);
                
                // Send to analytics if needed
                this.trackPerformance('page_load', loadTime);
            }
        });
        
        // Monitor API call times
        const originalFetch = window.fetch;
        window.fetch = async (...args) => {
            const startTime = performance.now();
            try {
                const response = await originalFetch(...args);
                const endTime = performance.now();
                const duration = endTime - startTime;
                
                console.log(`🌐 API call to ${args[0]} took ${duration.toFixed(2)}ms`);
                this.trackPerformance('api_call', duration, args[0]);
                
                return response;
            } catch (error) {
                const endTime = performance.now();
                const duration = endTime - startTime;
                
                console.error(`❌ API call to ${args[0]} failed after ${duration.toFixed(2)}ms:`, error);
                this.trackPerformance('api_error', duration, args[0]);
                
                throw error;
            }
        };
    },
    
    // Track performance metrics
    trackPerformance(eventType, duration, details = null) {
        // Simple performance tracking - could be sent to analytics service
        const performanceData = {
            type: eventType,
            duration: duration,
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent,
            url: window.location.href,
            details: details
        };
        
        // Store in localStorage for debugging (optional)
        try {
            const perfHistory = JSON.parse(localStorage.getItem('greenrec_perf') || '[]');
            perfHistory.push(performanceData);
            
            // Keep only last 50 entries
            if (perfHistory.length > 50) {
                perfHistory.splice(0, perfHistory.length - 50);
            }
            
            localStorage.setItem('greenrec_perf', JSON.stringify(perfHistory));
        } catch (e) {
            // localStorage might not be available
            console.warn('Could not store performance data:', e);
        }
    },
    
    // Utility functions
    utils: {
        // Debounce function
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
        
        // Throttle function
        throttle(func, limit) {
            let inThrottle;
            return function() {
                const args = arguments;
                const context = this;
                if (!inThrottle) {
                    func.apply(context, args);
                    inThrottle = true;
                    setTimeout(() => inThrottle = false, limit);
                }
            };
        },
        
        // Format numbers
        formatNumber(num, decimals = 0) {
            return new Intl.NumberFormat('hu-HU', {
                minimumFractionDigits: decimals,
                maximumFractionDigits: decimals
            }).format(num);
        },
        
        // Format dates
        formatDate(date, options = {}) {
            const defaultOptions = {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            };
            
            return new Intl.DateTimeFormat('hu-HU', { ...defaultOptions, ...options }).format(new Date(date));
        },
        
        // Get random color
        getRandomColor() {
            const colors = Object.values(GreenRec.config.chartColors);
            return colors[Math.floor(Math.random() * colors.length)];
        },
        
        // Validate email
        isValidEmail(email) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            return emailRegex.test(email);
        },
        
        // Copy to clipboard
        async copyToClipboard(text) {
            try {
                await navigator.clipboard.writeText(text);
                GreenRec.showFlashMessage('Vágólapra másolva!', 'success');
            } catch (err) {
                console.error('Copy failed:', err);
                GreenRec.showFlashMessage('Másolás sikertelen', 'error');
            }
        },
        
        // Generate unique ID
        generateId(prefix = 'id') {
            return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        },
        
        // Smooth scroll to element
        scrollToElement(element, offset = 0) {
            const targetElement = typeof element === 'string' ? document.querySelector(element) : element;
            if (targetElement) {
                const targetPosition = targetElement.getBoundingClientRect().top + window.pageYOffset - offset;
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        },
        
        // Check if element is in viewport
        isInViewport(element) {
            const rect = element.getBoundingClientRect();
            return (
                rect.top >= 0 &&
                rect.left >= 0 &&
                rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                rect.right <= (window.innerWidth || document.documentElement.clientWidth)
            );
        }
    },
    
    // Advanced features
    advanced: {
        // Auto-save functionality
        setupAutoSave() {
            let autoSaveTimer;
            
            const autoSave = GreenRec.utils.debounce(() => {
                const unsavedRatings = Object.keys(GreenRec.state.currentRatings);
                if (unsavedRatings.length > 0) {
                    console.log('💾 Auto-saving ratings...');
                    // Implementation would save to server
                }
            }, 5000);
            
            // Trigger auto-save on rating changes
            document.addEventListener('ratingChanged', autoSave);
        },
        
        // Keyboard shortcuts
        setupKeyboardShortcuts() {
            document.addEventListener('keydown', (e) => {
                // Ctrl/Cmd + K for search focus
                if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                    e.preventDefault();
                    const searchInput = document.querySelector('.search-input');
                    if (searchInput) {
                        searchInput.focus();
                        searchInput.select();
                    }
                }
                
                // Ctrl/Cmd + Enter for next round
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                    const nextRoundBtn = document.querySelector('.next-round-btn');
                    if (nextRoundBtn && !nextRoundBtn.disabled) {
                        nextRoundBtn.click();
                    }
                }
                
                // Number keys 1-5 for rating when recipe card is focused
                if (/^[1-5]$/.test(e.key)) {
                    const focusedCard = document.querySelector('.recipe-card:focus-within');
                    if (focusedCard) {
                        const stars = focusedCard.querySelectorAll('.star');
                        const rating = parseInt(e.key);
                        if (stars[rating - 1]) {
                            stars[rating - 1].click();
                        }
                    }
                }
            });
        },
        
        // Offline support
        setupOfflineSupport() {
            window.addEventListener('online', () => {
                GreenRec.showFlashMessage('Kapcsolat helyreállt', 'success');
            });
            
            window.addEventListener('offline', () => {
                GreenRec.showFlashMessage('Nincs internetkapcsolat - Offline módban működik', 'warning');
            });
        },
        
        // Export functionality
        async exportData(format = 'json') {
            try {
                const response = await fetch('/api/export-data', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ format: format })
                });
                
                if (!response.ok) {
                    throw new Error('Export failed');
                }
                
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `greenrec_data_${new Date().toISOString().split('T')[0]}.${format}`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                GreenRec.showFlashMessage('Adatok exportálva!', 'success');
            } catch (error) {
                console.error('Export error:', error);
                GreenRec.showFlashMessage('Export sikertelen', 'error');
            }
        }
    }
};

// CSS animations for JavaScript
const additionalStyles = `
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
    
    .lazy {
        opacity: 0;
        transition: opacity 0.3s;
    }
    
    .lazy.loaded {
        opacity: 1;
    }
    
    .tooltip {
        animation: tooltipFadeIn 0.2s ease-out;
    }
    
    @keyframes tooltipFadeIn {
        from {
            opacity: 0;
            transform: translateY(5px);
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

// Initialize application when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => GreenRec.init());
} else {
    GreenRec.init();
}

// Expose GreenRec globally for debugging
window.GreenRec = GreenRec;

// Service Worker registration (if available)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', async () => {
        try {
            const registration = await navigator.serviceWorker.register('/static/sw.js');
            console.log('✅ Service Worker registered:', registration);
        } catch (error) {
            console.log('❌ Service Worker registration failed:', error);
        }
    });
}

// Error boundary for global error handling
window.addEventListener('error', (event) => {
    console.error('❌ Global error:', event.error);
    
    // Don't overwhelm user with too many error messages
    if (!GreenRec.state.hasShownGlobalError) {
        GreenRec.showFlashMessage('Váratlan hiba történt. Kérjük, frissítse az oldalt.', 'error');
        GreenRec.state.hasShownGlobalError = true;
        
        // Reset flag after 30 seconds
        setTimeout(() => {
            GreenRec.state.hasShownGlobalError = false;
        }, 30000);
    }
});

// Unhandled promise rejection handling
window.addEventListener('unhandledrejection', (event) => {
    console.error('❌ Unhandled promise rejection:', event.reason);
    event.preventDefault(); // Prevent default browser behavior
    
    if (!GreenRec.state.hasShownPromiseError) {
        GreenRec.showFlashMessage('Hálózati hiba történt. Kérjük, próbálja újra.', 'error');
        GreenRec.state.hasShownPromiseError = true;
        
        setTimeout(() => {
            GreenRec.state.hasShownPromiseError = false;
        }, 30000);
    }
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GreenRec;
}
