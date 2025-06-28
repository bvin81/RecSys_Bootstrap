import os
import logging
import json
import random
import numpy as np
from datetime import datetime, timedelta
from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify, Response

# Logging beállítása
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def get_score_color(score, score_type):
    """
    Pontszám alapján színkódolás
    score_type: 'hsi', 'esi', 'ppi'
    """
    if score_type == 'hsi' or score_type == 'ppi':
        # HSI és PPI: magasabb = jobb
        if score >= 75:
            return 'success'  # Zöld
        elif score >= 50:
            return 'warning'  # Sárga
        else:
            return 'danger'   # Piros
    
    elif score_type == 'esi':
        # ESI: alacsonyabb = jobb (normalizált 0-100 skála)
        if score <= 33:      # Alacsony környezeti hatás
            return 'success'  # Zöld
        elif score <= 66:    # Közepes környezeti hatás
            return 'warning'  # Sárga
        else:                # Magas környezeti hatás
            return 'danger'   # Piros
try:
    import psycopg2
    from psycopg2 import sql
    from urllib.parse import urlparse
    from werkzeug.security import generate_password_hash, check_password_hash
    import pandas as pd
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.preprocessing import MinMaxScaler
    logger.info("✅ Összes dependency importálva")
except ImportError as e:
    logger.error(f"❌ Import hiba: {e}")

try:
    from visualizations import visualizer
    VISUALIZATIONS_AVAILABLE = True
    logger.info("✅ Vizualizációs modul betöltve")
except ImportError as e:
    VISUALIZATIONS_AVAILABLE = False
    logger.warning(f"⚠️ Vizualizációs modul nem elérhető: {e}")

# Flask alkalmazás inicializálás
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# ===== DATABASE CONNECTION =====
def get_db_connection():
    """Adatbázis kapcsolat létrehozása robusztus hibakezeléssel"""
    try:
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            # Heroku Postgres URL javítás
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
                logger.info("✅ Database URL javítva postgresql://-re")
            
            result = urlparse(database_url)
            conn = psycopg2.connect(
                dbname=result.path[1:],
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port,
                sslmode='require'
            )
            logger.info("✅ PostgreSQL kapcsolat létrehozva")
            return conn
        else:
            logger.warning("⚠️  DATABASE_URL nincs beállítva")
            return None
    except Exception as e:
        logger.error(f"❌ Adatbázis kapcsolat hiba: {e}")
        return None

# 1. MÓDOSÍTOTT GreenRecRecommender CLASS - 50-50%

