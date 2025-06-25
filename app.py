@app.route('/status')
def status():
    """Rendszer status JSON"""
    ensure_initialized()
    
    try:
        status_info = {
            'receptek_betoltve': recipes_df is not None,
            'receptek_szama': len(recipes_df) if recipes_df is not None else 0,
            'viselkedesi_adatok': len(behavior_data),
            'ertekelesek_szama': len(ratings_data),
            'algoritmus_kesz': tfidf_matrix is not None,
            'initialization_done': initialization_done,
            'utolso_frissites': datetime.now().isoformat(),
            'deployment': 'enhanced-final-with-learning',
            'features': {
                'dynamic_learning': True,
                'inverse_esi': True,
                'composite_scoring': True,
                'personalized_recommendations': True,
                'multi_round_testing': True
            },
            'debug_messages_count': len(load_debug_messages),
            'debug_info': {
                'working_directory': os.getcwd(),
                'files_in_directory': os.listdir(os.getcwd()) if os.path.exists(os.getcwd()) else 'N/A',
                'recipes_df_columns': list(recipes_df.columns) if recipes_df is not None else 'N/A',
                'tfidf_shape': str(tfidf_matrix.shape) if tfidf_matrix is not None else 'N/A',
                'json_file_exists': any(os.path.exists(f) for f in ['greenrec_dataset.json', 'data.json', 'recipes.json']),
                'last_debug_messages': load_debug_messages[-5:] if load_debug_messages else [],
                'composite_score_range': f"{recipes_df['composite_score'].min():.1f}-{recipes_df['composite_score'].max():.1f}" if recipes_df is not None else 'N/A'
            }
        }
        
        return jsonify(status_info)
        
    except Exception as e:
        debug_log(f"❌ Status hiba: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'initialized': initialization_done
    })

# ✅ HTML TEMPLATE-EK JAVÍTVA (UI fejlesztések)

