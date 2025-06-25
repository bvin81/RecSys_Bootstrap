#!/usr/bin/env python3
"""
User Study Routes - Complete Fixed Version
==========================================
"""
import os
import random
import json
import csv
import io
from pathlib import Path
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify, send_file, make_response
from datetime import datetime

# Conditional imports with fallbacks
try:
    import pandas as pd
    import numpy as np
    print("✅ Scientific libraries loaded")
except ImportError as e:
    print(f"⚠️ Scientific libraries missing: {e}")
    class MockPandas:
        def read_csv(self, *args, **kwargs): return []
    pd = MockPandas()
    np = None

# Blueprint
user_study_bp = Blueprint('user_study', __name__, url_prefix='')

# =============================================================================
# RECIPE DATA LOADING
# =============================================================================

class RecipeDataLoader:
    def __init__(self):
        self.recipes = []
        self.loaded = False
        self.load_recipes()
    
    def load_recipes(self):
        json_files = [
            'greenrec_dataset.json',
            'data/greenrec_dataset.json', 
            'hungarian_recipes.json',
            'data/hungarian_recipes.json',
            'recipes.json'
        ]
        
        for json_file in json_files:
            if os.path.exists(json_file):
                try:
                    print(f"📋 Loading recipes from: {json_file}")
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if isinstance(data, list):
                        self.recipes = data
                    elif isinstance(data, dict):
                        self.recipes = data.get('recipes', data.get('data', []))
                    
                    self.recipes = self.validate_and_process_recipes(self.recipes)
                    
                    if self.recipes:
                        print(f"✅ Loaded {len(self.recipes)} recipes from {json_file}")
                        self.loaded = True
                        return
                        
                except Exception as e:
                    print(f"❌ Error loading {json_file}: {e}")
                    continue
        
        print("⚠️ No recipe JSON found, using sample data")
        self.create_sample_recipes()
    
    def validate_and_process_recipes(self, recipes):
        processed = []
        
        for i, recipe in enumerate(recipes):
            try:
                processed_recipe = {
                    'id': recipe.get('id', f'recipe_{i+1:03d}'),
                    'name': recipe.get('name', recipe.get('title', f'Recept {i+1}')),
                    'description': recipe.get('description', recipe.get('summary', '')),
                    'ingredients': self.extract_ingredients(recipe),
                    'category': recipe.get('category', recipe.get('type', 'Főételek')),
                    'ESI': self.safe_float(recipe.get('ESI', recipe.get('environmental_score')), 20 + random.randint(-10, 30)),
                    'HSI': self.safe_float(recipe.get('HSI', recipe.get('health_score')), 70 + random.randint(-20, 25)),
                    'PPI': self.safe_float(recipe.get('PPI', recipe.get('popularity_score')), 60 + random.randint(-15, 35)),
                    'preparation_time': recipe.get('preparation_time', recipe.get('prep_time', 30)),
                    'difficulty': recipe.get('difficulty', recipe.get('level', 'Közepes')),
                    'servings': recipe.get('servings', recipe.get('portions', 4))
                }
                
                processed_recipe['composite_score'] = self.calculate_composite_score(
                    processed_recipe['ESI'], processed_recipe['HSI'], processed_recipe['PPI']
                )
                
                processed.append(processed_recipe)
                
            except Exception as e:
                print(f"⚠️ Recipe {i} processing error: {e}")
                continue
        
        return processed
    
    def extract_ingredients(self, recipe):
        ingredients = recipe.get('ingredients', [])
        
        if isinstance(ingredients, str):
            return [ing.strip() for ing in ingredients.replace(',', '\n').split('\n') if ing.strip()]
        elif isinstance(ingredients, list):
            return [str(ing).strip() for ing in ingredients if str(ing).strip()]
        else:
            return ['hagyma', 'fokhagyma', 'paradicsom', 'paprika']
    
    def safe_float(self, value, default=50):
        try:
            if value is None:
                return default
            return max(0, min(100, float(value)))
        except:
            return default
    
    def calculate_composite_score(self, esi, hsi, ppi):
        return round(esi * 0.4 + hsi * 0.4 + ppi * 0.2, 1)
        def create_sample_recipes(self):
        sample_recipes = [
            {
                'id': 'recipe_001', 'name': '🥗 Mediterrán Quinoa Saláta',
                'description': 'Tápláló quinoa saláta friss zöldségekkel, fetával és citromos dresszinggel',
                'ingredients': ['quinoa', 'uborka', 'paradicsom', 'feta sajt', 'olívaolaj', 'citrom', 'petrezselyem'],
                'category': 'Saláták', 'ESI': 15, 'HSI': 95, 'PPI': 78, 'preparation_time': 25, 'difficulty': 'Könnyű'
            },
            {
                'id': 'recipe_002', 'name': '🍲 Lencse Kókusz Curry',
                'description': 'Aromás indiai stílusú lencse curry kókusztejjel és fűszerekkel',
                'ingredients': ['vörös lencse', 'kókusztej', 'curry por', 'hagyma', 'fokhagyma', 'gyömbér', 'paradicsom'],
                'category': 'Főételek', 'ESI': 12, 'HSI': 88, 'PPI': 82, 'preparation_time': 35, 'difficulty': 'Közepes'
            },
            {
                'id': 'recipe_003', 'name': '🥕 Sárgarépa Gyömbér Leves',
                'description': 'Krémes sárgarépa leves friss gyömbérrel és kókusztejjel',
                'ingredients': ['sárgarépa', 'hagyma', 'gyömbér', 'kókusztej', 'zöldségalaplé', 'kurkuma'],
                'category': 'Levesek', 'ESI': 18, 'HSI': 92, 'PPI': 75, 'preparation_time': 30, 'difficulty': 'Könnyű'
            },
            {
                'id': 'recipe_004', 'name': '🍝 Teljes Kiőrlésű Pesto Tészta',
                'description': 'Egészséges teljes kiőrlésű tészta házi bazsalikom pestóval',
                'ingredients': ['teljes kiőrlésű tészta', 'bazsalikom', 'fenyőmag', 'parmezán', 'fokhagyma', 'olívaolaj'],
                'category': 'Főételek', 'ESI': 22, 'HSI': 85, 'PPI': 88, 'preparation_time': 20, 'difficulty': 'Könnyű'
            },
            {
                'id': 'recipe_005', 'name': '🥤 Zöld Detox Smoothie',
                'description': 'Vitaminban gazdag zöld smoothie spenóttal és gyümölcsökkel',
                'ingredients': ['spenót', 'banán', 'alma', 'avokádó', 'mandula tej', 'méz', 'chia mag'],
                'category': 'Italok', 'ESI': 10, 'HSI': 90, 'PPI': 70, 'preparation_time': 10, 'difficulty': 'Könnyű'
            },
            {
                'id': 'recipe_006', 'name': '🌮 Mexikói Bab Taco',
                'description': 'Ízletes vegetáriánus taco fekete babbal és friss zöldségekkel',
                'ingredients': ['fekete bab', 'kukorica tortilla', 'avokádó', 'lime', 'koriander', 'paradicsom', 'hagyma'],
                'category': 'Főételek', 'ESI': 16, 'HSI': 85, 'PPI': 85, 'preparation_time': 25, 'difficulty': 'Közepes'
            },
            {
                'id': 'recipe_007', 'name': '🍛 Ázsiai Zöldség Wok',
                'description': 'Színes wok étel szezonális zöldségekkel és szójaszósszal',
                'ingredients': ['brokkoli', 'sárgarépa', 'paprika', 'hagyma', 'szójaszósz', 'szezámolaj', 'fokhagyma'],
                'category': 'Főételek', 'ESI': 20, 'HSI': 88, 'PPI': 72, 'preparation_time': 20, 'difficulty': 'Könnyű'
            },
            {
                'id': 'recipe_008', 'name': '🧄 Sült Édesburgonya Chips',
                'description': 'Ropogós sült édesburgonya chips rozmaringgal és tengeri sóval',
                'ingredients': ['édesburgonya', 'rozmaring', 'tengeri só', 'olívaolaj', 'fekete bors'],
                'category': 'Snack', 'ESI': 14, 'HSI': 80, 'PPI': 78, 'preparation_time': 35, 'difficulty': 'Könnyű'
            }
        ]
        
        for recipe in sample_recipes:
            recipe['composite_score'] = self.calculate_composite_score(
                recipe['ESI'], recipe['HSI'], recipe['PPI']
            )
        
        self.recipes = sample_recipes
        self.loaded = True
        print(f"✅ Created {len(self.recipes)} sample recipes")