class GreenRecRecommender:
    def __init__(self):
        logger.info("🔧 Ajánlórendszer inicializálása...")
        self.recipes_df = None
        # COSINE SIMILARITY hozzáadása
        self.vectorizer = CountVectorizer(
            stop_words='english', 
            max_features=1000,
            ngram_range=(1, 2),  # 1-2 gram kombinációk
            lowercase=True,
            token_pattern=r'\b[a-zA-ZáéíóöőúüűÁÉÍÓÖŐÚÜŰ]+\b'  # Magyar karakterek
        )
        self.scaler = MinMaxScaler()
        self.ingredient_matrix = None  # ÚJ: Cosine similarity mátrix
        self.user_history = {}  # Felhasználói előzmények tárolása
        self.load_recipes()
        logger.info("✅ Ajánlórendszer sikeresen inicializálva")
    
    def load_recipes(self):
        """Receptek betöltése adatbázisból SAFE hibakezeléssel"""
        try:
            conn = get_db_connection()
            if conn is None:
                logger.warning("⚠️  Nincs adatbázis kapcsolat, dummy adatok létrehozása")
                self.create_dummy_data()
                return
                
            # Ellenőrizzük, hogy létezik-e a recipes tábla
            cur = conn.cursor()
            try:
                cur.execute("SELECT COUNT(*) FROM recipes LIMIT 1;")
                count = cur.fetchone()[0]
                logger.info(f"✅ Recipes tábla létezik, {count} recept található")
            except psycopg2.errors.UndefinedTable:
                logger.warning("⚠️  Recipes tábla nem létezik")
                logger.warning("⚠️  Nincs recept adat, dummy adatok létrehozása")
                conn.close()
                self.create_dummy_data()
                return
            
            # Receptek betöltése
            if count > 0:
                query = """
                    SELECT id, title, hsi, esi, ppi, category, ingredients, instructions, images
                    FROM recipes 
                    ORDER BY id
                """
                self.recipes_df = pd.read_sql_query(query, conn)
                logger.info(f"✅ {len(self.recipes_df)} recept betöltve az adatbázisból")
                
                # Adatok előfeldolgozása
                self.preprocess_data()
            else:
                logger.warning("⚠️  Nincs recept adat, dummy adatok létrehozása")
                self.create_dummy_data()
                
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Recept betöltési hiba: {e}")
            self.create_dummy_data()
    
    def create_dummy_data(self):
        """3 dummy recept létrehozása ha nincs adat"""
        logger.info("🔧 Dummy adatok létrehozása...")
        dummy_recipes = [
            {
                'id': 1,
                'title': 'Zöldséges quinoa saláta',
                'hsi': 95.2,
                'esi': 24.4,
                'ppi': 67.8,
                'category': 'Saláták',
                'ingredients': 'quinoa, uborka, paradicsom, avokádó, citrom',
                'instructions': 'Főzd meg a quinoát, várd meg hogy kihűljön. Vágd apróra a zöldségeket.',
                'images': 'https://via.placeholder.com/300x200?text=Quinoa+Salat'
            },
            {
                'id': 2,
                'title': 'Vegán chili sin carne',
                'hsi': 76.3,
                'esi': 15.1,
                'ppi': 84.5,
                'category': 'Főételek',
                'ingredients': 'vörös bab, kukorica, paprika, hagyma, paradicsom',
                'instructions': 'Dinszteld le a hagymát és paprikát. Add hozzá a babot.',
                'images': 'https://via.placeholder.com/300x200?text=Vegan+Chili'
            },
            {
                'id': 3,
                'title': 'Spenótos lencse curry',
                'hsi': 82.7,
                'esi': 42.1,
                'ppi': 75.8,
                'category': 'Főételek',
                'ingredients': 'lencse, spenót, kókusztej, curry, gyömbér',
                'instructions': 'Főzd meg a lencsét, add hozzá a fűszereket.',
                'images': 'https://via.placeholder.com/300x200?text=Lentil+Curry'
            }
        ]
        
        self.recipes_df = pd.DataFrame(dummy_recipes)
        self.preprocess_data()
        logger.info("✅ Dummy adatok létrehozva")
    
    def preprocess_data(self):
        """Adatok előfeldolgozása ÉS cosine similarity előkészítés"""
        try:
            # HSI, ESI, PPI normalizálása
            score_columns = ['hsi', 'esi', 'ppi']
            self.recipes_df[score_columns] = self.scaler.fit_transform(self.recipes_df[score_columns])
            
            # ESI invertálása (alacsonyabb környezeti hatás = jobb)
            self.recipes_df['esi_inv'] = 1 - self.recipes_df['esi']
            
            # ===== COSINE SIMILARITY ELŐKÉSZÍTÉS =====
            if 'ingredients' in self.recipes_df.columns:
                # Ingredients tisztítása és előkészítése
                ingredients_text = self.recipes_df['ingredients'].fillna('').astype(str)
                
                # Alapvető szöveg tisztítás
                ingredients_text = ingredients_text.str.lower()
                ingredients_text = ingredients_text.str.replace(r'[^\w\s,]', '', regex=True)
                
                # Ingredient matrix létrehozása
                self.ingredient_matrix = self.vectorizer.fit_transform(ingredients_text)
                logger.info(f"✅ Ingredient matrix létrehozva: {self.ingredient_matrix.shape}")
                
                # Vocabulary mérete
                vocab_size = len(self.vectorizer.get_feature_names_out())
                logger.info(f"📚 Vocabulary méret: {vocab_size} ingrediens")
            
        except Exception as e:
            logger.error(f"❌ Adatok előfeldolgozási hiba: {e}")
    
    def get_content_similarity(self, target_ingredients, top_k=20):
        """ÚJ: Content-based similarity számítás ingredients alapján"""
        try:
            if self.ingredient_matrix is None:
                logger.warning("⚠️  Ingredient matrix nincs inicializálva")
                return []
            
            # Target ingredients előkészítése
            if isinstance(target_ingredients, list):
                target_text = ', '.join(target_ingredients)
            else:
                target_text = str(target_ingredients)
            
            # Tisztítás
            target_text = target_text.lower().strip()
            if not target_text:
                return []
            
            # Target vectorizálása
            target_vector = self.vectorizer.transform([target_text])
            
            # Cosine similarity számítás
            similarities = cosine_similarity(target_vector, self.ingredient_matrix).flatten()
            
            # Top K hasonló recept indexei
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            # Eredmények készítése
            similar_recipes = []
            for idx in top_indices:
                if similarities[idx] > 0.01:  # Minimum similarity threshold
                    recipe_data = self.recipes_df.iloc[idx].copy()
                    recipe_data['similarity_score'] = similarities[idx]
                    similar_recipes.append(recipe_data.to_dict())
            
            logger.info(f"🔍 {len(similar_recipes)} hasonló recept találva cosine similarity alapján")
            return similar_recipes
            
        except Exception as e:
            logger.error(f"❌ Content similarity hiba: {e}")
            return []
    
    def get_recommendations(self, user_preferences=None, num_recommendations=5, user_id=None, diversity_factor=0.3):
        """
        🎯 HIBRID ajánlások generálása - Content-based + Score-based
        """
        try:
            if self.recipes_df is None or len(self.recipes_df) == 0:
                logger.warning("⚠️  Nincs elérhető recept adat")
                return []
            
            # 1. ALAPVETŐ PONTSZÁMOK SZÁMÍTÁSA
            df = self.recipes_df.copy()
            
            # Kompozit pontszám számítása
            df['composite_score'] = (
                0.4 * df['hsi'] +
                0.4 * df['esi_inv'] +
                0.2 * df['ppi']
            )
            
            # 2. FELHASZNÁLÓI ELŐZMÉNYEK FIGYELEMBEVÉTELE
            excluded_ids = []
            if user_id and user_id in self.user_history:
                # Kizárjuk a már látott recepteket (utolsó 10 ajánlás)
                excluded_ids = self.user_history[user_id][-10:]
                df = df[~df['id'].isin(excluded_ids)]
                logger.info(f"🔍 {len(excluded_ids)} már látott recept kizárva")
            
            # 3. ÚJ: HIBRID CONTENT-BASED + SCORE-BASED
            recommendations = []
            
            # Ellenőrizzük van-e target ingredients
            target_ingredients = ""
            if user_preferences and 'ingredients' in user_preferences:
                target_ingredients = user_preferences['ingredients']
            
            if target_ingredients and target_ingredients.strip():
                # HIBRID MEGKÖZELÍTÉS: Content-based + Score-based
                logger.info("🔄 Hibrid ajánlás: Content-based + Score-based")
                
                # Content-based similarity számítás
                content_candidates = self.get_content_similarity(target_ingredients, top_k=15)
                
                if content_candidates:
                    # Súlyozott pontszám: similarity + composite score
                    for recipe in content_candidates:
                        recipe_id = recipe['id']
                        if recipe_id in df['id'].values:
                            # Normalizált similarity (0-1)
                            similarity_norm = recipe['similarity_score']
                            
                            # Megfelelő composite score lekérése
                            matching_row = df[df['id'] == recipe_id]
                            if not matching_row.empty:
                                composite_norm = matching_row['composite_score'].iloc[0]
                                
                                # Hibrid pontszám: 50% content + 50% score
                                hybrid_score = 0.5 * similarity_norm + 0.5 * composite_norm
                                recipe['hybrid_score'] = hybrid_score
                    
                    # Rendezés hibrid pontszám szerint
                    content_candidates.sort(key=lambda x: x.get('hybrid_score', 0), reverse=True)
                    
                    # Top receptek kiválasztása
                    for recipe in content_candidates[:num_recommendations]:
                        recommendations.append(recipe)
                
            if not recommendations:
                # CSAK SCORE-BASED (ha nincs content similarity vagy nincs target)
                logger.info("📊 Score-based ajánlás (nincs target ingredients vagy similarity)")
                
                # Kategória diverzitás
                available_categories = df['category'].unique()
                
                for category in available_categories[:num_recommendations]:
                    category_recipes = df[df['category'] == category]
                    if not category_recipes.empty:
                        # Weighted selection
                        weights = category_recipes['composite_score'].values
                        weights = (weights - weights.min() + 0.1) ** 2
                        
                        try:
                            selected_idx = np.random.choice(
                                category_recipes.index, 
                                p=weights/weights.sum()
                            )
                            selected_recipe = category_recipes.loc[selected_idx].to_dict()
                            selected_recipe['similarity_score'] = 0.0  # Nincs similarity
                            selected_recipe['hybrid_score'] = selected_recipe['composite_score']
                            recommendations.append(selected_recipe)
                        except:
                            # Ha hiba van a random choice-szal
                            selected_recipe = category_recipes.nlargest(1, 'composite_score').iloc[0].to_dict()
                            selected_recipe['similarity_score'] = 0.0
                            selected_recipe['hybrid_score'] = selected_recipe['composite_score']
                            recommendations.append(selected_recipe)
            
            # 4. FELHASZNÁLÓI ELŐZMÉNYEK FRISSÍTÉSE
            if user_id:
                if user_id not in self.user_history:
                    self.user_history[user_id] = []
                
                new_ids = [rec['id'] for rec in recommendations]
                self.user_history[user_id].extend(new_ids)
                # Korlátozás az utolsó 50 receptre
                self.user_history[user_id] = self.user_history[user_id][-50:]
            
            # 5. RANDOM SHUFFLE ÉS FORMÁTUM ÁTALAKÍTÁSA
            random.shuffle(recommendations)  # Véletlenszerű sorrend
            
            final_recommendations = []
            for recipe in recommendations[:num_recommendations]:
                # Pontszámok visszaalakítása megjelenítéshez (0-100 skála)
                final_recommendations.append({
                    'id': int(recipe['id']),
                    'title': recipe['title'],
                    'hsi': round(float(recipe['hsi']) * 100, 1),
                    'esi': round(float(recipe['esi']) * 100, 1),
                    'ppi': round(float(recipe['ppi']) * 100, 1),
                    'category': recipe['category'],
                    'ingredients': recipe['ingredients'],
                    'instructions': recipe['instructions'],
                    'images': recipe.get('images', 'https://via.placeholder.com/300x200?text=No+Image'),
                    'similarity_score': round(recipe.get('similarity_score', 0), 3),
                    'hybrid_score': round(recipe.get('hybrid_score', 0), 3)
                })
            
            logger.info(f"✅ {len(final_recommendations)} hibrid ajánlás generálva")
            return final_recommendations
            
        except Exception as e:
            logger.error(f"❌ Ajánlási hiba: {e}")
            return []
    
    def get_personalized_recommendations(self, user_id, user_preferences=None, num_recommendations=5):
        """Személyre szabott ajánlások felhasználói preferenciák alapján"""
        # Alapértelmezett diversity_factor beállítás felhasználói típus szerint
        diversity_factors = {
            'A': 0.4,  # Kontroll csoport - több változatosság
            'B': 0.3,  # Pontszámos - mérsékelt változatosság  
            'C': 0.2   # Magyarázatos - kevesebb változatosság (tudatosabb választás)
        }
        
        user_group = user_preferences.get('group', 'A') if user_preferences else 'A'
        diversity = diversity_factors.get(user_group, 0.3)
        
        return self.get_recommendations(
            user_preferences=user_preferences,
            num_recommendations=num_recommendations,
            user_id=user_id,
            diversity_factor=diversity
        )