HOME_TEMPLATE = """
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GreenRec - Fenntartható Receptajánló</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .recipe-card { margin-bottom: 20px; }
        .group-info { background: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 20px; }
        .scores { margin-top: 10px; }
        .score-badge { display: inline-block; margin-right: 10px; padding: 5px 10px; border-radius: 15px; font-size: 14px; }
        .score-high { background-color: #d4edda; color: #155724; }
        .score-medium { background-color: #fff3cd; color: #856404; }
        .score-low { background-color: #f8d7da; color: #721c24; }
        .explanation { background: #e7f3ff; padding: 10px; margin-top: 10px; border-left: 4px solid #007bff; border-radius: 5px; }
        
        .rating-widget { margin-top: 15px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; background: #f9f9f9; }
        .star-rating { margin: 10px 0; }
        .star { font-size: 24px; color: #ddd; cursor: pointer; transition: color 0.2s; margin-right: 2px; }
        .star:hover, .star.selected { color: #ffd700; }
        .star.locked { color: #ffd700; cursor: default; }
        .rating-comment { width: 100%; margin-top: 10px; }
        .rating-submit { margin-top: 10px; }
        .rating-success { color: #28a745; margin-top: 10px; display: none; }
        
        .round-info { background: #e3f2fd; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #2196f3; }
        .next-round-btn { background: #4caf50; color: white; border: none; padding: 10px 20px; border-radius: 5px; margin-top: 15px; }
        .next-round-btn:disabled { background: #cccccc; cursor: not-allowed; }
        
        .icon-legend { background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .icon-item { display: inline-block; margin-right: 20px; margin-bottom: 5px; }
        
        .composite-score { font-weight: bold; color: #2e7d32; }
    </style>
</head>
<body>
    <div class="container mt-4">
        <h1 class="text-center mb-4">🍃 GreenRec - Fenntartható Receptajánló</h1>
        
        <!-- ✅ PIKTOGRAMM MAGYARÁZAT -->
        <div class="icon-legend">
            <h6><strong>📊 Pontszám magyarázat:</strong></h6>
            <span class="icon-item"><strong>🌍</strong> Környezeti hatás</span>
            <span class="icon-item"><strong>💚</strong> Egészségügyi érték</span>
            <span class="icon-item"><strong>👤</strong> Népszerűség</span>
            <span class="icon-item"><strong>⭐</strong> Kompozit pontszám</span>
        </div>
        
        <div class="group-info">
            <strong>Test csoport:</strong> {{ group.title() }} | <strong>User ID:</strong> {{ user_id[:8] }}...
            <div class="mt-2">
                <a href="/analytics" class="btn btn-sm btn-outline-info">📊 Analytics</a>
                <a href="/analytics/metrics" class="btn btn-sm btn-outline-success">📈 Metrikák</a>
                <a href="/status" class="btn btn-sm btn-outline-secondary">🔧 Status</a>
            </div>
        </div>
        
        {% if not is_search_results %}
        <!-- ✅ TANULÁSI KÖR INFORMÁCIÓ -->
        <div class="round-info">
            <h5>🎯 {{ current_round }}. Tanulási Kör</h5>
            {% if current_round == 1 %}
            <p>Fedezze fel a recepteket és értékelje őket! Az értékelései alapján a következő körben személyre szabott ajánlásokat kap.</p>
            {% else %}
            <p>Személyre szabott ajánlások az előző {{ current_round - 1 }} kör értékelései alapján.</p>
            {% endif %}
            
            <div id="round-progress">
                <small>Értékelések ebben a körben: <span id="ratings-count">0</span>/6</small>
                <div class="progress mt-2">
                    <div class="progress-bar" id="progress-bar" style="width: 0%"></div>
                </div>
            </div>
            
            <button class="next-round-btn" id="next-round-btn" onclick="advanceToNextRound()" disabled>
                🚀 Következő kör indítása
            </button>
        </div>
        {% endif %}
        
        {% if not is_search_results %}
        <form method="POST" action="/search" class="mb-4">
            <div class="input-group">
                <input type="text" name="query" class="form-control" 
                       placeholder="Keresés összetevők alapján (pl. 'paradicsom, hagyma')" 
                       value="{{ query or '' }}">
                <button class="btn btn-primary" type="submit">🔍 Keresés</button>
            </div>
        </form>
        {% else %}
        <div class="alert alert-info">
            <strong>Keresési eredmények:</strong> "{{ query }}"
            <a href="/" class="btn btn-outline-primary btn-sm float-end">🏠 Vissza a főoldalra</a>
        </div>
        {% endif %}
        
        {% if message %}
        <div class="alert alert-warning">{{ message }}</div>
        {% endif %}
        
        <div class="row">
            {% for recipe in recipes %}
            <div class="col-md-6 col-lg-4">
                <div class="card recipe-card">
                    {% if recipe.images %}
                    <img src="{{ recipe.images }}" class="card-img-top" style="height: 200px; object-fit: cover;">
                    {% endif %}
                    
                    <div class="card-body">
                        <h5 class="card-title">{{ recipe.title }}</h5>
                        <p class="card-text">
                            <strong>Kategória:</strong> {{ recipe.category or 'Egyéb' }}<br>
                            <strong>Összetevők:</strong> {{ recipe.ingredients[:100] }}{% if recipe.ingredients|length > 100 %}...{% endif %}
                        </p>
                        
                        <!-- ✅ KOMPOZIT PONTSZÁM MINDIG LÁTHATÓ -->
                        <div class="mb-2">
                            <span class="composite-score">⭐ Összpontszám: {{ "%.0f"|format(recipe.composite_score) }}/100</span>
                        </div>
                        
                        {% if group in ['scores_visible', 'explanations'] %}
                        <div class="scores">
                            <!-- ✅ JAVÍTOTT ESI MEGJELENÍTÉS (inverz) -->
                            {% set esi_class = 'score-high' if recipe.ESI_final > 70 else ('score-medium' if recipe.ESI_final > 40 else 'score-low') %}
                            {% set hsi_class = 'score-high' if recipe.HSI > 70 else ('score-medium' if recipe.HSI > 40 else 'score-low') %}
                            {% set ppi_class = 'score-high' if recipe.PPI > 70 else ('score-medium' if recipe.PPI > 40 else 'score-low') %}
                            
                            <span class="score-badge {{ esi_class }}">🌍 {{ "%.0f"|format(recipe.ESI_final) }}</span>
                            <span class="score-badge {{ hsi_class }}">💚 {{ "%.0f"|format(recipe.HSI) }}</span>
                            <span class="score-badge {{ ppi_class }}">👤 {{ "%.0f"|format(recipe.PPI) }}</span>
                        </div>
                        {% endif %}
                        
                        {% if group == 'explanations' %}
                        <div class="explanation">
                            <strong>💡 Miért ajánljuk?</strong><br>
                            {% if recipe.ESI_final > 70 %}🌍 Környezetbarát választás<br>{% endif %}
                            {% if recipe.HSI > 70 %}💚 Egészséges összetevők<br>{% endif %}
                            {% if recipe.PPI > 70 %}👤 Népszerű recept<br>{% endif %}
                            {% if recipe.recommendation_reason %}🎯 {{ recipe.recommendation_reason }}<br>{% endif %}
                            ⭐ Magas kompozit pontszám ({{ "%.0f"|format(recipe.composite_score) }}/100)
                        </div>
                        {% endif %}
                        
                        <!-- ✅ JAVÍTOTT RATING WIDGET -->
                        <div class="rating-widget">
                            <h6>Értékelje ezt a receptet:</h6>
                            <div class="star-rating" data-recipe-id="{{ recipe.id }}">
                                <span class="star" data-rating="1">⭐</span>
                                <span class="star" data-rating="2">⭐</span>
                                <span class="star" data-rating="3">⭐</span>
                                <span class="star" data-rating="4">⭐</span>
                                <span class="star" data-rating="5">⭐</span>
                            </div>
                            <textarea class="form-control rating-comment" rows="2" 
                                    placeholder="Opcionális megjegyzés..." 
                                    data-recipe-id="{{ recipe.id }}"></textarea>
                            <button class="btn btn-sm btn-success rating-submit" 
                                    onclick="submitRating({{ recipe.id }})">
                                Értékelés küldése
                            </button>
                            <div class="rating-success" data-recipe-id="{{ recipe.id }}">
                                ✅ Köszönjük az értékelést!
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    
    <script>
        let currentRatings = {};
        let ratingsInCurrentRound = 0;
        
        document.addEventListener('DOMContentLoaded', function() {
            initializeRatingWidgets();
            updateRoundProgress();
        });
        
        function initializeRatingWidgets() {
            document.querySelectorAll('.star-rating').forEach(ratingWidget => {
                const recipeId = ratingWidget.dataset.recipeId;
                const stars = ratingWidget.querySelectorAll('.star');
                
                stars.forEach(star => {
                    star.addEventListener('click', function() {
                        const rating = parseInt(this.dataset.rating);
                        currentRatings[recipeId] = rating;
                        highlightStars(recipeId, rating);
                    });
                    
                    star.addEventListener('mouseover', function() {
                        const rating = parseInt(this.dataset.rating);
                        if (!star.classList.contains('locked')) {
                            highlightStars(recipeId, rating, true);
                        }
                    });
                });
                
                ratingWidget.addEventListener('mouseleave', function() {
                    const savedRating = currentRatings[recipeId] || 0;
                    highlightStars(recipeId, savedRating);
                });
            });
        }
        
        function highlightStars(recipeId, rating, isHover = false) {
            const ratingWidget = document.querySelector(`.star-rating[data-recipe-id="${recipeId}"]`);
            const stars = ratingWidget.querySelectorAll('.star');
            
            stars.forEach((star, index) => {
                star.classList.remove('selected');
                if (index < rating) {
                    star.classList.add('selected');
                }
            });
        }
        
        function lockStars(recipeId, rating) {
            const ratingWidget = document.querySelector(`.star-rating[data-recipe-id="${recipeId}"]`);
            const stars = ratingWidget.querySelectorAll('.star');
            
            stars.forEach((star, index) => {
                star.classList.add('locked');
                star.style.pointerEvents = 'none';
                if (index < rating) {
                    star.classList.add('selected');
                }
            });
        }
        
        function submitRating(recipeId) {
            const rating = currentRatings[recipeId];
            if (!rating) {
                alert('Kérem válasszon értékelést (1-5 csillag)!');
                return;
            }
            
            const commentElement = document.querySelector(`textarea[data-recipe-id="${recipeId}"]`);
            const comment = commentElement ? commentElement.value : '';
            
            fetch('/api/rate_recipe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: '{{ user_id }}',
                    recipe_id: recipeId,
                    rating: rating,
                    comment: comment
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Siker üzenet
                    const successElement = document.querySelector(`div[data-recipe-id="${recipeId}"].rating-success`);
                    if (successElement) {
                        successElement.style.display = 'block';
                    }
                    
                    // Submit gomb letiltása
                    const submitButton = document.querySelector(`button[onclick="submitRating(${recipeId})"]`);
                    if (submitButton) {
                        submitButton.disabled = true;
                        submitButton.textContent = 'Értékelve ✓';
                    }
                    
                    // ✅ CSILLAGOK LEZÁRÁSA
                    lockStars(recipeId, rating);
                    
                    // ✅ PROGRESS FRISSÍTÉSE
                    ratingsInCurrentRound = data.ratings_in_round || 0;
                    updateRoundProgress();
                    
                    // ✅ KÖVETKEZŐ KÖR GOMB AKTIVÁLÁSA
                    if (data.can_advance_round) {
                        document.getElementById('next-round-btn').disabled = false;
                    }
                } else {
                    alert('Hiba: ' + (data.error || 'Ismeretlen hiba'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Hiba történt az értékelés küldésekor.');
            });
        }
        
        function updateRoundProgress() {
            const ratingsCountElement = document.getElementById('ratings-count');
            const progressBarElement = document.getElementById('progress-bar');
            
            if (ratingsCountElement) {
                ratingsCountElement.textContent = ratingsInCurrentRound;
            }
            
            if (progressBarElement) {
                const percentage = (ratingsInCurrentRound / 6) * 100;
                progressBarElement.style.width = percentage + '%';
            }
        }
        
        function advanceToNextRound() {
            fetch('/next_round', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    alert(data.message);
                    window.location.reload(); // Oldal újratöltése az új körrel
                } else {
                    alert('Hiba: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Hiba történt a következő kör indításakor.');
            });
        }
    </script>
</body>
</html>
"""

