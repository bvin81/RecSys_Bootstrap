import os
import logging
from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify

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

# ===== ROUND-ROBIN A/B/C CSOPORTOSÍTÁS =====
def assign_group():
    """Soros A/B/C csoport kiosztás hibakezeléssel"""
    try:
        conn = get_db_connection()
        if not conn:
            return 'A'  # Fallback
            
        cur = conn.cursor()
        cur.execute("SELECT group_name FROM users ORDER BY id DESC LIMIT 1;")
        last_user = cur.fetchone()
        
        if last_user is None:
            next_group = 'A'
        else:
            last_group = last_user[0]
            if last_group == 'A':
                next_group = 'B'
            elif last_group == 'B':
                next_group = 'C'
            else:
                next_group = 'A'
        
        cur.close()
        conn.close()
        return next_group
        
    except Exception as e:
        logger.error(f"❌ Csoport kiosztási hiba: {e}")
        import random
        return random.choice(['A', 'B', 'C'])

# ===== AJÁNLÓRENDSZER OSZTÁLY =====
class GreenRecRecommender:
    def __init__(self):
        logger.info("🔧 Ajánlórendszer inicializálása...")
        self.recipes_df = None
        self.vectorizer = None
        self.ingredients_matrix = None
        self.scaler = None
        
        try:
            self.load_recipes()
            if self.recipes_df is None or len(self.recipes_df) == 0:
                logger.warning("⚠️  Nincs recept adat, dummy adatok létrehozása")
                self.create_dummy_data()
            logger.info("✅ Ajánlórendszer sikeresen inicializálva")
        except Exception as e:
            logger.error(f"❌ Ajánlórendszer inicializálási hiba: {e}")
            self.create_dummy_data()
    
    def load_recipes(self):
        """Receptek betöltése adatbázisból hibakezeléssel"""
        try:
            conn = get_db_connection()
            if not conn:
                logger.warning("⚠️  Nincs adatbázis kapcsolat")
                return
            
            # Ellenőrizzük, hogy létezik-e a recipes tábla
            cur = conn.cursor()
            try:
                cur.execute("SELECT COUNT(*) FROM recipes LIMIT 1;")
                count = cur.fetchone()[0]
                logger.info(f"📊 {count} recept található az adatbázisban")
                
                if count == 0:
                    logger.warning("⚠️  Recipes tábla üres")
                    return
                    
            except Exception as e:
                logger.warning(f"⚠️  Recipes tábla nem létezik: {e}")
                return
            
            query = """
            SELECT id, title, hsi, esi, ppi, category, ingredients, instructions, images
            FROM recipes
            LIMIT 100
            """
            
            # SQL Alchemy használata pandas warning elkerülésére
            from sqlalchemy import create_engine
            DATABASE_URL = os.environ.get('DATABASE_URL')
            if DATABASE_URL.startswith('postgres://'):
                DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
                
            engine = create_engine(DATABASE_URL)
            self.recipes_df = pd.read_sql_query(query, engine)
            
            conn.close()
            
            if len(self.recipes_df) > 0:
                self.preprocess_data()
                logger.info(f"✅ {len(self.recipes_df)} recept betöltve")
                
        except Exception as e:
            logger.error(f"❌ Receptek betöltési hiba: {e}")
    
    def create_dummy_data(self):
        """Dummy adatok létrehozása"""
        logger.info("🔧 Dummy adatok létrehozása...")
        
        self.recipes_df = pd.DataFrame({
            'id': [1, 2, 3, 4, 5],
            'title': ['Mediterrán Saláta', 'Quinoa Bowl', 'Csirkemell', 'Vegán Curry', 'Halfilé'],
            'hsi': [85.5, 92.1, 76.8, 88.3, 79.2],
            'esi': [45.2, 38.7, 120.5, 42.1, 95.3],
            'ppi': [78.3, 65.4, 88.2, 71.7, 83.1],
            'category': ['Saláta', 'Vegán', 'Hús', 'Vegán', 'Hal'],
            'ingredients': [
                'paradicsom, uborka, olívabogyó, feta sajt',
                'quinoa, édesburgonya, spenót, avokádó',
                'csirkemell, brokkoli, sárgarépa, paprika',
                'kókusztej, curry, zöldségek, rizs',
                'hal, citrom, fűszerek, zöldségek'
            ],
            'instructions': ['Keverj össze', 'Főzd meg', 'Süsd meg', 'Párold', 'Grillezd'],
            'images': ['url1', 'url2', 'url3', 'url4', 'url5']
        })
        
        self.preprocess_data()
        logger.info("✅ Dummy adatok létrehozva")
    
    def preprocess_data(self):
        """Adatok előfeldolgozása"""
        try:
            # Normalizálás
            self.scaler = MinMaxScaler()
            self.recipes_df[['HSI_norm', 'ESI_norm', 'PPI_norm']] = self.scaler.fit_transform(
                self.recipes_df[['hsi', 'esi', 'ppi']]
            )
            
            # Kompozit pontszám (ESI inverz)
            self.recipes_df['composite_score'] = (
                0.4 * self.recipes_df['HSI_norm'] + 
                0.4 * (1 - self.recipes_df['ESI_norm']) + 
                0.2 * self.recipes_df['PPI_norm']
            )
            
            # Összetevők vektorizálása
            self.vectorizer = CountVectorizer(stop_words='english', max_features=500)
            self.ingredients_matrix = self.vectorizer.fit_transform(
                self.recipes_df['ingredients'].fillna('')
            )
            
        except Exception as e:
            logger.error(f"❌ Adatok előfeldolgozási hiba: {e}")
    
    def recommend_by_id(self, recipe_id, top_n=5):
        """Ajánlás generálása"""
        try:
            if self.recipes_df is None or len(self.recipes_df) == 0:
                return pd.DataFrame()
            
            recipe_idx = self.recipes_df[self.recipes_df['id'] == recipe_id].index
            if len(recipe_idx) == 0:
                return self.recipes_df.sample(min(top_n, len(self.recipes_df)))
            
            recipe_idx = recipe_idx[0]
            
            if self.vectorizer is not None and self.ingredients_matrix is not None:
                recipe_vector = self.ingredients_matrix[recipe_idx]
                similarities = cosine_similarity(recipe_vector, self.ingredients_matrix).flatten()
            else:
                similarities = np.random.random(len(self.recipes_df))
            
            self.recipes_df['similarity'] = similarities
            self.recipes_df['final_score'] = (
                0.6 * self.recipes_df['composite_score'] + 
                0.4 * self.recipes_df['similarity']
            )
            
            recommendations = self.recipes_df[
                self.recipes_df['id'] != recipe_id
            ].nlargest(top_n, 'final_score')
            
            return recommendations
            
        except Exception as e:
            logger.error(f"❌ Ajánlás generálási hiba: {e}")
            return self.recipes_df.sample(min(top_n, len(self.recipes_df)))
    
    def generate_explanation(self, recipe_row):
        """Magyarázat generálás"""
        try:
            explanations = []
            
            if 'HSI_norm' in recipe_row and recipe_row['HSI_norm'] > 0.7:
                explanations.append("🥗 Magas egészségességi pontszám")
            elif 'HSI_norm' in recipe_row and recipe_row['HSI_norm'] > 0.4:
                explanations.append("🥗 Közepes egészségességi pontszám")
            
            if 'ESI_norm' in recipe_row and recipe_row['ESI_norm'] < 0.3:
                explanations.append("🌱 Alacsony környezeti terhelés")
            elif 'ESI_norm' in recipe_row and recipe_row['ESI_norm'] < 0.6:
                explanations.append("🌱 Közepes környezeti terhelés")
            
            if 'PPI_norm' in recipe_row and recipe_row['PPI_norm'] > 0.7:
                explanations.append("⭐ Nagyon népszerű recept")
            elif 'PPI_norm' in recipe_row and recipe_row['PPI_norm'] > 0.4:
                explanations.append("⭐ Népszerű recept")
            
            return " • ".join(explanations) if explanations else "Kiegyensúlyozott recept"
            
        except Exception as e:
            logger.error(f"❌ Magyarázat generálási hiba: {e}")
            return "Ajánlott recept fenntarthatósági szempontok alapján"