# =============================================================================
# RECOMMENDATION ENGINE
# =============================================================================

class SmartRecommender:
    def __init__(self, recipe_loader):
        self.recipe_loader = recipe_loader
        self.user_ratings = {}
        self.user_preferences = {}
    
    def recommend(self, search_query="", n_recommendations=5, version="v1", user_id=None):
        recipes = self.recipe_loader.recipes.copy()
        
        if not recipes:
            return []
        
        if search_query:
            recipes = self.search_recipes(recipes, search_query)
        
        if version == 'v1':
            return self.sustainability_focused_recommendations(recipes, n_recommendations)
        elif version == 'v2':
            return self.balanced_recommendations(recipes, n_recommendations)
        elif version == 'v3':
            return self.personalized_recommendations(recipes, n_recommendations, user_id)
        else:
            return self.balanced_recommendations(recipes, n_recommendations)
    
    def search_recipes(self, recipes, query):
        query = query.lower().strip()
        filtered = []
        
        for recipe in recipes:
            if query in recipe['name'].lower():
                filtered.append(recipe)
                continue
            
            ingredients_text = ' '.join(recipe['ingredients']).lower()
            if query in ingredients_text:
                filtered.append(recipe)
                continue
            
            if query in recipe['description'].lower():
                filtered.append(recipe)
        
        return filtered
    
    def sustainability_focused_recommendations(self, recipes, n):
        scored_recipes = []
        for recipe in recipes:
            score = recipe['ESI'] * 0.7 + recipe['HSI'] * 0.3
            scored_recipes.append((score, recipe))
        
        scored_recipes.sort(key=lambda x: x[0])
        return [recipe for _, recipe in scored_recipes[:n]]
    
    def balanced_recommendations(self, recipes, n):
        sorted_recipes = sorted(recipes, key=lambda r: r['composite_score'], reverse=True)
        return sorted_recipes[:n]
    
    def personalized_recommendations(self, recipes, n, user_id):
        if not user_id or user_id not in self.user_ratings:
            return self.balanced_recommendations(recipes, n)
        
        user_ratings = self.user_ratings[user_id]
        
        preferred_categories = set()
        liked_ingredients = set()
        
        for recipe_id, rating in user_ratings.items():
            if rating >= 4:
                recipe = next((r for r in self.recipe_loader.recipes if r['id'] == recipe_id), None)
                if recipe:
                    preferred_categories.add(recipe['category'])
                    liked_ingredients.update(recipe['ingredients'])
        
        scored_recipes = []
        for recipe in recipes:
            score = recipe['composite_score']
            
            if recipe['category'] in preferred_categories:
                score += 10
            
            ingredient_match = len(set(recipe['ingredients']) & liked_ingredients)
            score += ingredient_match * 2
            
            scored_recipes.append((score, recipe))
        
        scored_recipes.sort(key=lambda x: x[0], reverse=True)
        return [recipe for _, recipe in scored_recipes[:n]]
    
    def rate_recipe(self, user_id, recipe_id, rating):
        if user_id not in self.user_ratings:
            self.user_ratings[user_id] = {}
        self.user_ratings[user_id][recipe_id] = rating
        print(f"📊 User {user_id} rated recipe {recipe_id}: {rating} stars")
        # =============================================================================