METRICS_TEMPLATE = """
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GreenRec - Precision/Recall/F1 Metrikák + Tanulási Görbék</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container mt-4">
        <h1 class="text-center mb-4">📈 Recommendation Metrics + Learning Curves</h1>
        
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5>📊 Általános Statisztikák</h5>
                        <div class="row">
                            <div class="col-md-4">
                                <strong>Összes értékelés:</strong> {{ total_ratings }}
                            </div>
                            <div class="col-md-4">
                                <strong>Értékelő felhasználók:</strong> {{ total_users_with_ratings }}
                            </div>
                            <div class="col-md-4">
                                <strong>Átlagos értékelés:</strong> {{ "%.2f"|format(avg_rating) }}/5
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- ✅ TANULÁSI GÖRBÉK VIZUALIZÁCIÓ -->
        {% if metrics_control and metrics_scores and metrics_explanations %}
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-info text-white">
                        <h5>📈 Tanulási Görbék (F1-Score fejlődése körönként)</h5>
                    </div>
                    <div class="card-body">
                        <canvas id="learningCurveChart" width="400" height="200"></canvas>
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
        
        <div class="row">
            <!-- A Csoport -->
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header bg-secondary text-white">
                        <h5>🔍 A Csoport (Control)</h5>
                    </div>
                    <div class="card-body">
                        {% if metrics_control %}
                        <div class="mb-3">
                            <strong>Precision@5:</strong> {{ "%.3f"|format(metrics_control.precision) }}<br>
                            <strong>Recall@5:</strong> {{ "%.3f"|format(metrics_control.recall) }}<br>
                            <strong>F1-Score@5:</strong> {{ "%.3f"|format(metrics_control.f1_score) }}
                        </div>
                        <hr>
                        <small>
                            <strong>Felhasználók:</strong> {{ metrics_control.num_users }}<br>
                            <strong>Összes értékelés:</strong> {{ metrics_control.total_ratings }}<br>
                            <strong>Max körök:</strong> {{ metrics_control.max_rounds }}<br>
                            <strong>Átlag/fő:</strong> {{ "%.1f"|format(metrics_control.avg_ratings_per_user) }}
                        </small>
                        {% else %}
                        <div class="text-muted">
                            <p>Nincs elegendő adat a metrikák számításához.</p>
                            <small>Minimum 3 értékelés szükséges felhasználónként.</small>
                        </div>
                        {% endif %}
                    </div>
                </div>
            </div>
            
            <!-- B Csoport -->
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header bg-warning text-dark">
                        <h5>📊 B Csoport (Scores)</h5>
                    </div>
                    <div class="card-body">
                        {% if metrics_scores %}
                        <div class="mb-3">
                            <strong>Precision@5:</strong> {{ "%.3f"|format(metrics_scores.precision) }}<br>
                            <strong>Recall@5:</strong> {{ "%.3f"|format(metrics_scores.recall) }}<br>
                            <strong>F1-Score@5:</strong> {{ "%.3f"|format(metrics_scores.f1_score) }}
                        </div>
                        <hr>
                        <small>
                            <strong>Felhasználók:</strong> {{ metrics_scores.num_users }}<br>
                            <strong>Összes értékelés:</strong> {{ metrics_scores.total_ratings }}<br>
                            <strong>Max körök:</strong> {{ metrics_scores.max_rounds }}<br>
                            <strong>Átlag/fő:</strong> {{ "%.1f"|format(metrics_scores.avg_ratings_per_user) }}
                        </small>
                        {% else %}
                        <div class="text-muted">
                            <p>Nincs elegendő adat a metrikák számításához.</p>
                            <small>Minimum 3 értékelés szükséges felhasználónként.</small>
                        </div>
                        {% endif %}
                    </div>
                </div>
            </div>
            
            <!-- C Csoport -->
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header bg-success text-white">
                        <h5>🤖 C Csoport (XAI)</h5>
                    </div>
                    <div class="card-body">
                        {% if metrics_explanations %}
                        <div class="mb-3">
                            <strong>Precision@5:</strong> {{ "%.3f"|format(metrics_explanations.precision) }}<br>
                            <strong>Recall@5:</strong> {{ "%.3f"|format(metrics_explanations.recall) }}<br>
                            <strong>F1-Score@5:</strong> {{ "%.3f"|format(metrics_explanations.f1_score) }}
                        </div>
                        <hr>
                        <small>
                            <strong>Felhasználók:</strong> {{ metrics_explanations.num_users }}<br>
                            <strong>Összes értékelés:</strong> {{ metrics_explanations.total_ratings }}<br>
                            <strong>Max körök:</strong> {{ metrics_explanations.max_rounds }}<br>
                            <strong>Átlag/fő:</strong> {{ "%.1f"|format(metrics_explanations.avg_ratings_per_user) }}
                        </small>
                        {% else %}
                        <div class="text-muted">
                            <p>Nincs elegendő adat a metrikák számításához.</p>
                            <small>Minimum 3 értékelés szükséges felhasználónként.</small>
                        </div>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
        
        <div class="text-center mt-4">
            <a href="/" class="btn btn-primary">🏠 Vissza a főoldalra</a>
            <a href="/analytics" class="btn btn-outline-info">📊 Általános Analytics</a>
            <button onclick="location.reload()" class="btn btn-outline-secondary">🔄 Frissítés</button>
        </div>
    </div>
    
    {% if metrics_control and metrics_scores and metrics_explanations %}
    <script>
        // ✅ TANULÁSI GÖRBE CHART
        const ctx = document.getElementById('learningCurveChart').getContext('2d');
        
        // Adatok előkészítése
        const learningData = {
            control: {{ metrics_control.learning_curve | tojson }},
            scores: {{ metrics_scores.learning_curve | tojson }},
            explanations: {{ metrics_explanations.learning_curve | tojson }}
        };
        
        // Körök meghatározása
        const maxRounds = Math.max(
            {{ metrics_control.max_rounds }},
            {{ metrics_scores.max_rounds }},
            {{ metrics_explanations.max_rounds }}
        );
        
        const rounds = Array.from({length: maxRounds}, (_, i) => i + 1);
        
        // Dataset létrehozása
        const datasets = [
            {
                label: 'A Csoport (Control)',
                data: rounds.map(r => learningData.control[`round_${r}`] || null),
                borderColor: '#6c757d',
                backgroundColor: '#6c757d',
                fill: false
            },
            {
                label: 'B Csoport (Scores)',
                data: rounds.map(r => learningData.scores[`round_${r}`] || null),
                borderColor: '#ffc107',
                backgroundColor: '#ffc107',
                fill: false
            },
            {
                label: 'C Csoport (XAI)',
                data: rounds.map(r => learningData.explanations[`round_${r}`] || null),
                borderColor: '#28a745',
                backgroundColor: '#28a745',
                fill: false
            }
        ];
        
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: rounds,
                datasets: datasets
            },
            options: {
                responsive: true,
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Tanulási Kör'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'F1-Score (proxy)'
                        },
                        min: 0,
                        max: 1
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Tanulási Görbék - F1-Score fejlődése körönként'
                    },
                    legend: {
                        display: true
                    }
                }
            }
        });
    </script>
    {% endif %}
</body>
</html>
"""

