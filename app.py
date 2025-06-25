# app.py - TELJES JAVÍTOTT VERZIÓ
"""
GreenRec - Fenntartható Receptajánló Rendszer
MINDEN SYNTAX ERROR JAVÍTVA
"""

from flask import Flask, render_template_string, request, session, jsonify, redirect
import json
import pandas as pd
import numpy as np
import hashlib
import os
import time
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'greenrec-secret-key-2025')

# Globális változók
recipes_df = None
tfidf_matrix = None
tfidf_vectorizer = None
behavior_data = []
load_debug_messages = []

def debug_log(message):
    """Debug üzenetek naplózása"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    formatted_msg = f"[{timestamp}] {message}"
    load_debug_messages.append(formatted_msg)
    print(formatted_msg)
    
    if len(load_debug_messages) > 200:
        load_debug_messages[:100] = []

def load_recipes():
    """JSON receptek betöltése és feldolgozása"""
    global recipes_df, tfidf_matrix, tfidf_vectorizer
    
    try:
        debug_log("🔄 JSON fájl betöltése indítása...")
        
        if not os.path.exists('greenrec_dataset.json'):
            debug_log("❌ greenrec_dataset.json nem található!")
            return False
        
        with open('greenrec_dataset.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        debug_log(f"✅ JSON betöltve. Típus: {type(data)}")
        
        # Lista formátum kezelése
        if isinstance(data, list):
            recipes = data
        elif isinstance(data, dict) and 'recipes' in data:
            recipes = data['recipes']
        else:
            debug_log("❌ Ismeretlen JSON struktúra!")
            return False
        
        debug_log(f"📊 {len(recipes)} recept találva")
        
        # DataFrame létrehozása
        df_list = []
        for recipe in recipes:
            try:
                # Mezők normalizálása
                recipe_data = {
                    'id': recipe.get('recipeid') or recipe.get('id', 0),
                    'name': recipe.get('title', 'Névtelen recept'),
                    'ingredients_text': recipe.get('ingredients', ''),
                    'instructions': recipe.get('instructions', ''),
                    'category': recipe.get('category', 'Egyéb'),
                    'image': recipe.get('images', ''),
                    'esi': float(recipe.get('ESI', 0)),
                    'hsi': float(recipe.get('HSI', 0)),
                    'ppi': float(recipe.get('PPI', 0))
                }
                df_list.append(recipe_data)
            except Exception as e:
                debug_log(f"⚠️ Recept feldolgozási hiba: {e}")
        
        recipes_df = pd.DataFrame(df_list)
        debug_log(f"✅ DataFrame létrehozva: {len(recipes_df)} sor")
        
        # TF-IDF mátrix építése
        debug_log("🔧 TF-IDF mátrix építése...")
        tfidf_vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words=None,
            ngram_range=(1, 2),
            lowercase=True
        )
        
        tfidf_matrix = tfidf_vectorizer.fit_transform(recipes_df['ingredients_text'].fillna(''))
        debug_log(f"✅ TF-IDF kész: {tfidf_matrix.shape}")
        
        return True
        
    except Exception as e:
        debug_log(f"❌ Kritikus hiba: {e}")
        return False

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
            'data': data or {}
        }
        behavior_data.append(behavior_entry)
        
        if len(behavior_data) > 10000:
            behavior_data[:5000] = []
            
    except Exception as e:
        debug_log(f"❌ Behavior logging hiba: {e}")

def get_recommendations(recipe_id, n=5):
    """Content-based ajánlások"""
    try:
        if recipes_df is None or tfidf_matrix is None:
            return []
        
        recipe_idx = recipes_df[recipes_df['id'] == recipe_id].index
        if len(recipe_idx) == 0:
            return []
        
        recipe_idx = recipe_idx[0]
        cosine_sim = cosine_similarity(tfidf_matrix[recipe_idx:recipe_idx+1], tfidf_matrix).flatten()
        
        # Hibrid scoring ESI-vel
        df_copy = recipes_df.copy()
        df_copy['similarity'] = cosine_sim
        df_copy['hybrid_score'] = 0.6 * cosine_sim + 0.4 * (df_copy['esi'] / 300.0)
        
        # Top N ajánlás (eredeti recept kizárása)
        recommendations = df_copy[df_copy['id'] != recipe_id].nlargest(n, 'hybrid_score')
        
        results = []
        for _, rec in recommendations.iterrows():
            results.append({
                'id': int(rec['id']),
                'name': str(rec['name']),
                'category': str(rec['category']),
                'ingredients': str(rec['ingredients_text']),
                'image': str(rec['image']),
                'esi': float(rec['esi']),
                'hsi': float(rec['hsi']),
                'ppi': float(rec['ppi']),
                'similarity': float(rec['similarity'])
            })
        
        return results
        
    except Exception as e:
        debug_log(f"❌ Ajánlási hiba: {e}")
        return []

def generate_explanation(recipe, similarity_score):
    """AI-szerű magyarázatok generálása"""
    explanations = []
    try:
        if recipe['esi'] < 150:
            explanations.append("🌱 Kiváló környezeti teljesítmény")
        elif recipe['esi'] < 200:
            explanations.append("🌿 Jó környezeti választás")
        
        if similarity_score > 0.3:
            explanations.append(f"🎯 Nagy hasonlóság ({similarity_score:.1%})")
        
        if 'Vegán' in recipe.get('category', ''):
            explanations.append("🌱 100% növényi alapú")
        
    except Exception as e:
        debug_log(f"❌ Magyarázat hiba: {e}")
    
    return explanations

# HTML Template
TEMPLATE_BASE = """
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🍃 GreenRec - Fenntartható Receptajánló</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; }
        .recipe-card { margin-bottom: 1rem; cursor: pointer; transition: all 0.3s; border: none; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .recipe-card:hover { transform: translateY(-3px); box-shadow: 0 6px 12px rgba(0,0,0,0.15); }
        .score-badge { margin: 0.2rem; padding: 0.4rem 0.8rem; border-radius: 20px; font-size: 0.85rem; font-weight: 600; }
        .score-esi { background: linear-gradient(135deg, #e3f2fd, #bbdefb); color: #1565c0; }
        .score-hsi { background: linear-gradient(135deg, #f3e5f5, #e1bee7); color: #6a1b9a; }
        .score-ppi { background: linear-gradient(135deg, #e8f5e8, #c8e6c9); color: #2e7d32; }
        .explanation { background-color: #fff3e0; padding: 0.8rem; border-radius: 8px; margin-top: 0.5rem; border-left: 4px solid #ff9800; }
    </style>
</head>
<body>
    <div class="container mt-4">
        <header class="text-center mb-4">
            <h1>🍃 GreenRec</h1>
            <p class="text-muted">Fenntartható Receptajánló Rendszer</p>
        </header>
        
        <div class="mb-4">
            <form method="POST" action="/search">
                <div class="input-group">
                    <input type="text" class="form-control" name="query" 
                           placeholder="Keresés összetevők alapján (pl. paradicsom, mozzarella)..." 
                           value="{{ query or '' }}">
                    <button class="btn btn-success" type="submit">🔍 Keresés</button>
                </div>
            </form>
        </div>
        
        {% if recipes %}
        <div class="mb-4">
            <h3>{{ title }}</h3>
            <p class="text-muted">{{ recipes|length }} találat</p>
        </div>
        
        <div class="row">
            {% for recipe in recipes %}
            <div class="col-md-6 col-lg-4">
                <div class="card recipe-card" onclick="selectRecipe({{ recipe.id }})">
                    {% if recipe.image and recipe.image != '' %}
                    <img src="{{ recipe.image }}" class="card-img-top" style="height: 200px; object-fit: cover;" onerror="this.style.display='none'">
                    {% endif %}
                    <div class="card-body">
                        <h5 class="card-title">{{ recipe.name }}</h5>
                        
                        {% if group in ['scores_visible', 'explanations'] %}
                        <div class="mb-3">
                            <span class="score-badge score-esi">ESI: {{ (recipe.esi) | round | int }}</span>
                            <span class="score-badge score-hsi">HSI: {{ (recipe.hsi) | round | int }}</span>
                            <span class="score-badge score-ppi">PPI: {{ (recipe.ppi) | round | int }}</span>
                        </div>
                        {% endif %}
                        
                        <p class="card-text">
                            <strong>Kategória:</strong> {{ recipe.category }}<br>
                            <strong>Összetevők:</strong> {{ recipe.ingredients[:80] }}{% if recipe.ingredients|length > 80 %}...{% endif %}
                        </p>
                        
                        {% if group == 'explanations' and recipe.explanations %}
                        <div class="explanation">
                            <strong>💡 Miért ajánljuk?</strong><br>
                            {% for exp in recipe.explanations %}
                            <small>{{ exp }}</small><br>
                            {% endfor %}
                        </div>
                        {% endif %}
                        
                        <button class="btn btn-outline-success btn-sm" onclick="selectRecipe({{ recipe.id }})">
                            📖 Hasonló receptek
                        </button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="text-center">
            <h3>🔍 Keresés vagy Véletlenszerű Recept</h3>
            <p class="text-muted">Adjon meg összetevőket a keresőmezőben, vagy próbáljon ki egy véletlenszerű receptet!</p>
            <a href="/random" class="btn btn-success">🎲 Véletlenszerű recept</a>
            <a href="/analytics" class="btn btn-info">📊 Analytics</a>
            <a href="/debug" class="btn btn-secondary">🔍 Debug</a>
        </div>
        {% endif %}
    </div>
    
    <script>
        function selectRecipe(recipeId) {
            fetch('/api/behavior', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: 'recipe_click', recipe_id: recipeId})
            });
            
            window.location.href = '/recommend/' + recipeId;
        }
    </script>
</body>
</html>
"""

# ===== FLASK ROUTES =====

@app.route('/')
def index():
    try:
        user_id = session.get('user_id')
        if not user_id:
            user_id = f"user_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
            session['user_id'] = user_id
        
        group = get_user_group(user_id)
        log_behavior(user_id, 'page_visit', {'page': 'index'})
        
        return render_template_string(TEMPLATE_BASE, group=group, recipes=None, title="Kezdőlap")
    except Exception as e:
        debug_log(f"❌ Index hiba: {e}")
        return f"<div class='container mt-4'><h3>❌ Hiba: {e}</h3><a href='/debug'>Debug info</a></div>"

@app.route('/search', methods=['POST'])
def search():
    try:
        user_id = session.get('user_id')
        query = request.form.get('query', '').strip()
        
        if not query:
            return redirect('/')
        
        log_behavior(user_id, 'search', {'query': query})
        
        if recipes_df is None:
            load_recipes()
            if recipes_df is None:
                return "<div class='container mt-4'><h3>❌ Adatok nem elérhetők.</h3><a href='/debug'>Debug info</a></div>"
        
        # Keresés
        mask = recipes_df['ingredients_text'].str.contains(query, case=False, na=False, regex=False)
        found_recipes = recipes_df[mask].head(12)
        
        group = get_user_group(user_id)
        results = []
        
        for _, recipe in found_recipes.iterrows():
            recipe_data = {
                'id': int(recipe['id']),
                'name': str(recipe['name']),
                'category': str(recipe['category']),
                'ingredients': str(recipe['ingredients_text']),
                'image': str(recipe['image']),
                'esi': float(recipe['esi']),
                'hsi': float(recipe['hsi']),
                'ppi': float(recipe['ppi'])
            }
            
            if group == 'explanations':
                recipe_data['explanations'] = [
                    f"🔍 Találat: '{query}' az összetevők között",
                    f"📂 Kategória: {recipe['category']}",
                    "🌱 Fenntartható választás"
                ]
            
            results.append(recipe_data)
        
        return render_template_string(TEMPLATE_BASE,
                                    group=group,
                                    recipes=results,
                                    query=query,
                                    title=f"Keresési eredmények: '{query}'")
                                    
    except Exception as e:
        debug_log(f"❌ Keresési hiba: {e}")
        return f"<div class='container mt-4'><h3>❌ Keresési hiba: {e}</h3><a href='/'>Vissza</a></div>"

@app.route('/recommend/<int:recipe_id>')
def recommend(recipe_id):
    try:
        user_id = session.get('user_id')
        log_behavior(user_id, 'get_recommendations', {'recipe_id': recipe_id})
        
        recommendations = get_recommendations(recipe_id, n=6)
        group = get_user_group(user_id)
        
        if group == 'explanations':
            for rec in recommendations:
                rec['explanations'] = generate_explanation(rec, rec['similarity'])
        
        original_recipe = recipes_df[recipes_df['id'] == recipe_id]
        original_name = original_recipe['name'].iloc[0] if len(original_recipe) > 0 else f"Recept #{recipe_id}"
        
        return render_template_string(TEMPLATE_BASE,
                                    group=group,
                                    recipes=recommendations,
                                    title=f"Ajánlások: '{original_name}' alapján")
                                    
    except Exception as e:
        debug_log(f"❌ Ajánlási hiba: {e}")
        return f"<div class='container mt-4'><h3>❌ Ajánlási hiba: {e}</h3><a href='/'>Vissza</a></div>"

@app.route('/random')
def random_recipe():
    try:
        user_id = session.get('user_id')
        
        if recipes_df is None or len(recipes_df) == 0:
            return redirect('/')
        
        random_id = recipes_df.sample(1)['id'].iloc[0]
        log_behavior(user_id, 'random_recipe', {'recipe_id': int(random_id)})
        
        return redirect(f'/recommend/{random_id}')
        
    except Exception as e:
        debug_log(f"❌ Random hiba: {e}")
        return redirect('/')

@app.route('/api/behavior', methods=['POST'])
def api_behavior():
    try:
        user_id = session.get('user_id')
        data = request.json
        
        if user_id and data:
            log_behavior(user_id, data.get('action', 'unknown'), data)
            return jsonify({'status': 'ok'})
        
        return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
        
    except Exception as e:
        debug_log(f"❌ Behavior API hiba: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/analytics')
def analytics():
    try:
        if not behavior_data:
            return """
            <div class='container mt-4'>
                <h3>📊 Nincs még elegendő adat az elemzéshez</h3>
                <p>Várjon, amíg több felhasználó használja a rendszert.</p>
                <a href='/' class='btn btn-success'>🏠 Vissza a főoldalra</a>
            </div>
            """
        
        df = pd.DataFrame(behavior_data)
        
        group_stats = df.groupby('group').agg({
            'user_id': 'nunique',
            'action': 'count'
        }).rename(columns={'user_id': 'unique_users', 'action': 'total_actions'})
        
        action_stats = df.groupby(['group', 'action']).size().unstack(fill_value=0)
        recent_events = df.tail(20)[['timestamp', 'group', 'action', 'user_id']].copy()
        recent_events['timestamp'] = pd.to_datetime(recent_events['timestamp']).dt.strftime('%H:%M:%S')
        
        # JAVÍTOTT HTML string - minden syntax error elhárítva
        html_parts = []
        html_parts.append("""
        <div class='container mt-4'>
            <h2>📊 GreenRec A/B/C Teszt Analytics</h2>
            <div class='row mt-4'>
                <div class='col-md-6'>
                    <h4>👥 Csoportonkénti statisztikák:</h4>
        """)
        html_parts.append(group_stats.to_html(classes='table table-striped table-sm'))
        html_parts.append("""
                </div>
                <div class='col-md-6'>
                    <h4>🔄 Akciók csoportonként:</h4>
        """)
        html_parts.append(action_stats.to_html(classes='table table-striped table-sm'))
        html_parts.append("""
                </div>
            </div>
            
            <div class='mt-4'>
                <h4>📈 Legutóbbi 20 esemény:</h4>
        """)
        html_parts.append(recent_events.to_html(classes='table table-striped table-sm', index=False))
        html_parts.append("""
            </div>
            
            <div class="mt-4">
                <a href="/" class="btn btn-success me-2">🏠 Vissza a főoldalra</a>
                <a href="/export-data" class="btn btn-info me-2">💾 Adatok exportálása</a>
                <a href="/status" class="btn btn-outline-secondary">ℹ️ Rendszer állapot</a>
            </div>
        </div>
        """)
        
        return ''.join(html_parts)
        
    except Exception as e:
        debug_log(f"❌ Analytics hiba: {e}")
        return f"<div class='container mt-4'><h3>❌ Analytics hiba: {e}</h3></div>"

@app.route('/export-data')
def export_data():
    try:
        export = {
            'timestamp': datetime.now().isoformat(),
            'total_behaviors': len(behavior_data),
            'behaviors': behavior_data[-1000:],
            'metadata': {
                'recipes_count': len(recipes_df) if recipes_df is not None else 0,
                'app_version': '1.0.0-heroku-final-fix',
                'deployment': 'heroku'
            }
        }
        return jsonify(export)
        
    except Exception as e:
        debug_log(f"❌ Export hiba: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/debug')
def debug():
    """Debug információk megjelenítése - TELJES JAVÍTÁS"""
    try:
        debug_info = {
            'load_debug_messages': load_debug_messages[-50:],
            'recipes_loaded': recipes_df is not None,
            'recipes_count': len(recipes_df) if recipes_df is not None else 0,
            'tfidf_ready': tfidf_matrix is not None,
            'working_directory': os.getcwd(),
            'files_in_directory': os.listdir(os.getcwd()),
            'json_file_exists': os.path.exists('greenrec_dataset.json'),
            'json_file_size': os.path.getsize('greenrec_dataset.json') if os.path.exists('greenrec_dataset.json') else 0
        }
        
        # JAVÍTOTT HTML építés - részekre bontva
        html_parts = []
        
        html_parts.append("""
        <div class='container mt-4'>
            <h2>🔍 GreenRec Debug Information</h2>
            
            <div class='row mt-4'>
                <div class='col-12'>
                    <h4>📋 Debug üzenetek:</h4>
                    <div class='alert alert-info'>
                        <pre style='max-height: 400px; overflow-y: auto;'>
        """)
        
        for msg in debug_info['load_debug_messages']:
            html_parts.append(f"{msg}\n")
        
        html_parts.append("""
                        </pre>
                    </div>
                </div>
            </div>
            
            <div class='row mt-4'>
                <div class='col-md-6'>
                    <h4>📊 Rendszer állapot:</h4>
                    <ul class='list-group'>
        """)
        
        # Állapot információk
        status_items = [
            f"<li class='list-group-item'>Receptek betöltve: {'✅' if debug_info['recipes_loaded'] else '❌'}</li>",
            f"<li class='list-group-item'>Receptek száma: {debug_info['recipes_count']}</li>",
            f"<li class='list-group-item'>TF-IDF kész: {'✅' if debug_info['tfidf_ready'] else '❌'}</li>",
            f"<li class='list-group-item'>JSON fájl létezik: {'✅' if debug_info['json_file_exists'] else '❌'}</li>",
            f"<li class='list-group-item'>JSON fájl mérete: {debug_info['json_file_size']} byte</li>"
        ]
        
        for item in status_items:
            html_parts.append(item)
        
        html_parts.append("""
                    </ul>
                </div>
                <div class='col-md-6'>
                    <h4>📁 Fájlok:</h4>
                    <ul class='list-group' style='max-height: 300px; overflow-y: auto;'>
        """)
        
        for file in debug_info['files_in_directory']:
            html_parts.append(f"<li class='list-group-item'>{file}</li>")
        
        html_parts.append("""
                    </ul>
                </div>
            </div>
            
            <div class="mt-4">
                <a href="/" class="btn btn-success me-2">🏠 Vissza a főoldalra</a>
                <a href="/status" class="btn btn-info me-2">📊 Status JSON</a>
            </div>
        </div>
        """)
        
        return ''.join(html_parts)
        
    except Exception as e:
        return f"<div class='container mt-4'><h3>Debug hiba: {e}</h3></div>"

@app.route('/status')
def status():
    try:
        status_info = {
            'receptek_betoltve': recipes_df is not None,
            'receptek_szama': len(recipes_df) if recipes_df is not None else 0,
            'viselkedesi_adatok': len(behavior_data),
            'algoritmus_kesz': tfidf_matrix is not None,
            'utolso_frissites': datetime.now().isoformat(),
            'deployment': 'heroku-final-fix',
            'python_version': os.sys.version,
            'flask_version': '2.3.3',
            'debug_messages_count': len(load_debug_messages),
            'debug_info': {
                'working_directory': os.getcwd(),
                'files_in_directory': os.listdir(os.getcwd()) if os.path.exists(os.getcwd()) else 'N/A',
                'recipes_df_columns': list(recipes_df.columns) if recipes_df is not None else 'N/A',
                'tfidf_shape': str(tfidf_matrix.shape) if tfidf_matrix is not None else 'N/A',
                'json_file_exists': os.path.exists('greenrec_dataset.json'),
                'json_file_size': os.path.getsize('greenrec_dataset.json') if os.path.exists('greenrec_dataset.json') else 0,
                'last_debug_messages': load_debug_messages[-10:] if load_debug_messages else []
            }
        }
        
        return jsonify(status_info)
        
    except Exception as e:
        debug_log(f"❌ DEBUG: Status hiba: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

# Error handlers - JAVÍTOTT
@app.errorhandler(404)
def not_found(error):
    return """
    <div class='container mt-4 text-center'>
        <h3>❌ Oldal nem található</h3>
        <p>A keresett oldal nem elérhető.</p>
        <a href='/' class='btn btn-success'>🏠 Vissza a főoldalra</a>
    </div>
    """, 404
