from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
import random
import json
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = 'greenrec-secret-key-2025'

# Konfiguráció
LEARNING_ROUNDS = 3  # 3 kör az 5 helyett
RECOMMENDATION_COUNT = 5
RATING_SCALE = [1, 2, 3, 4, 5]

# Minta recept adatok (később JSON fájlból)
SAMPLE_RECIPES = [
    {
        'id': '1', 'recipeid': 1, 'name': 'Magyar Gulyás', 'recipe_name': 'Magyar Gulyás',
        'ingredients': 'marhahús, hagyma, paprika, burgonya, paradicsom',
        'HSI': 75, 'ESI': 45, 'PPI': 85, 'composite_score': 72,
        'category': 'Hagyományos Magyar', 'image_url': ''
    },
    {
        'id': '2', 'recipeid': 2, 'name': 'Vegán Buddha Bowl', 'recipe_name': 'Vegán Buddha Bowl',
        'ingredients': 'quinoa, avokádó, spenót, csicseriborsó, sárgarépa',
        'HSI': 90, 'ESI': 85, 'PPI': 70, 'composite_score': 85,
        'category': 'Vegán', 'image_url': ''
    },
    {
        'id': '3', 'recipeid': 3, 'name': 'Grillezett Csirkemell', 'recipe_name': 'Grillezett Csirkemell',
        'ingredients': 'csirkemell, olivaolaj, rozmarinг, citrom, fokhagyma',
        'HSI': 85, 'ESI': 60, 'PPI': 80, 'composite_score': 75,
        'category': 'Főétel', 'image_url': ''
    },
    {
        'id': '4', 'recipeid': 4, 'name': 'Mediterrán Saláta', 'recipe_name': 'Mediterrán Saláta',
        'ingredients': 'paradicsom, uborka, feta sajt, olívabogyó, hagyma',
        'HSI': 80, 'ESI': 90, 'PPI': 65, 'composite_score': 82,
        'category': 'Saláta', 'image_url': ''
    },
    {
        'id': '5', 'recipeid': 5, 'name': 'Lencsecurry', 'recipe_name': 'Lencsecurry',
        'ingredients': 'vörös lencse, kókusztej, curry fűszer, hagyma, gyömbér',
        'HSI': 85, 'ESI': 95, 'PPI': 90, 'composite_score': 90,
        'category': 'Vegán', 'image_url': ''
    },
    {
        'id': '6', 'recipeid': 6, 'name': 'Sütőtökös Rizottó', 'recipe_name': 'Sütőtökös Rizottó',
        'ingredients': 'arborio rizs, sütőtök, parmezán, fehérbor, hagyma',
        'HSI': 70, 'ESI': 75, 'PPI': 75, 'composite_score': 73,
        'category': 'Vegetáriánus', 'image_url': ''
    }
]

# Session inicializálás
def initialize_user_session():
    """Felhasználói session inicializálása A/B/C teszthez"""
    if 'user_id' not in session:
        session['user_id'] = f"user_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"
        session['user_group'] = random.choice(['A', 'B', 'C'])  # A/B/C teszt
        session['learning_round'] = 1
        session['ratings'] = {}
        session['session_started'] = datetime.now().isoformat()
    
    return session['user_id'], session['user_group'], session['learning_round']

# Ajánlások generálása
def get_recommendations(user_group, learning_round, n=5):
    """Ajánlások generálása csoport szerint"""
    recipes = SAMPLE_RECIPES.copy()
    
    if user_group == 'A':
        # A csoport: Random ajánlások (baseline)
        selected = random.sample(recipes, min(n, len(recipes)))
    elif user_group == 'B':
        # B csoport: Magas pontszámú receptek
        sorted_recipes = sorted(recipes, key=lambda x: x['composite_score'], reverse=True)
        selected = sorted_recipes[:n]
    else:  # user_group == 'C'
        # C csoport: Hibrid megközelítés
        high_score = sorted(recipes, key=lambda x: x['composite_score'], reverse=True)[:3]
        random_recipes = random.sample([r for r in recipes if r not in high_score], min(2, len(recipes)-3))
        selected = high_score + random_recipes
    
    # A csoport számára rejtett pontszámok
    for recipe in selected:
        recipe['show_scores'] = user_group in ['B', 'C']
    
    return selected

