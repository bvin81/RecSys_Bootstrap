# Explicit Ratings Rendszer - Teljes Implementáció
"""
RecSys_Bootstrap bővítés explicit felhasználói értékelési rendszerrel
Precision/Recall/F1 metrikák számításához
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

app = Flask(__name__)
app.secret_key = "greenrec_secret_key_2024"

# Globális változók
recipes_df = None
tfidf_matrix = None
vectorizer = None
behavior_data = []
ratings_data = []  # ÚJ: Explicit ratings tárolás

# JSON betöltés
def load_data():
    global recipes_df, tfidf_matrix, vectorizer
    try:
        with open('greenrec_dataset.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        recipes_list = data.get('recipes', [])
        if not recipes_list:
            return False
        
        # DataFrame létrehozás
        recipes_df = pd.DataFrame(recipes_list)
        
        # ID konverzió
        if 'recipeid' in recipes_df.columns:
            recipes_df['id'] = recipes_df['recipeid']
        
        # Pontszámok normalizálása 0-1 közé
        for col in ['ESI', 'HSI', 'PPI']:
            if col in recipes_df.columns:
                max_val = recipes_df[col].max()
                if max_val > 0:
                    recipes_df[f'{col}_norm'] = recipes_df[col] / max_val
        
        # TF-IDF vektorizálás
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        tfidf_matrix = vectorizer.fit_transform(recipes_df['ingredients'].fillna(''))
        
        print(f"✅ Adatok betöltve: {len(recipes_df)} recept")
        return True
        
    except Exception as e:
        print(f"❌ Adatbetöltési hiba: {e}")
        return False

def get_user_id():
    """Egyedi felhasználói azonosító generálás"""
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return session['user_id']

def get_user_group(user_id):
    """A/B/C csoport meghatározása"""
    hash_val = int(hashlib.md5(str(user_id).encode()).hexdigest(), 16)
    group_num = hash_val % 3
    return ['control', 'scores_visible', 'explanations'][group_num]

def log_behavior(user_id, action, data=None):
    """Viselkedési adatok naplózása"""
    behavior_entry = {
        'timestamp': datetime.now().isoformat(),
        'user_id': str(user_id),
        'group': get_user_group(user_id),
        'action': action,
        'data': data or {}
    }
    behavior_data.append(behavior_entry)

# ÚJ: Rating funkcionalitás
def save_rating(user_id, recipe_id, rating, comment=""):
    """Felhasználói értékelés mentése"""
    # Rating konvertálása binary relevance-re
    # Rating >= 4 = relevant (1), < 4 = irrelevant (0)
    relevance = 1 if rating >= 4 else 0
    
    rating_entry = {
        'timestamp': datetime.now().isoformat(),
        'user_id': str(user_id),
        'recipe_id': int(recipe_id),
        'rating': int(rating),
        'relevance': relevance,
        'comment': comment,
        'group': get_user_group(user_id)
    }
    
    # Ellenőrizzük, hogy már értékelte-e ezt a receptet
    existing_ratings = [r for r in ratings_data if r['user_id'] == str(user_id) and r['recipe_id'] == int(recipe_id)]
    
    if existing_ratings:
        # Frissítjük a meglévő értékelést
        for i, rating_item in enumerate(ratings_data):
            if rating_item['user_id'] == str(user_id) and rating_item['recipe_id'] == int(recipe_id):
                ratings_data[i] = rating_entry
                break
    else:
        # Új értékelés hozzáadása
        ratings_data.append(rating_entry)
    
    # Viselkedési log
    log_behavior(user_id, 'rating_submitted', {
        'recipe_id': recipe_id,
        'rating': rating,
        'relevance': relevance
    })
    
    return rating_entry

def search_recipes(query, top_n=10):
    """Content-based filtering keresés"""
    if not query or recipes_df is None or tfidf_matrix is None:
        return recipes_df.head(top_n).to_dict('records') if recipes_df is not None else []
    
    try:
        # TF-IDF vektorizálás a keresési kifejezésre
        query_vec = vectorizer.transform([query])
        
        # Cosine similarity számítás
        similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
        
        # Sustainability scores kombinálása
        sustainability_scores = (
            recipes_df.get('ESI_norm', 0) * 0.3 + 
            recipes_df.get('HSI_norm', 0) * 0.3 + 
            recipes_df.get('PPI_norm', 0) * 0.4
        )
        
        # Hibrid scoring: 50% similarity + 50% sustainability
        final_scores = similarities * 0.5 + sustainability_scores * 0.5
        
        # Top N receptek kiválasztása
        top_indices = final_scores.argsort()[-top_n:][::-1]
        results = recipes_df.iloc[top_indices].copy()
        results['similarity_score'] = similarities[top_indices]
        results['final_score'] = final_scores[top_indices]
        
        return results.to_dict('records')
        
    except Exception as e:
        print(f"❌ Keresési hiba: {e}")
        return recipes_df.head(top_n).to_dict('records')

# ÚJ: Precision/Recall/F1 számítás
def calculate_user_metrics(user_id, k=5):
    """Precision@K, Recall@K, F1@K számítása egy felhasználóra"""
    try:
        # Felhasználó értékelései
        user_ratings = [r for r in ratings_data if r['user_id'] == str(user_id)]
        
        if len(user_ratings) < 3:  # Minimum 3 értékelés szükséges
            return None
            
        # Relevant receptek (rating >= 4)
        relevant_recipes = set([r['recipe_id'] for r in user_ratings if r['relevance'] == 1])
        
        if not relevant_recipes:
            return None
        
        # Utolsó keresés megkeresése
        user_behaviors = [b for b in behavior_data if b['user_id'] == str(user_id)]
        last_search_query = None
        
        for behavior in reversed(user_behaviors):
            if behavior['action'] == 'search':
                last_search_query = behavior['data'].get('query', '')
                break
        
        if not last_search_query:
            return None
        
        # Ajánlások generálása
        recommendations = search_recipes(last_search_query, top_n=k)
        recommended_ids = set([r['id'] for r in recommendations])
        
        # Metrikák számítása
        true_positives = len(recommended_ids.intersection(relevant_recipes))
        false_positives = len(recommended_ids - relevant_recipes)
        false_negatives = len(relevant_recipes - recommended_ids)
        
        precision = true_positives / len(recommended_ids) if len(recommended_ids) > 0 else 0
        recall = true_positives / len(relevant_recipes) if len(relevant_recipes) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'true_positives': true_positives,
            'false_positives': false_positives,
            'false_negatives': false_negatives,
            'num_ratings': len(user_ratings),
            'num_relevant': len(relevant_recipes)
        }
        
    except Exception as e:
        print(f"❌ Metrika számítási hiba: {e}")
        return None

def calculate_group_metrics(group=None, k=5):
    """Csoport átlagos metrikák számítása"""
    try:
        user_metrics = []
        
        # Minden felhasználó, akinek van értékelése
        user_ids = list(set([r['user_id'] for r in ratings_data]))
        
        for user_id in user_ids:
            if group and get_user_group(user_id) != group:
                continue
                
            metrics = calculate_user_metrics(user_id, k)
            if metrics:
                user_metrics.append(metrics)
        
        if not user_metrics:
            return None
        
        # Átlagos metrikák
        avg_metrics = {
            'precision': np.mean([m['precision'] for m in user_metrics]),
            'recall': np.mean([m['recall'] for m in user_metrics]),
            'f1_score': np.mean([m['f1_score'] for m in user_metrics]),
            'num_users': len(user_metrics),
            'total_ratings': sum([m['num_ratings'] for m in user_metrics]),
            'avg_ratings_per_user': np.mean([m['num_ratings'] for m in user_metrics])
        }
        
        return avg_metrics
        
    except Exception as e:
        print(f"❌ Csoport metrika hiba: {e}")
        return None

# Flask route-ok
@app.route('/')
def home():
    user_id = get_user_id()
    group = get_user_group(user_id)
    
    # Alapértelmezett receptek megjelenítése
    if recipes_df is not None:
        default_recipes = recipes_df.head(6).to_dict('records')
    else:
        default_recipes = []
    
    log_behavior(user_id, 'page_visit', {'page': 'home'})
    
    return render_template_string(HOME_TEMPLATE, 
                                recipes=default_recipes, 
                                group=group,
                                user_id=user_id)

@app.route('/search', methods=['POST'])
def search():
    user_id = get_user_id()
    group = get_user_group(user_id)
    query = request.form.get('query', '').strip()
    
    if not query:
        return render_template_string(HOME_TEMPLATE, 
                                    recipes=[], 
                                    group=group,
                                    user_id=user_id,
                                    message="Kérem adjon meg keresési kifejezést!")
    
    # Keresés végrehajtása
    results = search_recipes(query, top_n=10)
    
    # Viselkedési log
    log_behavior(user_id, 'search', {
        'query': query,
        'results_count': len(results),
        'results_ids': [r['id'] for r in results[:5]]
    })
    
    return render_template_string(HOME_TEMPLATE, 
                                recipes=results, 
                                group=group,
                                user_id=user_id,
                                query=query)

# ÚJ: Rating API endpoint
@app.route('/api/rate_recipe', methods=['POST'])
def rate_recipe():
    """Recept értékelése API"""
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
        
        # Értékelés mentése
        rating_entry = save_rating(user_id, recipe_id, rating, comment)
        
        return jsonify({
            'status': 'success',
            'message': 'Értékelés sikeresen mentve!',
            'rating': rating_entry
        })
        
    except Exception as e:
        return jsonify({'error': f'Hiba: {str(e)}'}), 500

# ÚJ: Metrikák megjelenítése
@app.route('/analytics/metrics')
def analytics_metrics():
    """Precision/Recall/F1 metrikák dashboard"""
    try:
        # A/B/C csoportok metrikái
        metrics_control = calculate_group_metrics('control', k=5)
        metrics_scores = calculate_group_metrics('scores_visible', k=5)
        metrics_explanations = calculate_group_metrics('explanations', k=5)
        
        # Általános statisztikák
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
        return f"❌ Metrikák megjelenítési hiba: {str(e)}"

@app.route('/analytics')
def analytics():
    """Alapvető analytics dashboard"""
    try:
        # Csoportonkénti statisztikák
        group_stats = {}
        for group in ['control', 'scores_visible', 'explanations']:
            group_behaviors = [b for b in behavior_data if b.get('group') == group]
            group_ratings = [r for r in ratings_data if r.get('group') == group]
            
            group_stats[group] = {
                'total_users': len(set([b['user_id'] for b in group_behaviors])),
                'total_interactions': len(group_behaviors),
                'total_ratings': len(group_ratings),
                'avg_rating': np.mean([r['rating'] for r in group_ratings]) if group_ratings else 0
            }
        
        return render_template_string(ANALYTICS_TEMPLATE, 
                                    group_stats=group_stats,
                                    total_behaviors=len(behavior_data),
                                    total_ratings=len(ratings_data))
        
    except Exception as e:
        return f"❌ Analytics hiba: {str(e)}"

# HTML template-ek
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
        .score-badge { display: inline-block; margin-right: 10px; padding: 5px 10px; border-radius: 15px; }
        .score-high { background-color: #d4edda; color: #155724; }
        .score-medium { background-color: #fff3cd; color: #856404; }
        .score-low { background-color: #f8d7da; color: #721c24; }
        .explanation { background: #e7f3ff; padding: 10px; margin-top: 10px; border-left: 4px solid #007bff; }
        
        /* Rating Widget */
        .rating-widget { margin-top: 15px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; background: #f9f9f9; }
        .star-rating { margin: 10px 0; }
        .star { font-size: 24px; color: #ddd; cursor: pointer; transition: color 0.2s; }
        .star:hover, .star.selected { color: #ffd700; }
        .rating-comment { width: 100%; margin-top: 10px; }
        .rating-submit { margin-top: 10px; }
        .rating-success { color: #28a745; margin-top: 10px; display: none; }
    </style>
</head>
<body>
    <div class="container mt-4">
        <h1 class="text-center mb-4">🍃 GreenRec - Fenntartható Receptajánló</h1>
        
        <div class="group-info">
            <strong>Test csoport:</strong> {{ group.title() }} | <strong>User ID:</strong> {{ user_id[:8] }}...
            <div class="mt-2">
                <a href="/analytics" class="btn btn-sm btn-outline-info">📊 Analytics</a>
                <a href="/analytics/metrics" class="btn btn-sm btn-outline-success">📈 Metrikák</a>
            </div>
        </div>
        
        <!-- Keresés -->
        <form method="POST" action="/search" class="mb-4">
            <div class="input-group">
                <input type="text" name="query" class="form-control" 
                       placeholder="Keresés összetevők alapján (pl. 'paradicsom, hagyma')" 
                       value="{{ query or '' }}">
                <button class="btn btn-primary" type="submit">🔍 Keresés</button>
            </div>
        </form>
        
        {% if message %}
        <div class="alert alert-warning">{{ message }}</div>
        {% endif %}
        
        <!-- Receptek -->
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
                        
                        <!-- B és C csoport: Pontszámok megjelenítése -->
                        {% if group in ['scores_visible', 'explanations'] %}
                        <div class="scores">
                            {% set esi_class = 'score-high' if recipe.ESI > 70 else ('score-medium' if recipe.ESI > 40 else 'score-low') %}
                            {% set hsi_class = 'score-high' if recipe.HSI > 70 else ('score-medium' if recipe.HSI > 40 else 'score-low') %}
                            {% set ppi_class = 'score-high' if recipe.PPI > 70 else ('score-medium' if recipe.PPI > 40 else 'score-low') %}
                            
                            <span class="score-badge {{ esi_class }}">🌱 ESI: {{ recipe.ESI }}</span>
                            <span class="score-badge {{ hsi_class }}">💚 HSI: {{ recipe.HSI }}</span>
                            <span class="score-badge {{ ppi_class }}">👤 PPI: {{ recipe.PPI }}</span>
                        </div>
                        {% endif %}
                        
                        <!-- C csoport: XAI magyarázatok -->
                        {% if group == 'explanations' %}
                        <div class="explanation">
                            <strong>💡 Miért ajánljuk?</strong><br>
                            {% if recipe.ESI > 70 %}
                            🌱 Környezetbarát recept - alacsony CO2 lábnyom<br>
                            {% endif %}
                            {% if recipe.HSI > 70 %}
                            💚 Egészséges választás - magas tápanyagtartalom<br>
                            {% endif %}
                            {% if recipe.PPI > 70 %}
                            👤 Népszerű recept - mások is kedvelik<br>
                            {% endif %}
                            🎯 Összetevők {{ "%.0f"|format((recipe.similarity_score or 0) * 100) }}%-ban egyeznek keresésével
                        </div>
                        {% endif %}
                        
                        <!-- Rating Widget -->
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
        
        {% if not recipes %}
        <div class="text-center mt-4">
            <p>Nincs megjeleníthető recept.</p>
        </div>
        {% endif %}
    </div>
    
    <script>
        let currentRatings = {};
        
        // Rating widget inicializálás
        document.addEventListener('DOMContentLoaded', function() {
            initializeRatingWidgets();
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
                        highlightStars(recipeId, rating, true);
                    });
                });
                
                ratingWidget.addEventListener('mouseleave', function() {
                    const savedRating = currentRatings[recipeId] || 0;
                    highlightStars(recipeId, savedRating);
                });
            });
        }
        
        function highlightStars(recipeId, rating, isHover = false) {
            const ratingWidget = document.querySelector(`[data-recipe-id="${recipeId}"]`);
            const stars = ratingWidget.querySelectorAll('.star');
            
            stars.forEach((star, index) => {
                if (index < rating) {
                    star.classList.add('selected');
                } else {
                    star.classList.remove('selected');
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
            
            // API hívás
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
                    // Siker üzenet megjelenítése
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
                } else {
                    alert('Hiba: ' + (data.error || 'Ismeretlen hiba'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Hiba történt az értékelés küldésekor.');
            });
        }
        
        // Page view tracking
        if (typeof gtag !== 'undefined') {
            gtag('event', 'page_view', {
                'page_title': 'GreenRec Home',
                'user_group': '{{ group }}'
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
    <title>GreenRec - Precision/Recall/F1 Metrikák</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-4">
        <h1 class="text-center mb-4">📈 Recommendation Metrics Dashboard</h1>
        
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
        
        <div class="row">
            <!-- A Csoport (Control) -->
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header bg-secondary text-white">
                        <h5>🔍 A Csoport (Control)</h5>
                        <small>Csak alapfunkciók</small>
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
            
            <!-- B Csoport (Scores Visible) -->
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header bg-warning text-dark">
                        <h5>📊 B Csoport (Scores)</h5>
                        <small>ESI/HSI/PPI pontszámokkal</small>
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
            
            <!-- C Csoport (Explanations) -->
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header bg-success text-white">
                        <h5>🤖 C Csoport (XAI)</h5>
                        <small>Pontszámok + magyarázatok</small>
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
        
        <!-- Összehasonlító elemzés -->
        {% if metrics_control and metrics_scores and metrics_explanations %}
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-info text-white">
                        <h5>🔬 Összehasonlító Elemzés</h5>
                    </div>
                    <div class="card-body">
                        <h6>F1-Score@5 Összehasonlítás:</h6>
                        <div class="progress-group mb-3">
                            <div class="d-flex justify-content-between">
                                <span>A Csoport (Control)</span>
                                <span>{{ "%.3f"|format(metrics_control.f1_score) }}</span>
                            </div>
                            <div class="progress">
                                <div class="progress-bar bg-secondary" 
                                     style="width: {{ (metrics_control.f1_score * 100)|round(1) }}%"></div>
                            </div>
                        </div>
                        
                        <div class="progress-group mb-3">
                            <div class="d-flex justify-content-between">
                                <span>B Csoport (Scores)</span>
                                <span>{{ "%.3f"|format(metrics_scores.f1_score) }}</span>
                            </div>
                            <div class="progress">
                                <div class="progress-bar bg-warning" 
                                     style="width: {{ (metrics_scores.f1_score * 100)|round(1) }}%"></div>
                            </div>
                        </div>
                        
                        <div class="progress-group mb-3">
                            <div class="d-flex justify-content-between">
                                <span>C Csoport (XAI)</span>
                                <span>{{ "%.3f"|format(metrics_explanations.f1_score) }}</span>
                            </div>
                            <div class="progress">
                                <div class="progress-bar bg-success" 
                                     style="width: {{ (metrics_explanations.f1_score * 100)|round(1) }}%"></div>
                            </div>
                        </div>
                        
                        <hr>
                        <h6>📈 Eredmények Interpretációja:</h6>
                        {% set best_f1 = [metrics_control.f1_score, metrics_scores.f1_score, metrics_explanations.f1_score] | max %}
                        {% if best_f1 == metrics_explanations.f1_score %}
                        <div class="alert alert-success">
                            <strong>🏆 A C csoport (XAI) teljesített a legjobban!</strong><br>
                            Az explainable AI magyarázatok javítják az ajánlórendszer precizitását.
                        </div>
                        {% elif best_f1 == metrics_scores.f1_score %}
                        <div class="alert alert-warning">
                            <strong>🥈 A B csoport (Scores) teljesített a legjobban!</strong><br>
                            A fenntarthatósági pontszámok megjelenítése hatékony.
                        </div>
                        {% else %}
                        <div class="alert alert-secondary">
                            <strong>🥉 Az A csoport (Control) teljesített a legjobban!</strong><br>
                            Az egyszerű interface meglepően hatékony.
                        </div>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
        
        <!-- Navigáció -->
        <div class="text-center mt-4">
            <a href="/" class="btn btn-primary">🏠 Vissza a főoldalra</a>
            <a href="/analytics" class="btn btn-outline-info">📊 Általános Analytics</a>
            <button onclick="location.reload()" class="btn btn-outline-secondary">🔄 Frissítés</button>
        </div>
        
        <!-- Metrikák magyarázata -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h6>ℹ️ Metrikák Magyarázata</h6>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-4">
                                <strong>Precision@5:</strong><br>
                                <small>A top 5 ajánlásból hány releváns (≥4 csillag)?</small>
                            </div>
                            <div class="col-md-4">
                                <strong>Recall@5:</strong><br>
                                <small>Az összes releváns receptből mennyit talált meg a top 5?</small>
                            </div>
                            <div class="col-md-4">
                                <strong>F1-Score@5:</strong><br>
                                <small>Precision és Recall harmonikus átlaga.</small>
                            </div>
                        </div>
                        <hr>
                        <small class="text-muted">
                            <strong>Megjegyzés:</strong> A metrikák számításához minden felhasználónak minimum 3 értékelést kell adnia, 
                            és legalább egy receptet 4-5 csillagra kell értékelnie (releváns).
                        </small>
                    </div>
                </div>
            </div>
        </div>
    </div>
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
        
        <!-- Általános statisztikák -->
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
        
        <!-- A/B/C csoportok statisztikái -->
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
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Navigáció -->
        <div class="text-center mt-4">
            <a href="/" class="btn btn-primary">🏠 Vissza a főoldalra</a>
            <a href="/analytics/metrics" class="btn btn-success">📈 Precision/Recall Metrikák</a>
            <button onclick="location.reload()" class="btn btn-outline-secondary">🔄 Frissítés</button>
        </div>
    </div>
</body>
</html>
"""

# Alkalmazás indítás
if __name__ == '__main__':
    print("🔄 GreenRec Explicit Ratings rendszer indítása...")
    
    if load_data():
        print("✅ Adatok sikeresen betöltve")
        print(f"📊 Receptek száma: {len(recipes_df) if recipes_df is not None else 0}")
        print("🌐 Alkalmazás elérhető: http://localhost:5000")
        print("📈 Metrikák: http://localhost:5000/analytics/metrics")
        print("📊 Analytics: http://localhost:5000/analytics")
        print("\n🎯 HASZNÁLATI ÚTMUTATÓ:")
        print("1. Keressren recepteket")
        print("2. Értékelje a recepteket (1-5 csillag)")
        print("3. Minimum 3 értékelés után láthatóak a metrikák")
        print("4. 4-5 csillag = releváns, 1-3 csillag = irreleváns")
        
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("❌ Hiba az adatok betöltésekor. Ellenőrizze a greenrec_dataset.json fájlt!")
