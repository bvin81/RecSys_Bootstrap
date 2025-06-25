#!/usr/bin/env python3
"""
User Study Routes - Heroku Compatible Simplified Version
"""
import os
import random
import json
from pathlib import Path
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from datetime import datetime

# Blueprint
user_study_bp = Blueprint('user_study', __name__, url_prefix='')

# Simple recommendation engine (fallback)
class SimpleRecommender:
    def __init__(self):
        self.recipes = [
            {
                "id": "recipe_001",
                "name": "🥗 Mediterrán Saláta",
                "description": "Friss zöldségek olivaolajjal és citrommal",
                "ESI": 15,
                "HSI": 95,
                "PPI": 78,
                "composite_score": 85,
                "ingredients": ["saláta", "paradicsom", "uborka", "olívaolaj"],
                "category": "Saláták"
            },
            {
                "id": "recipe_002", 
                "name": "🍲 Lencse Curry",
                "description": "Fűszeres lencse curry kókusztejjel",
                "ESI": 12,
                "HSI": 88,
                "PPI": 82,
                "composite_score": 82,
                "ingredients": ["vörös lencse", "kókusztej", "curry", "hagyma"],
                "category": "Főételek"
            },
            {
                "id": "recipe_003",
                "name": "🥕 Sárgarépa Krémleves", 
                "description": "Krémes sárgarépa leves gyömbérrel",
                "ESI": 18,
                "HSI": 92,
                "PPI": 75,
                "composite_score": 80,
                "ingredients": ["sárgarépa", "gyömbér", "kókusztej", "hagyma"],
                "category": "Levesek"
            },
            {
                "id": "recipe_004",
                "name": "🍝 Teljes Kiőrlésű Tészta",
                "description": "Teljes kiőrlésű tészta zöldségekkel",
                "ESI": 22,
                "HSI": 85,
                "PPI": 88,
                "composite_score": 78,
                "ingredients": ["teljes kiőrlésű tészta", "brokkoli", "paprika"],
                "category": "Főételek"
            },
            {
                "id": "recipe_005", 
                "name": "🥤 Zöld Smoothie",
                "description": "Spenótos-banános smoothie",
                "ESI": 10,
                "HSI": 90,
                "PPI": 70,
                "composite_score": 77,
                "ingredients": ["spenót", "banán", "alma", "mandula tej"],
                "category": "Italok"
            }
        ]
    
    def recommend(self, search_query="", n_recommendations=5, version="v1"):
        """Simple recommendation logic"""
        if search_query:
            # Simple search in names and ingredients
            filtered = [r for r in self.recipes 
                       if search_query.lower() in r['name'].lower() 
                       or any(search_query.lower() in ing.lower() for ing in r['ingredients'])]
            return filtered[:n_recommendations]
        else:
            # Return random selection
            import random
            return random.sample(self.recipes, min(n_recommendations, len(self.recipes)))

# Global recommender instance
recommender = SimpleRecommender()

# Simple database simulation
users_db = {}
ratings_db = {}

# =============================================================================
# ROUTES
# =============================================================================

@user_study_bp.route('/welcome')
def welcome():
    """Üdvözlő oldal"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🌱 Fenntartható Receptajánló</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .card {{ background: #f8f9fa; padding: 30px; border-radius: 10px; margin: 20px 0; }}
            .btn {{ display: inline-block; padding: 12px 24px; background: #28a745; color: white; 
                   text-decoration: none; border-radius: 5px; margin: 10px 5px; }}
            .btn:hover {{ background: #218838; }}
            .version {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🌱 Fenntartható Receptajánló Rendszer</h1>
            <p><strong>Üdvözöljük a GreenRec tanulmányban!</strong></p>
            
            <p>A rendszer különböző verziókat tesztel a fenntarthatóság-tudatos receptajánlásban:</p>
            
            <div class="version">
                <h3>🧪 A/B/C Teszt Verziók:</h3>
                <ul>
                    <li><strong>A csoport:</strong> Alapvető ajánlások (ESI hangsúly)</li>
                    <li><strong>B csoport:</strong> Kiegyensúlyozott (ESI + HSI + PPI)</li>
                    <li><strong>C csoport:</strong> ML-alapú personalizálás</li>
                </ul>
            </div>
            
            <p><strong>🎯 Csatlakozás:</strong></p>
            <a href="/register" class="btn">📝 Regisztráció</a>
            <a href="/login" class="btn">🔑 Bejelentkezés</a>
            
            <p><strong>🔍 Gyors tesztelés:</strong></p>
            <a href="/study" class="btn">🚀 Közvetlen Tanulmány</a>
            <a href="/health" class="btn">📊 Rendszer Állapot</a>
        </div>
        
        <div class="card">
            <h3>📋 Tanulmány menete:</h3>
            <ol>
                <li>Regisztráció és csoport hozzárendelés</li>
                <li>5 recept értékelése (1-5 csillag)</li>
                <li>Keresési funkció tesztelése</li>
                <li>Újabb értékelési kör</li>
                <li>Személyre szabott ajánlások</li>
            </ol>
        </div>
        
        <p><small>🌍 A fenntartható táplálkozásért • GreenRec v3.0</small></p>
    </body>
    </html>
    """