# Főoldal template
HOME_TEMPLATE = """
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GreenRec - Környezettudatos Receptek</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            min-height: 100vh;
        }
        .hero-section {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .hero-card {
            background: white;
            border-radius: 20px;
            padding: 50px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.1);
            text-align: center;
            max-width: 600px;
        }
        .hero-title {
            font-size: 3rem;
            color: #2d5a27;
            margin-bottom: 20px;
        }
        .hero-subtitle {
            font-size: 1.3rem;
            color: #666;
            margin-bottom: 40px;
        }
        .feature-box {
            background: #f8f9fa;
            border-radius: 15px;
            padding: 25px;
            margin: 20px 0;
            border-left: 5px solid #4caf50;
        }
        .btn-start {
            background: linear-gradient(135deg, #4caf50, #2d5a27);
            border: none;
            color: white;
            padding: 18px 40px;
            font-size: 1.2rem;
            border-radius: 30px;
            transition: all 0.3s ease;
        }
        .btn-start:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(76, 175, 80, 0.3);
            color: white;
        }
        .user-info {
            background: rgba(45, 90, 39, 0.1);
            border-radius: 10px;
            padding: 15px;
            margin-top: 30px;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="hero-section">
        <div class="hero-card">
            <h1 class="hero-title">🌱 GreenRec</h1>
            <p class="hero-subtitle">Környezettudatos Recept Ajánlórendszer</p>
            
            <div class="feature-box">
                <h4><i class="fas fa-flask text-success me-2"></i>AI-alapú A/B/C Teszt</h4>
                <p class="mb-0">Vegyen részt egy innovatív kutatásban a fenntartható étkezésről</p>
            </div>
            
            <div class="feature-box">
                <h4><i class="fas fa-chart-line text-success me-2"></i>Fenntarthatósági Metrikák</h4>
                <p class="mb-0">🌍 Környezeti Hatás • 💚 Egészségügyi Érték • 👤 Népszerűség</p>
            </div>
            
            <div class="feature-box">
                <h4><i class="fas fa-clock text-success me-2"></i>{{ rounds }} Gyors Kör</h4>
                <p class="mb-0">Csak {{ rounds * 2 }} perc alatt • {{ recipes_per_round }} recept körönként</p>
            </div>
            
            <a href="/study" class="btn btn-start btn-lg mt-4">
                <i class="fas fa-play me-2"></i>Tanulmány Indítása
            </a>
            
            <div class="user-info">
                <small>
                    <i class="fas fa-info-circle me-1"></i>
                    Anonim kutatás • Adatok biztonságban • Tudományos célokra
                </small>
            </div>
        </div>
    </div>
</body>
</html>
"""