# Globális ajánlórendszer inicializálás
logger.info("🔧 Globális ajánlórendszer inicializálása...")
try:
    recommender = GreenRecRecommender()
    logger.info("✅ Globális ajánlórendszer kész")
except Exception as e:
    logger.error(f"❌ Ajánlórendszer inicializálási hiba: {e}")
    recommender = None

# ===== RECOMMENDATION LOGGING =====
def log_recommendations(user_id, recommendations):
    """Ajánlások rögzítése az adatbázisba metrikák számításához"""
    try:
        conn = get_db_connection()
        if conn is None:
            return
            
        cur = conn.cursor()
        
        # Recommendation sessions tábla létrehozása ha nem létezik
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recommendation_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                session_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                recommended_recipe_ids TEXT NOT NULL,
                recommendation_count INTEGER DEFAULT 5
            )
        """)
        
        # Session adatok beszúrása
        recipe_ids = ','.join([str(rec['id']) for rec in recommendations])
        cur.execute("""
            INSERT INTO recommendation_sessions (user_id, recommended_recipe_ids, recommendation_count)
            VALUES (%s, %s, %s)
        """, (user_id, recipe_ids, len(recommendations)))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Ajánlások logolva: user={user_id}, recipes={recipe_ids}")
        
    except Exception as e:
        logger.error(f"❌ Ajánlási logging hiba: {e}")

# ===== USER MANAGEMENT =====
def create_user(username, password, group_name):
    """Új felhasználó létrehozása"""
    try:
        conn = get_db_connection()
        if conn is None:
            return False, "Adatbázis kapcsolati hiba"
        
        cur = conn.cursor()
        
        # Users tábla létrehozása ha nem létezik
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                group_name VARCHAR(10) NOT NULL DEFAULT 'A',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Ellenőrizzük, hogy létezik-e már a felhasználó
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            conn.close()
            return False, "Ez a felhasználónév már foglalt!"
        
        # Új felhasználó beszúrása
        password_hash = generate_password_hash(password)
        cur.execute("""
            INSERT INTO users (username, password_hash, group_name) 
            VALUES (%s, %s, %s)
        """, (username, password_hash, group_name))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Új felhasználó létrehozva: {username} (csoport: {group_name})")
        return True, "Sikeres regisztráció!"
        
    except Exception as e:
        logger.error(f"❌ Felhasználó létrehozási hiba: {e}")
        return False, "Hiba a regisztráció során"

def check_user_credentials(username, password):
    """Felhasználói hitelesítés ellenőrzése"""
    try:
        conn = get_db_connection()
        if conn is None:
            return False, None
        
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, password_hash, group_name 
            FROM users WHERE username = %s
        """, (username,))
        
        user = cur.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            return True, {
                'id': user[0],
                'username': user[1],
                'group': user[3]
            }
        return False, None
        
    except Exception as e:
        logger.error(f"❌ Hitelesítési hiba: {e}")
        return False, None

