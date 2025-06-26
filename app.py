import os
import random
from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify
import psycopg2
from urllib.parse import urlparse
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler
import pandas as pd
import numpy as np
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fejlesztesi_kulcs_123')

# ===== DATABASE CONNECTION =====
def get_db_connection():
    """PostgreSQL kapcsolat létrehozása"""
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        # Heroku környezet
        result = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            dbname=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port,
            sslmode='require'
        )
    else:
        # Helyi fejlesztés
        conn = psycopg2.connect(
            host="localhost",
            database="greenrec_local",
            user="postgres",
            password="password"
        )
    return conn

# ===== ROUND-ROBIN A/B/C CSOPORTOSÍTÁS =====
def assign_group():
    """Soros A/B/C csoport kiosztás új felhasználóknak"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Utolsó felhasználó csoportjának lekérése
    cur.execute("SELECT group_name FROM users ORDER BY id DESC LIMIT 1;")
    last_user = cur.fetchone()
    
    if last_user is None:
        next_group = 'A'  # Első felhasználó
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

# ===== AJÁNLÓRENDSZER OSZTÁLY =====
class GreenRecRecommender:
    def __init__(self):
        self.recipes_df = None
        self.vectorizer = None
        self.ingredients_matrix = None
        self.scaler = None
        self.load_recipes()
    
    def load_recipes(self):
        """Receptek betöltése adatbázisból"""
        conn = get_db_connection()
        query = """
        SELECT id, title, hsi, esi, ppi, category, ingredients, instructions, images
        FROM recipes
        """
        self.recipes_df = pd.read_sql_query(query, conn)
        conn.close()
        
        if len(self.recipes_df) > 0:
            self.preprocess_data()
    
    def preprocess_data(self):
        """Adatok előfeldolgozása és normalizálása"""
        # Normalizálás 0-1 közé
        self.scaler = MinMaxScaler()
        self.recipes_df[['HSI_norm', 'ESI_norm', 'PPI_norm']] = self.scaler.fit_transform(
            self.recipes_df[['hsi', 'esi', 'ppi']]
        )
        
        # Kompozit pontszám számítása (ESI inverz, mert alacsonyabb jobb)
        self.recipes_df['composite_score'] = (
            0.4 * self.recipes_df['HSI_norm'] + 
            0.4 * (1 - self.recipes_df['ESI_norm']) + 
            0.2 * self.recipes_df['PPI_norm']
        )
        
        # Összetevők vektorizálása
        self.vectorizer = CountVectorizer(stop_words='english', max_features=1000)
        self.ingredients_matrix = self.vectorizer.fit_transform(self.recipes_df['ingredients'].fillna(''))
    
    def recommend_by_id(self, recipe_id, top_n=5):
        """Adott recept ID alapján ajánlás"""
        if self.recipes_df is None or len(self.recipes_df) == 0:
            return pd.DataFrame()
        
        try:
            # Kiválasztott recept indexének megkeresése
            recipe_idx = self.recipes_df[self.recipes_df['id'] == recipe_id].index[0]
            
            # Hasonlóság számítása összetevők alapján
            recipe_vector = self.ingredients_matrix[recipe_idx]
            similarities = cosine_similarity(recipe_vector, self.ingredients_matrix).flatten()
            
            # Kombinált pontszám: hasonlóság + kompozit pontszám
            self.recipes_df['similarity'] = similarities
            self.recipes_df['final_score'] = (
                0.6 * self.recipes_df['composite_score'] + 
                0.4 * self.recipes_df['similarity']
            )
            
            # Top-N ajánlás (kivéve az eredeti recept)
            recommendations = self.recipes_df[self.recipes_df['id'] != recipe_id].nlargest(top_n, 'final_score')
            
            return recommendations
            
        except IndexError:
            return pd.DataFrame()
    
    def generate_explanation(self, recipe_row):
        """Egyszerű demonstratív magyarázat generálása"""
        explanations = []
        
        if recipe_row['HSI_norm'] > 0.7:
            explanations.append("🥗 Magas egészségességi pontszám")
        elif recipe_row['HSI_norm'] > 0.4:
            explanations.append("🥗 Közepes egészségességi pontszám")
        
        if recipe_row['ESI_norm'] < 0.3:
            explanations.append("🌱 Alacsony környezeti terhelés")
        elif recipe_row['ESI_norm'] < 0.6:
            explanations.append("🌱 Közepes környezeti terhelés")
        else:
            explanations.append("🌱 Magasabb környezeti terhelés")
        
        if recipe_row['PPI_norm'] > 0.7:
            explanations.append("⭐ Nagyon népszerű recept")
        elif recipe_row['PPI_norm'] > 0.4:
            explanations.append("⭐ Népszerű recept")
        
        return " • ".join(explanations) if explanations else "Kiegyensúlyozott recept"

# Globális ajánlórendszer példány
recommender = GreenRecRecommender()

# ===== FLASK ROUTE-OK =====

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Felhasználói regisztráció"""
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        if not username or not password:
            flash('Kérlek, töltsd ki az összes mezőt.')
            return redirect(url_for('register'))
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Ellenőrizzük, hogy létezik-e már a felhasználó
        cur.execute("SELECT id FROM users WHERE username = %s;", (username,))
        if cur.fetchone():
            flash('Ez a felhasználónév már foglalt.')
            cur.close()
            conn.close()
            return redirect(url_for('register'))
        
        # Új felhasználó létrehozása
        group = assign_group()
        pw_hash = generate_password_hash(password)
        
        cur.execute(
            "INSERT INTO users (username, password_hash, group_name, created_at) VALUES (%s, %s, %s, %s);",
            (username, pw_hash, group, datetime.now())
        )
        conn.commit()
        cur.close()
        conn.close()
        
        flash(f'Sikeres regisztráció! Tesztcsoport: {group}')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Felhasználói bejelentkezés"""
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT id, password_hash, group_name FROM users WHERE username = %s;", (username,))
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
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Felhasználói kijelentkezés"""
    session.clear()
    flash('Sikeres kijelentkezés.')
    return redirect(url_for('login'))