# Tanulmány template
STUDY_TEMPLATE = """
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GreenRec - {{ learning_round }}. Kör</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%); font-family: 'Segoe UI', sans-serif; min-height: 100vh; }
        .header { background: linear-gradient(135deg, #2d5a27, #4caf50); color: white; padding: 2rem 0; margin-bottom: 2rem; }
        .recipe-card { background: white; border-radius: 15px; margin-bottom: 2rem; box-shadow: 0 4px 15px rgba(0,0,0,0.1); overflow: hidden; transition: transform 0.3s ease; }
        .recipe-card:hover { transform: translateY(-5px); }
        .recipe-image { height: 180px; background: linear-gradient(45deg, #e8f5e8, #c8e6c9); display: flex; align-items: center; justify-content: center; }
        .recipe-content { padding: 1.5rem; }
        .recipe-title { font-size: 1.25rem; font-weight: bold; color: #2d5a27; margin-bottom: 1rem; }
        .recipe-ingredients { color: #666; font-size: 0.9rem; margin-bottom: 1rem; }
        .score-badges { display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
        .score-badge { padding: 0.5rem 1rem; border-radius: 20px; font-size: 0.9rem; font-weight: 600; color: white; min-width: 80px; text-align: center; }
        .hsi-badge { background: linear-gradient(135deg, #ff9800, #f57c00); }
        .esi-badge { background: linear-gradient(135deg, #26a69a, #00695c); }
        .ppi-badge { background: linear-gradient(135deg, #9c27b0, #6a1b9a); }
        .hidden-scores { background: #f5f5f5; border: 2px dashed #ccc; color: #999; text-align: center; padding: 1rem; border-radius: 10px; margin-bottom: 1.5rem; }
        .rating-section { background: #f8f9fa; border-radius: 10px; padding: 1rem; }
        .rating-stars { display: flex; gap: 0.5rem; justify-content: center; margin-bottom: 1rem; }
        .star { font-size: 2rem; color: #ddd; cursor: pointer; transition: color 0.2s ease; }
        .star:hover, .star.active { color: #ffc107; transform: scale(1.1); }
        .btn-rate { background: linear-gradient(135deg, #4caf50, #2d5a27); border: none; color: white; padding: 0.75rem 2rem; border-radius: 25px; width: 100%; }
        .btn-next { background: linear-gradient(135deg, #2d5a27, #4caf50); border: none; color: white; padding: 1rem 3rem; border-radius: 30px; font-size: 1.1rem; }
        .progress-indicator { display: flex; justify-content: center; align-items: center; margin-bottom: 2rem; }
        .round-step { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; color: white; margin: 0 10px; }
        .round-step.completed { background-color: #4caf50; }
        .round-step.current { background-color: #2d5a27; animation: pulse 2s infinite; }
        .round-step.upcoming { background-color: #ccc; color: #666; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(45, 90, 39, 0.7); } 70% { box-shadow: 0 0 0 10px rgba(45, 90, 39, 0); } 100% { box-shadow: 0 0 0 0 rgba(45, 90, 39, 0); } }
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <div class="row align-items-center">
                <div class="col-md-8">
                    <h1><i class="fas fa-leaf me-2"></i>GreenRec Tanulmány</h1>
                    <p class="mb-0">{{ learning_round }}. kör a {{ total_rounds }}-ból • {{ user_group }} Csoport</p>
                </div>
                <div class="col-md-4 text-end">
                    <span class="badge bg-light text-dark">{{ user_id }}</span>
                </div>
            </div>
        </div>
    </div>

    <div class="container">
        <!-- Progress Indicator -->
        <div class="progress-indicator">
            {% for round_num in range(1, total_rounds + 1) %}
                <div class="round-step {% if round_num < learning_round %}completed{% elif round_num == learning_round %}current{% else %}upcoming{% endif %}">
                    {% if round_num < learning_round %}<i class="fas fa-check"></i>{% else %}{{ round_num }}{% endif %}
                </div>
            {% endfor %}
        </div>

        <!-- Recipe Cards -->
        <div class="row">
            {% for recipe in recommendations %}
            <div class="col-lg-6 col-xl-4">
                <div class="recipe-card" data-recipe-id="{{ recipe.id }}">
                    <div class="recipe-image">
                        {% if recipe.image_url %}
                            <img src="{{ recipe.image_url }}" alt="{{ recipe.name }}" style="width: 100%; height: 100%; object-fit: cover;">
                        {% else %}
                            <div class="text-center">
                                <i class="fas fa-utensils fa-3x text-muted mb-2"></i>
                                <div class="text-muted">{{ recipe.recipe_name or recipe.name }}</div>
                            </div>
                        {% endif %}
                    </div>
                    
                    <div class="recipe-content">
                        <h5 class="recipe-title">{{ recipe.recipe_name or recipe.name }}</h5>
                        <div class="recipe-ingredients">
                            <i class="fas fa-list-ul me-1"></i>
                            <strong>Összetevők:</strong> {{ recipe.ingredients[:80] }}{% if recipe.ingredients|length > 80 %}...{% endif %}
                        </div>

                        <!-- Sustainability Scores -->
                        {% if recipe.show_scores %}
                            <div class="score-badges">
                                <div class="score-badge hsi-badge" title="Egészségügyi Érték">
                                    💚 {{ recipe.HSI }}
                                </div>
                                <div class="score-badge esi-badge" title="Környezeti Hatás">
                                    🌍 {{ recipe.ESI }}
                                </div>
                                <div class="score-badge ppi-badge" title="Népszerűség">
                                    👤 {{ recipe.PPI }}
                                </div>
                            </div>
                        {% else %}
                            <!-- A csoport: teljesen rejtett -->
                            <div style="height: 45px;"></div>
                        {% endif %}

                        <!-- Rating Section -->
                        <div class="rating-section">
                            <h6 class="text-center mb-3">Mennyire tetszik ez a recept?</h6>
                            <div class="rating-stars" data-recipe-id="{{ recipe.id }}">
                                {% for star in range(1, 6) %}
                                    <span class="star" data-rating="{{ star }}"><i class="fas fa-star"></i></span>
                                {% endfor %}
                            </div>
                            <button class="btn btn-rate" data-recipe-id="{{ recipe.id }}" disabled>
                                <i class="fas fa-thumbs-up me-2"></i>Értékelés Mentése
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>

        <!-- Next Round Button -->
        <div class="text-center mt-4" id="next-round-section" style="display: none;">
            <div class="card">
                <div class="card-body">
                    {% if is_final_round %}
                        <h4><i class="fas fa-trophy text-warning me-2"></i>Gratulálunk!</h4>
                        <p>Sikeresen befejezte a tanulmányt!</p>
                        <a href="/results" class="btn btn-next">
                            <i class="fas fa-chart-bar me-2"></i>Eredmények Megtekintése
                        </a>
                    {% else %}
                        <h4><i class="fas fa-arrow-right me-2"></i>{{ learning_round }}. kör befejezve</h4>
                        <p>Folytassa a következő körrel!</p>
                        <button class="btn btn-next" id="next-round-btn">
                            <i class="fas fa-forward me-2"></i>Következő Kör ({{ learning_round + 1 }}/{{ total_rounds }})
                        </button>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/js/bootstrap.bundle.min.js"></script>
    <script>
        let ratedRecipes = new Set();
        const totalRecipes = {{ recommendations|length }};

        document.addEventListener('DOMContentLoaded', function() {
            initializeRatingSystem();
        });

        function initializeRatingSystem() {
            document.querySelectorAll('.rating-stars').forEach(function(starsContainer) {
                const recipeId = starsContainer.dataset.recipeId;
                const stars = starsContainer.querySelectorAll('.star');
                const rateBtn = document.querySelector(`button[data-recipe-id="${recipeId}"]`);
                let selectedRating = 0;

                stars.forEach(function(star, index) {
                    const rating = index + 1;
                    
                    star.addEventListener('click', function() {
                        selectedRating = rating;
                        setStarRating(stars, rating);
                        rateBtn.disabled = false;
                        rateBtn.innerHTML = `<i class="fas fa-thumbs-up me-2"></i>Értékelés Mentése (${rating} csillag)`;
                    });

                    star.addEventListener('mouseenter', function() {
                        highlightStars(stars, rating);
                    });
                });

                starsContainer.addEventListener('mouseleave', function() {
                    setStarRating(stars, selectedRating);
                });

                rateBtn.addEventListener('click', function() {
                    if (selectedRating > 0) {
                        submitRating(recipeId, selectedRating, rateBtn);
                    }
                });
            });

            document.getElementById('next-round-btn')?.addEventListener('click', function() {
                window.location.href = '/next_round';
            });
        }

        function highlightStars(stars, rating) {
            stars.forEach(function(star, index) {
                star.classList.toggle('active', index < rating);
            });
        }

        function setStarRating(stars, rating) {
            stars.forEach(function(star, index) {
                star.classList.toggle('active', index < rating);
            });
        }

        function submitRating(recipeId, rating, buttonElement) {
            buttonElement.disabled = true;
            buttonElement.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i>Mentés...`;

            fetch('/rate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ recipe_id: recipeId, rating: rating })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    ratedRecipes.add(recipeId);
                    buttonElement.innerHTML = `<i class="fas fa-check me-2"></i>Elmentve (${rating} csillag)`;
                    buttonElement.classList.add('btn-success');
                    
                    if (ratedRecipes.size >= totalRecipes) {
                        document.getElementById('next-round-section').style.display = 'block';
                        document.getElementById('next-round-section').scrollIntoView({ behavior: 'smooth' });
                    }
                } else {
                    buttonElement.innerHTML = `<i class="fas fa-exclamation-triangle me-2"></i>Hiba`;
                    buttonElement.classList.add('btn-danger');
                }
            })
            .catch(error => {
                console.error('Rating error:', error);
                buttonElement.innerHTML = `<i class="fas fa-wifi me-2"></i>Kapcsolat hiba`;
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Főoldal"""
    return render_template_string(results_template)

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0-full'
    })