ANALYTICS_TEMPLATE = """
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GreenRec - Analytics Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-4">
        <h1 class="text-center mb-4">📊 Analytics Dashboard</h1>
        
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body text-center">
                        <h3 class="text-primary">{{ total_behaviors }}</h3>
                        <p>Összes Interakció</p>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body text-center">
                        <h3 class="text-success">{{ total_ratings }}</h3>
                        <p>Összes Értékelés</p>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header bg-secondary text-white">
                        <h5>A Csoport (Control)</h5>
                    </div>
                    <div class="card-body">
                        <p><strong>Felhasználók:</strong> {{ group_stats.control.total_users }}</p>
                        <p><strong>Interakciók:</strong> {{ group_stats.control.total_interactions }}</p>
                        <p><strong>Értékelések:</strong> {{ group_stats.control.total_ratings }}</p>
                        <p><strong>Átlag értékelés:</strong> {{ "%.2f"|format(group_stats.control.avg_rating) }}/5</p>
                        <p><strong>Átlag kör:</strong> {{ "%.1f"|format(group_stats.control.avg_round) }}</p>
                    </div>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header bg-warning text-dark">
                        <h5>B Csoport (Scores)</h5>
                    </div>
                    <div class="card-body">
                        <p><strong>Felhasználók:</strong> {{ group_stats.scores_visible.total_users }}</p>
                        <p><strong>Interakciók:</strong> {{ group_stats.scores_visible.total_interactions }}</p>
                        <p><strong>Értékelések:</strong> {{ group_stats.scores_visible.total_ratings }}</p>
                        <p><strong>Átlag értékelés:</strong> {{ "%.2f"|format(group_stats.scores_visible.avg_rating) }}/5</p>
                        <p><strong>Átlag kör:</strong> {{ "%.1f"|format(group_stats.scores_visible.avg_round) }}</p>
                    </div>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header bg-success text-white">
                        <h5>C Csoport (XAI)</h5>
                    </div>
                    <div class="card-body">
                        <p><strong>Felhasználók:</strong> {{ group_stats.explanations.total_users }}</p>
                        <p><strong>Interakciók:</strong> {{ group_stats.explanations.total_interactions }}</p>
                        <p><strong>Értékelések:</strong> {{ group_stats.explanations.total_ratings }}</p>
                        <p><strong>Átlag értékelés:</strong> {{ "%.2f"|format(group_stats.explanations.avg_rating) }}/5</p>
                        <p><strong>Átlag kör:</strong> {{ "%.1f"|format(group_stats.explanations.avg_round) }}</p>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-info text-white">
                        <h5>🔍 A/B/C Teszt Eredmények Összefoglalás</h5>
                    </div>
                    <div class="card-body">
                        <h6>📈 Tanulási Sebesség (Átlag kör/felhasználó):</h6>
                        <div class="progress-group mb-3">
                            <div class="d-flex justify-content-between">
                                <span>A Csoport (Control)</span>
                                <span>{{ "%.1f"|format(group_stats.control.avg_round) }} kör</span>
                            </div>
                            <div class="progress">
                                <div class="progress-bar bg-secondary" 
                                     style="width: {{ (group_stats.control.avg_round * 20)|round(1) }}%"></div>
                            </div>
                        </div>
                        
                        <div class="progress-group mb-3">
                            <div class="d-flex justify-content-between">
                                <span>B Csoport (Scores)</span>
                                <span>{{ "%.1f"|format(group_stats.scores_visible.avg_round) }} kör</span>
                            </div>
                            <div class="progress">
                                <div class="progress-bar bg-warning" 
                                     style="width: {{ (group_stats.scores_visible.avg_round * 20)|round(1) }}%"></div>
                            </div>
                        </div>
                        
                        <div class="progress-group mb-3">
                            <div class="d-flex justify-content-between">
                                <span>C Csoport (XAI)</span>
                                <span>{{ "%.1f"|format(group_stats.explanations.avg_round) }} kör</span>
                            </div>
                            <div class="progress">
                                <div class="progress-bar bg-success" 
                                     style="width: {{ (group_stats.explanations.avg_round * 20)|round(1) }}%"></div>
                            </div>
                        </div>
                        
                        <hr>
                        <h6>⭐ Elégedettség (Átlag értékelés):</h6>
                        <p>
                            <span class="badge bg-secondary">A: {{ "%.2f"|format(group_stats.control.avg_rating) }}/5</span>
                            <span class="badge bg-warning text-dark">B: {{ "%.2f"|format(group_stats.scores_visible.avg_rating) }}/5</span>
                            <span class="badge bg-success">C: {{ "%.2f"|format(group_stats.explanations.avg_rating) }}/5</span>
                        </p>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="text-center mt-4">
            <a href="/" class="btn btn-primary">🏠 Vissza a főoldalra</a>
            <a href="/analytics/metrics" class="btn btn-success">📈 Precision/Recall Metrikák</a>
            <button onclick="location.reload()" class="btn btn-outline-secondary">🔄 Frissítés</button>
        </div>
    </div>
</body>
</html>
"""

