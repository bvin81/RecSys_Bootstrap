import os
import logging
import json
from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify, Response

# Logging beállítása
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import psycopg2
    from urllib.parse import urlparse
    logger.info("✅ psycopg2 importálva")
except ImportError as e:
    logger.error(f"❌ psycopg2 import hiba: {e}")
    psycopg2 = None

try:
    from werkzeug.security import generate_password_hash, check_password_hash
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.preprocessing import MinMaxScaler
    import pandas as pd
    import numpy as np
    logger.info("✅ Összes dependency importálva")
except ImportError as e:
    logger.error(f"❌ Dependency import hiba: {e}")
    raise

from datetime import datetime

# Flask app inicializálás
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fejlesztesi_kulcs_123_heroku')
app.config['DEBUG'] = False
logger.info("🚀 Flask app inicializálva")

# ===== DATABASE CONNECTION =====
def get_db_connection():
    """PostgreSQL kapcsolat létrehozása hibakezeléssel"""
    try:
        DATABASE_URL = os.environ.get('DATABASE_URL')
        if DATABASE_URL:
            # Heroku PostgreSQL URL javítása
            if DATABASE_URL.startswith('postgres://'):
                DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
                logger.info("✅ Database URL javítva postgresql://-re")
            
            result = urlparse(DATABASE_URL)
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
                self.create_dummy_data()
                return
            except Exception as e:
                logger.warning(f"⚠️  Recipes tábla nem létezik: {e}")
                logger.warning("⚠️  Nincs recept adat, dummy adatok létrehozása")
                self.create_dummy_data()
                return
                
            # Ha létezik a tábla, betöltjük az adatokat
            query = """
                SELECT id, title, hsi, esi, ppi, category, ingredients, instructions, images
                FROM recipes
                """
            self.recipes_df = pd.read_sql_query(query, conn)
            
            if len(self.recipes_df) == 0:
                logger.warning("⚠️  Üres recipes tábla, dummy adatok létrehozása")
                self.create_dummy_data()
                return
                
            logger.info(f"✅ {len(self.recipes_df)} recept betöltve az adatbázisból")
            self.preprocess_data()
            
        except Exception as e:
            logger.error(f"❌ Receptek betöltési hiba: {e}")
            logger.warning("⚠️  Fallback: dummy adatok létrehozása")
            self.create_dummy_data()
    
    def create_dummy_data(self):
        """Dummy adatok létrehozása ha nincs adatbázis"""
        logger.info("🔧 Dummy adatok létrehozása...")
        dummy_recipes = [
            {
                'id': 1,
                'title': 'Zöldséges quinoa saláta',
                'hsi': 85.5,
                'esi': 45.2,
                'ppi': 78.0,
                'category': 'Saláták',
                'ingredients': 'quinoa, uborka, paradicsom, avokádó, citrom',
                'instructions': 'Főzd meg a quinoát, keverd össze a zöldségekkel.',
                'images': 'https://via.placeholder.com/300x200?text=Quinoa+Salat'
            },
            {
                'id': 2,
                'title': 'Vegán chili sin carne',
                'hsi': 78.3,
                'esi': 38.7,
                'ppi': 82.5,
                'category': 'Főételek',
                'ingredients': 'bab, kukorica, paprika, hagyma, paradicsom',
                'instructions': 'Dinszteld le a zöldségeket, add hozzá a babot.',
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
    
    def get_recommendations(self, user_preferences=None, num_recommendations=5):
        """Ajánlások generálása hibakezeléssel"""
        try:
            if self.recipes_df is None or len(self.recipes_df) == 0:
                logger.warning("⚠️  Nincs elérhető recept adat")
                return []
            
            # Kompozit pontszám számítása
            self.recipes_df['composite_score'] = (
                0.4 * self.recipes_df['hsi'] +
                0.4 * self.recipes_df['esi_inv'] +
                0.2 * self.recipes_df['ppi']
            )
            
            # Top receptek kiválasztása
            top_recipes = self.recipes_df.nlargest(num_recommendations, 'composite_score')
            
            recommendations = []
            for _, recipe in top_recipes.iterrows():
                recommendations.append({
                    'id': int(recipe['id']),
                    'title': recipe['title'],
                    'hsi': round(float(recipe['hsi']) * 100, 1),  # Visszaalakítás 0-100 skálára
                    'esi': round(float(recipe['esi']) * 100, 1),
                    'ppi': round(float(recipe['ppi']) * 100, 1),
                    'category': recipe['category'],
                    'ingredients': recipe['ingredients'],
                    'instructions': recipe['instructions'],
                    'images': recipe.get('images', 'https://via.placeholder.com/300x200?text=No+Image')
                })
            
            logger.info(f"✅ {len(recommendations)} ajánlás generálva")
            return recommendations
            
        except Exception as e:
            logger.error(f"❌ Ajánlási hiba: {e}")
            return []

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
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                session_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                recommendations_json TEXT NOT NULL
            );
        """)
        
        # Ajánlások mentése JSON formátumban
        recommendations_json = json.dumps(recommendations, ensure_ascii=False)
        
        cur.execute("""
            INSERT INTO recommendation_sessions (user_id, recommendations_json)
            VALUES (%s, %s)
        """, (user_id, recommendations_json))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ Ajánlások rögzítve user_id={user_id}, {len(recommendations)} recept")
        
    except Exception as e:
        logger.error(f"❌ Ajánlás logging hiba: {e}")

# ===== AUTHENTICATION FUNCTIONS =====
def check_user_credentials(username, password):
    """Felhasználó hitelesítés"""
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("❌ Nincs adatbázis kapcsolat a bejelentkezéshez")
            return False, None
            
        cur = conn.cursor()
        
        # Ellenőrizzük hogy létezik-e a users tábla
        try:
            cur.execute("""
                SELECT id, password_hash, group_name 
                FROM users 
                WHERE username = %s
                """, (username,))
        except psycopg2.errors.UndefinedTable:
            logger.error("❌ Users tábla nem létezik")
            return False, None
            
        user = cur.fetchone()
        conn.close()
        
        if user and check_password_hash(user[1], password):
            return True, {'id': user[0], 'username': username, 'group': user[2]}
        return False, None
        
    except Exception as e:
        logger.error(f"❌ Bejelentkezés hiba: {e}")
        return False, None

def create_user(username, password, group_name):
    """Új felhasználó létrehozása"""
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("❌ Nincs adatbázis kapcsolat a regisztrációhoz")
            return False, "Adatbázis kapcsolati hiba"
            
        cur = conn.cursor()
        
        # Ellenőrizzük, hogy létezik-e már a felhasználó
        try:
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                return False, "A felhasználónév már foglalt"
        except psycopg2.errors.UndefinedTable:
            logger.error("❌ Users tábla nem létezik")
            return False, "Adatbázis nincs inicializálva"
        
        # Jelszó hash-elése és felhasználó létrehozása
        password_hash = generate_password_hash(password)
        cur.execute("""
            INSERT INTO users (username, password_hash, group_name, created_at)
            VALUES (%s, %s, %s, %s)
            """, (username, password_hash, group_name, datetime.now()))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Új felhasználó létrehozva: {username} ({group_name})")
        return True, "Sikeres regisztráció"
        
    except Exception as e:
        logger.error(f"❌ Regisztrációs hiba: {e}")
        return False, f"Regisztrációs hiba: {str(e)}"

# ===== ROUTES =====
@app.route('/')
def index():
    """Főoldal - bejelentkezés ellenőrzéssel"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        if recommender is None:
            flash('Az ajánlórendszer jelenleg nem elérhető.', 'warning')
            recommendations = []
        else:
            recommendations = recommender.get_recommendations(num_recommendations=5)
        
        user_group = session.get('user_group', 'A')
        
        return render_template('index.html', 
                             recommendations=recommendations,
                             user_group=user_group,
                             username=session.get('username'))
    except Exception as e:
        logger.error(f"❌ Index oldal hiba: {e}")
        flash('Hiba történt az ajánlások betöltésekor.', 'error')
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
    """AJAX ajánlások endpoint BŐVÍTETT LOGGING-GAL"""
    if 'user_id' not in session:
        return jsonify({'error': 'Nincs bejelentkezve'}), 401
    
    try:
        if recommender is None:
            return jsonify({'error': 'Ajánlórendszer nem elérhető'}), 500
            
        recommendations = recommender.get_recommendations(num_recommendations=5)
        
        # ✅ ÚJ: Ajánlások logging-ja az adatbázisba
        log_recommendations(session['user_id'], recommendations)
        
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
        
        # Ellenőrizzük hogy létezik-e a user_choices tábla
        try:
            cur.execute("""
                INSERT INTO user_choices (user_id, recipe_id, selected_at)
                VALUES (%s, %s, %s)
                """, (session['user_id'], recipe_id, datetime.now()))
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Recept választás rögzítve: user={session['user_id']}, recipe={recipe_id}")
            return jsonify({'success': True})
            
        except psycopg2.errors.UndefinedTable:
            logger.warning("⚠️  user_choices tábla nem létezik")
            return jsonify({'success': True})  # Silent fail, ne akadjon meg ezen
        
    except Exception as e:
        logger.error(f"❌ Recept választás hiba: {e}")
        return jsonify({'error': 'Hiba a választás rögzítésekor'}), 500

@app.route('/stats')
def stats():
    """Statisztikai oldal"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Adatbázis kapcsolati hiba', 'error')
            return render_template('stats.html', stats={})
        
        cur = conn.cursor()
        
        # Alapvető statisztikák lekérdezése
        stats = {}
        
        try:
            # Felhasználók száma csoportonként
            cur.execute("""
                SELECT group_name, COUNT(*) as count
                FROM users
                GROUP BY group_name
                ORDER BY group_name
                """)
            stats['user_groups'] = dict(cur.fetchall())
        except:
            stats['user_groups'] = {}
        
        try:
            # Összes felhasználó
            cur.execute("SELECT COUNT(*) FROM users")
            stats['total_users'] = cur.fetchone()[0]
        except:
            stats['total_users'] = 0
        
        try:
            # Összes recept
            cur.execute("SELECT COUNT(*) FROM recipes")
            stats['total_recipes'] = cur.fetchone()[0]
        except:
            stats['total_recipes'] = len(recommender.recipes_df) if recommender and recommender.recipes_df is not None else 0
        
        try:
            # Összes választás
            cur.execute("SELECT COUNT(*) FROM user_choices")
            stats['total_choices'] = cur.fetchone()[0]
        except:
            stats['total_choices'] = 0
        
        conn.close()
        return render_template('stats.html', stats=stats)
        
    except Exception as e:
        logger.error(f"❌ Statisztika oldal hiba: {e}")
        flash('Hiba történt a statisztikák betöltésekor', 'error')
        return render_template('stats.html', stats={})

# ===== EXPORT ROUTES =====
@app.route('/export/users')
def export_users():
    """Felhasználók exportálása CSV-be"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        if conn is None:
            return "Adatbázis kapcsolati hiba", 500
        
        cur = conn.cursor()
        
        # Felhasználók adatai
        cur.execute("""
            SELECT 
                id,
                username,
                group_name,
                created_at,
                CASE 
                    WHEN username LIKE 'user_%' THEN 'teszt'
                    ELSE 'valós'
                END as user_type
            FROM users 
            ORDER BY created_at
        """)
        
        users = cur.fetchall()
        conn.close()
        
        # CSV generálás
        import io
        output = io.StringIO()
        output.write('id,username,group_name,created_at,user_type\n')
        
        for user in users:
            output.write(f'{user[0]},{user[1]},{user[2]},{user[3]},{user[4]}\n')
        
        # Response
        response = Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=greenrec_users.csv'}
        )
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Users export hiba: {e}")
        return f"Export hiba: {str(e)}", 500