@app.route('/analytics')
def analytics():
    """Analytics dashboard (fejlesztés alatt)"""
    analytics_template = """
    <!DOCTYPE html>
    <html lang="hu">
    <head>
        <meta charset="UTF-8">
        <title>GreenRec Analytics</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%); font-family: 'Segoe UI', sans-serif; min-height: 100vh; }
            .analytics-container { max-width: 1200px; margin: 50px auto; padding: 20px; }
            .analytics-card { background: white; border-radius: 20px; padding: 30px; margin-bottom: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.1); }
        </style>
    </head>
    <body>
        <div class="analytics-container">
            <div class="analytics-card">
                <h1 class="text-center text-success mb-4">📊 GreenRec Analytics</h1>
                <div class="row">
                    <div class="col-md-4">
                        <div class="card text-center">
                            <div class="card-body">
                                <h5 class="card-title">A Csoport</h5>
                                <h2 class="text-info">-</h2>
                                <p class="card-text">Baseline (rejtett pontszámok)</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card text-center">
                            <div class="card-body">
                                <h5 class="card-title">B Csoport</h5>
                                <h2 class="text-warning">-</h2>
                                <p class="card-text">Score-enhanced</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card text-center">
                            <div class="card-body">
                                <h5 class="card-title">C Csoport</h5>
                                <h2 class="text-success">-</h2>
                                <p class="card-text">Hybrid approach</p>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="alert alert-info mt-4">
                    <h4>🚧 Fejlesztés alatt</h4>
                    <p>Az analytics dashboard hamarosan elérhető lesz a részletes A/B/C teszt eredményekkel:</p>
                    <ul>
                        <li>Precision@5, Recall@5, F1 metrikák</li>
                        <li>Diversity és Novelty mérések</li>
                        <li>Mean HSI/ESI értékek csoportonként</li>
                        <li>Felhasználói engagement statisztikák</li>
                    </ul>
                </div>
                <div class="text-center">
                    <a href="/" class="btn btn-success">Vissza a főoldalra</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(analytics_template)

@app.route('/reset')
def reset_session():
    """Session reset (fejlesztéshez)"""
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    print("🌱 GreenRec - Teljes Funkcionális Verzió")
    print("=" * 50)
    print("✅ A/B/C Teszt rendszer")
    print("✅ 3 tanulási kör")
    print("✅ Recept képek és nevek")
    print("✅ A csoport: rejtett pontszámok")
    print("✅ Responsive design")
    print("✅ Rating system")
    print("=" * 50)
    print(f"🚀 Server: http://localhost:{port}")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)_string(HOME_TEMPLATE, 
                                rounds=LEARNING_ROUNDS,
                                recipes_per_round=RECOMMENDATION_COUNT)

@app.route('/study')
def study():
    """Tanulmány oldal"""
    user_id, user_group, learning_round = initialize_user_session()
    
    # Ellenőrzés: tanulmány befejezve?
    if learning_round > LEARNING_ROUNDS:
        return redirect(url_for('results'))
    
    # Ajánlások generálása
    recommendations = get_recommendations(user_group, learning_round, RECOMMENDATION_COUNT)
    
    return render_template_string(STUDY_TEMPLATE,
                                user_id=user_id,
                                user_group=user_group,
                                learning_round=learning_round,
                                total_rounds=LEARNING_ROUNDS,
                                recommendations=recommendations,
                                is_final_round=(learning_round >= LEARNING_ROUNDS))

@app.route('/rate', methods=['POST'])
def rate_recipe():
    """Recept értékelése"""
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        rating = int(data.get('rating'))
        
        if rating not in RATING_SCALE:
            return jsonify({'error': 'Invalid rating'}), 400
        
        # Session-be mentés
        if 'ratings' not in session:
            session['ratings'] = {}
        
        session['ratings'][recipe_id] = {
            'rating': rating,
            'timestamp': datetime.now().isoformat(),
            'round': session.get('learning_round', 1)
        }
        
        session.permanent = True
        
        return jsonify({'success': True, 'rating': rating})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/next_round')
def next_round():
    """Következő kör"""
    current_round = session.get('learning_round', 1)
    
    if current_round >= LEARNING_ROUNDS:
        return redirect(url_for('results'))
    
    session['learning_round'] = current_round + 1
    session.permanent = True
    
    return redirect(url_for('study'))

@app.route('/results')
def results():
    """Eredmények oldal"""
    user_id = session.get('user_id', 'Unknown')
    user_group = session.get('user_group', 'Unknown')
    ratings = session.get('ratings', {})
    
    # Alapstatisztikák
    total_ratings = len(ratings)
    avg_rating = sum(r['rating'] for r in ratings.values()) / total_ratings if total_ratings > 0 else 0
    
    results_template = f"""
    <!DOCTYPE html>
    <html lang="hu">
    <head>
        <meta charset="UTF-8">
        <title>GreenRec - Eredmények</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%); font-family: 'Segoe UI', sans-serif; min-height: 100vh; }}
            .results-container {{ max-width: 800px; margin: 50px auto; padding: 20px; }}
            .results-card {{ background: white; border-radius: 20px; padding: 40px; box-shadow: 0 15px 35px rgba(0,0,0,0.1); }}
            .stat-card {{ background: #f8f9fa; border-radius: 15px; padding: 20px; margin: 15px 0; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="results-container">
            <div class="results-card">
                <h1 class="text-center text-success mb-4">🎉 Köszönjük a részvételt!</h1>
                
                <div class="stat-card">
                    <h3>📊 Az Ön eredményei</h3>
                    <p><strong>Felhasználó ID:</strong> {user_id}</p>
                    <p><strong>Teszt csoport:</strong> {user_group}</p>
                    <p><strong>Értékelt receptek:</strong> {total_ratings}</p>
                    <p><strong>Átlag értékelés:</strong> {avg_rating:.1f} / 5.0</p>
                </div>
                
                <div class="stat-card">
                    <h4>🔬 Kutatási információk</h4>
                    <p>Az Ön adatai hozzájárulnak a fenntartható étkezési szokások kutatásához.</p>
                    <p>A tanulmány eredményei segítenek fejleszteni az AI-alapú ajánlórendszereket.</p>
                </div>
                
                <div class="text-center mt-4">
                    <a href="/" class="btn btn-success btn-lg">
                        <i class="fas fa-home me-2"></i>Vissza a főoldalra
                    </a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return render_template