# ===== FLASK ROUTES =====
@app.route('/')
def index():
    """Főoldal - csak bejelentkezett felhasználóknak"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        username = session.get('username', 'Ismeretlen')
        user_group = session.get('user_group', 'A')
        
        return render_template('index.html', 
                             username=username,
                             user_group=user_group,
                             recommendations=[])
    except Exception as e:
        logger.error(f"❌ Index oldal hiba: {e}")
        flash('Hiba történt az oldal betöltésekor.', 'error')
        return render_template('index.html', 
                             recommendations=[], 
                             user_group='A',
                             username=session.get('username'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Bejelentkezés oldal"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Kérlek add meg a felhasználónevet és jelszót!', 'error')
            return render_template('login.html')
        
        success, user_data = check_user_credentials(username, password)
        
        if success and user_data:
            session['user_id'] = user_data['id']
            session['username'] = user_data['username']
            session['user_group'] = user_data['group']
            logger.info(f"✅ Sikeres bejelentkezés: {username}")
            return redirect(url_for('index'))
        else:
            flash('Hibás felhasználónév vagy jelszó!', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Regisztráció oldal"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not username or not password:
            flash('Kérlek add meg a felhasználónevet és jelszót!', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('A jelszavak nem egyeznek!', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('A jelszónak legalább 6 karakter hosszúnak kell lennie!', 'error')
            return render_template('register.html')
        
        # Random csoport hozzárendelés (A/B/C teszt)
        import random
        group_name = random.choice(['A', 'B', 'C'])
        
        success, message = create_user(username, password, group_name)
        
        if success:
            flash(f'Sikeres regisztráció! Te a(z) {group_name} csoportba kerültél.', 'success')
            return redirect(url_for('login'))
        else:
            flash(message, 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """Kijelentkezés"""
    username = session.get('username', 'Ismeretlen')
    session.clear()
    logger.info(f"✅ Kijelentkezés: {username}")
    flash('Sikeresen kijelentkeztél!', 'info')
    return redirect(url_for('login'))

@app.route('/recommend', methods=['POST'])
def recommend():
    """🎯 HIBRID AJAX ajánlások endpoint - JAVÍTOTT JSON kezelés"""
    if 'user_id' not in session:
        return jsonify({'error': 'Nincs bejelentkezve'}), 401
    
    try:
        if recommender is None:
            return jsonify({'error': 'Ajánlórendszer nem elérhető'}), 500
        
        # JAVÍTOTT JSON kezelés - több módon próbáljuk
        target_ingredients = ''
        try:
            # Első próbálkozás: JSON request
            if request.is_json and request.get_json():
                request_data = request.get_json()
                target_ingredients = request_data.get('ingredients', '')
        except Exception as json_error:
            logger.warning(f"⚠️ JSON parsing hiba: {json_error}")
            # Második próbálkozás: form data
            try:
                target_ingredients = request.form.get('ingredients', '')
            except Exception as form_error:
                logger.warning(f"⚠️ Form parsing hiba: {form_error}")
                # Harmadik próbálkozás: üres ingredients
                target_ingredients = ''
        
        # Felhasználói csoport és preferenciák
        user_group = session.get('user_group', 'A')
        user_preferences = {
            'group': user_group,
            'user_id': session['user_id'],
            'ingredients': target_ingredients  # Content-based input
        }
        
        logger.info(f"🔍 Ajánlás kérés: user={session['user_id']}, group={user_group}, ingredients='{target_ingredients}'")
        
        # 🚀 HIBRID ajánlások generálása
        recommendations = recommender.get_personalized_recommendations(
            user_id=session['user_id'],
            user_preferences=user_preferences,
            num_recommendations=5
        )
        
        # Ellenőrzés hogy van-e eredmény
        if not recommendations:
            logger.warning("⚠️ Nincs ajánlás eredmény")
            return jsonify({'error': 'Nem sikerült ajánlásokat generálni'}), 500
        
        # ✨ SZÍNKÓDOLÁS hozzáadása minden recepthez
        for rec in recommendations:
            rec['hsi_color'] = get_score_color(rec['hsi'], 'hsi')
            rec['esi_color'] = get_score_color(rec['esi'], 'esi')
            rec['ppi_color'] = get_score_color(rec['ppi'], 'ppi')
            
            # Tooltip szövegek
            rec['hsi_tooltip'] = f"Egészségességi mutató: {rec['hsi']:.1f} (magasabb = jobb)"
            rec['esi_tooltip'] = f"Környezeti hatás: {rec['esi']:.1f} (alacsonyabb = jobb)"
            rec['ppi_tooltip'] = f"Népszerűségi mutató: {rec['ppi']:.1f} (magasabb = jobb)"
            
            # Hibrid info hozzáadása
            if rec.get('similarity_score', 0) > 0:
                rec['is_hybrid'] = True
                rec['hybrid_tooltip'] = f"Hibrid pontszám: {rec.get('hybrid_score', 0):.3f} (50% hasonlóság + 50% minőség)"
            else:
                rec['is_hybrid'] = False
                rec['hybrid_tooltip'] = f"Minőségi pontszám: {rec.get('hybrid_score', 0):.3f} (csak HSI/ESI/PPI alapú)"
        
        # ✅ KULCS: AJÁNLÁSOK TELJES LOGGING-JA
        if recommendations:
            log_recommendation_session(session['user_id'], recommendations, user_group)
        
        logger.info(f"✅ {len(recommendations)} hibrid ajánlás generálva user_id={session['user_id']}, group={user_group}")
        
        # Debug info logolása
        hybrid_count = sum(1 for rec in recommendations if rec.get('similarity_score', 0) > 0)
        logger.info(f"📊 Hibrid ajánlások: {hybrid_count}/{len(recommendations)} content-based")
        
        return jsonify({'recommendations': recommendations})
        
    except Exception as e:
        logger.error(f"❌ Hibrid ajánlási endpoint hiba: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Hiba az ajánlások generálásakor'}), 500

@app.route('/select_recipe', methods=['POST'])
def select_recipe():
    """Recept választás rögzítése"""
    if 'user_id' not in session:
        return jsonify({'error': 'Nincs bejelentkezve'}), 401
    
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        
        if not recipe_id:
            return jsonify({'error': 'Hiányzó recept ID'}), 400
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Adatbázis kapcsolati hiba'}), 500
        
        cur = conn.cursor()
        
        # User choices tábla létrehozása ha nem létezik
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_choices (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                recipe_id INTEGER NOT NULL,
                selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Választás rögzítése
        cur.execute("""
            INSERT INTO user_choices (user_id, recipe_id, selected_at)
            VALUES (%s, %s, %s)
            """, (session['user_id'], recipe_id, datetime.now()))
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Recept választás rögzítve: user={session['user_id']}, recipe={recipe_id}")
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"❌ Recept választás hiba: {e}")
        return jsonify({'error': 'Hiba történt a választás rögzítésekor'}), 500

@app.route('/stats')
def stats():
    """Statisztikai áttekintő oldal"""
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Adatbázis kapcsolati hiba', 'error')
            return render_template('stats.html', stats={})
        
        cur = conn.cursor()
        
        # Alapvető statisztikák
        stats = {}
        
        # Felhasználók száma csoportonként
        try:
            cur.execute("SELECT group_name, COUNT(*) FROM users GROUP BY group_name ORDER BY group_name")
            stats['users_by_group'] = dict(cur.fetchall())
        except:
            stats['users_by_group'] = {'A': 0, 'B': 0, 'C': 0}
        
        # Választások száma
        try:
            cur.execute("SELECT COUNT(*) FROM user_choices")
            stats['total_choices'] = cur.fetchone()[0]
        except:
            stats['total_choices'] = 0
        
        # Receptek száma
        try:
            cur.execute("SELECT COUNT(*) FROM recipes")
            stats['total_recipes'] = cur.fetchone()[0]
        except:
            stats['total_recipes'] = 0
        
        conn.close()
        return render_template('stats.html', stats=stats)
        
    except Exception as e:
        logger.error(f"❌ Statisztikák hiba: {e}")
        return render_template('stats.html', stats={})

# ===== EXPORT ENDPOINTS =====
@app.route('/export/users')
def export_users():
    """Felhasználók exportálása CSV formátumban"""
    try:
        conn = get_db_connection()
        if conn is None:
            return "Adatbázis kapcsolati hiba", 500
        
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, group_name, created_at,
            CASE WHEN username LIKE 'user_%' THEN 'teszt' ELSE 'valós' END as user_type
            FROM users ORDER BY created_at
        """)
        
        users_data = cur.fetchall()
        conn.close()
        
        # CSV generálás
        csv_content = "id,username,group_name,created_at,user_type\n"
        for user in users_data:
            csv_content += f"{user[0]},{user[1]},{user[2]},{user[3]},{user[4]}\n"
        
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=greenrec_users.csv'}
        )
        
    except Exception as e:
        logger.error(f"❌ Users export hiba: {e}")
        return "Export hiba", 500