# Heroku compatibility - inicializálás az első request-nél
@app.before_request
def ensure_initialization():
    """Biztosítja az inicializálást az első request előtt"""
    if not initialization_done:
        initialize_data()

# Heroku compatibility
if __name__ == '__main__':
    debug_log("🚀 GreenRec Enhanced alkalmazás indítása...")
    debug_log("✅ Újdonságok: Dinamikus tanulás, Inverz ESI, Kompozit scoring, Többkörös teszt")
    
    # Próbáljuk meg inicializálni az adatokat startup-kor
    initialize_data()
    
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    debug_log(f"🌐 Alkalmazás indítása - Port: {port}")
    debug_log(f"🔧 Debug mode: {debug_mode}")
    debug_log(f"📊 Inicializálás státusz: {initialization_done}")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)# app.py - GreenRec Enhanced Final Version
"""
GreenRec - Fenntartható Receptajánló Rendszer
✅ Dinamikus tanulási flow (többkörös ajánlás)
✅ Inverz ESI normalizálás (100-ESI)
✅ Helyes kompozit pontszám (ESI*0.4+HSI*0.4+PPI*0.2)
✅ Javított UI (piktogramok, csillag feedback)
✅ Content-based learning az értékelések alapján
"""

from flask import Flask, render_template_string, request, session, jsonify
import json
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import precision_score, recall_score, f1_score
import hashlib
from datetime import datetime
import uuid
import random
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', "greenrec_secret_key_2024")

# Globális változók
recipes_df = None
tfidf_matrix = None
vectorizer = None
behavior_data = []
ratings_data = []
load_debug_messages = []
initialization_done = False

def debug_log(message):
    """Debug üzenetek naplózása"""
    load_debug_messages.append(f"{datetime.now().isoformat()}: {message}")
    print(f"DEBUG: {message}")

def initialize_data():
    """Adatok inicializálása"""
    global recipes_df, tfidf_matrix, vectorizer, initialization_done
    
    if initialization_done:
        return True
    
    try:
        debug_log("🔄 Adatok inicializálása...")
        
        # JSON fájl keresése
        json_file = None
        possible_files = ['greenrec_dataset.json', 'data.json', 'recipes.json']
        
        for filename in possible_files:
            if os.path.exists(filename):
                json_file = filename
                break
        
        if not json_file:
            debug_log("❌ Nem található JSON fájl")
            return False
        
        debug_log(f"📄 JSON fájl található: {json_file}")
        
        # JSON betöltés
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Recipes list kinyerése
        if isinstance(data, dict):
            recipes_list = data.get('recipes', data.get('data', []))
        elif isinstance(data, list):
            recipes_list = data
        else:
            recipes_list = []
        
        if not recipes_list:
            debug_log("❌ Üres receptlista")
            return False
        
        debug_log(f"📊 Receptek száma: {len(recipes_list)}")
        
        # DataFrame létrehozás
        recipes_df = pd.DataFrame(recipes_list)
        
        # ID normalizálás
        if 'recipeid' in recipes_df.columns:
            recipes_df['id'] = recipes_df['recipeid']
        elif 'id' not in recipes_df.columns:
            recipes_df['id'] = range(1, len(recipes_df) + 1)
        
        # Kötelező oszlopok ellenőrzése
        required_cols = ['title', 'ingredients']
        for col in required_cols:
            if col not in recipes_df.columns:
                recipes_df[col] = f"Hiányzó {col}"
        
        # ✅ JAVÍTOTT ESI/HSI/PPI KEZELÉS
        # ESI: Inverz normalizálás (magasabb ESI = rosszabb környezetterhelés)
        if 'ESI' in recipes_df.columns:
            # 1. ESI normalizálás 0-100 közé
            esi_min = recipes_df['ESI'].min()
            esi_max = recipes_df['ESI'].max()
            recipes_df['ESI_normalized'] = 100 * (recipes_df['ESI'] - esi_min) / (esi_max - esi_min)
            # 2. Inverz ESI (100 - normalizált, mivel magasabb ESI = rosszabb)
            recipes_df['ESI_final'] = 100 - recipes_df['ESI_normalized']
            debug_log(f"✅ ESI inverz normalizálás: {esi_min:.1f}-{esi_max:.1f} → 0-100 (inverz)")
        else:
            recipes_df['ESI'] = random.randint(30, 90)
            recipes_df['ESI_final'] = 100 - recipes_df['ESI']
        
        # HSI és PPI: Megtartjuk eredeti értékeket (már 0-100 között, magasabb = jobb)
        for col in ['HSI', 'PPI']:
            if col not in recipes_df.columns:
                recipes_df[col] = random.randint(30, 90)
        
        # ✅ KOMPOZIT PONTSZÁM SZÁMÍTÁSA
        # Képlet: ESI_final*0.4 + HSI*0.4 + PPI*0.2
        recipes_df['composite_score'] = (
            recipes_df['ESI_final'] * 0.4 + 
            recipes_df['HSI'] * 0.4 + 
            recipes_df['PPI'] * 0.2
        )
        
        debug_log(f"✅ Kompozit pontszám: min={recipes_df['composite_score'].min():.1f}, max={recipes_df['composite_score'].max():.1f}")
        
        # TF-IDF vektorizálás
        try:
            vectorizer = TfidfVectorizer(stop_words='english', max_features=1000, min_df=1)
            ingredients_text = recipes_df['ingredients'].fillna('').astype(str)
            tfidf_matrix = vectorizer.fit_transform(ingredients_text)
            debug_log(f"✅ TF-IDF matrix: {tfidf_matrix.shape}")
        except Exception as tfidf_error:
            debug_log(f"❌ TF-IDF hiba: {tfidf_error}")
            vectorizer = None
            tfidf_matrix = None
        
        initialization_done = True
        debug_log(f"✅ Inicializálás sikeres: {len(recipes_df)} recept")
        return True
        
    except Exception as e:
        debug_log(f"❌ Inicializálási hiba: {e}")
        return False