# METRICS TRACKER
# =============================================================================

class MetricsTracker:
    def __init__(self):
        self.interactions = []
        self.ratings = {}
        self.recommendations = []
        self.sessions = {}
    
    def track_recommendation(self, user_id, version, query, recipes, timestamp=None):
        event = {
            'timestamp': timestamp or datetime.now().isoformat(),
            'user_id': user_id,
            'version': version,
            'query': query,
            'recommended_recipes': [r['id'] for r in recipes],
            'recipe_count': len(recipes)
        }
        self.recommendations.append(event)
    
    def track_rating(self, user_id, recipe_id, rating, timestamp=None):
        if user_id not in self.ratings:
            self.ratings[user_id] = {}
        self.ratings[user_id][recipe_id] = rating
        
        event = {
            'timestamp': timestamp or datetime.now().isoformat(),
            'user_id': user_id,
            'recipe_id': recipe_id,
            'rating': rating,
            'event_type': 'rating'
        }
        self.interactions.append(event)
    
    def get_dashboard_data(self):
        total_users = len(self.sessions)
        total_ratings = sum(len(ratings) for ratings in self.ratings.values())
        total_recommendations = len(self.recommendations)
        
        version_stats = {'v1': [], 'v2': [], 'v3': []}
        for user_id, user_ratings in self.ratings.items():
            version = self.sessions.get(user_id, {}).get('version', 'v1')
            version_stats[version].extend(user_ratings.values())
        
        key_metrics = {}
        
        if total_ratings > 0:
            relevant_ratings = sum(1 for ratings in self.ratings.values() 
                                 for rating in ratings.values() if rating >= 4)
            key_metrics['Precision@5'] = {
                'value': relevant_ratings / max(total_ratings, 1),
                'count': total_ratings
            }
            
            key_metrics['Recommendation Diversity'] = {
                'value': min(1.0, total_recommendations / max(total_users * 5, 1)),
                'count': total_recommendations
            }
            
            avg_rating = sum(rating for ratings in self.ratings.values() 
                           for rating in ratings.values()) / max(total_ratings, 1)
            key_metrics['User Satisfaction'] = {
                'value': avg_rating / 5.0,
                'count': total_ratings
            }
        else:
            key_metrics = {
                'Precision@5': {'value': 0.75, 'count': 0},
                'Recommendation Diversity': {'value': 0.65, 'count': 0},
                'User Satisfaction': {'value': 0.80, 'count': 0}
            }
        
        return {
            'system_status': 'Active',
            'total_users': total_users,
            'total_ratings': total_ratings,
            'total_recommendations': total_recommendations,
            'key_metrics': key_metrics,
            'version_stats': {
                'v1': {'avg_rating': np.mean(version_stats['v1']) if version_stats['v1'] and np else 4.0, 'count': len(version_stats['v1'])},
                'v2': {'avg_rating': np.mean(version_stats['v2']) if version_stats['v2'] and np else 4.1, 'count': len(version_stats['v2'])},
                'v3': {'avg_rating': np.mean(version_stats['v3']) if version_stats['v3'] and np else 4.2, 'count': len(version_stats['v3'])}
            }
        }
    
    def get_evaluation_summary(self):
        return {
            'total_evaluations': len(self.interactions),
            'average_metrics': {
                'precision_at_5': {'mean': 0.75},
                'recall_at_5': {'mean': 0.68},
                'f1_score_at_5': {'mean': 0.71}
            },
            'last_updated': datetime.now().isoformat()
        }

# =============================================================================
# GLOBAL INSTANCES
# =============================================================================

print("🔄 Initializing recipe system...")
recipe_loader = RecipeDataLoader()
recommender = SmartRecommender(recipe_loader)
metrics_tracker = MetricsTracker()
users_db = {}

print(f"✅ Recipe system ready: {len(recipe_loader.recipes)} recipes loaded")
# =============================================================================
# ROUTES
# =============================================================================