@app.route('/export/choices')
def export_choices():
    """Választások exportálása CSV formátumban"""
    try:
        conn = get_db_connection()
        if conn is None:
            return "Adatbázis kapcsolati hiba", 500
        
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                uc.id as choice_id,
                u.username,
                u.group_name,
                r.title as recipe_title,
                r.hsi, r.esi, r.ppi,
                r.category,
                uc.selected_at,
                CASE WHEN u.username LIKE 'user_%' THEN 'teszt' ELSE 'valós' END as user_type
            FROM user_choices uc
            JOIN users u ON uc.user_id = u.id  
            JOIN recipes r ON uc.recipe_id = r.id
            ORDER BY uc.selected_at
        """)
        
        choices_data = cur.fetchall()
        conn.close()
        
        # CSV generálás
        csv_content = "choice_id,username,group_name,recipe_title,hsi,esi,ppi,category,selected_at,user_type\n"
        for choice in choices_data:
            csv_content += f"{choice[0]},{choice[1]},{choice[2]},{choice[3]},{choice[4]},{choice[5]},{choice[6]},{choice[7]},{choice[8]},{choice[9]}\n"
        
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=greenrec_choices.csv'}
        )
        
    except Exception as e:
        logger.error(f"❌ Choices export hiba: {e}")
        return "Export hiba", 500

@app.route('/export/json')
def export_json():
    """TELJES JSON export - többlépéses lekérdezéssel"""
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Adatbázis kapcsolati hiba'}), 500
            
        cur = conn.cursor()
        
        logger.info("🔍 JSON export kezdése - többlépéses lekérdezés")
        
        # 1. VÁLASZTÁSOK lekérdezése
        cur.execute("SELECT id, user_id, recipe_id, selected_at FROM user_choices ORDER BY selected_at;")
        choices_raw = cur.fetchall()
        logger.info(f"📊 {len(choices_raw)} választás betöltve")
        
        # 2. FELHASZNÁLÓK lekérdezése
        cur.execute("SELECT id, username, group_name FROM users;")
        users_raw = cur.fetchall()
        users_dict = {user[0]: {'username': user[1], 'group_name': user[2]} for user in users_raw}
        logger.info(f"👥 {len(users_dict)} felhasználó betöltve")
        
        # 3. RECEPTEK lekérdezése  
        cur.execute("SELECT id, title, hsi, esi, ppi, category FROM recipes;")
        recipes_raw = cur.fetchall()
        recipes_dict = {
            recipe[0]: {
                'title': recipe[1], 
                'hsi': float(recipe[2]), 
                'esi': float(recipe[3]), 
                'ppi': float(recipe[4]),
                'category': recipe[5]
            } for recipe in recipes_raw
        }
        logger.info(f"🍽️ {len(recipes_dict)} recept betöltve")
        
        # 4. TELJES ADATOK ÖSSZEÁLLÍTÁSA
        export_data = {
            'metadata': {
                'export_timestamp': str(datetime.now()),
                'total_choices': len(choices_raw),
                'total_users': len(users_dict),
                'total_recipes': len(recipes_dict)
            },
            'choices': []
        }
        
        for choice in choices_raw:
            choice_id, user_id, recipe_id, selected_at = choice
            
            # Felhasználó adatok
            user_data = users_dict.get(user_id, {'username': 'Unknown', 'group_name': 'Unknown'})
            
            # Recept adatok
            recipe_data = recipes_dict.get(recipe_id, {
                'title': 'Unknown Recipe', 
                'hsi': 0, 'esi': 0, 'ppi': 0, 
                'category': 'Unknown'
            })
            
            # Kompozit pontszám számítása
            hsi = recipe_data['hsi']
            esi = recipe_data['esi'] 
            ppi = recipe_data['ppi']
            esi_normalized = esi * 100 / 255  # ESI normalizálás 0-100 skálára
            composite_score = 0.4 * hsi + 0.4 * (100 - esi_normalized) + 0.2 * ppi
            
            # Teljes record összeállítása
            choice_record = {
                'choice_id': choice_id,
                'user_id': user_id,
                'username': user_data['username'],
                'group_name': user_data['group_name'],
                'recipe_id': recipe_id,
                'recipe_title': recipe_data['title'],
                'category': recipe_data['category'],
                'hsi': hsi,
                'esi': esi,
                'ppi': ppi,
                'composite_score': round(composite_score, 2),
                'good_choice': composite_score > 60,
                'selected_at': selected_at.isoformat() if selected_at else None,
                'user_type': 'virtual' if user_data['username'].startswith('virtual_') else 'real'
            }
            
            export_data['choices'].append(choice_record)
        
        conn.close()
        
        logger.info(f"✅ JSON export kész: {len(export_data['choices'])} teljes rekord")
        
        return Response(
            json.dumps(export_data, indent=2, ensure_ascii=False),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=greenrec_complete.json'}
        )
        
    except Exception as e:
        logger.error(f"❌ JSON export hiba: {e}")
        return jsonify({'error': f'Export hiba: {str(e)}'}), 500

# ===== HEALTH CHECK =====
@app.route('/health')
def health_check():
    """Alkalmazás állapot ellenőrzés"""
    try:
        conn = get_db_connection()
        status = {
            'status': 'healthy',
            'database': 'connected' if conn else 'disconnected',
            'recommender': 'active' if recommender else 'inactive',
            'timestamp': datetime.now().isoformat()
        }
        if conn:
            conn.close()
        return jsonify(status)
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ===== ERROR HANDLERS =====
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

def log_recommendation_session(user_id, recommendations, user_group):
    """Teljes ajánlási szesszió rögzítése a metrikákhoz"""
    try:
        conn = get_db_connection()
        if conn is None:
            return
            
        cur = conn.cursor()
        
        # Recept ID-k és pozíciók
        recipe_ids = [str(rec['id']) for rec in recommendations]
        recipe_positions = {str(rec['id']): i+1 for i, rec in enumerate(recommendations)}
        
        # Session rögzítése
        cur.execute("""
            INSERT INTO recommendation_sessions 
            (user_id, recommended_recipe_ids, recipe_positions, user_group)
            VALUES (%s, %s, %s, %s)
        """, (
            user_id, 
            ','.join(recipe_ids),
            json.dumps(recipe_positions),
            user_group
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Recommendation session logged: user={user_id}, recipes={recipe_ids}")
        
    except Exception as e:
        logger.error(f"❌ Recommendation logging hiba: {e}")

@app.route('/export/metrics')
def export_metrics():
    """Egyszerű metrikák export - user_group nélkül"""
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Adatbázis kapcsolati hiba'}), 500
        
        cur = conn.cursor()
        
        # Ajánlási szesszók
        cur.execute("SELECT COUNT(*) FROM recommendation_sessions")
        total_sessions = cur.fetchone()[0]
        
        # Választások
        cur.execute("SELECT COUNT(*) FROM user_choices")
        total_choices = cur.fetchone()[0]
        
        # Hit rate
        hit_rate = (total_choices / total_sessions) if total_sessions > 0 else 0
        
        # Utolsó 5 szesszió
        cur.execute("""
            SELECT id, user_id, session_timestamp, recommended_recipe_ids
            FROM recommendation_sessions 
            ORDER BY session_timestamp DESC
            LIMIT 5
        """)
        
        sessions = cur.fetchall()
        conn.close()
        
        return jsonify({
            'message': 'Alapvető metrikák',
            'total_sessions': total_sessions,
            'total_choices': total_choices,
            'hit_rate': round(hit_rate, 3),
            'recent_sessions': [
                {
                    'id': s[0],
                    'user_id': s[1],
                    'timestamp': str(s[2]),
                    'recipes_count': len(s[3].split(',')) if s[3] else 0
                } for s in sessions
            ]
        })
        
    except Exception as e:
        return jsonify({'error': f'Hiba: {str(e)}'}), 500

# Add hozzá ezt a route-ot az app.py-ba (az /export/metrics után):

@app.route('/metrics/dashboard')
def metrics_dashboard():
    """Metrikák dashboard oldal"""
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Adatbázis kapcsolati hiba', 'error')
            return render_template('metrics.html', metrics={})
        
        cur = conn.cursor()
        
        # Alapvető számok
        cur.execute("SELECT COUNT(*) FROM recommendation_sessions")
        total_sessions = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COUNT(*) FROM user_choices uc
            JOIN recommendation_sessions rs ON uc.user_id = rs.user_id
            WHERE uc.selected_at > rs.session_timestamp
            AND uc.selected_at < rs.session_timestamp + INTERVAL '30 minutes'
        """)
        total_choices = cur.fetchone()[0]
        
        # CTR számítása
        ctr = (total_choices / total_sessions * 100) if total_sessions > 0 else 0
        
        # Csoportonkénti stats
        cur.execute("""
            SELECT 
                rs.user_group,
                COUNT(rs.id) as sessions,
                COUNT(uc.id) as choices
            FROM recommendation_sessions rs
            LEFT JOIN user_choices uc ON rs.user_id = uc.user_id
                AND uc.selected_at > rs.session_timestamp
                AND uc.selected_at < rs.session_timestamp + INTERVAL '30 minutes'
            GROUP BY rs.user_group
            ORDER BY rs.user_group
        """)
        
        group_stats = cur.fetchall()
        conn.close()
        
        metrics_summary = {
            'total_sessions': total_sessions,
            'total_choices': total_choices,
            'overall_ctr': round(ctr, 1),
            'group_stats': [
                {
                    'group': stat[0],
                    'sessions': stat[1],
                    'choices': stat[2],
                    'ctr': round((stat[2] / stat[1] * 100) if stat[1] > 0 else 0, 1)
                }
                for stat in group_stats
            ]
        }
        
        return render_template('metrics.html', metrics=metrics_summary)
        
    except Exception as e:
        logger.error(f"❌ Metrics dashboard hiba: {e}")
        return render_template('metrics.html', metrics={})