@app.route('/export/choices')
def export_choices():
    """Felhasználói választások exportálása CSV-be"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        if conn is None:
            return "Adatbázis kapcsolati hiba", 500
        
        cur = conn.cursor()
        
        # Választások részletes adatokkal
        cur.execute("""
            SELECT 
                uc.id as choice_id,
                u.username,
                u.group_name,
                r.title as recipe_title,
                r.hsi,
                r.esi, 
                r.ppi,
                r.category,
                uc.selected_at,
                CASE 
                    WHEN u.username LIKE 'user_%' THEN 'teszt'
                    ELSE 'valós'
                END as user_type
            FROM user_choices uc
            JOIN users u ON uc.user_id = u.id  
            JOIN recipes r ON uc.recipe_id = r.id
            ORDER BY uc.selected_at
        """)
        
        choices = cur.fetchall()
        conn.close()
        
        # CSV generálás
        import io
        output = io.StringIO()
        output.write('choice_id,username,group_name,recipe_title,hsi,esi,ppi,category,selected_at,user_type\n')
        
        for choice in choices:
            # CSV-safe string formatting
            title = str(choice[3]).replace(',', ';').replace('\n', ' ')
            output.write(f'{choice[0]},{choice[1]},{choice[2]},"{title}",{choice[4]},{choice[5]},{choice[6]},{choice[7]},{choice[8]},{choice[9]}\n')
        
        # Response
        response = Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=greenrec_choices.csv'}
        )
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Choices export hiba: {e}")
        return f"Export hiba: {str(e)}", 500

@app.route('/export/recommendations')
def export_recommendations():
    """Ajánlási szeszók exportálása"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        if conn is None:
            return "Adatbázis kapcsolati hiba", 500
        
        cur = conn.cursor()
        
        # Ajánlási szeszók lekérdezése
        cur.execute("""
            SELECT 
                rs.id as session_id,
                u.username,
                u.group_name,
                rs.session_timestamp,
                rs.recommendations_json,
                CASE 
                    WHEN u.username LIKE 'user_%' THEN 'teszt'
                    ELSE 'valós'
                END as user_type
            FROM recommendation_sessions rs
            JOIN users u ON rs.user_id = u.id
            ORDER BY rs.session_timestamp
        """)
        
        sessions = cur.fetchall()
        conn.close()
        
        # CSV generálás
        import io
        output = io.StringIO()
        output.write('session_id,username,group_name,session_timestamp,recipe_1_id,recipe_1_title,recipe_2_id,recipe_2_title,recipe_3_id,recipe_3_title,recipe_4_id,recipe_4_title,recipe_5_id,recipe_5_title,user_type\n')
        
        for session in sessions:
            recommendations = json.loads(session[4])
            
            # 5 recept kicsomagolása
            recipe_data = []
            for i in range(5):
                if i < len(recommendations):
                    recipe_data.extend([
                        recommendations[i]['id'],
                        recommendations[i]['title'].replace(',', ';').replace('"', '')
                    ])
                else:
                    recipe_data.extend(['', ''])
            
            output.write(f'{session[0]},{session[1]},{session[2]},{session[3]},{",".join(map(str, recipe_data))},{session[5]}\n')
        
        # Response
        response = Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=greenrec_recommendations.csv'}
        )
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Recommendations export hiba: {e}")
        return f"Export hiba: {str(e)}", 500