@app.route('/')
def index():
    """Főoldal - receptválasztó"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Véletlenszerű 20 recept kiválasztása a választáshoz
    if recommender.recipes_df is not None and len(recommender.recipes_df) > 0:
        sample_recipes = recommender.recipes_df.sample(min(20, len(recommender.recipes_df)))
        recipes_list = sample_recipes[['id', 'title', 'category']].to_dict('records')
    else:
        recipes_list = []
    
    return render_template('index.html', recipes=recipes_list, group=session['group'])

@app.route('/recommend', methods=['POST'])
def recommend():
    """Ajánlás generálása kiválasztott recept alapján"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    recipe_id = int(request.form['recipe_id'])
    
    # Ajánlások generálása
    recommendations = recommender.recommend_by_id(recipe_id, top_n=5)
    
    if recommendations.empty:
        flash('Nem találtunk ajánlásokat.')
        return redirect(url_for('index'))
    
    # Felhasználó csoportja alapján eltérő megjelenítés
    group = session['group']
    show_scores = group in ['B', 'C']
    show_explanation = group == 'C'
    
    # Magyarázatok generálása C csoportnak
    explanations = {}
    if show_explanation:
        for idx, row in recommendations.iterrows():
            explanations[row['id']] = recommender.generate_explanation(row)
    
    # Választás naplózása
    log_user_interaction(session['user_id'], recipe_id, 'view_recommendations')
    
    return render_template('results.html', 
                         recommendations=recommendations.to_dict('records'),
                         group=group,
                         show_scores=show_scores,
                         show_explanation=show_explanation,
                         explanations=explanations)

@app.route('/select_recipe', methods=['POST'])
def select_recipe():
    """Felhasználói választás naplózása"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    recipe_id = data.get('recipe_id')
    
    if recipe_id:
        log_user_choice(session['user_id'], recipe_id)
        return jsonify({'success': True})
    
    return jsonify({'error': 'No recipe selected'}), 400

def log_user_interaction(user_id, recipe_id, action_type):
    """Felhasználói interakciók naplózása"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(
        "INSERT INTO user_interactions (user_id, recipe_id, action_type, timestamp) VALUES (%s, %s, %s, %s);",
        (user_id, recipe_id, action_type, datetime.now())
    )
    conn.commit()
    cur.close()
    conn.close()

def log_user_choice(user_id, recipe_id):
    """Felhasználói választás specifikus naplózása"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute(
        "INSERT INTO user_choices (user_id, recipe_id, chosen_at) VALUES (%s, %s, %s);",
        (user_id, recipe_id, datetime.now())
    )
    conn.commit()
    cur.close()
    conn.close()

@app.route('/stats')
def stats():
    """Egyszerű statisztika oldal (fejlesztői célra)"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Csoportonkénti felhasználók száma
    group_stats = pd.read_sql_query(
        "SELECT group_name, COUNT(*) as user_count FROM users GROUP BY group_name ORDER BY group_name;",
        conn
    )
    
    # Választások száma csoportonként
    choice_stats = pd.read_sql_query("""
        SELECT u.group_name, COUNT(uc.id) as choice_count, 
               AVG(r.hsi) as avg_hsi, AVG(r.esi) as avg_esi, AVG(r.ppi) as avg_ppi
        FROM users u 
        LEFT JOIN user_choices uc ON u.id = uc.user_id
        LEFT JOIN recipes r ON uc.recipe_id = r.id
        GROUP BY u.group_name 
        ORDER BY u.group_name;
    """, conn)
    
    conn.close()
    
    return render_template('stats.html', 
                         group_stats=group_stats.to_dict('records'),
                         choice_stats=choice_stats.to_dict('records'))

if __name__ == '__main__':
    app.run(debug=True)
