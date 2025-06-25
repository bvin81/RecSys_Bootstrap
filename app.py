# app.py - GreenRec Logging Fix Version
"""
GreenRec - Fenntartható Receptajánló Rendszer
LOGGING FIX verzió - print helyett logging használat
"""
import os
import logging
from flask import Flask, request, render_template_string, session, jsonify, redirect
import pandas as pd
import numpy as np
import json
import hashlib
import time
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Logging konfiguráció
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask app inicializálás
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'greenrec-secret-key-2024')

# Globális változók
recipes_df = None
tfidf_matrix = None
vectorizer = None
behavior_data = []
load_debug_messages = []  # Debug üzenetek tárolása

def debug_log(message):
    """Debug üzenet logging és tárolás"""
    logger.info(message)
    load_debug_messages.append(f"{datetime.now().strftime('%H:%M:%S')} - {message}")
    print(message)  # Fallback

def create_fallback_data():
    """Minta adatok létrehozása ha nincs JSON"""
    return [
        {
            "recipeid": 317804,
            "title": "New Orleans-i töltött paprika",
            "ingredients": "fokhagyma gerezdek, lila hagyma, zeller, tojás, mozzarella sajt, paprika",
            "instructions": "Süsd meg a darált húst fokhagymával, hagymával és zellerrel...",
            "ESI": 216.9399893,
            "HSI": 70.88419297,
            "PPI": 75,
            "category": "Hús",
            "images": "https://img.sndimg.com/food/image/upload/w_555,h_416,c_fit,fl_progressive,q_95/v1/img/recipes/31/78/04/pic1jsSpC.jpg"
        },
        {
            "recipeid": 421807,
            "title": "Minestrone leves (Lassúfőzőben)",
            "ingredients": "marhacomb, marhahúsos pörkölt, víz, hagyma, só, kakukkfű, petrezselyem, fekete bors, paradicsom, cukkini, csicseriborsó, káposzta, parmezán sajt",
            "instructions": "Egy lassúfőzőben keverd össze a marhahúst vízzel...",
            "ESI": 206.1332885,
            "HSI": 57.49590336,
            "PPI": 90,
            "category": "Hüvelyesek",
            "images": "https://img.sndimg.com/food/image/upload/w_555,h_416,c_fit,fl_progressive,q_95/v1/img/recipes/42/18/07/picR5DDQr.jpg"
        },
        {
            "recipeid": 123456,
            "title": "Mediterrán saláta",
            "ingredients": "paradicsom, mozzarella sajt, bazsalikom, olívaolaj, balzsamecet",
            "instructions": "Vágd fel a paradicsomot és a mozzarellát. Keverd össze bazsalikommal, olívaolajjal és balzsamecettel.",
            "ESI": 45.2,
            "HSI": 85.3,
            "PPI": 88,
            "category": "Saláta",
            "images": "https://example.com/mediterranean-salad.jpg"
        },
        {
            "recipeid": 789012,
            "title": "Quinoa tál zöldségekkel",
            "ingredients": "quinoa, brokkoli, sárgarépa, cukkini, tahini, citrom",
            "instructions": "Főzd meg a quinoát. Párold a zöldségeket. Keverd össze tahini-citrom öntettel.",
            "ESI": 32.1,
            "HSI": 92.5,
            "PPI": 75,
            "category": "Vegán",
            "images": "https://example.com/quinoa-bowl.jpg"
        },
        {
            "recipeid": 345678,
            "title": "Spenótos-ricottás lasagne",
            "ingredients": "lasagne tészta, spenót, ricotta sajt, paradicsom szósz, mozzarella",
            "instructions": "Rétegelj tésztát, spenótot, ricottát és szószt. Süsd 40 percig 180 fokon.",
            "ESI": 158.7,
            "HSI": 68.2,
            "PPI": 82,
            "category": "Vegetáriánus",
            "images": "https://example.com/spinach-lasagne.jpg"
        }
    ]