@app.route('/visualizations')
def visualizations():
    """Interaktív vizualizációs dashboard"""
    try:
        if not VISUALIZATIONS_AVAILABLE:
            flash('Vizualizációk jelenleg nem érhetők el', 'warning')
            return redirect(url_for('stats'))
        
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        conn = get_db_connection()
        if conn is None:
            flash('Adatbázis kapcsolati hiba', 'error')
            return render_template('visualizations.html', charts={})
        
        cur = conn.cursor()
        
        # BIZTOS MEGOLDÁS: Először nézzük meg milyen oszlopok vannak
        cur.execute("SELECT * FROM user_choices LIMIT 1;")
        columns = [desc[0] for desc in cur.description]
        logger.info(f"📋 user_choices tábla oszlopai: {columns}")
        
        # BIZTOS: Minden oszlopot lekérdezünk és Python-ban dolgozunk
        cur.execute("SELECT * FROM user_choices;")
        all_rows = cur.fetchall()
        
        # Python-ban készítjük az adatokat
        group_stats = {}
        choice_data = []
        
        for row in all_rows:
            row_dict = dict(zip(columns, row))
            
            # Csoport meghatározása (próbáljuk a lehetséges oszlopneveket)
            group = None
            for possible_group_col in ['group_name', 'group', 'test_group', 'user_group']:
                if possible_group_col in row_dict:
                    group = row_dict[possible_group_col] or 'Unknown'
                    break
            
            if not group:
                group = 'Unknown'
            
            # Felhasználónév meghatározása
            username = None
            for possible_user_col in ['username', 'user_name', 'name']:
                if possible_user_col in row_dict:
                    username = row_dict[possible_user_col]
                    break
            
            # Csoportstatisztika
            if group not in group_stats:
                group_stats[group] = set()
            if username:
                group_stats[group].add(username)
            
            # Választási adat készítése
            choice_record = {
                'group': group,
                'hsi': row_dict.get('hsi', 0),
                'esi': row_dict.get('esi', 0),
                'ppi': row_dict.get('ppi', 0),
                'chosen_at': row_dict.get('selected_at') or row_dict.get('created_at') or row_dict.get('chosen_at'),
                'recipe_title': row_dict.get('recipe_title') or row_dict.get('title') or row_dict.get('name', 'Unknown Recipe')
            }
            
            # Kompozit pontszám számítása
            esi_normalized = choice_record['esi'] * 100 / 255
            choice_record['composite_score'] = 0.4 * choice_record['hsi'] + 0.4 * (100 - esi_normalized) + 0.2 * choice_record['ppi']
            
            choice_data.append(choice_record)
        
        # Csoportstatisztika formázása
        formatted_group_stats = [
            {'group': group, 'user_count': len(users)} 
            for group, users in group_stats.items()
        ]
        
        conn.close()
        
        logger.info(f"📊 Feldolgozott adatok: {len(choice_data)} választás, {len(formatted_group_stats)} csoport")
        
        # Vizualizációk generálása
        charts = {}
        
        if formatted_group_stats:
            charts['group_distribution'] = visualizer.group_distribution_chart(formatted_group_stats)
        
        if choice_data:
            charts['composite_analysis'] = visualizer.composite_score_analysis(choice_data)
            charts['hsi_esi_ppi_breakdown'] = visualizer.hsi_esi_ppi_breakdown(choice_data)
            charts['timeline_analysis'] = visualizer.choice_timeline_analysis(choice_data)
        
        return render_template('visualizations.html', 
                             charts=charts,
                             stats={'total_choices': len(choice_data),
                                   'total_groups': len(formatted_group_stats)})
        
    except Exception as e:
        logger.error(f"❌ Visualizations hiba: {e}")
        flash('Hiba történt a vizualizációk generálása során', 'error')
        return render_template('visualizations.html', charts={})
        
