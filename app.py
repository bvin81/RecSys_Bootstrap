# app.py - GreenRec Heroku Production Version (FIXED)
"""
GreenRec - Fenntartható Receptajánló Rendszer
🚀 Heroku + PostgreSQL + GitHub Deployment Ready
✅ 3 tanulási kör (javított)
✅ Syntax error javítások
✅ Egyszerűsített template-ek
✅ A/B/C teszt A csoport rejtett pontszámokkal
"""

import os
import json
import random
import hashlib
import logging
from datetime import datetime
from collections import defaultdict, Counter

import pandas as pd
import numpy as np
from flask import Flask, request, jsonify, session, render_template_string
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# PostgreSQL import
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    print("⚠️ psycopg2 not available, using fallback storage")
    POSTGRES_AVAILABLE = False

# Flask alkalmazás inicializálása
app = Flask(__name__)

# 🔧 HEROKU KONFIGURÁCIÓ
app.secret_key = os.environ.get('SECRET_KEY', 'greenrec-fallback-secret-key-2025')

# Environment-based configuration
DEBUG_MODE = os.environ.get('FLASK_ENV') == 'development'
PORT = int(os.environ.get('PORT', 5000))

# PostgreSQL konfiguráció
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    # Heroku Postgres URL fix
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# ALKALMAZÁS KONSTANSOK (JAVÍTOTT)
RECOMMENDATION_COUNT = 5  # ✅ 5 recept ajánlás
RELEVANCE_THRESHOLD = 4   # Rating >= 4 = releváns
MAX_LEARNING_ROUNDS = 3   # ✅ 3 kör az 5 helyett
GROUP_ALGORITHMS = {
    'A': 'content_based', 
    'B': 'score_enhanced', 
    'C': 'hybrid_xai'
}

# Globális változók
recipes_df = None
tfidf_vectorizer = None
tfidf_matrix = None
user_sessions = {}
analytics_data = defaultdict(list)

