# app.py - GreenRec az Ön JSON struktúrájához optimalizálva
"""
GreenRec - Fenntartható Receptajánló Rendszer
Optimalizálva a valós GreenRec JSON formátumhoz
"""

from flask import Flask, render_template_string, request, session, jsonify
import json
import pandas as pd
import numpy as np
import hashlib
from datetime import datetime
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler

# Flask alkalmazás inicializálása
app = Flask(__name__)
app.secret_key = 'greenrec-secret-key-2024'

# Globális változók
recipes_df = None
vectorizer = None
ingredients_matrix = None
user_behaviors = []

def load_json_data(filename='greenrec_dataset.json'):
    """JSON adatok betöltése és DataFrame-é alakítása - valós struktúrához"""
    global recipes_df, vectorizer, ingredients_matrix
    
    try:
        print(f"📂 JSON fájl betöltése: {filename}")
        
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Az Ön JSON-ja egy lista objektumokat tartalmaz
        if isinstance(data, list):
            recipes_data = data
        else:
            raise ValueError("A JSON fájl nem lista formátumú")
        
        # DataFrame létrehozása
        recipes_df = pd.DataFrame(recipes_data)
        
        print(f"📊 Eredeti oszlopok: {list(recipes_df.columns)}")
        
        # Oszlop nevének standardizálása az Ön struktúrájához
        column_mapping = {
            'recipeid': 'id',
            'title': 'title',
            'ingredients': 'ingredients', 
            'instructions': 'instructions',
            'ESI': 'ESI',
            'HSI': 'HSI',
            'PPI': 'PPI',
            'category': 'category',
            'images': 'image_url'
        }
        
        # Oszlopok átnevezése ha szükséges
        recipes_df = recipes_df.rename(columns=column_mapping)
        
        # Kötelező oszlopok ellenőrzése
        required_columns = ['title', 'ingredients', 'HSI', 'ESI', 'PPI']
        missing_columns = [col for col in required_columns if col not in recipes_df.columns]
        
        if missing_columns:
            print(f"❌ Hiányzó kötelező oszlopok: {missing_columns}")
            return False
        
        # Adattisztítás
        recipes_df = recipes_df.dropna(subset=['title', 'ingredients'])
        
        # ID oszlop kezelése
        if 'id' not in recipes_df.columns and 'recipeid' in recipes_df.columns:
            recipes_df['id'] = recipes_df['recipeid']
        elif 'id' not in recipes_df.columns:
            recipes_df['id'] = range(1, len(recipes_df) + 1)
        
        # Pontszámok normalizálása 0-1 közé (mivel az eredeti értékek nagyobbak lehetnek)
        print("🔧 Pontszámok normalizálása...")
        scaler = MinMaxScaler()
        score_columns = ['HSI', 'ESI', 'PPI']
        
        # Ellenőrizzük a pontszámok tartományát
        for col in score_columns:
            print(f"   {col}: {recipes_df[col].min():.2f} - {recipes_df[col].max():.2f}")
        
        recipes_df[score_columns] = scaler.fit_transform(recipes_df[score_columns])
        
        # Content-based filtering előkészítés
        print("🤖 Content-based filtering modell építése...")
        vectorizer = CountVectorizer(
            max_features=1000, 
            stop_words='english',
            token_pattern=r'\b[a-zA-ZáéíóöőúüűÁÉÍÓÖŐÚÜŰ]+\b'  # Magyar karakterek támogatása
        )
        
        # Összetevők előfeldolgozása
        ingredients_text = recipes_df['ingredients'].fillna('').astype(str)
        ingredients_matrix = vectorizer.fit_transform(ingredients_text)
        
        print(f"✅ Sikeresen betöltve {len(recipes_df)} recept")
        print(f"📊 Végső oszlopok: {list(recipes_df.columns)}")
        print(f"🔤 Szótár mérete: {len(vectorizer.get_feature_names_out())} szó")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ JSON fájl nem található: {filename}")
        create_sample_json(filename)
        return False
    except Exception as e:
        print(f"❌ Hiba a JSON betöltésekor: {e}")
        return False