@app.route('/export/statistical_report')
def export_statistical_report():
    """Részletes statisztikai jelentés exportálása JSON formátumban"""
    try:
        if not VISUALIZATIONS_AVAILABLE:
            return jsonify({'error': 'Statisztikai modul nem elérhető'}), 503
            
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Adatbázis kapcsolati hiba'}), 500
        
        cur = conn.cursor()
        
        # Ugyanaz az adatlekérés mint a visualizations route-ban
        cur.execute("""
            SELECT 
                u.group_name as group,
                r.hsi, r.esi, r.ppi,
                (0.4 * r.hsi + 0.4 * (100 - r.esi * 100 / 255) + 0.2 * r.ppi) as composite_score
                uc.chosen_at
            FROM user_choices uc
            JOIN users u ON uc.user_id = u.id
            JOIN recipes r ON uc.recipe_id = r.id
            ORDER BY uc.chosen_at
        """)
        
        choice_data = []
        for row in cur.fetchall():
            choice_data.append({
                'group': row[0],
                'hsi': row[1],
                'esi': row[2],
                'ppi': row[3], 
                'composite_score': row[4],
                'chosen_at': row[5].isoformat() if row[5] else None
            })
        
        # Csoportstatisztikák
        cur.execute("""
            SELECT group_name, COUNT(*) as user_count
            FROM users GROUP BY group_name ORDER BY group_name
        """)
        group_stats = [{'group': row[0], 'user_count': row[1]} for row in cur.fetchall()]
        
        conn.close()
        
        # Statisztikai jelentés generálása
        report = visualizer.export_statistical_report(choice_data, group_stats)
        
        return jsonify(report), 200, {
            'Content-Type': 'application/json',
            'Content-Disposition': 'attachment; filename=greenrec_statistical_report.json'
        }
        
    except Exception as e:
        logger.error(f"❌ Statistical report export hiba: {e}")
        return jsonify({'error': f'Hiba: {str(e)}'}), 500