def ensure_initialized():
    """Biztosítja, hogy az adatok inicializálva legyenek"""
    if not initialization_done:
        initialize_data()

def get_user_id():
    """Egyedi felhasználói azonosító"""
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        session['recommendation_round'] = 1  # ✅ TANULÁSI KÖR TRACKING
        session['user_preferences'] = {}     # ✅ FELHASZNÁLÓI PREFERENCIÁK
    return session['user_id']

def get_user_group(user_id):
    """A/B/C csoport meghatározása"""
    hash_val = int(hashlib.md5(str(user_id).encode()).hexdigest(), 16)
    group_num = hash_val % 3
    return ['control', 'scores_visible', 'explanations'][group_num]

def log_behavior(user_id, action, data=None):
    """Viselkedési adatok naplózása"""
    try:
        behavior_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': str(user_id),
            'group': get_user_group(user_id),
            'action': action,
            'round': session.get('recommendation_round', 1),
            'data': data or {}
        }
        behavior_data.append(behavior_entry)
        
        # Memory management
        if len(behavior_data) > 10000:
            behavior_data[:5000] = []
    except Exception as e:
        debug_log(f"❌ Behavior logging hiba: {e}")

def save_rating(user_id, recipe_id, rating, comment=""):
    """Felhasználói értékelés mentése"""
    try:
        relevance = 1 if rating >= 4 else 0
        
        rating_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': str(user_id),
            'recipe_id': int(recipe_id),
            'rating': int(rating),
            'relevance': relevance,
            'comment': comment,
            'group': get_user_group(user_id),
            'round': session.get('recommendation_round', 1)
        }
        
        # Meglévő értékelés felülírása
        ratings_data[:] = [r for r in ratings_data if not (r['user_id'] == str(user_id) and r['recipe_id'] == int(recipe_id))]
        ratings_data.append(rating_entry)
        
        # ✅ FELHASZNÁLÓI PREFERENCIÁK FRISSÍTÉSE
        update_user_preferences(user_id, recipe_id, rating)
        
        # Viselkedési log
        log_behavior(user_id, 'rating_submitted', {
            'recipe_id': recipe_id,
            'rating': rating,
            'relevance': relevance
        })
        
        return rating_entry
    except Exception as e:
        debug_log(f"❌ Rating mentési hiba: {e}")
        return None

def update_user_preferences(user_id, recipe_id, rating):
    """✅ FELHASZNÁLÓI PREFERENCIÁK TANULÁSA"""
    try:
        if 'user_preferences' not in session:
            session['user_preferences'] = {}
        
        # Recept adatok lekérése
        recipe = recipes_df[recipes_df['id'] == int(recipe_id)]
        if recipe.empty:
            return
        
        recipe = recipe.iloc[0]
        
        # Preferenciák frissítése a rating alapján
        prefs = session['user_preferences']
        
        if rating >= 4:  # Pozitív értékelés
            # Kedvelt kategóriák
            category = recipe.get('category', 'Unknown')
            prefs.setdefault('liked_categories', []).append(category)
            
            # Kedvelt összetevők (első 3 szó)
            ingredients = str(recipe.get('ingredients', '')).split()[:3]
            prefs.setdefault('liked_ingredients', []).extend(ingredients)
            
            # ESI/HSI/PPI preferenciák
            prefs.setdefault('esi_scores', []).append(recipe.get('ESI_final', 50))
            prefs.setdefault('hsi_scores', []).append(recipe.get('HSI', 50))
            prefs.setdefault('ppi_scores', []).append(recipe.get('PPI', 50))
        
        # Session frissítés
        session['user_preferences'] = prefs
        session.modified = True
        
    except Exception as e:
        debug_log(f"❌ Preferencia frissítési hiba: {e}")

def get_personalized_recommendations(user_id, n=6):
    """✅ SZEMÉLYRE SZABOTT AJÁNLÁSOK GENERÁLÁSA"""
    ensure_initialized()
    
    if recipes_df is None:
        return []
    
    try:
        current_round = session.get('recommendation_round', 1)
        
        # 1. KÖR: Random receptek (baseline)
        if current_round == 1:
            debug_log(f"🎲 1. kör: Random ajánlások felhasználó {user_id[:8]}...")
            random_recipes = recipes_df.sample(n=min(n, len(recipes_df)))
            results = random_recipes.copy()
            results['similarity_score'] = 0.5
            results['recommendation_reason'] = 'Kezdeti felfedezés'
            return results.to_dict('records')
        
        # 2+ KÖR: Személyre szabott ajánlások
        prefs = session.get('user_preferences', {})
        
        if not prefs:
            # Fallback: random, ha nincs preferencia
            random_recipes = recipes_df.sample(n=min(n, len(recipes_df)))
            results = random_recipes.copy()
            results['similarity_score'] = 0.5
            results['recommendation_reason'] = 'Felfedezés (nincs korábbi adat)'
            return results.to_dict('records')
        
        debug_log(f"🎯 {current_round}. kör: Személyre szabott ajánlások...")
        
        # Pontszám számítás minden recepthez
        scores = []
        reasons = []
        
        for idx, recipe in recipes_df.iterrows():
            score = 0
            reason_parts = []
            
            # Kategória egyezés
            if 'liked_categories' in prefs:
                if recipe.get('category') in prefs['liked_categories']:
                    score += 30
                    reason_parts.append("kedvelt kategória")
            
            # Összetevő egyezés
            if 'liked_ingredients' in prefs:
                ingredients = str(recipe.get('ingredients', '')).lower()
                liked_ingredients = [ing.lower() for ing in prefs['liked_ingredients']]
                matches = sum(1 for ing in liked_ingredients if ing in ingredients)
                if matches > 0:
                    score += matches * 20
                    reason_parts.append(f"{matches} kedvelt összetevő")
            
            # ESI/HSI/PPI hasonlóság
            if 'esi_scores' in prefs and prefs['esi_scores']:
                avg_esi_pref = np.mean(prefs['esi_scores'])
                esi_similarity = 100 - abs(recipe.get('ESI_final', 50) - avg_esi_pref)
                score += esi_similarity * 0.3
                if esi_similarity > 70:
                    reason_parts.append("hasonló környezeti profil")
            
            if 'hsi_scores' in prefs and prefs['hsi_scores']:
                avg_hsi_pref = np.mean(prefs['hsi_scores'])
                hsi_similarity = 100 - abs(recipe.get('HSI', 50) - avg_hsi_pref)
                score += hsi_similarity * 0.3
                if hsi_similarity > 70:
                    reason_parts.append("hasonló egészségügyi profil")
            
            # Kompozit pontszám bonus
            score += recipe.get('composite_score', 50) * 0.2
            
            scores.append(score)
            reasons.append(", ".join(reason_parts) if reason_parts else "általános ajánlás")
        
        # Top N kiválasztása
        recipes_df_copy = recipes_df.copy()
        recipes_df_copy['personalization_score'] = scores
        recipes_df_copy['recommendation_reason'] = reasons
        
        # Randomizálás a top 20%-ból (hogy ne legyen teljesen determinisztikus)
        top_candidates = recipes_df_copy.nlargest(n*3, 'personalization_score')
        results = top_candidates.sample(n=min(n, len(top_candidates)))
        
        results['similarity_score'] = results['personalization_score'] / 100
        
        return results.to_dict('records')
        
    except Exception as e:
        debug_log(f"❌ Személyre szabott ajánlási hiba: {e}")
        # Fallback
        random_recipes = recipes_df.sample(n=min(n, len(recipes_df)))
        results = random_recipes.copy()
        results['similarity_score'] = 0.5
        results['recommendation_reason'] = 'Fallback ajánlás'
        return results.to_dict('records')

