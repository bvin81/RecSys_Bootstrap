# app.py - GreenRec Complete Debug Version
"""
GreenRec - Fenntartható Receptajánló Rendszer
TELJES DEBUG verzió hibakeresési információkkal és fallback adatokkal
"""
import os
from flask import Flask, request, render_template_string, session, jsonify, redirect
import pandas as pd
import numpy as np
import json
import hashlib
import time
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Flask app inicializálás
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'greenrec-secret-key-2024')

# Globális változók
recipes_df = None
tfidf_matrix = None
vectorizer = None
behavior_data = []

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
    """JSON receptek betöltése - DEBUG verzióval"""
    global recipes_df, tfidf_matrix, vectorizer
    
    print("🔍 DEBUG: load_recipes() indítása...")
    
    try:
        # Working directory ellenőrzése
        current_dir = os.getcwd()
        print(f"📁 DEBUG: Current working directory: {current_dir}")
        
        # Fájlok listázása
        files_in_dir = os.listdir(current_dir)
        print(f"📋 DEBUG: Fájlok a working directory-ban: {files_in_dir}")
        
        # Lehetséges JSON fájl nevek ellenőrzése
        possible_files = [
            'greenrec_dataset.json',
            'greenrec-dataset.json', 
            'dataset.json',
            'recipes.json',
            'data.json'
        ]
        
        json_data = None
        used_file = None
        
        # Fájlok próbálgatása
        for filename in possible_files:
            full_path = os.path.join(current_dir, filename)
            print(f"🔍 DEBUG: Próbálkozás: {full_path}")
            
            if os.path.exists(full_path):
                print(f"✅ DEBUG: Fájl megtalálva: {filename}")
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        json_content = f.read()
                        print(f"📄 DEBUG: Fájl mérete: {len(json_content)} karakter")
                        print(f"📄 DEBUG: Első 200 karakter: {json_content[:200]}...")
                        
                    # JSON parsing
                    with open(full_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
                        print(f"✅ DEBUG: JSON sikeresen betöltve: {type(json_data)}")
                        
                    used_file = filename
                    break
                    
                except json.JSONDecodeError as e:
                    print(f"❌ DEBUG: JSON parse hiba {filename}-ben: {e}")
                    continue
                except Exception as e:
                    print(f"❌ DEBUG: Hiba {filename} beolvasásakor: {e}")
                    continue
            else:
                print(f"❌ DEBUG: Fájl nem található: {full_path}")
        
        # Ha nincs JSON fájl, készítsünk minta adatokat
        if json_data is None:
            print("🔄 DEBUG: Nincs JSON fájl, minta adatok létrehozása...")
            json_data = create_fallback_data()
            used_file = "built-in fallback data"
        
        # JSON struktúra elemzése
        print(f"🔍 DEBUG: JSON adatok típusa: {type(json_data)}")
        
        # JSON struktúra kezelése
        if isinstance(json_data, list):
            recipes = json_data
            print(f"✅ DEBUG: JSON array, {len(recipes)} elem")
        elif isinstance(json_data, dict) and 'recipes' in json_data:
            recipes = json_data['recipes']
            print(f"✅ DEBUG: JSON object 'recipes' kulccsal, {len(recipes)} elem")
        elif isinstance(json_data, dict):
            recipes = [json_data]  # Single recipe case
            print("✅ DEBUG: Egyetlen recipe object")
        else:
            raise ValueError(f"Ismeretlen JSON struktúra: {type(json_data)}")
        
        print(f"📊 DEBUG: Talált receptek száma: {len(recipes)}")
        
        if len(recipes) > 0:
            print(f"📝 DEBUG: Első recept kulcsai: {list(recipes[0].keys())}")
            print(f"📝 DEBUG: Első recept: {recipes[0]}")
        
        # DataFrame létrehozása
        recipes_df = pd.DataFrame(recipes)
        print(f"📊 DEBUG: DataFrame létrehozva: {recipes_df.shape}")
        
        # Oszlopok normalizálása
        print("🔄 DEBUG: Oszlopok normalizálása...")
        recipes_df['id'] = recipes_df.get('recipeid', range(len(recipes_df)))
        recipes_df['name'] = recipes_df.get('title', 'Névtelen recept')
        recipes_df['ingredients_text'] = recipes_df.get('ingredients', '')
        recipes_df['instructions'] = recipes_df.get('instructions', '')
        
        # Numerikus oszlopok
        print("🔄 DEBUG: Numerikus oszlopok feldolgozása...")
        recipes_df['esi'] = pd.to_numeric(recipes_df.get('ESI', 0), errors='coerce').fillna(0)
        recipes_df['hsi'] = pd.to_numeric(recipes_df.get('HSI', 0), errors='coerce').fillna(0)
        recipes_df['ppi'] = pd.to_numeric(recipes_df.get('PPI', 0), errors='coerce').fillna(0)
        
        recipes_df['category'] = recipes_df.get('category', 'Egyéb')
        recipes_df['image'] = recipes_df.get('images', '')
        
        print(f"📋 DEBUG: Végleges DataFrame oszlopok: {list(recipes_df.columns)}")
        print(f"📝 DEBUG: Első recept név: {recipes_df.iloc[0]['name'] if len(recipes_df) > 0 else 'N/A'}")
        print(f"📊 DEBUG: ESI értékek: min={recipes_df['esi'].min()}, max={recipes_df['esi'].max()}")
        print(f"📊 DEBUG: HSI értékek: min={recipes_df['hsi'].min()}, max={recipes_df['hsi'].max()}")
        
        # Content-based filtering: TF-IDF matrix
        if len(recipes_df) > 0:
            print("🤖 DEBUG: TF-IDF mátrix létrehozása...")
            vectorizer = TfidfVectorizer(
                max_features=1000, 
                stop_words=None,
                lowercase=True,
                token_pattern=r'\b\w+\b'
            )
            
            ingredients_texts = recipes_df['ingredients_text'].fillna('')
            print(f"📝 DEBUG: Első összetevő szöveg: {ingredients_texts.iloc[0][:100]}...")
            
            tfidf_matrix = vectorizer.fit_transform(ingredients_texts)
            print(f"🤖 DEBUG: TF-IDF mátrix létrehozva: {tfidf_matrix.shape}")
            print(f"🤖 DEBUG: Vocabulary mérete: {len(vectorizer.vocabulary_)}")
        
        print(f"✅ DEBUG: Sikeres betöltés! Forrás: {used_file}")
        print(f"✅ DEBUG: Végleges receptek száma: {len(recipes_df)}")
        return True
        
    except Exception as e:
        print(f"❌ DEBUG: Kritikus hiba a receptek betöltésekor: {e}")
        import traceback
        print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")
        
        # Fallback: mindig hozzon létre minta adatokat hiba esetén
        print("🔄 DEBUG: Fallback minta adatok létrehozása...")
        try:
            fallback_data = create_fallback_data()
            recipes_df = pd.DataFrame(fallback_data)
            
            # Oszlopok normalizálása
            recipes_df['id'] = recipes_df.get('recipeid', range(len(recipes_df)))
            recipes_df['name'] = recipes_df.get('title', 'Névtelen recept')
            recipes_df['ingredients_text'] = recipes_df.get('ingredients', '')
            recipes_df['instructions'] = recipes_df.get('instructions', '')
            recipes_df['esi'] = pd.to_numeric(recipes_df.get('ESI', 0), errors='coerce').fillna(0)
            recipes_df['hsi'] = pd.to_numeric(recipes_df.get('HSI', 0), errors='coerce').fillna(0)
            recipes_df['ppi'] = pd.to_numeric(recipes_df.get('PPI', 0), errors='coerce').fillna(0)
            recipes_df['category'] = recipes_df.get('category', 'Egyéb')
            recipes_df['image'] = recipes_df.get('images', '')
            
            # TF-IDF
            vectorizer = TfidfVectorizer(max_features=1000, stop_words=None, lowercase=True, token_pattern=r'\b\w+\b')
            tfidf_matrix = vectorizer.fit_transform(recipes_df['ingredients_text'].fillna(''))
            
            print(f"✅ DEBUG: Fallback sikeres! Receptek: {len(recipes_df)}")
            return True
            
        except Exception as fallback_error:
            print(f"❌ DEBUG: Fallback is sikertelen: {fallback_error}")
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
        
        # Memory management
        if len(behavior_data) > 10000:
            behavior_data[:5000] = []
            
    except Exception as e:
        print(f"❌ DEBUG: Hiba a behavior logging-nál: {e}")

def get_recommendations(recipe_id, n=5):
    """Content-based ajánlások hibrid algoritmussal"""
    try:
        if recipes_df is None or tfidf_matrix is None:
            print("❌ DEBUG: Hiányzó adatok az ajánlásokhoz")
            return []
        
        recipe_idx = recipes_df[recipes_df['id'] == recipe_id].index
        if len(recipe_idx) == 0:
            print(f"❌ DEBUG: Nem található recept ID: {recipe_id}")
            return []
        
        recipe_idx = recipe_idx[0]
        print(f"🎯 DEBUG: Ajánlások generálása recipe #{recipe_id} alapján (index: {recipe_idx})")
        
        # Cosine similarity számítás
        cosine_sim = cosine_similarity(tfidf_matrix[recipe_idx:recipe_idx+1], tfidf_matrix).flatten()
        
        # Hibrid scoring
        max_esi = recipes_df['esi'].max() if recipes_df['esi'].max() > 0 else 1
        max_hsi = recipes_df['hsi'].max() if recipes_df['hsi'].max() > 0 else 1
        
        esi_norm = recipes_df['esi'] / max_esi
        hsi_norm = recipes_df['hsi'] / max_hsi
        sustainability_score = (esi_norm + hsi_norm) / 2
        
        # Kombinált pontszám
        hybrid_scores = 0.6 * cosine_sim + 0.4 * sustainability_score
        
        # Top N ajánlás
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
        
        print(f"✅ DEBUG: {len(recommendations)} ajánlás generálva")
        return recommendations
        
    except Exception as e:
        print(f"❌ DEBUG: Hiba az ajánlások generálásánál: {e}")
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
        print(f"❌ DEBUG: Hiba a magyarázat generálásánál: {e}")
    
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
        .recipe-card { 
            margin-bottom: 1rem; 
            cursor: pointer; 
            transition: all 0.3s;
            border: none;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .recipe-card:hover { 
            transform: translateY(-3px); 
            box-shadow: 0 6px 12px rgba(0,0,0,0.15); 
        }
        .score-badge { 
            margin: 0.2rem; 
            padding: 0.4rem 0.8rem; 
            border-radius: 20px; 
            font-size: 0.85rem;
            font-weight: 600;
        }
        .score-esi { background: linear-gradient(135deg, #e3f2fd, #bbdefb); color: #1565c0; }
        .score-hsi { background: linear-gradient(135deg, #f3e5f5, #e1bee7); color: #6a1b9a; }
        .score-ppi { background: linear-gradient(135deg, #fff3e0, #ffe0b2); color: #ef6c00; }
        .explanation { 
            background: linear-gradient(135deg, #e8f5e8, #c8e6c9);
            border-left: 4px solid #4caf50; 
            padding: 0.8rem; 
            margin: 0.8rem 0;
            border-radius: 0 8px 8px 0;
        }
        .group-indicator { 
            position: fixed; 
            top: 15px; 
            right: 15px; 
            padding: 0.6rem 1rem; 
            border-radius: 25px; 
            font-size: 0.9rem;
            font-weight: bold;
            z-index: 1000;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }
        .group-control { background: linear-gradient(135deg, #f44336, #d32f2f); color: white; }
        .group-scores_visible { background: linear-gradient(135deg, #ff9800, #f57c00); color: white; }
        .group-explanations { background: linear-gradient(135deg, #4caf50, #388e3c); color: white; }
        .search-section { 
            background: white; 
            padding: 2rem; 
            border-radius: 15px; 
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }
        .header { 
            text-align: center; 
            margin-bottom: 2rem;
            background: linear-gradient(135deg, #4caf50, #81c784);
            color: white;
            padding: 2rem;
            border-radius: 15px;
        }
    </style>
</head>
<body>
    <div class="group-indicator group-{{ group }}">
        {{ group.upper() }} Csoport
    </div>
    
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
                    <button class="btn btn-success" type="submit">
                        🔍 Keresés
                    </button>
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
                    <img src="{{ recipe.image }}" class="card-img-top" 
                         style="height: 200px; object-fit: cover;" 
                         onerror="this.style.display='none'">
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
                        <small class="text-success">
                            <strong>Hasonlóság: {{ (recipe.similarity * 100) | round }}%</strong>
                        </small>
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
            <a href="/export-data" class="btn btn-outline-primary">💾 Adatok exportálása</a>
        </div>
        
        <footer class="mt-5 text-center text-muted">
            <small>GreenRec - Fenntartható Receptajánló Kutatás | Powered by Heroku</small>
        </footer>
    </div>
    
    <script>
        function selectRecipe(recipeId) {
            fetch('/api/behavior', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    action: 'recipe_click',
                    recipe_id: recipeId
                })
            }).catch(e => console.log('Tracking error:', e));
            
            setTimeout(() => {
                window.location.href = '/recommend/' + recipeId;
            }, 100);
        }
        
        fetch('/api/behavior', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                action: 'page_view',
                page: window.location.pathname
            })
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
        
        return render_template_string(TEMPLATE_BASE, 
                                    group=group, 
                                    recipes=None, 
                                    title="Kezdőlap")
    except Exception as e:
        print(f"❌ DEBUG: Hiba az index oldalon: {e}")
        return f"<h3>❌ Hiba történt: {e}</h3><a href='/status'>Rendszer állapot ellenőrzése</a>"

@app.route('/search', methods=['POST'])
def search():
    try:
        user_id = session.get('user_id')
        query = request.form.get('query', '').strip()
        
        print(f"🔍 DEBUG: Keresési kérés: '{query}' - User: {user_id}")
        
        if not query:
            return redirect('/')
        
        log_behavior(user_id, 'search', {'query': query})
        
        if recipes_df is None:
            print("❌ DEBUG: recipes_df is None!")
            return "❌ Adatok nem elérhetők. <a href='/status'>Rendszer állapot ellenőrzése</a>"
        
        print(f"📊 DEBUG: Keresés a {len(recipes_df)} receptben...")
        
        # Keresés az összetevőkben
        mask = recipes_df['ingredients_text'].str.contains(query, case=False, na=False, regex=False)
        found_recipes = recipes_df[mask].head(12)
        
        print(f"📋 DEBUG: {len(found_recipes)} találat")
        
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
        
        print(f"✅ DEBUG: {len(results)} eredmény visszaadva")
        
        return render_template_string(TEMPLATE_BASE,
                                    group=group,
                                    recipes=results,
                                    query=query,
                                    title=f"Keresési eredmények: '{query}'")
                                    
    except Exception as e:
        print(f"❌ DEBUG: Hiba a keresésben: {e}")
        import traceback
        print(f"🔍 DEBUG: Search traceback: {traceback.format_exc()}")
        return f"<h3>❌ Keresési hiba: {e}</h3><a href='/'>Vissza a főoldalra</a>"

@app.route('/recommend/<int:recipe_id>')
def recommend(recipe_id):
    try:
        user_id = session.get('user_id')
        log_behavior(user_id, 'get_recommendations', {'recipe_id': recipe_id})
        
        print(f"🎯 DEBUG: Ajánlások kérése recipe ID: {recipe_id}")
        
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
        print(f"❌ DEBUG: Hiba az ajánlásokban: {e}")
        return f"<h3>❌ Ajánlási hiba: {e}</h3><a href='/'>Vissza a főoldalra</a>"

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
        print(f"❌ DEBUG: Hiba a random receptnél: {e}")
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
        print(f"❌ DEBUG: Hiba a behavior API-ban: {e}")
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
        print(f"❌ DEBUG: Hiba az analytics-ben: {e}")
        return f"<div class='container mt-4'><h3>❌ Analytics hiba: {e}</h3><a href='/'>Vissza a főoldalra</a></div>"

@app.route('/export-data')
def export_data():
    try:
        export = {
            'timestamp': datetime.now().isoformat(),
            'total_behaviors': len(behavior_data),
            'behaviors': behavior_data[-1000:],
            'metadata': {
                'recipes_count': len(recipes_df) if recipes_df is not None else 0,
                'app_version': '1.0.0-heroku-debug',
                'deployment': 'heroku'
            }
        }
        return jsonify(export)
        
    except Exception as e:
        print(f"❌ DEBUG: Hiba az export-nál: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def status():
    try:
        status_info = {
            'receptek_betoltve': recipes_df is not None,
            'receptek_szama': len(recipes_df) if recipes_df is not None else 0,
            'viselkedesi_adatok': len(behavior_data),
            'algoritmus_kesz': tfidf_matrix is not None,
            'utolso_frissites': datetime.now().isoformat(),
            'deployment': 'heroku-debug',
            'python_version': os.sys.version,
            'flask_version': '2.3.3',
            'debug_info': {
                'working_directory': os.getcwd(),
                'files_in_directory': os.listdir(os.getcwd()) if os.path.exists(os.getcwd()) else 'N/A',
                'recipes_df_columns': list(recipes_df.columns) if recipes_df is not None else 'N/A',
                'tfidf_shape': str(tfidf_matrix.shape) if tfidf_matrix is not None else 'N/A'
            }
        }
        
        return jsonify(status_info)
        
    except Exception as e:
        print(f"❌ DEBUG: Hiba a status-nál: {e}")
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
    
    print("🚀 GreenRec DEBUG verzió indítása...")
    print(f"🌐 Port: {port}")
    print(f"🔧 Debug mód: {debug}")
    
    # Receptek betöltése
    if load_recipes():
        print("✅ Rendszer kész!")
        print("🌐 Heroku URL-en elérhető")
    else:
        print("⚠️ Receptek betöltése részben sikertelen, de fallback adatokkal folytatjuk")
    
    app.run(debug=debug, host='0.0.0.0', port=port)