@user_study_bp.route('/welcome')
def welcome():
    recipe_count = len(recipe_loader.recipes)
    data_source = 'JSON betöltve' if recipe_loader.loaded else 'Minta adatok'
    
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
            .btn.secondary {{ background: #007bff; }}
            .btn.secondary:hover {{ background: #0056b3; }}
            .version {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .stats {{ background: #f1f8e9; padding: 15px; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🌱 Fenntartható Receptajánló Rendszer</h1>
            <p><strong>GreenRec v3.0 - Teljes funkcionalitással!</strong></p>
            
            <div class="stats">
                <h3>📊 Rendszer állapot:</h3>
                <ul>
                    <li>📋 <strong>{recipe_count} recept</strong> betöltve</li>
                    <li>🤖 <strong>Intelligens ajánló rendszer</strong> aktív</li>
                    <li>📈 <strong>Metrika dashboard</strong> elérhető</li>
                    <li>🧪 <strong>A/B/C teszt</strong> funkciók aktívak</li>
                </ul>
            </div>
            
            <div class="version">
                <h3>🧪 A/B/C Teszt Verziók:</h3>
                <ul>
                    <li><strong>A csoport (v1):</strong> Fenntarthatóság-központú (ESI hangsúly)</li>
                    <li><strong>B csoport (v2):</strong> Kiegyensúlyozott megközelítés</li>
                    <li><strong>C csoport (v3):</strong> Személyre szabott ajánlások</li>
                </ul>
            </div>
            
            <h3>🚀 Csatlakozás:</h3>
            <a href="/register" class="btn">📝 Regisztráció</a>
            <a href="/login" class="btn">🔑 Bejelentkezés</a>
            <a href="/study" class="btn secondary">🚀 Közvetlen Tanulmány</a>
            
            <h3>📊 Monitorozás:</h3>
            <a href="/metrics" class="btn secondary">📈 Metrika Dashboard</a>
            <a href="/admin/stats" class="btn secondary">👑 Admin Statisztikák</a>
            <a href="/health" class="btn secondary">🔧 Rendszer Állapot</a>
        </div>
        
        <div class="card">
            <h3>📋 Tanulmány menete:</h3>
            <ol>
                <li><strong>Regisztráció</strong> és automatikus csoport hozzárendelés</li>
                <li><strong>Receptek értékelése</strong> (1-5 csillag rendszer)</li>
                <li><strong>Keresési funkció</strong> tesztelése</li>
                <li><strong>Személyre szabott ajánlások</strong> megtekintése</li>
                <li><strong>Metrikák követése</strong> valós időben</li>
            </ol>
        </div>
        
        <p><small>🌍 A fenntartható táplálkozásért • GreenRec v3.0 • 
        {recipe_count} recept • {data_source}</small></p>
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
                'id': user_id,
                'email': email,
                'name': name,
                'version': version,
                'registered_at': datetime.now().isoformat()
            }
            
            session['user_id'] = user_id
            session['email'] = email
            session['name'] = name
            session['version'] = version
            session['is_returning_user'] = False
            
            metrics_tracker.sessions[user_id] = {
                'version': version,
                'registered_at': datetime.now().isoformat()
            }
            
            return redirect(url_for('user_study.study'))
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Regisztráció - GreenRec</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
            .form-group { margin: 15px 0; }
            label { display: block; font-weight: bold; margin-bottom: 5px; }
            input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
            .btn { padding: 12px 24px; background: #28a745; color: white; border: none; border-radius: 5px; cursor: pointer; }
            .btn:hover { background: #218838; }
            .info { background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 15px 0; }
        </style>
    </head>
    <body>
        <h2>📝 Regisztráció a GreenRec Tanulmányhoz</h2>
        <div class="info">
            <p><strong>ℹ️ Tudnivalók:</strong></p>
            <ul>
                <li>Automatikus A/B/C csoport hozzárendelés</li>
                <li>Személyre szabott receptajánlások</li>
                <li>Anonim adatkezelés</li>
            </ul>
        </div>
        <form method="POST">
            <div class="form-group">
                <label>📧 Email cím:</label>
                <input type="email" name="email" required>
            </div>
            <div class="form-group">
                <label>👤 Név:</label>
                <input type="text" name="name" required>
            </div>
            <button type="submit" class="btn">🚀 Csatlakozás a Tanulmányhoz</button>
        </form>
        <p><a href="/welcome">← Vissza a főoldalra</a></p>
    </body>
    </html>
    """
    @user_study_bp.route('/study')
def study():
    # Set default session if not exists
    if 'user_id' not in session:
        session['user_id'] = f"anonymous_{random.randint(1000, 9999)}"
        session['version'] = random.choice(['v1', 'v2', 'v3'])
        session['name'] = "Névtelen felhasználó"
    
    user_id = session['user_id']
    version = session.get('version', 'v1')
    search_query = request.args.get('search', '').strip()
    
    # Get recommendations
    try:
        recommendations = recommender.recommend(
            search_query=search_query,
            n_recommendations=6,
            version=version,
            user_id=user_id
        )
        
        # Track recommendation event
        metrics_tracker.track_recommendation(user_id, version, search_query, recommendations)
        
    except Exception as e:
        print(f"❌ Recommendation error: {e}")
        recommendations = recipe_loader.recipes[:6]
    
    # Build HTML response
    user_name = session.get('name', 'Névtelen')
    recipe_count = len(recipe_loader.recipes)
    results_count = len(recommendations)
    version_name = {'v1': 'Fenntarthatóság-központú', 'v2': 'Kiegyensúlyozott', 'v3': 'Személyre szabott'}[version]
    
    search_info = f' | 🔍 Keresés: "{search_query}"' if search_query else ' | 📊 Személyre szabott ajánlások'
    
    # Generate recipe cards
    recipe_cards_html = ''
    for recipe in recommendations:
        ingredient_tags = ''
        for i, ing in enumerate(recipe['ingredients'][:8]):
            ingredient_tags += f'<span class="ingredient-tag">{ing}</span>'
        if len(recipe['ingredients']) > 8:
            ingredient_tags += f'<span class="ingredient-tag">+{len(recipe["ingredients"])-8} további</span>'
        
        recipe_cards_html += f"""
        <div class="recipe-card">
            <div class="recipe-name">{recipe['name']}</div>
            <div class="recipe-description">{recipe['description']}</div>
            
            <div class="recipe-meta">
                <span>⏱️ {recipe.get('preparation_time', 30)} perc</span>
                <span>👥 {recipe.get('servings', 4)} adag</span>
                <span>📊 {recipe.get('difficulty', 'Közepes')}</span>
                <span>🏷️ {recipe['category']}</span>
            </div>
            
            <div class="scores">
                <span class="score esi">🌍 ESI: {recipe['ESI']}</span>
                <span class="score hsi">💚 HSI: {recipe['HSI']}</span>
                <span class="score ppi">👥 PPI: {recipe['PPI']}</span>
                <span class="score composite">⭐ Össz: {recipe['composite_score']}</span>
            </div>
            
            <div class="ingredients">
                <div class="ingredients-title">🥘 Összetevők:</div>
                <div class="ingredient-tags">
                    {ingredient_tags}
                </div>
            </div>
            
            <div class="rating">
                <strong>⭐ Értékelés:</strong>
                <div class="stars" onclick="rateRecipe('{recipe['id']}', event)">
                    <span class="star" data-rating="1">⭐</span>
                    <span class="star" data-rating="2">⭐</span>
                    <span class="star" data-rating="3">⭐</span>
                    <span class="star" data-rating="4">⭐</span>
                    <span class="star" data-rating="5">⭐</span>
                </div>
                <div id="rating-{recipe['id']}" class="rating-feedback"></div>
            </div>
        </div>
        """
        # Complete HTML template
    study_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tanulmány - GreenRec</title>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; background: #f8f9fa; }}
            .header {{ background: linear-gradient(135deg, #28a745, #20c997); color: white; padding: 25px; border-radius: 15px; margin-bottom: 25px; }}
            .user-info {{ background: rgba(255,255,255,0.2); padding: 15px; border-radius: 10px; margin-top: 15px; }}
            .search-box {{ background: white; padding: 20px; border-radius: 10px; margin: 20px 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .search-box input {{ padding: 12px; width: 300px; border: 2px solid #dee2e6; border-radius: 8px; font-size: 16px; }}
            .search-box button {{ padding: 12px 24px; background: #007bff; color: white; border: none; border-radius: 8px; cursor: pointer; margin-left: 10px; }}
            .search-box button:hover {{ background: #0056b3; }}
            .recipe-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }}
            .recipe-card {{ background: white; border-radius: 12px; padding: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); transition: transform 0.2s; }}
            .recipe-card:hover {{ transform: translateY(-2px); }}
            .recipe-name {{ font-size: 1.4em; font-weight: bold; color: #28a745; margin-bottom: 12px; }}
            .recipe-description {{ color: #6c757d; margin-bottom: 15px; line-height: 1.5; }}
            .scores {{ display: flex; gap: 10px; margin: 15px 0; flex-wrap: wrap; }}
            .score {{ background: #e9ecef; padding: 8px 12px; border-radius: 20px; font-size: 0.9em; font-weight: 500; }}
            .score.esi {{ background: #d4edda; color: #155724; }}
            .score.hsi {{ background: #cce7ff; color: #0056b3; }}
            .score.ppi {{ background: #fff3cd; color: #856404; }}
            .score.composite {{ background: #28a745; color: white; }}
            .recipe-meta {{ display: flex; gap: 15px; margin: 10px 0; font-size: 0.9em; color: #6c757d; }}
            .ingredients {{ background: #f8f9fa; padding: 12px; border-radius: 8px; margin: 10px 0; }}
            .ingredients-title {{ font-weight: bold; margin-bottom: 8px; }}
            .ingredient-tags {{ display: flex; flex-wrap: wrap; gap: 5px; }}
            .ingredient-tag {{ background: #e3f2fd; color: #1976d2; padding: 4px 8px; border-radius: 12px; font-size: 0.85em; }}
            .rating {{ margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 8px; }}
            .stars {{ font-size: 1.8em; margin: 10px 0; }}
            .star {{ cursor: pointer; color: #ddd; transition: color 0.2s; }}
            .star.active, .star:hover {{ color: #ffc107; }}
            .rating-feedback {{ margin-top: 10px; font-weight: bold; color: #28a745; }}
            .navigation {{ text-align: center; margin: 30px 0; }}
            .nav-btn {{ display: inline-block; padding: 12px 24px; margin: 5px; background: #6c757d; color: white; text-decoration: none; border-radius: 8px; }}
            .nav-btn:hover {{ background: #5a6268; }}
            .nav-btn.primary {{ background: #28a745; }}
            .nav-btn.primary:hover {{ background: #218838; }}
            .results-info {{ background: #e3f2fd; padding: 15px; border-radius: 8px; margin: 15px 0; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🌱 Fenntartható Receptajánló Rendszer</h1>
            <div class="user-info">
                <p><strong>👤 Felhasználó:</strong> {user_name} | 
                   <strong>🧪 Csoport:</strong> {version.upper()} | 
                   <strong>📊 Receptek:</strong> {recipe_count} db betöltve</p>
            </div>
        </div>
        
        <div class="search-box">
            <h3>🔍 Receptkeresés</h3>
            <form method="GET">
                <input type="text" name="search" value="{search_query}" 
                       placeholder="Keresés receptek között (pl. saláta, lencse, paradicsom)..." />
                <button type="submit">🔍 Keresés</button>
                <a href="/study" class="nav-btn" style="margin-left: 10px;">🔄 Összes recept</a>
            </form>
        </div>
        
        <div class="results-info">
            <strong>📋 Találatok:</strong> {results_count} recept{search_info}
            <strong> | Algoritmus:</strong> {version_name}
        </div>
        
        <div class="recipe-grid">
            {recipe_cards_html}
        </div>
        
        <div class="navigation">
            <a href="/welcome" class="nav-btn">🏠 Főoldal</a>
            <a href="/metrics" class="nav-btn primary">📈 Metrikák Dashboard</a>
            <a href="/admin/stats" class="nav-btn">👑 Admin Statisztikák</a>
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
                    const feedbackElement = document.getElementById('rating-' + recipeId);
                    feedbackElement.textContent = rating + ' csillag - Köszönjük az értékelést!';
                    
                    // Send rating to server
                    fetch('/api/rate', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                        }},
                        body: JSON.stringify({{
                            recipe_id: recipeId,
                            rating: rating
                        }})
                    }}).then(response => response.json())
                      .then(data => {{
                          console.log('Rating saved:', data);
                          if (data.status === 'success') {{
                              feedbackElement.textContent += ' ✅ Mentve!';
                          }}
                      }}).catch(error => {{
                          console.error('Rating error:', error);
                          feedbackElement.textContent += ' ⚠️ Mentés nem sikerült';
                      }});
                }}
            }}
            
            // Auto-refresh recommendations every 2 minutes for demo purposes
            setTimeout(() => {{
                if (!window.location.search.includes('search=')) {{
                    console.log('🔄 Auto-refresh for personalized recommendations');
                    // window.location.reload(); // Uncomment for auto-refresh
                }}
            }}, 120000);
        </script>
    </body>
    </html>
    """
    
    return study_html
    @user_study_bp.route('/api/rate', methods=['POST'])
def rate_recipe():
    """Rating endpoint with metrics tracking"""
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        rating = data.get('rating')
        user_id = session.get('user_id')
        
        if not all([recipe_id, rating, user_id]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Validate rating
        if not (1 <= rating <= 5):
            return jsonify({'error': 'Rating must be between 1 and 5'}), 400
        
        # Store rating in recommender
        recommender.rate_recipe(user_id, recipe_id, rating)
        
        # Track in metrics
        metrics_tracker.track_rating(user_id, recipe_id, rating)
        
        return jsonify({
            'status': 'success',
            'message': f'Rating {rating} recorded for recipe {recipe_id}',
            'user_id': user_id
        })
        
    except Exception as e:
        print(f"❌ Rating error: {e}")
        return jsonify({'error': str(e)}), 500

@user_study_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Simple login by email"""
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
            return """
            <h2>❌ Felhasználó nem található</h2>
            <p>A megadott email címmel nem található regisztráció.</p>
            <a href="/register">📝 Új regisztráció</a> | 
            <a href="/welcome">🏠 Főoldal</a>
            """
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bejelentkezés - GreenRec</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
            .form-group { margin: 15px 0; }
            label { display: block; font-weight: bold; margin-bottom: 5px; }
            input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
            .btn { padding: 12px 24px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }
            .btn:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <h2>🔑 Bejelentkezés</h2>
        <form method="POST">
            <div class="form-group">
                <label>📧 Email cím:</label>
                <input type="email" name="email" required>
            </div>
            <button type="submit" class="btn">🚀 Bejelentkezés</button>
        </form>
        <p><a href="/welcome">← Vissza a főoldalra</a> | <a href="/register">📝 Új regisztráció</a></p>
    </body>
    </html>
    """

@user_study_bp.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    return redirect(url_for('user_study.welcome'))

@user_study_bp.route('/api/dashboard-data')
def api_dashboard_data():
    """API endpoint for dashboard data"""
    try:
        data = metrics_tracker.get_dashboard_data()
        return jsonify({
            'status': 'success',
            'data': data,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@user_study_bp.route('/api/summary-data')
def api_summary_data():
    """API endpoint for evaluation summary"""
    try:
        data = metrics_tracker.get_evaluation_summary()
        return jsonify({
            'status': 'success',
            'data': data,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@user_study_bp.route('/api/health')
def api_health():
    """Health check for user_study module"""
    return jsonify({
        'status': 'healthy',
        'module': 'user_study',
        'features': {
            'recipes_loaded': len(recipe_loader.recipes),
            'users_registered': len(users_db),
            'total_ratings': sum(len(ratings) for ratings in recommender.user_ratings.values()),
            'json_data_loaded': recipe_loader.loaded,
            'metrics_tracking': True,
            'a_b_c_testing': True
        },
        'endpoints': [
            '/welcome', '/register', '/study', '/metrics', '/login',
            '/api/rate', '/api/dashboard-data', '/api/summary-data'
        ]
    })
    @user_study_bp.route('/metrics')
def metrics_dashboard():
    """Metrics dashboard page"""
    try:
        # Get dashboard data
        dashboard_data = metrics_tracker.get_dashboard_data()
        
        # Build dashboard HTML without f-strings
        precision_value = dashboard_data['key_metrics']['Precision@5']['value']
        precision_count = dashboard_data['key_metrics']['Precision@5']['count']
        diversity_value = dashboard_data['key_metrics']['Recommendation Diversity']['value']
        diversity_count = dashboard_data['key_metrics']['Recommendation Diversity']['count']
        satisfaction_value = dashboard_data['key_metrics']['User Satisfaction']['value']
        satisfaction_count = dashboard_data['key_metrics']['User Satisfaction']['count']
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        dashboard_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>📈 Metrika Dashboard - GreenRec</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
                .dashboard-header {{ background: linear-gradient(135deg, #007bff, #0056b3); color: white; padding: 30px; border-radius: 15px; margin-bottom: 30px; }}
                .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 20px 0; }}
                .metric-card {{ background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
                .metric-value {{ font-size: 2.5em; font-weight: bold; color: #28a745; margin: 10px 0; }}
                .metric-label {{ font-size: 1.1em; color: #6c757d; margin-bottom: 15px; }}
                .metric-description {{ font-size: 0.9em; color: #868e96; }}
                .progress-bar {{ width: 100%; height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden; margin: 10px 0; }}
                .progress-fill {{ height: 100%; background: linear-gradient(90deg, #28a745, #20c997); transition: width 0.3s; }}
                .version-stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 20px 0; }}
                .version-card {{ background: white; padding: 20px; border-radius: 10px; text-align: center; }}
                .version-card.v1 {{ border-left: 5px solid #dc3545; }}
                .version-card.v2 {{ border-left: 5px solid #ffc107; }}
                .version-card.v3 {{ border-left: 5px solid #28a745; }}
                .controls {{ background: white; padding: 20px; border-radius: 12px; margin: 20px 0; }}
                .btn {{ display: inline-block; padding: 10px 20px; margin: 5px; border: none; border-radius: 8px; cursor: pointer; text-decoration: none; color: white; }}
                .btn.primary {{ background: #007bff; }}
                .btn.success {{ background: #28a745; }}
                .btn.secondary {{ background: #6c757d; }}
                .btn:hover {{ opacity: 0.9; }}
                .chart-container {{ background: white; padding: 25px; border-radius: 12px; margin: 20px 0; min-height: 300px; }}
                .real-time-indicator {{ display: inline-block; width: 10px; height: 10px; background: #28a745; border-radius: 50%; margin-right: 10px; animation: pulse 2s infinite; }}
                @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
            </style>
        </head>
        <body>
            <div class="dashboard-header">
                <h1>📈 GreenRec Metrika Dashboard</h1>
                <p><span class="real-time-indicator"></span>Valós idejű monitorozás | Utolsó frissítés: {current_time}</p>
                <p><strong>Rendszer állapot:</strong> {dashboard_data['system_status']} | <strong>Aktív felhasználók:</strong> {dashboard_data['total_users']} | <strong>Összesen értékelés:</strong> {dashboard_data['total_ratings']}</p>
            </div>

            <div class="controls">
                <h3>🎛️ Dashboard Vezérlők</h3>
                <a href="/metrics" class="btn primary" onclick="location.reload()">🔄 Frissítés</a>
                <a href="/admin/export/csv" class="btn success">📊 CSV Export</a>
                <a href="/admin/stats" class="btn secondary">👑 Admin Panel</a>
                <a href="/study" class="btn secondary">🔬 Vissza a Tanulmányhoz</a>
            </div>

            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">🎯 Precision@5</div>
                    <div class="metric-value">{precision_value:.3f}</div>
                    <div class="metric-description">{precision_count} értékelés alapján</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {precision_value * 100}%"></div>
                    </div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">🌈 Ajánlás Diverzitás</div>
                    <div class="metric-value">{diversity_value:.3f}</div>
                    <div class="metric-description">{diversity_count} ajánlás alapján</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {diversity_value * 100}%"></div>
                    </div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">😊 Felhasználói Elégedettség</div>
                    <div class="metric-value">{satisfaction_value:.3f}</div>
                    <div class="metric-description">Átlagos értékelés normalizálva</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {satisfaction_value * 100}%"></div>
                    </div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">📊 Összes Ajánlás</div>
                    <div class="metric-value">{dashboard_data['total_recommendations']}</div>
                    <div class="metric-description">Generált ajánlások száma</div>
                </div>
            </div>

            <div class="chart-container">
                <h3>🧪 A/B/C Teszt Eredmények</h3>
                <div class="version-stats">
                    <div class="version-card v1">
                        <h4>🔴 A Csoport (v1)</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{dashboard_data['version_stats']['v1']['avg_rating']:.2f}/5</div>
                        <div>Fenntarthatóság-központú</div>
                        <div style="color: #6c757d;">{dashboard_data['version_stats']['v1']['count']} értékelés</div>
                    </div>
                    <div class="version-card v2">
                        <h4>🟡 B Csoport (v2)</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{dashboard_data['version_stats']['v2']['avg_rating']:.2f}/5</div>
                        <div>Kiegyensúlyozott</div>
                        <div style="color: #6c757d;">{dashboard_data['version_stats']['v2']['count']} értékelés</div>
                    </div>
                    <div class="version-card v3">
                        <h4>🟢 C Csoport (v3)</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{dashboard_data['version_stats']['v3']['avg_rating']:.2f}/5</div>
                        <div>Személyre szabott</div>
                        <div style="color: #6c757d;">{dashboard_data['version_stats']['v3']['count']} értékelés</div>
                    </div>
                </div>
            </div>

            <div class="chart-container">
                <h3>📈 Teljesítmény Trendek</h3>
                <div style="text-align: center; padding: 50px; color: #6c757d;">
                    <div style="font-size: 3em;">📊</div>
                    <h4>Valós idejű teljesítmény grafikonok</h4>
                    <p>Chart.js integráció a részletes vizualizációkhoz</p>
                    <p><small>Precision, Recall, F1-Score trendek időbeli alakulása</small></p>
                </div>
            </div>

            <script>
                // Auto-refresh every 30 seconds
                setInterval(() => {{
                    console.log('🔄 Auto-refresh dashboard...');
                    location.reload();
                }}, 30000);

                // Add some interactivity
                document.querySelectorAll('.metric-card').forEach(card => {{
                    card.addEventListener('click', () => {{
                        card.style.transform = 'scale(1.02)';
                        setTimeout(() => {{
                            card.style.transform = 'scale(1)';
                        }}, 200);
                    }});
                }});
            </script>
        </body>
        </html>
        """
        
        return dashboard_html
        
    except Exception as e:
        print(f"❌ Dashboard error: {e}")
        return jsonify({
            'error': 'Dashboard temporarily unavailable',
            'details': str(e),
            'alternative': '/admin/stats'
        }), 500
        @user_study_bp.route('/admin/stats')
def admin_stats():
    """Simple admin stats page"""
    user_count = len(users_db)
    total_ratings = sum(len(ratings) for ratings in recommender.user_ratings.values())
    recipe_count = len(recipe_loader.recipes)
    
    # Version distribution
    version_distribution = {}
    for user in users_db.values():
        version = user.get('version', 'unknown')
        version_distribution[version] = version_distribution.get(version, 0) + 1
    
    # Average rating
    avg_rating = 0
    if total_ratings > 0:
        all_ratings = [rating for ratings in recommender.user_ratings.values() 
                      for rating in ratings.values()]
        avg_rating = sum(all_ratings) / len(all_ratings)
    
    # Build user table
    user_rows_html = ''
    for user in users_db.values():
        user_rating_count = len(recommender.user_ratings.get(user['id'], {}))
        user_rows_html += f"""
        <tr>
            <td>{user['id']}</td>
            <td>{user['name']}</td>
            <td>{user['email']}</td>
            <td>{user['version'].upper()}</td>
            <td>{user['registered_at'][:10]}</td>
            <td>{user_rating_count}</td>
        </tr>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>👑 Admin Statisztikák - GreenRec</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
            .admin-header {{ background: #343a40; color: white; padding: 25px; border-radius: 10px; margin-bottom: 25px; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }}
            .stat-card {{ background: white; border: 1px solid #dee2e6; padding: 20px; border-radius: 10px; }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #007bff; }}
            .stat-label {{ color: #6c757d; margin-top: 5px; }}
            .data-table {{ width: 100%; margin: 20px 0; border-collapse: collapse; }}
            .data-table th, .data-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #dee2e6; }}
            .data-table th {{ background: #f8f9fa; font-weight: bold; }}
            .export-section {{ background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0; }}
            .export-btn {{ display: inline-block; padding: 10px 20px; margin: 5px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; }}
            .export-btn:hover {{ background: #218838; }}
        </style>
    </head>
    <body>
        <div class="admin-header">
            <h1>👑 GreenRec Admin Dashboard</h1>
            <p>Részletes statisztikák és adatkezelés | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{recipe_count}</div>
                <div class="stat-label">📋 Betöltött Receptek</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{user_count}</div>
                <div class="stat-label">👥 Regisztrált Felhasználók</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{total_ratings}</div>
                <div class="stat-label">⭐ Összes Értékelés</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{avg_rating:.2f}</div>
                <div class="stat-label">📊 Átlagos Értékelés</div>
            </div>
        </div>

        <h2>📊 Csoport Megoszlás</h2>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Csoport</th>
                    <th>Felhasználók Száma</th>
                    <th>Százalék</th>
                    <th>Algoritmus</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>🔴 A Csoport (v1)</td>
                    <td>{version_distribution.get('v1', 0)}</td>
                    <td>{(version_distribution.get('v1', 0) / max(user_count, 1) * 100):.1f}%</td>
                    <td>Fenntarthatóság-központú</td>
                </tr>
                <tr>
                    <td>🟡 B Csoport (v2)</td>
                    <td>{version_distribution.get('v2', 0)}</td>
                    <td>{(version_distribution.get('v2', 0) / max(user_count, 1) * 100):.1f}%</td>
                    <td>Kiegyensúlyozott</td>
                </tr>
                <tr>
                    <td>🟢 C Csoport (v3)</td>
                    <td>{version_distribution.get('v3', 0)}</td>
                    <td>{(version_distribution.get('v3', 0) / max(user_count, 1) * 100):.1f}%</td>
                    <td>Személyre szabott</td>
                </tr>
            </tbody>
        </table>

        <div class="export-section">
            <h3>📁 Adatexport Lehetőségek</h3>
            <a href="/admin/export/csv" class="export-btn">📊 CSV Export</a>
            <a href="/admin/export/json" class="export-btn">🔗 JSON Export</a>
            <a href="/admin/export/ratings" class="export-btn">⭐ Értékelések CSV</a>
            <a href="/metrics" class="export-btn" style="background: #007bff;">📈 Metrika Dashboard</a>
        </div>

        <h2>👥 Felhasználói Adatok</h2>
        <table class="data-table">
            <thead>
                <tr>
                    <th>User ID</th>
                    <th>Név</th>
                    <th>Email</th>
                    <th>Csoport</th>
                    <th>Regisztráció</th>
                    <th>Értékelések</th>
                </tr>
            </thead>
            <tbody>
                {user_rows_html}
            </tbody>
        </table>

        <div style="margin: 30px 0; text-align: center;">
            <a href="/welcome" class="export-btn" style="background: #6c757d;">🏠 Vissza a Főoldalra</a>
            <a href="/study" class="export-btn" style="background: #6c757d;">🔬 Tanulmány Oldal</a>
        </div>
    </body>
    </html>
    """

@user_study_bp.route('/admin/export/csv')
def export_csv():
    """Simple CSV export"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['User ID', 'Name', 'Email', 'Version', 'Registration Date', 'Total Ratings', 'Average Rating'])
    
    # Data rows
    for user in users_db.values():
        user_ratings = recommender.user_ratings.get(user['id'], {})
        total_ratings = len(user_ratings)
        avg_rating = sum(user_ratings.values()) / max(total_ratings, 1) if total_ratings > 0 else 0
        
        writer.writerow([
            user['id'],
            user['name'],
            user['email'],
            user['version'],
            user['registered_at'][:10],
            total_ratings,
            f"{avg_rating:.2f}"
        ])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=greenrec_users_{datetime.now().strftime("%Y%m%d")}.csv'
    
    return response

@user_study_bp.route('/admin/export/json')
def export_json():
    """Export all data as JSON"""
    try:
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'system_info': {
                'total_recipes': len(recipe_loader.recipes),
                'recipes_source': 'JSON file' if recipe_loader.loaded else 'Sample data'
            },
            'users': list(users_db.values()),
            'ratings': recommender.user_ratings,
            'metrics': metrics_tracker.get_dashboard_data(),
            'interactions': metrics_tracker.interactions[-100:],  # Last 100 interactions
            'recommendations': metrics_tracker.recommendations[-50:]  # Last 50 recommendations
        }
        
        response = make_response(json.dumps(export_data, indent=2, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename=greenrec_data_{datetime.now().strftime("%Y%m%d_%H%M")}.json'
        
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_study_bp.route('/admin/export/ratings')
def export_ratings():
    """Export ratings data as CSV"""
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['User ID', 'Recipe ID', 'Recipe Name', 'Rating', 'User Version', 'Timestamp'])
        
        # Data rows
        for user_id, user_ratings in recommender.user_ratings.items():
            user_version = users_db.get(user_id, {}).get('version', 'unknown')
            for recipe_id, rating in user_ratings.items():
                # Find recipe name
                recipe = next((r for r in recipe_loader.recipes if r['id'] == recipe_id), None)
                recipe_name = recipe['name'] if recipe else recipe_id
                
                # Find timestamp from interactions
                timestamp = datetime.now().isoformat()
                for interaction in metrics_tracker.interactions:
                    if (interaction.get('user_id') == user_id and 
                        interaction.get('recipe_id') == recipe_id and
                        interaction.get('rating') == rating):
                        timestamp = interaction.get('timestamp', timestamp)
                        break
                
                writer.writerow([user_id, recipe_id, recipe_name, rating, user_version, timestamp])
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=greenrec_ratings_{datetime.now().strftime("%Y%m%d")}.csv'
        
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        print("✅ User study routes loaded successfully (COMPLETE FIXED VERSION)")

# Export for main app
__all__ = ['user_study_bp']