def search_recipes(query, top_n=10):
    """Content-based filtering keresés"""
    ensure_initialized()
    
    if recipes_df is None:
        return []
    
    try:
        if not query or tfidf_matrix is None:
            # Ha nincs query, személyre szabott ajánlások
            return get_personalized_recommendations(get_user_id(), top_n)
        
        # TF-IDF keresés
        query_vec = vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
        
        # Hibrid scoring: similarity + composite_score
        final_scores = similarities * 0.6 + (recipes_df['composite_score'] / 100) * 0.4
        
        # Top N receptek
        top_indices = final_scores.argsort()[-top_n:][::-1]
        results = recipes_df.iloc[top_indices].copy()
        results['similarity_score'] = similarities[top_indices]
        results['final_score'] = final_scores[top_indices]
        results['recommendation_reason'] = 'Keresés alapján'
        
        return results.to_dict('records')
        
    except Exception as e:
        debug_log(f"❌ Keresési hiba: {e}")
        return get_personalized_recommendations(get_user_id(), top_n)

def calculate_user_metrics(user_id, k=5):
    """Precision@K, Recall@K, F1@K számítása köronként"""
    try:
        user_ratings = [r for r in ratings_data if r['user_id'] == str(user_id)]
        
        if len(user_ratings) < 3:
            return None
            
        relevant_recipes = set([r['recipe_id'] for r in user_ratings if r['relevance'] == 1])
        
        if not relevant_recipes:
            return None
        
        # ✅ LEGUTÓBBI KÖR AJÁNLÁSAI (nem keresés alapján, hanem személyre szabott)
        # Ez egy egyszerűsítés - valójában a legutóbbi ajánlásokat kellene tárolni
        latest_recommendations = get_personalized_recommendations(user_id, k)
        recommended_ids = set([r['id'] for r in latest_recommendations])
        
        # Metrikák
        true_positives = len(recommended_ids.intersection(relevant_recipes))
        false_positives = len(recommended_ids - relevant_recipes)
        false_negatives = len(relevant_recipes - recommended_ids)
        
        precision = true_positives / len(recommended_ids) if len(recommended_ids) > 0 else 0
        recall = true_positives / len(relevant_recipes) if len(relevant_recipes) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        # ✅ KÖRÖNKÉNTI BONTÁS
        round_metrics = {}
        for round_num in range(1, max([r.get('round', 1) for r in user_ratings]) + 1):
            round_ratings = [r for r in user_ratings if r.get('round', 1) == round_num]
            if round_ratings:
                round_avg_rating = np.mean([r['rating'] for r in round_ratings])
                round_metrics[f'round_{round_num}_avg_rating'] = round_avg_rating
        
        return {
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'true_positives': true_positives,
            'false_positives': false_positives,
            'false_negatives': false_negatives,
            'num_ratings': len(user_ratings),
            'num_relevant': len(relevant_recipes),
            'round_metrics': round_metrics,
            'current_round': max([r.get('round', 1) for r in user_ratings])
        }
        
    except Exception as e:
        debug_log(f"❌ User metrics hiba: {e}")
        return None

def calculate_group_metrics(group=None, k=5):
    """Csoport átlagos metrikák"""
    try:
        user_metrics = []
        user_ids = list(set([r['user_id'] for r in ratings_data]))
        
        for user_id in user_ids:
            if group and get_user_group(user_id) != group:
                continue
                
            metrics = calculate_user_metrics(user_id, k)
            if metrics:
                user_metrics.append(metrics)
        
        if not user_metrics:
            return None
        
        # ✅ TANULÁSI GÖRBE SZÁMÍTÁS
        learning_curve = {}
        max_rounds = max([m.get('current_round', 1) for m in user_metrics])
        
        for round_num in range(1, max_rounds + 1):
            round_f1_scores = []
            for m in user_metrics:
                round_key = f'round_{round_num}_avg_rating'
                if round_key in m.get('round_metrics', {}):
                    # Átlagos rating → F1 proxy (egyszerűsítés)
                    avg_rating = m['round_metrics'][round_key]
                    f1_proxy = (avg_rating - 1) / 4  # 1-5 skála → 0-1
                    round_f1_scores.append(f1_proxy)
            
            if round_f1_scores:
                learning_curve[f'round_{round_num}'] = np.mean(round_f1_scores)
        
        return {
            'precision': np.mean([m['precision'] for m in user_metrics]),
            'recall': np.mean([m['recall'] for m in user_metrics]),
            'f1_score': np.mean([m['f1_score'] for m in user_metrics]),
            'num_users': len(user_metrics),
            'total_ratings': sum([m['num_ratings'] for m in user_metrics]),
            'avg_ratings_per_user': np.mean([m['num_ratings'] for m in user_metrics]),
            'learning_curve': learning_curve,
            'max_rounds': max_rounds
        }
        
    except Exception as e:
        debug_log(f"❌ Group metrics hiba: {e}")
        return None