def load_recipes():
    """JSON receptek betöltése - LOGGING verzióval"""
    global recipes_df, tfidf_matrix, vectorizer
    
    debug_log("🔍 DEBUG: load_recipes() indítása...")
    
    try:
        # Working directory ellenőrzése
        current_dir = os.getcwd()
        debug_log(f"📁 DEBUG: Current working directory: {current_dir}")
        
        # Fájlok listázása
        files_in_dir = os.listdir(current_dir)
        debug_log(f"📋 DEBUG: Fájlok a working directory-ban: {files_in_dir}")
        
        # JSON fájl keresése
        json_file_path = os.path.join(current_dir, 'greenrec_dataset.json')
        debug_log(f"🔍 DEBUG: JSON fájl keresése: {json_file_path}")
        
        if os.path.exists(json_file_path):
            debug_log("✅ DEBUG: greenrec_dataset.json megtalálva!")
            
            # Fájl méret ellenőrzése
            file_size = os.path.getsize(json_file_path)
            debug_log(f"📄 DEBUG: Fájl mérete: {file_size} byte")
            
            if file_size == 0:
                debug_log("❌ DEBUG: A JSON fájl üres!")
                raise ValueError("Üres JSON fájl")
            
            # JSON tartalom olvasása
            with open(json_file_path, 'r', encoding='utf-8') as f:
                json_content = f.read()
                debug_log(f"📄 DEBUG: Beolvasott tartalom hossza: {len(json_content)} karakter")
                debug_log(f"📄 DEBUG: Első 200 karakter: {json_content[:200]}...")
            
            # JSON parsing
            with open(json_file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
                debug_log(f"✅ DEBUG: JSON parse sikeres: {type(json_data)}")
                
                if isinstance(json_data, list):
                    debug_log(f"📊 DEBUG: JSON array {len(json_data)} elemmel")
                    recipes = json_data
                elif isinstance(json_data, dict):
                    debug_log("📊 DEBUG: JSON object formátum")
                    recipes = [json_data]  # Single recipe
                else:
                    raise ValueError(f"Váratlan JSON struktúra: {type(json_data)}")
        else:
            debug_log("❌ DEBUG: greenrec_dataset.json nem található!")
            debug_log("🔄 DEBUG: Fallback adatok használata...")
            recipes = create_fallback_data()
        
        debug_log(f"📊 DEBUG: Feldolgozandó receptek száma: {len(recipes)}")
        
        if len(recipes) == 0:
            debug_log("❌ DEBUG: Nincsenek receptek!")
            raise ValueError("Üres recipe lista")
        
        # DataFrame létrehozása
        debug_log("🔄 DEBUG: DataFrame létrehozása...")
        recipes_df = pd.DataFrame(recipes)
        debug_log(f"📊 DEBUG: DataFrame shape: {recipes_df.shape}")
        debug_log(f"📊 DEBUG: DataFrame oszlopok: {list(recipes_df.columns)}")
        
        # Oszlopok normalizálása
        debug_log("🔄 DEBUG: Oszlopok normalizálása...")
        recipes_df['id'] = recipes_df.get('recipeid', range(len(recipes_df)))
        recipes_df['name'] = recipes_df.get('title', 'Névtelen recept')
        recipes_df['ingredients_text'] = recipes_df.get('ingredients', '')
        recipes_df['instructions'] = recipes_df.get('instructions', '')
        
        # Numerikus oszlopok
        debug_log("🔄 DEBUG: Numerikus oszlopok konvertálása...")
        recipes_df['esi'] = pd.to_numeric(recipes_df.get('ESI', 0), errors='coerce').fillna(0)
        recipes_df['hsi'] = pd.to_numeric(recipes_df.get('HSI', 0), errors='coerce').fillna(0)
        recipes_df['ppi'] = pd.to_numeric(recipes_df.get('PPI', 0), errors='coerce').fillna(0)
        
        recipes_df['category'] = recipes_df.get('category', 'Egyéb')
        recipes_df['image'] = recipes_df.get('images', '')
        
        debug_log(f"📋 DEBUG: Végleges oszlopok: {list(recipes_df.columns)}")
        debug_log(f"📝 DEBUG: Első recept: {recipes_df.iloc[0]['name']}")
        debug_log(f"📊 DEBUG: ESI tartomány: {recipes_df['esi'].min()}-{recipes_df['esi'].max()}")
        debug_log(f"📊 DEBUG: HSI tartomány: {recipes_df['hsi'].min()}-{recipes_df['hsi'].max()}")
        
        # TF-IDF matrix létrehozása
        debug_log("🤖 DEBUG: TF-IDF mátrix építése...")
        vectorizer = TfidfVectorizer(
            max_features=1000, 
            stop_words=None,
            lowercase=True,
            token_pattern=r'\b\w+\b'
        )
        
        ingredients_texts = recipes_df['ingredients_text'].fillna('')
        debug_log(f"📝 DEBUG: TF-IDF input példa: {ingredients_texts.iloc[0][:100]}...")
        
        tfidf_matrix = vectorizer.fit_transform(ingredients_texts)
        debug_log(f"🤖 DEBUG: TF-IDF mátrix kész: {tfidf_matrix.shape}")
        debug_log(f"🤖 DEBUG: Vocabulary size: {len(vectorizer.vocabulary_)}")
        
        debug_log("✅ DEBUG: load_recipes() SIKERES!")
        debug_log(f"✅ DEBUG: Végleges receptek száma: {len(recipes_df)}")
        return True
        
    except Exception as e:
        debug_log(f"❌ DEBUG: KRITIKUS HIBA: {str(e)}")
        debug_log(f"❌ DEBUG: Exception type: {type(e).__name__}")
        
        import traceback
        traceback_str = traceback.format_exc()
        debug_log(f"🔍 DEBUG: Traceback: {traceback_str}")
        
        # Utolsó próbálkozás: fallback adatok
        debug_log("🔄 DEBUG: Utolsó próba - tiszta fallback...")
        try:
            fallback_recipes = create_fallback_data()
            recipes_df = pd.DataFrame(fallback_recipes)
            
            # Gyors normalizálás
            recipes_df['id'] = recipes_df['recipeid']
            recipes_df['name'] = recipes_df['title']
            recipes_df['ingredients_text'] = recipes_df['ingredients']
            recipes_df['instructions'] = recipes_df['instructions']
            recipes_df['esi'] = recipes_df['ESI']
            recipes_df['hsi'] = recipes_df['HSI'] 
            recipes_df['ppi'] = recipes_df['PPI']
            recipes_df['category'] = recipes_df['category']
            recipes_df['image'] = recipes_df['images']
            
            # TF-IDF
            vectorizer = TfidfVectorizer(max_features=100, stop_words=None, lowercase=True, token_pattern=r'\b\w+\b')
            tfidf_matrix = vectorizer.fit_transform(recipes_df['ingredients_text'])
            
            debug_log("✅ DEBUG: Fallback sikeres!")
            return True
            
        except Exception as fallback_error:
            debug_log(f"❌ DEBUG: Fallback is hibás: {str(fallback_error)}")
            return False

def get_user_group(user_id):
    """A/B/C csoport meghatározása determinisztikus hash alapján"""
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
        debug_log(f"❌ DEBUG: Behavior logging hiba: {e}")

def get_recommendations(recipe_id, n=5):
    """Content-based ajánlások hibrid algoritmussal"""
    try:
        if recipes_df is None or tfidf_matrix is None:
            debug_log("❌ DEBUG: Hiányzó adatok az ajánlásokhoz")
            return []
        
        recipe_idx = recipes_df[recipes_df['id'] == recipe_id].index
        if len(recipe_idx) == 0:
            debug_log(f"❌ DEBUG: Nem található recept ID: {recipe_id}")
            return []
        
        recipe_idx = recipe_idx[0]
        
        # Cosine similarity
        cosine_sim = cosine_similarity(tfidf_matrix[recipe_idx:recipe_idx+1], tfidf_matrix).flatten()
        
        # Hibrid scoring
        max_esi = recipes_df['esi'].max() if recipes_df['esi'].max() > 0 else 1
        max_hsi = recipes_df['hsi'].max() if recipes_df['hsi'].max() > 0 else 1
        
        esi_norm = recipes_df['esi'] / max_esi
        hsi_norm = recipes_df['hsi'] / max_hsi
        sustainability_score = (esi_norm + hsi_norm) / 2
        
        hybrid_scores = 0.6 * cosine_sim + 0.4 * sustainability_score
        similar_indices = hybrid_scores.argsort()[::-1][1:n+1]
        
        recommendations = []
        for idx in similar_indices:
            if idx < len(recipes_df):
                rec = recipes_df.iloc[idx]
                recommendations.append({
                    'id': int(rec['id']),
                    'name': str(rec['name']),
                    'similarity': float(cosine_sim[idx]),
                    'esi': float(rec['esi']),
                    'hsi': float(rec['hsi']),
                    'ppi': float(rec['ppi']),
                    'category': str(rec['category']),
                    'image': str(rec['image']),
                    'ingredients': str(rec['ingredients_text'])
                })
        
        return recommendations
        
    except Exception as e:
        debug_log(f"❌ DEBUG: Ajánlás hiba: {e}")
        return []

def generate_explanation(recipe, similarity_score):
    """XAI magyarázat generálása C csoportnak"""
    explanations = []
    
    try:
        if recipe['hsi'] > 70:
            explanations.append("✅ Egészséges választás: magas egészségügyi pontszám")
        elif recipe['hsi'] > 50:
            explanations.append("⚖️ Kiegyensúlyozott egészségügyi érték")
        
        if recipe['esi'] < 100:
            explanations.append("🌱 Környezetbarát: alacsony környezeti hatás")
        elif recipe['esi'] < 200:
            explanations.append("🌿 Mérsékelt környezeti hatás")
        
        if similarity_score > 0.3:
            explanations.append(f"🎯 Nagy hasonlóság az összetevők alapján ({similarity_score:.1%})")
        
        category = recipe.get('category', '')
        if 'Vegán' in category:
            explanations.append("🌱 100% növényi alapú recept")
        elif 'Vegetáriánus' in category:
            explanations.append("🥗 Vegetáriánus-barát választás")
        
    except Exception as e:
        debug_log(f"❌ DEBUG: Magyarázat hiba: {e}")
    
    return explanations

# HTML Template (egyszerűsített)
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
        .score-ppi { background: linear-gradient(135deg, #fff3e0, #ffe0b2); color: #ef6c00; }
        .explanation { background: linear-gradient(135deg, #e8f5e8, #c8e6c9); border-left: 4px solid #4caf50; padding: 0.8rem; margin: 0.8rem 0; border-radius: 0 8px 8px 0; }
        .group-indicator { position: fixed; top: 15px; right: 15px; padding: 0.6rem 1rem; border-radius: 25px; font-size: 0.9rem; font-weight: bold; z-index: 1000; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
        .group-control { background: linear-gradient(135deg, #f44336, #d32f2f); color: white; }
        .group-scores_visible { background: linear-gradient(135deg, #ff9800, #f57c00); color: white; }
        .group-explanations { background: linear-gradient(135deg, #4caf50, #388e3c); color: white; }
        .search-section { background: white; padding: 2rem; border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-bottom: 2rem; }
        .header { text-align: center; margin-bottom: 2rem; background: linear-gradient(135deg, #4caf50, #81c784); color: white; padding: 2rem; border-radius: 15px; }
    </style>
</head>
<body>
    <div class="group-indicator group-{{ group }}">{{ group.upper() }} Csoport</div>
    
    <div class="container mt-4">
        <div class="header">
            <h1>🍃 GreenRec</h1>
            <p class="mb-0">Fenntartható Receptajánló Rendszer</p>
        </div>
        
        <div class="search-section">
            <form method="POST" action="/search">
                <div class="input-group input-group-lg">
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
                        
                        {% if recipe.similarity %}
                        <small class="text-success"><strong>Hasonlóság: {{ (recipe.similarity * 100) | round }}%</strong></small>
                        {% endif %}
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="text-center mt-5">
            <div class="card" style="max-width: 600px; margin: 0 auto;">
                <div class="card-body">
                    <h3>🎯 Üdvözöljük a GreenRec rendszerben!</h3>
                    <p>Kezdjen el keresni fenntartható recepteket az összetevők alapján.</p>
                    <div class="mt-3">
                        <span class="badge bg-success me-2">Egészséges</span>
                        <span class="badge bg-info me-2">Környezetbarát</span>
                        <span class="badge bg-warning">Ízletes</span>
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
        
        <div class="mt-5 text-center">
            <a href="/random" class="btn btn-outline-success me-2">🎲 Véletlenszerű recept</a>
            <a href="/analytics" class="btn btn-outline-info me-2">📊 Statisztikák</a>
            <a href="/status" class="btn btn-outline-secondary me-2">ℹ️ Rendszer állapot</a>
            <a href="/debug" class="btn btn-outline-warning me-2">🔍 Debug info</a>
        </div>
    </div>
    
    <script>
        function selectRecipe(recipeId) {
            fetch('/api/behavior', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ action: 'recipe_click', recipe_id: recipeId })
            }).catch(e => console.log('Tracking error:', e));
            
            setTimeout(() => { window.location.href = '/recommend/' + recipeId; }, 100);
        }
        
        fetch('/api/behavior', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action: 'page_view', page: window.location.pathname })
        }).catch(e => console.log('Tracking error:', e));
    </script>
</body>
</html>
"""

# Routes
@app.route('/')
def index():
    try:
        user_id = session.get('user_id', str(int(time.time() * 1000)))
        session['user_id'] = user_id
        
        group = get_user_group(user_id)
        log_behavior(user_id, 'page_visit', {'page': 'index'})
        
        return render_template_string(TEMPLATE_BASE, group=group, recipes=None, title="Kezdőlap")
    except Exception as e:
        debug_log(f"❌ DEBUG: Index hiba: {e}")
        return f"<h3>❌ Hiba: {e}</h3><a href='/status'>Status</a>"

@app.route('/search', methods=['POST'])
def search():
    try:
        user_id = session.get('user_id')
        query = request.form.get('query', '').strip()
        
        debug_log(f"🔍 DEBUG: Keresés: '{query}'")
        
        if not query:
            return redirect('/')
        
        log_behavior(user_id, 'search', {'query': query})
        
        if recipes_df is None:
            debug_log("❌ DEBUG: recipes_df is None a keresésben!")
            return "❌ Adatok nem elérhetők. <a href='/debug'>Debug info</a>"
        
        # Keresés
        mask = recipes_df['ingredients_text'].str.contains(query, case=False, na=False, regex=False)
        found_recipes = recipes_df[mask].head(12)
        
        debug_log(f"📋 DEBUG: {len(found_recipes)} találat")
        
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
            
            # C csoport: magyarázatok hozzáadása
            if group == 'explanations':
                recipe_data['explanations'] = [
                    f"🔍 Találat: '{query}' az összetevők között",
                    f"📂 Kategória: {recipe['category']}",
                    "🌱 Fenntartható választás a GreenRec alapján"
                ]
            
            results.append(recipe_data)
        
        return render_template_string(TEMPLATE_BASE,
                                    group=group,
                                    recipes=results,
                                    query=query,
                                    title=f"Keresési eredmények: '{query}'")
                                    
    except Exception as e:
        debug_log(f"❌ DEBUG: Keresési hiba: {e}")
        return f"<h3>❌ Keresési hiba: {e}</h3><a href='/'>Vissza</a>"

@app.route('/recommend/<int:recipe_id>')
def recommend(recipe_id):
    try:
        user_id = session.get('user_id')
        log_behavior(user_id, 'get_recommendations', {'recipe_id': recipe_id})
        
        recommendations = get_recommendations(recipe_id, n=6)
        group = get_user_group(user_id)
        
        # C csoport: magyarázatok hozzáadása
        if group == 'explanations':
            for rec in recommendations:
                rec['explanations'] = generate_explanation(rec, rec['similarity'])
        
        # Eredeti recept információi
        original_recipe = recipes_df[recipes_df['id'] == recipe_id]
        original_name = original_recipe['name'].iloc[0] if len(original_recipe) > 0 else f"Recept #{recipe_id}"
        
        return render_template_string(TEMPLATE_BASE,
                                    group=group,
                                    recipes=recommendations,
                                    title=f"Ajánlások a(z) '{original_name}' alapján")
                                    
    except Exception as e:
        debug_log(f"❌ DEBUG: Ajánlási hiba: {e}")
        return f"<h3>❌ Ajánlási hiba: {e}</h3><a href='/'>Vissza</a>"

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
        debug_log(f"❌ DEBUG: Random hiba: {e}")
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
        debug_log(f"❌ DEBUG: Behavior API hiba: {e}")
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
        
        html = f"""
        <div class='container mt-4'>
            <h2>📊 GreenRec A/B/C Teszt Analytics</h2>
            <div class='row mt-4'>
                <div class='col-md-6'>
                    <h4>👥 Csoportonkénti statisztikák:</h4>
                    {group_stats.to_html(classes='table table-striped table-sm')}
                </div>
                <div class='col-md-6'>
                    <h4>🔄 Akciók csoportonként:</h4>
                    {action_stats.to_html(classes='table table-striped table-sm')}
                </div>
            </div>
            
            <div class='mt-4'>
                <h4>📈 Legutóbbi 20 esemény:</h4>
                {recent_events.to_html(classes='table table-striped table-sm', index=False)}
            </div>
            
            <div class="mt-4">
                <a href="/" class="btn btn-success me-2">🏠 Vissza a főoldalra</a>
                <a href="/export-data" class="btn btn-info me-2">💾 Adatok exportálása</a>
                <a href="/status" class="btn btn-outline-secondary">ℹ️ Rendszer állapot</a>
            </div>
        </div>
        """
        
        return html
        
    except Exception as e:
        debug_log(f"❌ DEBUG: Analytics hiba: {e}")
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
                'app_version': '1.0.0-heroku-logging',
                'deployment': 'heroku'
            }
        }
        return jsonify(export)
        
    except Exception as e:
        debug_log(f"❌ DEBUG: Export hiba: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/debug')
def debug():
    """Debug információk megjelenítése"""
    try:
        debug_info = {
            'load_debug_messages': load_debug_messages[-50:],  # Utolsó 50 üzenet
            'recipes_loaded': recipes_df is not None,
            'recipes_count': len(recipes_df) if recipes_df is not None else 0,
            'tfidf_ready': tfidf_matrix is not None,
            'working_directory': os.getcwd(),
            'files_in_directory': os.listdir(os.getcwd()),
            'json_file_exists': os.path.exists('greenrec_dataset.json'),
            'json_file_size': os.path.getsize('greenrec_dataset.json') if os.path.exists('greenrec_dataset.json') else 0
        }
        
        html = f"""
        <div class='container mt-4'>
            <h2>🔍 GreenRec Debug Information</h2>
            
            <div class='row mt-4'>
                <div class='col-12'>
                    <h4>📋 Debug üzenetek:</h4>
                    <div class='alert alert-info'>
                        <pre style='max-height: 400px; overflow-y: auto;'>
"""
        
        for msg in debug_info['load_debug_messages']:
            html += f"{msg}\n"
        
        html += f"""
                        </pre>
                    </div>
                </div>
            </div>
            
            <div class='row mt-4'>
                <div class='col-md-6'>
                    <h4>📊 Rendszer állapot:</h4>
                    <ul class='list-group'>
                        <li class='list-group-item'>Receptek betöltve: {'✅' if debug_info['recipes_loaded'] else '❌'}</li>
                        <li class='list-group-item'>Receptek száma: {debug_info['recipes_count']}</li>
                        <li class='list-group-item'>TF-IDF kész: {'✅' if debug_info['tfidf_ready'] else '❌'}</li>
                        <li class='list-group-item'>JSON fájl létezik: {'✅' if debug_info['json_file_exists'] else '❌'}</li>
                        <li class='list-group-item'>JSON fájl mérete: {debug_info['json_file_size']} byte</li>
                    </ul>
                </div>
                <div class='col-md-6'>
                    <h4>📁 Fájlok:</h4>
                    <ul class='list-group' style='max-height: 300px; overflow-y: auto;'>
"""
        
        for file in debug_info['files_in_directory']:
            html += f"<li class='list-group-item'>{file}</li>"
        
        html += f"""
                    </ul>
                </div>
            </div>
            
            <div class="mt-4">
                <a href="/" class="btn btn-success me-2">🏠 Vissza a főoldalra</a>
                <a href="/status" class="btn btn-info me-2">📊 Status JSON</a>
            </div>
        </div>
        """
        
        return html
        
    except Exception as e:
        return f"<h3>Debug hiba: {e}</h3>"

@app.route('/status')
def status():
    try:
        status_info = {
            'receptek_betoltve': recipes_df is not None,
            'receptek_szama': len(recipes_df) if recipes_df is not None else 0,
            'viselkedesi_adatok': len(behavior_data),
            'algoritmus_kesz': tfidf_matrix is not None,
            'utolso_frissites': datetime.now().isoformat(),
            'deployment': 'heroku-logging',
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

@app.errorhandler(404)
def not_found(error):
    return """
    <div class='container mt-4 text-center'>
        <h3>❌ Oldal nem található</h3>
        <p>A keresett oldal nem elérhető.</p>
        <a href='/' class='btn btn-success'>🏠 Vissza a főoldalra</a>
    </div>
    """, 404

@app.errorhandler(500)
def internal_error(error):
    return """
    <div class='container mt-4 text-center'>
        <h3>❌ Szerver hiba</h3>
        <p>Valami probléma merült fel. Próbálja újra később.</p>
        <a href='/' class='btn btn-success'>🏠 Vissza a főoldalra</a>
    </div>
    """, 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    
    debug_log("🚀 GreenRec LOGGING verzió indítása...")
    debug_log(f"🌐 Port: {port}")
    debug_log(f"🔧 Debug mód: {debug}")
    
    # Receptek betöltése
    load_success = load_recipes()
    if load_success:
        debug_log("✅ Alkalmazás kész!")
        debug_log("🌐 Heroku URL-en elérhető")
    else:
        debug_log("⚠️ Receptek betöltése sikertelen!")
    
    debug_log(f"📊 Végleges állapot: recipes_df={recipes_df is not None}, tfidf_matrix={tfidf_matrix is not None}")
    
    app.run(debug=debug, host='0.0.0.0', port=port)