def create_sample_json(filename='greenrec_dataset.json'):
    """Minta JSON fájl létrehozása az Ön struktúrájának megfelelően"""
    print(f"📝 Minta JSON fájl létrehozása: {filename}")
    
    sample_data = [
        {
            "recipeid": 1,
            "title": "Mediterrán Saláta",
            "ingredients": "paradicsom, mozzarella sajt, bazsalikom, olívaolaj, balzsamecet",
            "instructions": "Vágd fel a paradicsomot és a mozzarellát. Keverd össze bazsalikommal, olívaolajjal és balzsamecettel.",
            "ESI": 180.5,
            "HSI": 75.2,
            "PPI": 85,
            "category": "Saláta",
            "images": "https://example.com/salad.jpg"
        },
        {
            "recipeid": 2,
            "title": "Quinoa Buddha Bowl",
            "ingredients": "quinoa, avokádó, spenót, édesburgonya, csicseriborsó, tahini",
            "instructions": "Főzd meg a quinoát. Süsd meg az édesburgonyát. Keverd össze minden összetevőt tahini szósszal.",
            "ESI": 120.8,
            "HSI": 92.1,
            "PPI": 78,
            "category": "Vegán",
            "images": "https://example.com/bowl.jpg"
        },
        {
            "recipeid": 3,
            "title": "Sült Lazac Brokkolival",
            "ingredients": "lazac filé, brokkoli, citrom, fokhagyma, olívaolaj, rozmaring",
            "instructions": "Süsd meg a lazacot olívaolajjal és rozmaringgal. Párold a brokkolit fokhagymával.",
            "ESI": 250.3,
            "HSI": 88.7,
            "PPI": 92,
            "category": "Hal",
            "images": "https://example.com/salmon.jpg"
        }
    ]
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(sample_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Minta JSON fájl létrehozva: {filename}")

def assign_user_group(user_id):
    """Felhasználó A/B/C csoportba sorolása"""
    hash_val = int(hashlib.md5(str(user_id).encode()).hexdigest(), 16) % 3
    groups = ['A', 'B', 'C']
    return groups[hash_val]

def log_behavior(user_id, action, data=None):
    """Felhasználói viselkedés naplózása"""
    behavior = {
        'timestamp': datetime.now().isoformat(),
        'user_id': user_id,
        'group': session.get('group', 'unknown'),
        'action': action,
        'data': data or {}
    }
    user_behaviors.append(behavior)

def recommend_hybrid(user_input, top_n=8):
    """Hibrid ajánlómotor - Content-based + Sustainability scoring"""
    global recipes_df, vectorizer, ingredients_matrix
    
    if recipes_df is None or vectorizer is None:
        return []
    
    try:
        # Content-based filtering
        input_vec = vectorizer.transform([user_input])
        similarity = cosine_similarity(input_vec, ingredients_matrix).flatten()
        
        # Másolat készítése
        results = recipes_df.copy()
        results['similarity'] = similarity
        
        # Composite score számítása (súlyozott kombináció)
        def composite_score(row, w_esi=0.4, w_hsi=0.4, w_ppi=0.2):
            return w_ppi * row['PPI'] + w_hsi * row['HSI'] + w_esi * row['ESI']
        
        results['sustainability_score'] = results.apply(composite_score, axis=1)
        results['final_score'] = results['similarity'] * 0.5 + results['sustainability_score'] * 0.5
        
        # Top N eredmény
        top_results = results.nlargest(top_n, 'final_score')
        
        return top_results.to_dict('records')
        
    except Exception as e:
        print(f"Hiba az ajánláskor: {e}")
        return recipes_df.head(top_n).to_dict('records') if recipes_df is not None else []

def generate_explanation(recipe):
    """XAI magyarázatok generálása C csoportnak"""
    explanations = []
    
    # Egészségügyi magyarázat
    if recipe['HSI'] > 0.7:
        explanations.append("💚 Kiváló egészségügyi értékkel rendelkezik")
    elif recipe['HSI'] > 0.4:
        explanations.append("🟡 Közepes egészségügyi értékkel")
    
    # Környezeti magyarázat
    if recipe['ESI'] > 0.7:
        explanations.append("🌱 Alacsony környezeti terheléssel")
    elif recipe['ESI'] > 0.4:
        explanations.append("🟢 Mérsékelt környezeti hatással")
    
    # Személyes preferencia
    if recipe['PPI'] > 0.7:
        explanations.append("⭐ Az Ön preferenciáinak megfelelő")
    elif recipe['PPI'] > 0.4:
        explanations.append("👍 Megfelelhet az Ön ízlésének")
    
    # Kategória alapú magyarázat
    if 'category' in recipe and recipe['category']:
        explanations.append(f"🏷️ {recipe['category']} kategóriájú recept")
    
    return explanations

# HTML Template-ek
HOME_TEMPLATE = """
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GreenRec - Fenntartható Receptajánló</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .group-indicator { position: fixed; top: 10px; right: 10px; z-index: 1000; }
        .recipe-card { transition: transform 0.2s; margin-bottom: 1rem; }
        .recipe-card:hover { transform: translateY(-2px); }
        .score-badge { text-align: center; padding: 0.5rem; border: 1px solid #dee2e6; border-radius: 0.375rem; margin-bottom: 0.5rem; }
        .score-value { font-size: 1.1rem; font-weight: bold; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-success">
        <div class="container">
            <a class="navbar-brand" href="/">🍃 GreenRec</a>
            <div class="navbar-nav">
                <a class="nav-link text-white" href="/status">🔧 Státusz</a>
                <a class="nav-link text-white" href="/analytics">📊 Analytics</a>
            </div>
        </div>
    </nav>
    
    {% if group %}
    <div class="group-indicator">
        <span class="badge bg-secondary">Teszt Csoport: {{ group }}</span>
    </div>
    {% endif %}
    
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="text-center mb-4">
                    <h1>🍃 GreenRec Fenntartható Receptajánló</h1>
                    <p class="lead">Adja meg kedvenc összetevőit a fenntartható receptajánlásokért!</p>
                    
                    {% if group %}
                    <div class="alert alert-info">
                        <strong>🧪 A/B/C Teszt - Csoport {{ group }}:</strong>
                        {% if group == 'A' %}Alapvető felület{% elif group == 'B' %}Fenntarthatósági pontszámokkal{% else %}AI magyarázatokkal{% endif %}
                    </div>
                    {% endif %}
                </div>
                
                <form method="POST" action="/recommend" class="mb-4">
                    <div class="input-group input-group-lg">
                        <input type="text" name="query" class="form-control" 
                               placeholder="pl: paradicsom, mozzarella, bazsalikom" 
                               required>
                        <button type="submit" class="btn btn-success">🔍 Ajánlás kérése</button>
                    </div>
                </form>
                
                <div class="row text-center">
                    <div class="col-md-4">
                        <h5>📊 {{ total_recipes }}</h5>
                        <p>Elérhető recept</p>
                    </div>
                    <div class="col-md-4">
                        <h5>👥 {{ total_users }}</h5>
                        <p>Aktív felhasználó</p>
                    </div>
                    <div class="col-md-4">
                        <h5>🔍 {{ total_searches }}</h5>
                        <p>Keresés elvégezve</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

RESULTS_TEMPLATE_A = """
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Receptajánlások - GreenRec</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .recipe-card { transition: transform 0.2s; margin-bottom: 1rem; }
        .recipe-card:hover { transform: translateY(-2px); }
        .group-indicator { position: fixed; top: 10px; right: 10px; z-index: 1000; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-success">
        <div class="container">
            <a class="navbar-brand" href="/">🍃 GreenRec</a>
        </div>
    </nav>
    
    <div class="group-indicator">
        <span class="badge bg-secondary">Csoport: A</span>
    </div>
    
    <div class="container mt-4">
        <h2>📋 Receptajánlások</h2>
        <p class="text-muted">Keresés: "{{ query }}" - {{ results|length }} ajánlás</p>
        
        <div class="row">
            {% for recipe in results %}
            <div class="col-md-6 mb-3">
                <div class="card recipe-card">
                    {% if recipe.image_url %}
                    <img src="{{ recipe.image_url }}" class="card-img-top" style="height: 200px; object-fit: cover;" alt="{{ recipe.title }}">
                    {% endif %}
                    <div class="card-body">
                        <h5 class="card-title">{{ recipe.title }}</h5>
                        <p class="card-text">
                            <strong>Összetevők:</strong> {{ recipe.ingredients[:100] }}...
                        </p>
                        {% if recipe.category %}
                        <span class="badge bg-primary">{{ recipe.category }}</span>
                        {% endif %}
                        <p class="card-text mt-2">
                            <small class="text-muted">Ajánlási pontszám: {{ "%.2f" | format(recipe.final_score) }}</small>
                        </p>
                        <button onclick="rateRecipe({{ recipe.id }})" class="btn btn-primary btn-sm">
                            👍 Tetszik
                        </button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        
        <div class="text-center mt-4">
            <a href="/" class="btn btn-outline-success">🔙 Új keresés</a>
        </div>
    </div>
    
    <script>
    function rateRecipe(recipeId) {
        fetch('/rate/' + recipeId)
            .then(response => response.json())
            .then(data => {
                event.target.textContent = '✅ Értékelve';
                event.target.disabled = true;
            });
    }
    </script>
</body>
</html>
"""

RESULTS_TEMPLATE_B = """
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Receptajánlások - GreenRec</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .recipe-card { transition: transform 0.2s; margin-bottom: 1rem; }
        .recipe-card:hover { transform: translateY(-2px); }
        .group-indicator { position: fixed; top: 10px; right: 10px; z-index: 1000; }
        .score-badge { text-align: center; padding: 0.5rem; border: 1px solid #dee2e6; border-radius: 0.375rem; }
        .score-value { font-size: 1.1rem; font-weight: bold; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-success">
        <div class="container">
            <a class="navbar-brand" href="/">🍃 GreenRec</a>
        </div>
    </nav>
    
    <div class="group-indicator">
        <span class="badge bg-secondary">Csoport: B</span>
    </div>
    
    <div class="container mt-4">
        <h2>📋 Receptajánlások pontszámokkal</h2>
        <p class="text-muted">Keresés: "{{ query }}" - {{ results|length }} ajánlás</p>
        
        <div class="row">
            {% for recipe in results %}
            <div class="col-md-6 mb-3">
                <div class="card recipe-card">
                    {% if recipe.image_url %}
                    <img src="{{ recipe.image_url }}" class="card-img-top" style="height: 200px; object-fit: cover;" alt="{{ recipe.title }}">
                    {% endif %}
                    <div class="card-body">
                        <h5 class="card-title">{{ recipe.title }}</h5>
                        
                        <!-- Fenntarthatósági pontszámok -->
                        <div class="row text-center mb-3">
                            <div class="col-4">
                                <div class="score-badge">
                                    <div class="score-value text-danger">{{ (recipe.HSI * 100) | round | int }}%</div>
                                    <small>Egészség</small>
                                </div>
                            </div>
                            <div class="col-4">
                                <div class="score-badge">
                                    <div class="score-value text-success">{{ (recipe.ESI * 100) | round | int }}%</div>
                                    <small>Környezet</small>
                                </div>
                            </div>
                            <div class="col-4">
                                <div class="score-badge">
                                    <div class="score-value text-info">{{ (recipe.PPI * 100) | round | int }}%</div>
                                    <small>Személyes</small>
                                </div>
                            </div>
                        </div>
                        
                        <p class="card-text">
                            <strong>Összetevők:</strong> {{ recipe.ingredients[:100] }}...
                        </p>
                        {% if recipe.category %}
                        <span class="badge bg-primary">{{ recipe.category }}</span>
                        {% endif %}
                        <p class="card-text mt-2">
                            <small class="text-muted">Végső pontszám: {{ "%.2f" | format(recipe.final_score) }}</small>
                        </p>
                        <button onclick="rateRecipe({{ recipe.id }})" class="btn btn-primary btn-sm">
                            👍 Tetszik
                        </button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        
        <div class="text-center mt-4">
            <a href="/" class="btn btn-outline-success">🔙 Új keresés</a>
        </div>
    </div>
    
    <script>
    function rateRecipe(recipeId) {
        fetch('/rate/' + recipeId)
            .then(response => response.json())
            .then(data => {
                event.target.textContent = '✅ Értékelve';
                event.target.disabled = true;
            });
    }
    </script>
</body>
</html>
"""

RESULTS_TEMPLATE_C = """
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Receptajánlások - GreenRec</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .recipe-card { transition: transform 0.2s; margin-bottom: 1rem; }
        .recipe-card:hover { transform: translateY(-2px); }
        .group-indicator { position: fixed; top: 10px; right: 10px; z-index: 1000; }
        .score-badge { text-align: center; padding: 0.5rem; border: 1px solid #dee2e6; border-radius: 0.375rem; }
        .score-value { font-size: 1.1rem; font-weight: bold; }
        .explanation-box { background: #f8f9fa; border-left: 4px solid #28a745; padding: 1rem; margin: 1rem 0; border-radius: 0.25rem; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-success">
        <div class="container">
            <a class="navbar-brand" href="/">🍃 GreenRec</a>
        </div>
    </nav>
    
    <div class="group-indicator">
        <span class="badge bg-secondary">Csoport: C</span>
    </div>
    
    <div class="container mt-4">
        <h2>📋 Receptajánlások magyarázatokkal</h2>
        <p class="text-muted">Keresés: "{{ query }}" - {{ results|length }} ajánlás</p>
        
        <div class="row">
            {% for recipe in results %}
            <div class="col-md-6 mb-3">
                <div class="card recipe-card">
                    {% if recipe.image_url %}
                    <img src="{{ recipe.image_url }}" class="card-img-top" style="height: 200px; object-fit: cover;" alt="{{ recipe.title }}">
                    {% endif %}
                    <div class="card-body">
                        <h5 class="card-title">{{ recipe.title }}</h5>
                        
                        <!-- Fenntarthatósági pontszámok -->
                        <div class="row text-center mb-3">
                            <div class="col-4">
                                <div class="score-badge">
                                    <div class="score-value text-danger">{{ (recipe.HSI * 100) | round | int }}%</div>
                                    <small>Egészség</small>
                                </div>
                            </div>
                            <div class="col-4">
                                <div class="score-badge">
                                    <div class="score-value text-success">{{ (recipe.ESI * 100) | round | int }}%</div>
                                    <small>Környezet</small>
                                </div>
                            </div>
                            <div class="col-4">
                                <div class="score-badge">
                                    <div class="score-value text-info">{{ (recipe.PPI * 100) | round | int }}%</div>
                                    <small>Személyes</small>
                                </div>
                            </div>
                        </div>
                        
                        <!-- XAI Magyarázatok -->
                        {% if explanations and loop.index0 < explanations|length %}
                        <div class="explanation-box">
                            <strong>💡 Miért ajánljuk:</strong>
                            <ul class="mb-0 mt-1">
                                {% for explanation in explanations[loop.index0] %}
                                <li><small>{{ explanation }}</small></li>
                                {% endfor %}
                            </ul>
                        </div>
                        {% endif %}
                        
                        <p class="card-text">
                            <strong>Összetevők:</strong> {{ recipe.ingredients[:100] }}...
                        </p>
                        {% if recipe.category %}
                        <span class="badge bg-primary">{{ recipe.category }}</span>
                        {% endif %}
                        <p class="card-text mt-2">
                            <small class="text-muted">Végső pontszám: {{ "%.2f" | format(recipe.final_score) }}</small>
                        </p>
                        <button onclick="rateRecipe({{ recipe.id }})" class="btn btn-primary btn-sm">
                            👍 Tetszik
                        </button>
                        <button onclick="rateExplanation({{ recipe.id }}, true)" class="btn btn-outline-secondary btn-sm">
                            💬 Hasznos magyarázat
                        </button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        
        <div class="text-center mt-4">
            <a href="/" class="btn btn-outline-success">🔙 Új keresés</a>
        </div>
    </div>
    
    <script>
    function rateRecipe(recipeId) {
        fetch('/rate/' + recipeId)
            .then(response => response.json())
            .then(data => {
                event.target.textContent = '✅ Értékelve';
                event.target.disabled = true;
            });
    }

    function rateExplanation(recipeId, helpful) {
        fetch('/explanation-feedback/' + recipeId + '/' + helpful)
            .then(response => response.json())
            .then(data => {
                event.target.textContent = helpful ? '✅ Hasznos' : '❌ Nem hasznos';
                event.target.disabled = true;
            });
    }
    </script>
</body>
</html>
"""

# Flask Route-ok
@app.route('/')
def home():
    """Főoldal"""
    # Felhasználó azonosítás és csoportosítás
    if 'user_id' not in session:
        session['user_id'] = hashlib.md5(str(request.environ.get('REMOTE_ADDR', 'anonymous')).encode()).hexdigest()[:8]
        session['group'] = assign_user_group(session['user_id'])
    
    # Statisztikák
    stats = {
        'total_recipes': len(recipes_df) if recipes_df is not None else 0,
        'total_users': len(set(b['user_id'] for b in user_behaviors)) if user_behaviors else 1,
        'total_searches': len([b for b in user_behaviors if b['action'] == 'search'])
    }
    
    # Viselkedés naplózása
    log_behavior(session['user_id'], 'page_view', {'page': 'home'})
    
    return render_template_string(HOME_TEMPLATE, 
                                group=session['group'],
                                **stats)

@app.route('/recommend', methods=['POST'])
def recommend():
    """Ajánlás generálás"""
    query = request.form.get('query', '').strip()
    user_id = session.get('user_id')
    group = session.get('group')
    
    if not query:
