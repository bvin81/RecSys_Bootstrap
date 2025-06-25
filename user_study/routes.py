#!/usr/bin/env python3
"""
User Study Routes - Minimal Working Version
===========================================
"""
import os
import random
import json
from flask import Blueprint, request, session, redirect, url_for, jsonify
from datetime import datetime

# Blueprint
user_study_bp = Blueprint('user_study', __name__, url_prefix='')

# Simple data storage
recipes_data = [
    {
        'id': 'recipe_001', 'name': '🥗 Mediterrán Saláta',
        'description': 'Friss zöldségek olivaolajjal',
        'ingredients': ['saláta', 'paradicsom', 'uborka', 'olívaolaj'],
        'category': 'Saláták', 'ESI': 15, 'HSI': 95, 'PPI': 78
    },
    {
        'id': 'recipe_002', 'name': '🍲 Lencse Curry',
        'description': 'Fűszeres lencse curry kókusztejjel',
        'ingredients': ['vörös lencse', 'kókusztej', 'curry', 'hagyma'],
        'category': 'Főételek', 'ESI': 12, 'HSI': 88, 'PPI': 82
    },
    {
        'id': 'recipe_003', 'name': '🥕 Sárgarépa Leves',
        'description': 'Krémes sárgarépa leves gyömbérrel',
        'ingredients': ['sárgarépa', 'gyömbér', 'kókusztej', 'hagyma'],
        'category': 'Levesek', 'ESI': 18, 'HSI': 92, 'PPI': 75
    },
    {
        'id': 'recipe_004', 'name': '🍝 Teljes Kiőrlésű Tészta',
        'description': 'Teljes kiőrlésű tészta zöldségekkel',
        'ingredients': ['teljes kiőrlésű tészta', 'brokkoli', 'paprika'],
        'category': 'Főételek', 'ESI': 22, 'HSI': 85, 'PPI': 88
    },
    {
        'id': 'recipe_005', 'name': '🥤 Zöld Smoothie',
        'description': 'Spenótos-banános smoothie',
        'ingredients': ['spenót', 'banán', 'alma', 'mandula tej'],
        'category': 'Italok', 'ESI': 10, 'HSI': 90, 'PPI': 70
    }
]

users_db = {}
ratings_db = {}