# Globális ajánlórendszer példány
try:
    logger.info("🔧 Globális ajánlórendszer inicializálása...")
    recommender = GreenRecRecommender()
    logger.info("✅ Globális ajánlórendszer kész")
except Exception as e:
    logger.error(f"❌ Globális ajánlórendszer hiba: {e}")
    recommender = None

# ===== FLASK ROUTE-OK =====

@app.route('/health')
def health_check():
    """Egészség ellenőrzés endpoint"""
    try:
        status = {
            'status': 'healthy',
            'recommender': recommender is not None,
            'database': False,
            'recipes_count': len(recommender.recipes_df) if recommender and recommender.recipes_df is not None else 0
        }
        
        try:
            conn = get_db_connection()
            if conn:
                conn.close()
                status['database'] = True
        except:
            pass
        
        return jsonify(status), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Felhasználói regisztráció"""
    try:
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            
            if not username or not password:
                flash('Kérlek, töltsd ki az összes mezőt.')
                return redirect(url_for('register'))
            
            try:
                conn = get_db_connection()
                if not conn:
                    flash('Adatbázis kapcsolat hiba.')
                    return redirect(url_for('register'))
                    
                cur = conn.cursor()
                
                cur.execute("SELECT id FROM users WHERE username = %s;", (username,))
                if cur.fetchone():
                    flash('Ez a felhasználónév már foglalt.')
                    cur.close()
                    conn.close()
                    return redirect(url_for('register'))
                
                group = assign_group()
                pw_hash = generate_password_hash(password)
                
                cur.execute("""
                    INSERT INTO users (username, password_hash, group_name, created_at) 
                    VALUES (%s, %s, %s, %s);
                """, (username, pw_hash, group, datetime.now()))
                
                conn.commit()
                cur.close()
                conn.close()
                
                flash(f'Sikeres regisztráció! Tesztcsoport: {group}')
                return redirect(url_for('login'))
                
            except Exception as e:
                logger.error(f"❌ Regisztráció adatbázis hiba: {e}")
                flash('Regisztrációs hiba történt.')
                return redirect(url_for('register'))
        
        return render_template('register.html')
        
    except Exception as e:
        logger.error(f"❌ Regisztráció route hiba: {e}")
        flash('Váratlan hiba történt.')
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Bejelentkezés"""
    try:
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            
            try:
                conn = get_db_connection()
                if not conn:
                    flash('Adatbázis kapcsolat hiba.')
                    return render_template('login.html')
                    
                cur = conn.cursor()
                
                cur.execute("""
                    SELECT id, password_hash, group_name 
                    FROM users WHERE username = %s;
                """, (username,))
                user = cur.fetchone()
                
                cur.close()
                conn.close()
                
                if user and check_password_hash(user[1], password):
                    session['user_id'] = user[0]
                    session['username'] = username
                    session['group'] = user[2]
                    return redirect(url_for('index'))
                else:
                    flash('Helytelen felhasználónév vagy jelszó.')
                    
            except Exception as e:
                logger.error(f"❌ Bejelentkezés hiba: {e}")
                flash('Bejelentkezési hiba történt.')
        
        return render_template('login.html')
        
    except Exception as e:
        logger.error(f"❌ Bejelentkezés route hiba: {e}")
        return render_template('login.html')