# ✅ FLASK ROUTE-OK JAVÍTVA

@app.route('/')
def home():
    ensure_initialized()
    
    user_id = get_user_id()
    group = get_user_group(user_id)
    current_round = session.get('recommendation_round', 1)
    
    # Személyre szabott ajánlások generálása
    recommendations = get_personalized_recommendations(user_id, 6)
    
    log_behavior(user_id, 'page_visit', {
        'page': 'home',
        'round': current_round,
        'recommendations_count': len(recommendations)
    })
    
    return render_template_string(HOME_TEMPLATE, 
                                recipes=recommendations, 
                                group=group,
                                user_id=user_id,
                                current_round=current_round)

@app.route('/next_round', methods=['POST'])
def next_round():
    """✅ KÖVETKEZŐ KÖR INDÍTÁSA"""
    user_id = get_user_id()
    
    # Ellenőrizzük, hogy van-e elegendő értékelés az aktuális körben
    current_round = session.get('recommendation_round', 1)
    current_round_ratings = [r for r in ratings_data 
                           if r['user_id'] == str(user_id) and r.get('round', 1) == current_round]
    
    if len(current_round_ratings) >= 3:  # Minimum 3 értékelés szükséges
        session['recommendation_round'] = current_round + 1
        session.modified = True
        
        log_behavior(user_id, 'round_advance', {
            'from_round': current_round,
            'to_round': current_round + 1,
            'ratings_in_round': len(current_round_ratings)
        })
        
        return jsonify({
            'status': 'success',
            'new_round': current_round + 1,
            'message': f'Új kör indítva! ({current_round + 1}. kör)'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': f'Legalább 3 értékelés szükséges a következő körhöz! (Jelenlegi: {len(current_round_ratings)})'
        })

@app.route('/search', methods=['POST'])
def search():
    ensure_initialized()
    
    user_id = get_user_id()
    group = get_user_group(user_id)
    query = request.form.get('query', '').strip()
    
    if not query:
        return render_template_string(HOME_TEMPLATE, 
                                    recipes=[], 
                                    group=group,
                                    user_id=user_id,
                                    message="Kérem adjon meg keresési kifejezést!")
    
    results = search_recipes(query, top_n=10)
    
    log_behavior(user_id, 'search', {
        'query': query,
        'results_count': len(results),
        'results_ids': [r['id'] for r in results[:5]]
    })
    
    return render_template_string(HOME_TEMPLATE, 
                                recipes=results, 
                                group=group,
                                user_id=user_id,
                                query=query,
                                is_search_results=True)

@app.route('/api/rate_recipe', methods=['POST'])
def rate_recipe():
    """Rating API endpoint"""
    try:
        data = request.json
        user_id = data.get('user_id')
        recipe_id = data.get('recipe_id')
        rating = data.get('rating')
        comment = data.get('comment', '')
        
        if not all([user_id, recipe_id, rating]):
            return jsonify({'error': 'Hiányzó adatok'}), 400
        
        if not (1 <= int(rating) <= 5):
            return jsonify({'error': 'Érvénytelen értékelés (1-5)'}), 400
        
        rating_entry = save_rating(user_id, recipe_id, rating, comment)
        
        if rating_entry:
            # Ellenőrizzük, hogy van-e elegendő értékelés a következő körhöz
            current_round = session.get('recommendation_round', 1)
            current_round_ratings = [r for r in ratings_data 
                                   if r['user_id'] == str(user_id) and r.get('round', 1) == current_round]
            
            can_advance = len(current_round_ratings) >= 6  # Ha mind a 6 receptet értékelte
            
            return jsonify({
                'status': 'success',
                'message': 'Értékelés sikeresen mentve!',
                'rating': rating_entry,
                'can_advance_round': can_advance,
                'current_round': current_round,
                'ratings_in_round': len(current_round_ratings)
            })
        else:
            return jsonify({'error': 'Mentési hiba'}), 500
        
    except Exception as e:
        debug_log(f"❌ Rating API hiba: {e}")
        return jsonify({'error': f'Hiba: {str(e)}'}), 500

@app.route('/analytics/metrics')
def analytics_metrics():
    """Precision/Recall/F1 metrikák dashboard + tanulási görbék"""
    try:
        metrics_control = calculate_group_metrics('control', k=5)
        metrics_scores = calculate_group_metrics('scores_visible', k=5)
        metrics_explanations = calculate_group_metrics('explanations', k=5)
        
        total_ratings = len(ratings_data)
        total_users_with_ratings = len(set([r['user_id'] for r in ratings_data]))
        avg_rating = np.mean([r['rating'] for r in ratings_data]) if ratings_data else 0
        
        return render_template_string(METRICS_TEMPLATE,
                                    metrics_control=metrics_control,
                                    metrics_scores=metrics_scores,
                                    metrics_explanations=metrics_explanations,
                                    total_ratings=total_ratings,
                                    total_users_with_ratings=total_users_with_ratings,
                                    avg_rating=avg_rating)
        
    except Exception as e:
        debug_log(f"❌ Metrikák hiba: {e}")
        return f"❌ Metrikák megjelenítési hiba: {str(e)}"

@app.route('/analytics')
def analytics():
    """Alapvető analytics dashboard"""
    try:
        group_stats = {}
        for group in ['control', 'scores_visible', 'explanations']:
            group_behaviors = [b for b in behavior_data if b.get('group') == group]
            group_ratings = [r for r in ratings_data if r.get('group') == group]
            
            group_stats[group] = {
                'total_users': len(set([b['user_id'] for b in group_behaviors])),
                'total_interactions': len(group_behaviors),
                'total_ratings': len(group_ratings),
                'avg_rating': np.mean([r['rating'] for r in group_ratings]) if group_ratings else 0,
                'avg_round': np.mean([r.get('round', 1) for r in group_ratings]) if group_ratings else 1
            }
        
        return render_template_string(ANALYTICS_TEMPLATE, 
                                    group_stats=group_stats,
                                    total_behaviors=len(behavior_data),
                                    total_ratings=len(ratings_data))
        
    except Exception as e:
        debug_log(f"❌ Analytics hiba: {e}")
        return f"❌ Analytics hiba: {str(e)}"

@app.route('/status')
def status():
    """Rendszer status JSON"""
    ensure_initialized()
    
    try:
        status_info = {
            'receptek_betoltve': recipes_df is not None,
            'receptek_szama': len(recipes_df) if recipes_df is not None else 0,
            'viselkedesi_adatok': len(behavior_data
