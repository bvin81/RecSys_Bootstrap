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

# ===== GREEN RECIPE RECOMMENDER =====
class GreenRecRecommender:
    def __init__(self):
        logger.info("🔧 Ajánlórendszer inicializálása...")
        self.recipes_df = None
        self.vectorizer = CountVectorizer(stop_words='english', max_features=1000)
        self.scaler = MinMaxScaler()
        self.ingredient_matrix = None
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
        """Adatok előfeldolgozása"""
        try:
            # HSI, ESI, PPI normalizálása
            score_columns = ['hsi', 'esi', 'ppi']
            self.recipes_df[score_columns] = self.scaler.fit_transform(self.recipes_df[score_columns])
            
            # ESI invertálása (alacsonyabb környezeti hatás = jobb)
            self.recipes_df['esi_inv'] = 1 - self.recipes_df['esi']
            
            # Összetevők vektorizálása
            if 'ingredients' in self.recipes_df.columns:
                ingredients_text = self.recipes_df['ingredients'].fillna('')
                self.ingredient_matrix = self.vectorizer.fit_transform(ingredients_text)
            
        except Exception as e:
            logger.error(f"❌ Adatok előfeldolgozási hiba: {e}")
    
    def get_recommendations(self, user_preferences=None, num_recommendations=5, user_id=None, diversity_factor=0.3):
        """
        🎯 JAVÍTOTT ajánlások generálása változatossággal és personalizációval
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
            
            # 3. KATEGÓRIA DIVERZITÁS BIZTOSÍTÁSA
            available_categories = df['category'].unique()
            recommendations = []
            
            # Először válasszunk ki minden kategóriából legalább 1 receptet
            for category in available_categories[:num_recommendations]:
                category_recipes = df[df['category'] == category]
                if not category_recipes.empty:
                    # Weighted random selection (magasabb pontszám = nagyobb esély)
                    weights = category_recipes['composite_score'].values
                    weights = (weights - weights.min() + 0.1) ** 2  # Kvadratikus súlyozás
                    
                    try:
                        selected_idx = np.random.choice(
                            category_recipes.index, 
                            p=weights/weights.sum()
                        )
                        recommendations.append(category_recipes.loc[selected_idx])
                        df = df.drop(selected_idx)  # Eltávolítás, hogy ne válasszuk újra
                    except:
                        # Ha hiba van a random choice-szal, vegyük a legjobbat
                        recommendations.append(category_recipes.nlargest(1, 'composite_score').iloc[0])
            
            # 4. FENNMARADÓ HELYEK FELTÖLTÉSE
            remaining_slots = num_recommendations - len(recommendations)
            if remaining_slots > 0 and not df.empty:
                # Mix stratégia: részben top pontszámú, részben random
                top_count = max(1, int(remaining_slots * (1 - diversity_factor)))
                random_count = remaining_slots - top_count
                
                # Top pontszámú receptek
                if top_count > 0:
                    top_recipes = df.nlargest(min(top_count, len(df)), 'composite_score')
                    recommendations.extend(top_recipes.to_dict('records'))
                    df = df.drop(top_recipes.index)
                
                # Random receptek (weighted)
                if random_count > 0 and not df.empty:
                    weights = df['composite_score'].values
                    weights = (weights - weights.min() + 0.1)  # Elkerüljük a 0 súlyokat
                    
                    selected_indices = np.random.choice(
                        df.index,
                        size=min(random_count, len(df)),
                        replace=False,
                        p=weights/weights.sum()
                    )
                    recommendations.extend(df.loc[selected_indices].to_dict('records'))
            
            # 5. FELHASZNÁLÓI ELŐZMÉNYEK FRISSÍTÉSE
            if user_id:
                if user_id not in self.user_history:
                    self.user_history[user_id] = []
                
                new_ids = [rec['id'] for rec in recommendations if isinstance(rec, dict)]
                if not new_ids:  # Ha pandas Series-ek vannak
                    new_ids = [rec['id'] if isinstance(rec, dict) else rec.id for rec in recommendations]
                
                self.user_history[user_id].extend(new_ids)
                # Korlátozás az utolsó 50 receptre
                self.user_history[user_id] = self.user_history[user_id][-50:]
            
            # 6. RANDOM SHUFFLE ÉS FORMÁTUM ÁTALAKÍTÁSA
            random.shuffle(recommendations)  # Véletlenszerű sorrend
            
            final_recommendations = []
            for recipe in recommendations[:num_recommendations]:
                if isinstance(recipe, dict):
                    # Már dict formátumban van
                    formatted_recipe = recipe
                else:
                    # Pandas Series -> dict konverzió
                    formatted_recipe = recipe.to_dict()
                
                # Pontszámok visszaalakítása megjelenítéshez (0-100 skála)
                final_recommendations.append({
                    'id': int(formatted_recipe['id']),
                    'title': formatted_recipe['title'],
                    'hsi': round(float(formatted_recipe['hsi']) * 100, 1),
                    'esi': round(float(formatted_recipe['esi']) * 100, 1),
                    'ppi': round(float(formatted_recipe['ppi']) * 100, 1),
                    'category': formatted_recipe['category'],
                    'ingredients': formatted_recipe['ingredients'],
                    'instructions': formatted_recipe['instructions'],
                    'images': formatted_recipe.get('images', 'https://via.placeholder.com/300x200?text=No+Image')
                })
            
            logger.info(f"✅ {len(final_recommendations)} változatos ajánlás generálva (diversity: {diversity_factor})")
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
    """🎯 AJAX ajánlások endpoint VÁLTOZATOS AJÁNLÁSOKKAL"""
    if 'user_id' not in session:
        return jsonify({'error': 'Nincs bejelentkezve'}), 401
    
    try:
        if recommender is None:
            return jsonify({'error': 'Ajánlórendszer nem elérhető'}), 500
        
        # Felhasználói csoport és preferenciák
        user_group = session.get('user_group', 'A')
        user_preferences = {
            'group': user_group,
            'user_id': session['user_id']
        }
        
        # 🚀 VÁLTOZATOS ajánlások generálása
        recommendations = recommender.get_personalized_recommendations(
            user_id=session['user_id'],
            user_preferences=user_preferences,
            num_recommendations=5
        )
        
        # ✅ KULCS: AJÁNLÁSOK TELJES LOGGING-JA
        if recommendations:
            log_recommendation_session(session['user_id'], recommendations, user_group)
        
        logger.info(f"✅ {len(recommendations)} változatos ajánlás generálva user_id={session['user_id']}, group={user_group}")
        return jsonify({'recommendations': recommendations})
        
    except Exception as e:
        logger.error(f"❌ Ajánlási endpoint hiba: {e}")
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
    """Teljes adatexport JSON formátumban"""
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Adatbázis kapcsolati hiba'}), 500
        
        export_data = {}
        cur = conn.cursor()
        
        # Felhasználók
        cur.execute("""
            SELECT id, username, group_name, created_at,
            CASE WHEN username LIKE 'user_%' THEN 'teszt' ELSE 'valós' END as user_type
            FROM users ORDER BY created_at
        """)
        users_data = cur.fetchall()
        export_data['users'] = [
            {
                'id': user[0],
                'username': user[1], 
                'group_name': user[2],
                'created_at': user[3].isoformat() if user[3] else None,
                'user_type': user[4]
            } for user in users_data
        ]
        
        # Választások
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
        export_data['choices'] = [
            {
                'choice_id': choice[0],
                'username': choice[1],
                'group_name': choice[2], 
                'recipe_title': choice[3],
                'hsi': float(choice[4]),
                'esi': float(choice[5]),
                'ppi': float(choice[6]),
                'category': choice[7],
                'selected_at': choice[8].isoformat() if choice[8] else None,
                'user_type': choice[9]
            } for choice in choices_data
        ]
        
        # Ajánlási szesszók
        try:
            cur.execute("""
                SELECT rs.id, rs.user_id, u.username, u.group_name, 
                       rs.session_timestamp, rs.recommended_recipe_ids, rs.recommendation_count
                FROM recommendation_sessions rs
                JOIN users u ON rs.user_id = u.id
                ORDER BY rs.session_timestamp
            """)
            sessions_data = cur.fetchall()
            export_data['recommendation_sessions'] = [
                {
                    'session_id': session[0],
                    'user_id': session[1],
                    'username': session[2],
                    'group_name': session[3],
                    'timestamp': session[4].isoformat() if session[4] else None,
                    'recommended_recipe_ids': session[5],
                    'recommendation_count': session[6]
                } for session in sessions_data
            ]
        except:
            export_data['recommendation_sessions'] = []
        
        # Receptek
        cur.execute("SELECT id, title, hsi, esi, ppi, category FROM recipes ORDER BY id")
        recipes_data = cur.fetchall()
        export_data['recipes'] = [
            {
                'id': recipe[0],
                'title': recipe[1],
                'hsi': float(recipe[2]),
                'esi': float(recipe[3]), 
                'ppi': float(recipe[4]),
                'category': recipe[5]
            } for recipe in recipes_data
        ]
        
        conn.close()
        
        # Metaadatok
        export_data['export_metadata'] = {
            'export_timestamp': datetime.now().isoformat(),
            'total_users': len(export_data['users']),
            'total_choices': len(export_data['choices']),
            'total_recipes': len(export_data['recipes']),
            'total_sessions': len(export_data['recommendation_sessions'])
        }
        
        return Response(
            json.dumps(export_data, indent=2, ensure_ascii=False),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=greenrec_export.json'}
        )
        
    except Exception as e:
        logger.error(f"❌ JSON export hiba: {e}")
        return jsonify({'error': 'Export hiba'}), 500

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
        
        # Csoportonkénti felhasználói statisztikák
        cur.execute("""
            SELECT group_name, COUNT(*) as user_count
            FROM users 
            GROUP BY group_name 
            ORDER BY group_name
        """)
        group_stats = [{'group': row[0], 'user_count': row[1]} for row in cur.fetchall()]
        
        # Választási adatok részletes lekérése
        cur.execute("""
            SELECT 
                u.group_name as group,
                r.hsi, r.esi, r.ppi,
                (0.4 * r.hsi + 0.4 * (255 - r.esi) + 0.2 * r.ppi) as composite_score,
                uc.chosen_at,
                r.title as recipe_title
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
                'chosen_at': row[5],
                'recipe_title': row[6]
            })
        
        conn.close()
        
        # Vizualizációk generálása
        charts = {}
        
        if group_stats:
            charts['group_distribution'] = visualizer.group_distribution_chart(group_stats)
        
        if choice_data:
            charts['composite_analysis'] = visualizer.composite_score_analysis(choice_data)
            charts['hsi_esi_ppi_breakdown'] = visualizer.hsi_esi_ppi_breakdown(choice_data)
            charts['timeline_analysis'] = visualizer.choice_timeline_analysis(choice_data)
        
        return render_template('visualizations.html', 
                             charts=charts,
                             stats={'total_choices': len(choice_data),
                                   'total_groups': len(group_stats)})
        
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
                (0.4 * r.hsi + 0.4 * (255 - r.esi) + 0.2 * r.ppi) as composite_score,
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
                       (0.4 * r.hsi + 0.4 * (255 - r.esi) + 0.2 * r.ppi) as composite_score,
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

# ===== APPLICATION STARTUP =====
if __name__ == '__main__':
    logger.info("🚀 GreenRec alkalmazás indítása...")
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"🌐 Szerver indítás port {port}, debug={debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