@app.route('/logout')
def logout():
    """Kijelentkezés"""
    session.clear()
    flash('Sikeres kijelentkezés.')
    return redirect(url_for('login'))

@app.route('/')
def index():
    """Főoldal"""
    try:
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        recipes_list = []
        if recommender and recommender.recipes_df is not None:
            try:
                sample_size = min(20, len(recommender.recipes_df))
                sample_recipes = recommender.recipes_df.sample(sample_size)
                recipes_list = sample_recipes[['id', 'title', 'category']].to_dict('records')
            except Exception as e:
                logger.error(f"❌ Receptek mintavételezési hiba: {e}")
        
        return render_template('index.html', 
                             recipes=recipes_list, 
                             group=session.get('group', 'A'))
        
    except Exception as e:
        logger.error(f"❌ Főoldal hiba: {e}")
        return render_template('index.html', recipes=[], group='A')

@app.route('/recommend', methods=['POST'])
def recommend():
    """Ajánlás generálása"""
    try:
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        recipe_id = int(request.form.get('recipe_id', 0))
        
        if not recommender:
            flash('Az ajánlórendszer jelenleg nem elérhető.')
            return redirect(url_for('index'))
        
        recommendations = recommender.recommend_by_id(recipe_id, top_n=5)
        
        if recommendations.empty:
            flash('Nem találtunk ajánlásokat ehhez a recepthez.')
            return redirect(url_for('index'))
        
        group = session.get('group', 'A')
        show_scores = group in ['B', 'C']
        show_explanation = group == 'C'
        
        explanations = {}
        if show_explanation:
            for _, row in recommendations.iterrows():
                explanations[row['id']] = recommender.generate_explanation(row)
        
        return render_template('results.html', 
                             recommendations=recommendations.to_dict('records'),
                             group=group,
                             show_scores=show_scores,
                             show_explanation=show_explanation,
                             explanations=explanations)
        
    except Exception as e:
        logger.error(f"❌ Ajánlás hiba: {e}")
        flash('Hiba történt az ajánlások generálása során.')
        return redirect(url_for('index'))

@app.route('/select_recipe', methods=['POST'])
def select_recipe():
    """Receptválasztás naplózása"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        
        if recipe_id:
            logger.info(f"✅ Recept választás: {recipe_id}")
            return jsonify({'success': True})
        
        return jsonify({'error': 'No recipe selected'}), 400
        
    except Exception as e:
        logger.error(f"❌ Receptválasztás hiba: {e}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/stats')
def stats():
    """Statisztikai oldal"""
    try:
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        return render_template('stats.html', group_stats=[], choice_stats=[])
        
    except Exception as e:
        logger.error(f"❌ Statisztika hiba: {e}")
        return render_template('stats.html', group_stats=[], choice_stats=[])

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