@user_study_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Egyszerű regisztráció"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        name = request.form.get('name', '').strip()
        
        if email and name:
            # Generate user ID and assign version
            user_id = f"user_{len(users_db) + 1:03d}"
            version = ['v1', 'v2', 'v3'][len(users_db) % 3]  # A/B/C rotation
            
            # Store user
            users_db[user_id] = {
                'id': user_id,
                'email': email,
                'name': name,
                'version': version,
                'registered_at': datetime.now().isoformat()
            }
            
            # Set session
            session['user_id'] = user_id
            session['email'] = email
            session['name'] = name
            session['version'] = version
            session['is_returning_user'] = False
            
            return redirect(url_for('user_study.study'))
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Regisztráció - GreenRec</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
            .form-group {{ margin: 15px 0; }}
            label {{ display: block; font-weight: bold; margin-bottom: 5px; }}
            input {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }}
            .btn {{ padding: 12px 24px; background: #28a745; color: white; border: none; border-radius: 5px; cursor: pointer; }}
            .btn:hover {{ background: #218838; }}
        </style>
    </head>
    <body>
        <h2>📝 Regisztráció</h2>
        <form method="POST">
            <div class="form-group">
                <label>Email cím:</label>
                <input type="email" name="email" required>
            </div>
            <div class="form-group">
                <label>Név:</label>
                <input type="text" name="name" required>
            </div>
            <button type="submit" class="btn">🚀 Csatlakozás</button>
        </form>
        <p><a href="/welcome">← Vissza</a></p>
    </body>
    </html>
    """

@user_study_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Egyszerű bejelentkezés"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        # Find user by email
        user = None
        for user_data in users_db.values():
            if user_data['email'] == email:
                user = user_data
                break
                
        if user:
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['name'] = user['name']
            session['version'] = user['version']
            session['is_returning_user'] = True
            return redirect(url_for('user_study.study'))
        else:
            return f"<p>Felhasználó nem található. <a href='/register'>Regisztráció</a></p>"
    
    return f"""
    <h2>🔑 Bejelentkezés</h2>
    <form method="POST">
        <p><label>Email: <input type="email" name="email" required></label></p>
        <p><button type="submit">Bejelentkezés</button></p>
    </form>
    <p><a href="/welcome">← Vissza</a></p>
    """

@user_study_bp.route('/study')
def study():
    """Főtanulmány oldal"""
    # Set default session if not exists
    if 'user_id' not in session:
        session['user_id'] = f"anonymous_{random.randint(1000, 9999)}"
        session['version'] = random.choice(['v1', 'v2', 'v3'])
        session['name'] = "Névtelen felhasználó"
    
    version = session.get('version', 'v1')
    search_query = request.args.get('search', '').strip()
    
    # Get recommendations
    try:
        recommendations = recommender.recommend(search_query, 5, version)
    except Exception as e:
        print(f"Recommendation error: {e}")
        recommendations = recommender.recipes[:5]  # fallback
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tanulmány - GreenRec</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #28a745; color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
            .search-box {{ margin: 20px 0; }}
            .search-box input {{ padding: 10px; width: 300px; border: 1px solid #ddd; border-radius: 5px; }}
            .search-box button {{ padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }}
            .recipe-card {{ background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 10px; padding: 20px; margin: 15px 0; }}
            .recipe-name {{ font-size: 1.3em; font-weight: bold; color: #28a745; margin-bottom: 10px; }}
            .scores {{ display: flex; gap: 15px; margin: 10px 0; }}
            .score {{ background: #e9ecef; padding: 5px 10px; border-radius: 5px; font-size: 0.9em; }}
            .rating {{ margin: 15px 0; }}
            .stars {{ font-size: 1.5em; }}
            .star {{ cursor: pointer; color: #ddd; }}
            .star.active {{ color: #ffc107; }}
            .ingredients {{ color: #6c757d; font-style: italic; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🌱 Fenntartható Receptajánló</h1>
            <p><strong>Felhasználó:</strong> {session.get('name', 'Névtelen')} | 
               <strong>Csoport:</strong> {version.upper()} | 
               <strong>Receptek értékelése</strong></p>
        </div>
        
        <div class="search-box">
            <form method="GET">
                <input type="text" name="search" value="{search_query}" placeholder="Keresés receptek között..." />
                <button type="submit">🔍 Keresés</button>
                <a href="/study" style="margin-left: 10px;">🔄 Összes recept</a>
            </form>
        </div>
        
        <div id="recommendations">
            <h2>📋 Ajánlott receptek ({len(recommendations)} db)</h2>
            
            {''.join([f'''
            <div class="recipe-card">
                <div class="recipe-name">{recipe['name']}</div>
                <p>{recipe['description']}</p>
                
                <div class="scores">
                    <span class="score">🌍 ESI: {recipe['ESI']}</span>
                    <span class="score">💚 HSI: {recipe['HSI']}</span>
                    <span class="score">👥 PPI: {recipe['PPI']}</span>
                    <span class="score" style="background: #28a745; color: white;">⭐ Össz: {recipe['composite_score']}</span>
                </div>
                
                <div class="ingredients">
                    🥘 Összetevők: {', '.join(recipe['ingredients'])}
                </div>
                
                <div class="rating">
                    <strong>Értékelés:</strong>
                    <div class="stars" onclick="rateRecipe('{recipe['id']}', event)">
                        <span class="star" data-rating="1">⭐</span>
                        <span class="star" data-rating="2">⭐</span>
                        <span class="star" data-rating="3">⭐</span>
                        <span class="star" data-rating="4">⭐</span>
                        <span class="star" data-rating="5">⭐</span>
                    </div>
                    <span id="rating-{recipe['id']}" style="margin-left: 10px; color: #28a745; font-weight: bold;"></span>
                </div>
            </div>
            ''' for recipe in recommendations])}
        </div>
        
        <div style="margin: 30px 0; text-align: center;">
            <a href="/welcome" style="padding: 10px 20px; background: #6c757d; color: white; text-decoration: none; border-radius: 5px;">
                ← Vissza a főoldalra
            </a>
        </div>
        
        <script>
            function rateRecipe(recipeId, event) {{
                if (event.target.classList.contains('star')) {{
                    const rating = parseInt(event.target.dataset.rating);
                    const stars = event.target.parentElement.querySelectorAll('.star');
                    
                    // Update visual stars
                    stars.forEach((star, index) => {{
                        if (index < rating) {{
                            star.classList.add('active');
                        }} else {{
                            star.classList.remove('active');
                        }}
                    }});
                    
                    // Show rating feedback
                    document.getElementById('rating-' + recipeId).textContent = 
                        rating + ' csillag - Köszönjük!';
                    
                    // Send rating (simplified - no actual backend call for this demo)
                    console.log('Rating sent:', recipeId, rating);
                }}
            }}
        </script>
    </body>
    </html>
    """

@user_study_bp.route('/api/rate', methods=['POST'])
def rate_recipe():
    """Rating endpoint"""
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        rating = data.get('rating')
        user_id = session.get('user_id')
        
        if not all([recipe_id, rating, user_id]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Store rating (simplified)
        if user_id not in ratings_db:
            ratings_db[user_id] = {}
        ratings_db[user_id][recipe_id] = {
            'rating': rating,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({
            'status': 'success',
            'message': f'Rating {rating} recorded for recipe {recipe_id}'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Health check endpoint
@user_study_bp.route('/api/health')
def health_check():
    """Simple health check for user_study module"""
    return jsonify({
        'status': 'healthy',
        'module': 'user_study',
        'recipes_loaded': len(recommender.recipes),
        'users_count': len(users_db),
        'ratings_count': sum(len(ratings) for ratings in ratings_db.values())
    })

print("✅ User study routes loaded successfully (simplified version)")