# Logging setup
logging.basicConfig(
    level=logging.INFO if not DEBUG_MODE else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 🗄️ POSTGRESQL ADATBÁZIS FUNKCIÓK (EGYSZERŰSÍTETT)

def get_db_connection():
    """PostgreSQL kapcsolat létrehozása"""
    try:
        if DATABASE_URL and POSTGRES_AVAILABLE:
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            return conn
        else:
            return None
    except Exception as e:
        logger.error(f"❌ Adatbázis kapcsolat hiba: {str(e)}")
        return None

def init_database():
    """Adatbázis táblák inicializálása"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        # User sessions tábla
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id VARCHAR(100) PRIMARY KEY,
                user_group VARCHAR(1) NOT NULL,
                learning_round INTEGER DEFAULT 1,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Recipe ratings tábla
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recipe_ratings (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(100) NOT NULL,
                recipe_id VARCHAR(100) NOT NULL,
                rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
                learning_round INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, recipe_id, learning_round)
            )
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info("✅ PostgreSQL táblák inicializálva")
        return True
        
    except Exception as e:
        logger.error(f"❌ Adatbázis inicializálás hiba: {str(e)}")
        if conn:
            conn.rollback()
            conn.close()
        return False

def save_rating_db(user_id, recipe_id, rating, learning_round):
    """Értékelés mentése PostgreSQL-be"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO recipe_ratings (user_id, recipe_id, rating, learning_round)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, recipe_id, learning_round)
            DO UPDATE SET rating = %s, timestamp = CURRENT_TIMESTAMP
        """, (user_id, recipe_id, rating, learning_round, rating))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Rating mentés hiba: {str(e)}")
        if conn:
            conn.rollback()
            conn.close()
        return False

def get_user_ratings_db(user_id, learning_round=None):
    """Felhasználó értékeléseinek lekérése PostgreSQL-ből"""
    conn = get_db_connection()
    if not conn:
        return {}
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        if learning_round:
            cur.execute("""
                SELECT recipe_id, rating 
                FROM recipe_ratings 
                WHERE user_id = %s AND learning_round = %s
            """, (user_id, learning_round))
        else:
            cur.execute("""
                SELECT recipe_id, rating 
                FROM recipe_ratings 
                WHERE user_id = %s
            """, (user_id,))
        
        ratings = {row['recipe_id']: row['rating'] for row in cur.fetchall()}
        
        cur.close()
        conn.close()
        return ratings
        
    except Exception as e:
        logger.error(f"❌ Ratings lekérés hiba: {str(e)}")
        if conn:
            conn.close()
        return {}

# 🚀 ALKALMAZÁS INICIALIZÁLÁS (EGYSZERŰSÍTETT)

def ensure_initialized():
    """Rendszer inicializálása"""
    global recipes_df, tfidf_vectorizer, tfidf_matrix
    
    if recipes_df is None:
        logger.info("🚀 GreenRec rendszer inicializálása Heroku-n...")
        
        # PostgreSQL inicializálás
        if POSTGRES_AVAILABLE:
            init_database()
        
        try:
            # JSON fájl betöltése
            recipe_data = load_recipe_data()
            
            # DataFrame létrehozása
            recipes_df = pd.DataFrame(recipe_data)
            
            # ✅ ESI INVERZ NORMALIZÁLÁS
            if 'ESI' in recipes_df.columns:
                esi_min = recipes_df['ESI'].min()
                esi_max = recipes_df['ESI'].max()
                if esi_max > esi_min:
                    recipes_df['ESI_normalized'] = 100 * (recipes_df['ESI'] - esi_min) / (esi_max - esi_min)
                else:
                    recipes_df['ESI_normalized'] = 50
                
                # ✅ INVERZ ESI: 100 - normalizált_ESI
                recipes_df['ESI_final'] = 100 - recipes_df['ESI_normalized']
            else:
                recipes_df['ESI_final'] = np.random.uniform(30, 80, len(recipes_df))
            
            # HSI és PPI
            if 'HSI' not in recipes_df.columns:
                recipes_df['HSI'] = np.random.uniform(30, 95, len(recipes_df))
            if 'PPI' not in recipes_df.columns:
                recipes_df['PPI'] = np.random.uniform(20, 90, len(recipes_df))
            
            # ✅ KOMPOZIT PONTSZÁM
            recipes_df['composite_score'] = (
                recipes_df['ESI_final'] * 0.4 +
                recipes_df['HSI'] * 0.4 +
                recipes_df['PPI'] * 0.2
            ).round(1)
            
            ensure_required_columns()
            setup_tfidf()
            
            logger.info(f"✅ {len(recipes_df)} recept betöltve Heroku-n")
            logger.info(f"📊 Kompozit pontszám: {recipes_df['composite_score'].min():.1f} - {recipes_df['composite_score'].max():.1f}")
            
        except Exception as e:
            logger.error(f"❌ Inicializálási hiba: {str(e)}")
            recipes_df = pd.DataFrame(generate_demo_data())
            ensure_required_columns()
            setup_tfidf()

def load_recipe_data():
    """Recept adatok betöltése"""
    possible_files = [
        'greenrec_dataset.json',
        'data/greenrec_dataset.json', 
        'recipes.json'
    ]
    
    for filename in possible_files:
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"✅ Recept adatok betöltve: {filename}")
                return data
        except Exception as e:
            continue
    
    logger.warning("⚠️ Recept fájl nem található, demo adatok generálása...")
    return generate_demo_data()

def ensure_required_columns():
    """Szükséges oszlopok ellenőrzése"""
    global recipes_df
    
    if 'name' not in recipes_df.columns:
        recipes_df['name'] = [f"Recept {i+1}" for i in range(len(recipes_df))]
    if 'category' not in recipes_df.columns:
        categories = ['Főétel', 'Leves', 'Saláta', 'Desszert', 'Snack']
        recipes_df['category'] = [random.choice(categories) for _ in range(len(recipes_df))]
    if 'ingredients' not in recipes_df.columns:
        recipes_df['ingredients'] = ["hagyma, fokhagyma, paradicsom" for _ in range(len(recipes_df))]
    
    # ID oszlop
    if 'recipeid' not in recipes_df.columns and 'id' not in recipes_df.columns:
        recipes_df['recipeid'] = [f"recipe_{i+1}" for i in range(len(recipes_df))]

def setup_tfidf():
    """TF-IDF inicializálása"""
    global tfidf_vectorizer, tfidf_matrix
    
    try:
        content = []
        for _, recipe in recipes_df.iterrows():
            text = f"{recipe.get('name', '')} {recipe.get('category', '')} {recipe.get('ingredients', '')}"
            content.append(text.lower())
        
        tfidf_vectorizer = TfidfVectorizer(
            max_features=min(1000, len(content) * 10),
            stop_words=None,
            ngram_range=(1, 2)
        )
        tfidf_matrix = tfidf_vectorizer.fit_transform(content)
        logger.info("✅ TF-IDF mátrix inicializálva")
        
    except Exception as e:
        logger.error(f"❌ TF-IDF hiba: {str(e)}")

def generate_demo_data():
    """Demo adatok generálása"""
    categories = ['Főétel', 'Leves', 'Saláta', 'Desszert', 'Snack']
    ingredients_lists = [
        'hagyma, fokhagyma, paradicsom, paprika',
        'csirkemell, brokkoli, rizs, szójaszósz',
        'saláta, uborka, paradicsom, citrom',
        'tojás, liszt, cukor, vaj, vanília',
        'mandula, dió, méz, zabpehely',
        'avokádó, spenót, banán, chia mag'
    ]
    
    demo_recipes = []
    for i in range(100):
        demo_recipes.append({
            'recipeid': f'demo_recipe_{i+1}',
            'name': f'Demo Recept {i+1}',
            'category': random.choice(categories),
            'ingredients': random.choice(ingredients_lists),
            'ESI': random.uniform(10, 90),
            'HSI': random.uniform(30, 95),
            'PPI': random.uniform(20, 90)
        })
    
    return demo_recipes

# 🎯 FELHASZNÁLÓI FUNKCIÓK

def get_user_group(user_id):
    """Determinisztikus A/B/C csoport kiosztás"""
    hash_value = int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16)
    return ['A', 'B', 'C'][hash_value % 3]

def initialize_user_session():
    """Felhasználói session inicializálása"""
    if 'user_id' not in session:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        session['user_id'] = f"user_{timestamp}_{random.randint(1000, 9999)}"
        session['user_group'] = get_user_group(session['user_id'])
        session['learning_round'] = 1
        session['start_time'] = datetime.now().isoformat()
        
        logger.info(f"👤 Új felhasználó: {session['user_id']}, Csoport: {session['user_group']}")
    
    return session['user_id'], session['user_group'], session.get('learning_round', 1)

def get_personalized_recommendations(user_id, user_group, learning_round, n=5):
    """Személyre szabott ajánlások generálása"""
    ensure_initialized()
    
    if learning_round == 1:
        # Első kör: random receptek
        selected = recipes_df.sample(n=min(n, len(recipes_df)))
        logger.info(f"🎲 Random ajánlások (1. kör): {len(selected)} recept")
        return selected
    
    # 2+ kör: személyre szabott
    try:
        if POSTGRES_AVAILABLE:
            previous_ratings = get_user_ratings_db(user_id)
        else:
            previous_ratings = session.get('all_ratings', {})
        
        liked_recipe_ids = [rid for rid, rating in previous_ratings.items() if rating >= RELEVANCE_THRESHOLD]
        
        if not liked_recipe_ids:
            selected = recipes_df.nlargest(n, 'composite_score')
            logger.info(f"📊 Magas pontszámú ajánlások: {len(selected)} recept")
            return selected
        
        # Még nem értékelt receptek
        unrated_recipes = recipes_df[~recipes_df['recipeid'].isin(previous_ratings.keys())].copy()
        
        if len(unrated_recipes) == 0:
            selected = recipes_df.sample(n=min(n, len(recipes_df)))
            return selected
        
        # Csoportonkénti algoritmusok
        if user_group == 'A':
            # Content-based egyszerűsített
            selected = unrated_recipes.sample(n=min(n, len(unrated_recipes)))
        elif user_group == 'B':
            # Score-enhanced
            selected = unrated_recipes.nlargest(n, 'composite_score')
        else:  # Csoport C
            # Hybrid
            top_half = len(unrated_recipes) // 2
            high_score = unrated_recipes.nlargest(top_half, 'composite_score')
            selected = high_score.sample(n=min(n, len(high_score)))
        
        logger.info(f"🎯 Személyre szabott ajánlások ({user_group} csoport): {len(selected)} recept")
        return selected
        
    except Exception as e:
        logger.error(f"❌ Ajánlás hiba: {str(e)}")
        selected = recipes_df.sample(n=min(n, len(recipes_df)))
        return selected

# 🌐 FLASK ROUTE-OK (EGYSZERŰSÍTETT)

@app.route('/')
def index():
    """Főoldal - Egyszerűsített verzió"""
    ensure_initialized()
    user_id, user_group, learning_round = initialize_user_session()
    
    # Befejezés ellenőrzése
    if learning_round > MAX_LEARNING_ROUNDS:
        return redirect_to_results()
    
    # Ajánlások generálása
    recommendations = get_personalized_recommendations(
        user_id, user_group, learning_round, n=RECOMMENDATION_COUNT
    )
    
    # Jelenlegi kör értékelések
    if POSTGRES_AVAILABLE:
        current_ratings = get_user_ratings_db(user_id, learning_round)
    else:
        current_ratings = session.get('ratings', {})
    
    # HTML generálása
    html = generate_main_page_html(
        recommendations=recommendations.to_dict('records'),
        user_group=user_group,
        learning_round=learning_round,
        max_rounds=MAX_LEARNING_ROUNDS,
        rated_count=len(current_ratings)
    )
    
    return html

@app.route('/rate', methods=['POST'])
def rate_recipe():
    """Recept értékelése"""
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        rating = int(data.get('rating', 0))
        
        if not recipe_id or not (1 <= rating <= 5):
            return jsonify({'error': 'Érvénytelen adatok'}), 400
        
        user_id, user_group, learning_round = initialize_user_session()
        
        # PostgreSQL mentés
        if POSTGRES_AVAILABLE:
            save_rating_db(user_id, recipe_id, rating, learning_round)
            current_ratings = get_user_ratings_db(user_id, learning_round)
        else:
            # Session fallback
            if 'ratings' not in session:
                session['ratings'] = {}
            session['ratings'][recipe_id] = rating
            session.modified = True
            current_ratings = session['ratings']
        
        logger.info(f"⭐ Értékelés: {recipe_id} = {rating} csillag (Kör: {learning_round})")
        
        return jsonify({
            'success': True,
            'rated_count': len(current_ratings),
            'total_needed': RECOMMENDATION_COUNT
        })
        
    except Exception as e:
        logger.error(f"❌ Értékelési hiba: {str(e)}")
        return jsonify({'error': 'Szerver hiba'}), 500

@app.route('/next_round', methods=['POST'])
def next_round():
    """Következő tanulási kör"""
    try:
        user_id, user_group, learning_round = initialize_user_session()
        
        # Aktuális kör értékeléseinek ellenőrzése
        if POSTGRES_AVAILABLE:
            current_ratings = get_user_ratings_db(user_id, learning_round)
        else:
            current_ratings = session.get('ratings', {})
        
        if len(current_ratings) < RECOMMENDATION_COUNT:
            return jsonify({
                'success': False,
                'message': f'Kérjük, értékelje mind a {RECOMMENDATION_COUNT} receptet!'
            }), 400
        
        # Következő kör ellenőrzése
        if learning_round >= MAX_LEARNING_ROUNDS:
            return jsonify({
                'success': False,
                'message': 'Tanulmány befejezve!',
                'redirect': '/results'
            })
        
        # Következő kör inicializálása
        next_round_num = learning_round + 1
        session['learning_round'] = next_round_num
        
        # Session ratings tisztítása
        if 'ratings' in session:
            session['ratings'] = {}
        session.modified = True
        
        logger.info(f"🔄 {user_id} átlépett a {next_round_num}. körbe")
        
        return jsonify({
            'success': True,
            'new_round': next_round_num,
            'message': f'Sikeresen átlépett a {next_round_num}. körbe!'
        })
            
    except Exception as e:
        logger.error(f"❌ Következő kör hiba: {str(e)}")
        return jsonify({'error': 'Szerver hiba'}), 500

@app.route('/results')
def results():
    """Eredmények oldal"""
    user_id = session.get('user_id', 'Unknown')
    user_group = session.get('user_group', 'Unknown')
    
    if POSTGRES_AVAILABLE:
        all_ratings = get_user_ratings_db(user_id)
    else:
        all_ratings = session.get('all_ratings', {})
    
    html = generate_results_page_html(user_id, user_group, all_ratings)
    return html

@app.route('/health')
def health():
    """Health check"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/status')
def status():
    """Rendszer status"""
    ensure_initialized()
    
    return jsonify({
        'service': 'GreenRec',
        'version': '2.0-fixed',
        'status': 'running',
        'recipes_count': len(recipes_df) if recipes_df is not None else 0,
        'learning_rounds': MAX_LEARNING_ROUNDS,
        'database_status': 'connected' if get_db_connection() else 'disconnected',
        'timestamp': datetime.now().isoformat()
    })

# 📄 HTML GENERÁTOR FUNKCIÓK (EGYSZERŰSÍTETT)

def generate_main_page_html(recommendations, user_group, learning_round, max_rounds, rated_count):
    """Főoldal HTML generálása"""
    
    # Recept kártyák generálása
    recipe_cards = ""
    for recipe in recommendations:
        # A csoport: rejtett pontszámok
        if user_group == 'A':
            scores_html = '''
            <div style="background: #f5f5f5; border: 2px dashed #ccc; color: #999; text-align: center; padding: 15px; border-radius: 10px; margin: 15px 0;">
                <i>A fenntarthatósági pontszámok rejtve vannak ebben a tesztcsoportban</i>
            </div>
            '''
        else:
            scores_html = f'''
            <div style="display: flex; justify-content: space-around; margin: 15px 0; padding: 10px; background: rgba(0,0,0,0.05); border-radius: 8px;">
                <div style="text-align: center;">
                    <div style="font-size: 1.5em; margin-bottom: 5px;">🌍</div>
                    <div style="font-weight: bold;">{recipe.get("ESI_final", 50):.0f}</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 1.5em; margin-bottom: 5px;">💚</div>
                    <div style="font-weight: bold;">{recipe.get("HSI", 50):.0f}</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 1.5em; margin-bottom: 5px;">👤</div>
                    <div style="font-weight: bold;">{recipe.get("PPI", 50):.0f}</div>
                </div>
            </div>
            '''
        
        recipe_cards += f'''
        <div style="background: rgba(255,255,255,0.95); border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0 8px 32px rgba(0,0,0,0.1);">
            <h3 style="color: #2c3e50; margin-bottom: 10px;">{recipe.get("name", "Névtelen recept")}</h3>
            <div style="background: #3498db; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.8em; margin-bottom: 10px; display: inline-block;">
                {recipe.get("category", "Kategória")}
            </div>
            <p style="color: #666; margin-bottom: 15px;"><strong>Összetevők:</strong> {recipe.get("ingredients", "Nincs megadva")}</p>
            
            {scores_html}
            
            <div style="text-align: center; margin-top: 15px;">
                <p><strong>Mennyire tetszik ez a recept?</strong></p>
                <div class="rating-stars" data-recipe-id="{recipe.get("recipeid", "unknown")}" style="display: flex; justify-content: center; gap: 5px; margin: 10px 0;">
                    <span class="star" data-rating="1" style="font-size: 2em; cursor: pointer; color: #ddd;">☆</span>
                    <span class="star" data-rating="2" style="font-size: 2em; cursor: pointer; color: #ddd;">☆</span>
                    <span class="star" data-rating="3" style="font-size: 2em; cursor: pointer; color: #ddd;">☆</span>
                    <span class="star" data-rating="4" style="font-size: 2em; cursor: pointer; color: #ddd;">☆</span>
                    <span class="star" data-rating="5" style="font-size: 2em; cursor: pointer; color: #ddd;">☆</span>
                </div>
                <div class="rating-feedback" style="height: 20px; font-size: 0.9em; color: #666;"></div>
            </div>
        </div>
        '''
    
    html = f'''
    <!DOCTYPE html>
    <html lang="hu">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GreenRec - {learning_round}. Kör</title>
        <style>
            body {{
                font-family: 'Segoe UI', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0;
                padding: 20px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
            }}
            .header {{
                text-align: center;
                color: white;
                margin-bottom: 30px;
                background: rgba(255,255,255,0.1);
                padding: 20px;
                border-radius: 15px;
                backdrop-filter: blur(10px);
            }}
            .progress-info {{
                background: rgba(255,255,255,0.15);
                padding: 15px;
                border-radius: 15px;
                margin-bottom: 20px;
                text-align: center;
                color: white;
            }}
            .progress-bar {{
                background: rgba(255,255,255,0.3);
                height: 8px;
                border-radius: 4px;
                margin: 10px 0;
                overflow: hidden;
            }}
            .progress-fill {{
                background: linear-gradient(90deg, #4CAF50, #8BC34A);
                height: 100%;
                border-radius: 4px;
                transition: width 0.3s ease;
                width: {(rated_count / RECOMMENDATION_COUNT * 100)}%;
            }}
            .controls {{
                text-align: center;
                margin-top: 30px;
            }}
            .btn {{
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                border: none;
                padding: 15px 30px;
                border-radius: 25px;
                font-size: 1.1em;
                cursor: pointer;
                margin: 0 10px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }}
            .btn:disabled {{
                opacity: 0.6;
                cursor: not-allowed;
            }}
            .btn:hover:not(:disabled) {{
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0,0,0,0.3);
            }}
            .star:hover {{
                color: #FFA500 !important;
                transform: scale(1.2);
            }}
            .star.selected {{
                color: #FFD700 !important;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌱 GreenRec Tanulmány</h1>
                <p>{learning_round}. kör a {max_rounds}-ból • {user_group} Csoport</p>
            </div>
            
            <div class="progress-info">
                <h3>📊 Tanulási Folyamat</h3>
                <p>Értékelje az alábbi {RECOMMENDATION_COUNT} receptet 1-5 csillaggal!</p>
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <p><span id="ratedCount">{rated_count}</span> / {RECOMMENDATION_COUNT} recept értékelve</p>
            </div>
            
            <div id="messageArea"></div>
            
            {recipe_cards}
            
            <div class="controls">
                <button id="nextRoundBtn" class="btn" disabled>
                    🔄 Következő Kör ({learning_round + 1}/{max_rounds})
                </button>
                <button onclick="window.location.href='/status'" class="btn">
                    📊 Rendszer Status
                </button>
            </div>
        </div>

        <script>
            let ratings = {{}};
            let ratedCount = {rated_count};
            const totalCount = {RECOMMENDATION_COUNT};
            const maxRounds = {max_rounds};
            const currentRound = {learning_round};
            
            // Csillag kezelés
            document.querySelectorAll('.rating-stars').forEach(starsContainer => {{
                const recipeId = starsContainer.dataset.recipeId;
                const stars = starsContainer.querySelectorAll('.star');
                const feedback = starsContainer.parentElement.querySelector('.rating-feedback');
                
                stars.forEach((star, index) => {{
                    star.addEventListener('click', () => {{
                        const rating = parseInt(star.dataset.rating);
                        rateRecipe(recipeId, rating, stars, feedback);
                    }});
                    
                    star.addEventListener('mouseenter', () => {{
                        stars.forEach((s, i) => {{
                            if (i <= index) {{
                                s.style.color = '#FFA500';
                            }} else {{
                                s.style.color = '#ddd';
                            }}
                        }});
                    }});
                    
                    star.addEventListener('mouseleave', () => {{
                        stars.forEach(s => {{
                            if (!s.classList.contains('selected')) {{
                                s.style.color = '#ddd';
                            }}
                        }});
                    }});
                }});
            }});
            
            function rateRecipe(recipeId, rating, stars, feedback) {{
                // Vizuális feedback
                stars.forEach((star, index) => {{
                    if (index < rating) {{
                        star.classList.add('selected');
                        star.textContent = '★';
                        star.style.color = '#FFD700';
                    }} else {{
                        star.classList.remove('selected');
                        star.textContent = '☆';
                        star.style.color = '#ddd';
                    }}
                }});
                
                // Feedback szöveg
                const feedbackTexts = ['', '😞 Nem tetszik', '😐 Kicsit tetszik', '😊 Semleges', '😃 Tetszik', '🤩 Nagyon tetszik!'];
                feedback.textContent = feedbackTexts[rating];
                feedback.style.color = rating >= 4 ? '#4CAF50' : rating >= 3 ? '#FF9800' : '#f44336';
                
                // Értékelés mentése
                if (!ratings[recipeId]) {{
                    ratedCount++;
                }}
                ratings[recipeId] = rating;
                
                // AJAX kérés
                fetch('/rate', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{recipe_id: recipeId, rating: rating}})
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        updateProgress(data.rated_count, data.total_needed);
                    }} else {{
                        showMessage('Hiba történt az értékelés mentése során', 'error');
                    }}
                }})
                .catch(error => {{
                    console.error('Rating error:', error);
                    showMessage('Hiba történt az értékelés mentése során', 'error');
                }});
            }}
            
            function updateProgress(rated, total) {{
                ratedCount = rated;
                document.getElementById('ratedCount').textContent = rated;
                document.getElementById('progressFill').style.width = (rated / total * 100) + '%';
                
                const nextBtn = document.getElementById('nextRoundBtn');
                if (rated >= total) {{
                    nextBtn.disabled = false;
                    nextBtn.textContent = currentRound >= maxRounds ? 
                        '🏁 Tanulmány Befejezése' : 
                        '🔄 Következő Kör (' + (currentRound + 1) + '/' + maxRounds + ')';
                    showMessage('🎉 Minden recept értékelve! Indíthatja a következő kört.', 'success');
                }}
            }}
            
            // Következő kör
            document.getElementById('nextRoundBtn').addEventListener('click', () => {{
                if (ratedCount < totalCount) {{
                    showMessage('Kérjük, értékelje mind a ' + totalCount + ' receptet!', 'info');
                    return;
                }}
                
                showMessage('Következő kör előkészítése...', 'info');
                
                fetch('/next_round', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}}
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        showMessage(data.message || 'Következő kör indítása...', 'success');
                        setTimeout(() => {{
                            location.reload();
                        }}, 1500);
                    }} else if (data.redirect) {{
                        showMessage('Tanulmány befejezve! Átirányítás...', 'success');
                        setTimeout(() => {{
                            window.location.href = data.redirect;
                        }}, 2000);
                    }} else {{
                        showMessage(data.message || 'Hiba történt', 'error');
                    }}
                }})
                .catch(error => {{
                    console.error('Next round error:', error);
                    showMessage('Hiba történt a következő kör indításakor', 'error');
                }});
            }});
            
            function showMessage(text, type) {{
                const messageArea = document.getElementById('messageArea');
                const colors = {{
                    'success': '#4CAF50',
                    'error': '#f44336',
                    'info': '#2196F3'
                }};
                messageArea.innerHTML = '<div style="background: rgba(255,255,255,0.9); color: ' + colors[type] + '; padding: 15px; border-radius: 10px; text-align: center; margin: 20px 0; font-weight: bold;">' + text + '</div>';
                
                setTimeout(() => {{
                    messageArea.innerHTML = '';
                }}, 5000);
            }}
            
            // Kezdeti állapot
            updateProgress(ratedCount, totalCount);
        </script>
    </body>
    </html>
    '''
    
    return html

def generate_results_page_html(user_id, user_group, all_ratings):
    """Eredmények oldal HTML"""
    total_ratings = len(all_ratings)
    avg_rating = sum(all_ratings.values()) / total_ratings if total_ratings > 0 else 0
    
    html = f'''
    <!DOCTYPE html>
    <html lang="hu">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GreenRec - Eredmények</title>
        <style>
            body {{
                font-family: 'Segoe UI', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0;
                padding: 20px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 600px;
                margin: 50px auto;
                background: rgba(255,255,255,0.95);
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 15px 35px rgba(0,0,0,0.1);
                text-align: center;
            }}
            h1 {{
                color: #2c3e50;
                margin-bottom: 30px;
            }}
            .stat-card {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 15px;
                margin: 15px 0;
                border-left: 5px solid #4CAF50;
            }}
            .btn {{
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                border: none;
                padding: 15px 30px;
                border-radius: 25px;
                font-size: 1.1em;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                margin: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎉 Köszönjük a részvételt!</h1>
            
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
            
            <div style="margin-top: 30px;">
                <a href="/" class="btn">🏠 Vissza a főoldalra</a>
                <a href="/status" class="btn">📊 Rendszer Status</a>
            </div>
        </div>
    </body>
    </html>
    '''
    
    return html

def redirect_to_results():
    """Átirányítás az eredmények oldalra"""
    return '''
    <script>
        window.location.href = '/results';
    </script>
    <p>Átirányítás az eredményekhez...</p>
    '''

if __name__ == '__main__':
    print("🌱 GreenRec - Javított Production Verzió")
    print("=" * 50)
    print("✅ 3 tanulási kör")
    print("✅ Syntax error javítások")
    print("✅ A csoport: rejtett pontszámok")
    print("✅ Egyszerűsített template-ek") 
    print("✅ PostgreSQL opcionális")
    print("=" * 50)
    print(f"🚀 Szerver port: {PORT}")
    print(f"🔧 Debug mód: {DEBUG_MODE}")
    print(f"🗄️ PostgreSQL: {'✅ Elérhető' if POSTGRES_AVAILABLE else '❌ Memória-alapú'}")
    print("=" * 50)
    
    # Flask alkalmazás indítása
    app.run(
        debug=DEBUG_MODE,
        host='0.0.0.0',
        port=PORT
    )