@app.route('/export/json')
def export_json():
    """Teljes adatok exportálása JSON-be"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Adatbázis kapcsolati hiba'}), 500
        
        cur = conn.cursor()
        
        # Felhasználók
        cur.execute("""
            SELECT id, username, group_name, created_at,
                   CASE WHEN username LIKE 'user_%' THEN 'teszt' ELSE 'valós' END as user_type
            FROM users ORDER BY created_at
        """)
        users_data = []
        for row in cur.fetchall():
            users_data.append({
                'id': row[0],
                'username': row[1], 
                'group_name': row[2],
                'created_at': str(row[3]),
                'user_type': row[4]
            })
        
        # Választások
        cur.execute("""
            SELECT uc.id, u.username, u.group_name, r.title, r.hsi, r.esi, r.ppi, 
                   r.category, uc.selected_at,
                   CASE WHEN u.username LIKE 'user_%' THEN 'teszt' ELSE 'valós' END as user_type
            FROM user_choices uc
            JOIN users u ON uc.user_id = u.id  
            JOIN recipes r ON uc.recipe_id = r.id
            ORDER BY uc.selected_at
        """)
        choices_data = []
        for row in cur.fetchall():
            choices_data.append({
                'choice_id': row[0],
                'username': row[1],
                'group_name': row[2], 
                'recipe_title': row[3],
                'hsi': float(row[4]),
                'esi': float(row[5]),
                'ppi': float(row[6]),
                'category': row[7],
                'selected_at': str(row[8]),
                'user_type': row[9]
            })
        
        # Ajánlási szeszók (ha léteznek)
        try:
            cur.execute("""
                SELECT rs.id, u.username, u.group_name, rs.session_timestamp, rs.recommendations_json,
                       CASE WHEN u.username LIKE 'user_%' THEN 'teszt' ELSE 'valós' END as user_type
                FROM recommendation_sessions rs
                JOIN users u ON rs.user_id = u.id
                ORDER BY rs.session_timestamp
            """)
            recommendations_data = []
            for row in cur.fetchall():
                recommendations_data.append({
                    'session_id': row[0],
                    'username': row[1],
                    'group_name': row[2],
                    'session_timestamp': str(row[3]),
                    'recommendations': json.loads(row[4]),
                    'user_type': row[5]
                })
        except:
            recommendations_data = []
        
        # Statisztikák
        cur.execute("SELECT group_name, COUNT(*) FROM users GROUP BY group_name")
        stats_users = dict(cur.fetchall())
        
        cur.execute("""
            SELECT u.group_name, COUNT(uc.id) as choice_count
            FROM users u 
            LEFT JOIN user_choices uc ON u.id = uc.user_id
            GROUP BY u.group_name
        """)
        stats_choices = dict(cur.fetchall())
        
        conn.close()
        
        # JSON strukturálás
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'summary': {
                'total_users': len(users_data),
                'total_choices': len(choices_data),
                'total_recommendation_sessions': len(recommendations_data),
                'users_by_group': stats_users,
                'choices_by_group': stats_choices
            },
            'users': users_data,
            'choices': choices_data,
            'recommendation_sessions': recommendations_data
        }
        
        # JSON Response
        response = Response(
            json.dumps(export_data, indent=2, ensure_ascii=False),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=greenrec_export.json'}
        )
        
        return response
        
    except Exception as e:
        logger.error(f"❌ JSON export hiba: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        db_status = "OK" if get_db_connection() is not None else "ERROR"
        recommender_status = "OK" if recommender is not None else "ERROR"
        
        return jsonify({
            'status': 'OK',
            'database': db_status,
            'recommender': recommender_status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'ERROR',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ===== ERROR HANDLERS =====
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# ===== APPLICATION STARTUP =====
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"🚀 GreenRec alkalmazás indítása - Port: {port}, Debug: {debug}")
    app.run(host='0.0.0.0', port=port, debug=debug)