@app.route('/charts/<chart_type>')  
def generate_chart(chart_type):
    """Egyedi chart generálás AJAX hívásokhoz"""
    try:
        if not VISUALIZATIONS_AVAILABLE:
            return jsonify({'error': 'Vizualizációk nem elérhetők'}), 503
            
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Adatbázis hiba'}), 500
            
        # Chart típus alapján megfelelő adatok lekérése és chart generálása
        if chart_type == 'group_distribution':
            cur = conn.cursor()
            cur.execute("SELECT group_name, COUNT(*) FROM users GROUP BY group_name ORDER BY group_name")
            data = [{'group': row[0], 'user_count': row[1]} for row in cur.fetchall()]
            chart_data = visualizer.group_distribution_chart(data)
            
        elif chart_type == 'composite_scores':
            cur = conn.cursor()
            cur.execute("""
                SELECT u.group_name, r.hsi, r.esi, r.ppi,
                       (0.4 * r.hsi + 0.4 * (100 - r.esi * 100 / 255) + 0.2 * r.ppi) as composite_score
                       uc.chosen_at
                FROM user_choices uc
                JOIN users u ON uc.user_id = u.id
                JOIN recipes r ON uc.recipe_id = r.id
            """)
            data = [{'group': row[0], 'hsi': row[1], 'esi': row[2], 'ppi': row[3], 
                    'composite_score': row[4], 'chosen_at': row[5]} for row in cur.fetchall()]
            chart_data = visualizer.composite_score_analysis(data)
            
        else:
            return jsonify({'error': 'Ismeretlen chart típus'}), 400
            
        conn.close()
        
        if chart_data:
            return jsonify({'chart': chart_data})
        else:
            return jsonify({'error': 'Chart generálási hiba'}), 500
            
    except Exception as e:
        logger.error(f"❌ Chart generation hiba: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/debug/table_structure')
def debug_table_structure():
    """Debug endpoint a tábla struktúra ellenőrzéséhez"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Oszlopok lekérdezése
        cur.execute("SELECT * FROM user_choices LIMIT 1;")
        columns = [desc[0] for desc in cur.description]
        
        # Minta adatok
        cur.execute("SELECT * FROM user_choices LIMIT 3;")
        sample_rows = cur.fetchall()
        
        result = {
            'columns': columns,
            'sample_data': [dict(zip(columns, row)) for row in sample_rows],
            'total_rows': None
        }
        
        # Összes sor számolása
        cur.execute("SELECT COUNT(*) FROM user_choices;")
        result['total_rows'] = cur.fetchone()[0]
        
        conn.close()
        
        return f"<pre>{result}</pre>"
        
    except Exception as e:
        return f"<pre>HIBA: {e}</pre>"

# Add hozzá az app.py VÉGÉRE (nem módosít meglévő kódot):
@app.route('/debug/stats_data')
def debug_stats_data():
    """CSAK diagnosztika - nem módosít semmit"""
    try:
        conn = get_db_connection()
        if conn is None:
            return "❌ DB kapcsolat sikertelen"
        
        cur = conn.cursor()
        
        # 1. Users tábla ellenőrzés
        cur.execute("SELECT COUNT(*) FROM users;")
        total_users = cur.fetchone()[0]
        
        # 2. Users csoportonként
        cur.execute("SELECT group_name, COUNT(*) FROM users GROUP BY group_name;")
        users_by_group = dict(cur.fetchall())
        
        # 3. Choices ellenőrzés
        cur.execute("SELECT COUNT(*) FROM user_choices;")
        total_choices = cur.fetchone()[0]
        
        # 4. Session ellenőrzés
        session_info = {
            'logged_in': 'user_id' in session,
            'user_id': session.get('user_id'),
            'username': session.get('username'),
            'user_group': session.get('user_group')
        }
        
        conn.close()
        
        result = {
            'total_users': total_users,
            'users_by_group': users_by_group,
            'total_choices': total_choices,
            'session': session_info,
            'timestamp': str(datetime.now())
        }
        
        return f"<pre>{json.dumps(result, indent=2, ensure_ascii=False)}</pre>"
        
    except Exception as e:
        return f"❌ HIBA: {e}"

# ===== APPLICATION STARTUP =====
if __name__ == '__main__':
    logger.info("🚀 GreenRec alkalmazás indítása...")
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"🌐 Szerver indítás port {port}, debug={debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