@user_study_bp.route('/welcome')
def welcome():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🌱 GreenRec</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .card {{ background: #f8f9fa; padding: 30px; border-radius: 10px; margin: 20px 0; }}
            .btn {{ display: inline-block; padding: 12px 24px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; margin: 10px 5px; }}
            .btn:hover {{ background: #218838; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🌱 Fenntartható Receptajánló</h1>
            <p><strong>GreenRec működik!</strong></p>
            <p>📋 {len(recipes_data)} recept betöltve</p>
            <p>👥 {len(users_db)} felhasználó regisztrálva</p>
            
            <h3>🚀 Csatlakozás:</h3>
            <a href="/register" class="btn">📝 Regisztráció</a>
            <a href="/study" class="btn">🔬 Tanulmány</a>
            <a href="/metrics" class="btn">📈 Metrikák</a>
        </div>
    </body>
    </html>
    """

@user_study_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        name = request.form.get('name', '').strip()
        
        if email and name:
            user_id = f"user_{len(users_db) + 1:03d}"
            version = ['v1', 'v2', 'v3'][len(users_db) % 3]
            
            users_db[user_id] = {
                'id': user_id, 'email': email, 'name': name, 
                'version': version, 'registered_at': datetime.now().isoformat()
            }
            
            session['user_id'] = user_id
            session['name'] = name
            session['version'] = version
            
            return redirect(url_for('user_study.study'))
    
    return """
    <h2>📝 Regisztráció</h2>
    <form method="POST">
        <p><label>Email: <input type="email" name="email" required></label></p>
        <p><label>Név: <input type="text" name="name" required></label></p>
        <p><button type="submit">Regisztráció</button></p>
    </form>
    <p><a href="/welcome">← Vissza</a></p>
    """

@user_study_bp.route('/study')
def study():
    if 'user_id' not in session:
        session['user_id'] = f"anonymous_{random.randint(1000, 9999)}"
        session['version'] = random.choice(['v1', 'v2', 'v3'])
        session['name'] = "Névtelen"
    
    search_query = request.args.get('search', '').strip()
    
    # Simple search
    if search_query:
        filtered_recipes = [r for r in recipes_data if search_query.lower() in r['name'].lower() or 
                          any(search_query.lower() in ing.lower() for ing in r['ingredients'])]
    else:
        filtered_recipes = recipes_data
    
    recipe_cards = ''
    for recipe in filtered_recipes[:6]:
        ingredients_text = ', '.join(recipe['ingredients'])
        recipe_cards += f"""
        <div style="border: 1px solid #ddd; padding: 20px; margin: 15px 0; border-radius: 10px;">
            <h3>{recipe['name']}</h3>
            <p>{recipe['description']}</p>
            <p><strong>Összetevők:</strong> {ingredients_text}</p>
            <p><strong>Pontok:</strong> ESI: {recipe['ESI']}, HSI: {recipe['HSI']}, PPI: {recipe['PPI']}</p>
            <div>
                <strong>Értékelés:</strong>
                <button onclick="rate('{recipe['id']}', 1)">1⭐</button>
                <button onclick="rate('{recipe['id']}', 2)">2⭐</button>
                <button onclick="rate('{recipe['id']}', 3)">3⭐</button>
                <button onclick="rate('{recipe['id']}', 4)">4⭐</button>
                <button onclick="rate('{recipe['id']}', 5)">5⭐</button>
                <span id="rating-{recipe['id']}"></span>
            </div>
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Tanulmány - GreenRec</title></head>
    <body style="font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px;">
        <h1>🌱 GreenRec Tanulmány</h1>
        <p><strong>Felhasználó:</strong> {session.get('name')} | <strong>Csoport:</strong> {session.get('version', 'v1').upper()}</p>
        
        <form method="GET">
            <input type="text" name="search" value="{search_query}" placeholder="Keresés..." style="padding: 10px; width: 300px;">
            <button type="submit">🔍 Keresés</button>
            <a href="/study" style="margin-left: 10px;">🔄 Összes</a>
        </form>
        
        <h2>📋 Receptek ({len(filtered_recipes)} db)</h2>
        {recipe_cards}
        
        <p><a href="/welcome">🏠 Főoldal</a> | <a href="/metrics">📈 Metrikák</a></p>
        
        <script>
        function rate(recipeId, rating) {{
            fetch('/api/rate', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{recipe_id: recipeId, rating: rating}})
            }}).then(r => r.json()).then(data => {{
                document.getElementById('rating-' + recipeId).textContent = rating + ' csillag - Mentve!';
            }}).catch(e => {{
                document.getElementById('rating-' + recipeId).textContent = rating + ' csillag - Hiba!';
            }});
        }}
        </script>
    </body>
    </html>
    """

@user_study_bp.route('/metrics')
def metrics():
    total_users = len(users_db)
    total_ratings = sum(len(ratings) for ratings in ratings_db.values())
    
    return f"""
    <h1>📈 Metrikák</h1>
    <p><strong>Felhasználók:</strong> {total_users}</p>
    <p><strong>Értékelések:</strong> {total_ratings}</p>
    <p><strong>Receptek:</strong> {len(recipes_data)}</p>
    <p><a href="/study">🔬 Vissza a tanulmányhoz</a></p>
    """

@user_study_bp.route('/api/rate', methods=['POST'])
def rate_recipe():
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        rating = data.get('rating')
        user_id = session.get('user_id', 'anonymous')
        
        if user_id not in ratings_db:
            ratings_db[user_id] = {}
        ratings_db[user_id][recipe_id] = rating
        
        return jsonify({'status': 'success', 'message': f'Rating {rating} saved'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_study_bp.route('/api/health')
def api_health():
    return jsonify({
        'status': 'healthy',
        'module': 'user_study_minimal',
        'recipes': len(recipes_data),
        'users': len(users_db),
        'ratings': sum(len(r) for r in ratings_db.values())
    })

print("✅ User study routes loaded successfully (MINIMAL VERSION)")

# Export
__all__ = ['user_study_bp']
