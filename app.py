# app.py - GreenRec Heroku-Ready Single File
"""
GreenRec - Fenntartható Receptajánló Rendszer
============================================
Heroku-kompatibilis egyetlen fájlos verzió - teljes funkcionalitással
"""

from flask import Flask, request, jsonify, session, render_template_string
import pandas as pd
import numpy as np
import json
import logging
import os
import re
import secrets
import hashlib
import unicodedata
import string
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
import math

# Configure logging
logging.basicConfig(
    level=logging.INFO if os.environ.get('FLASK_ENV') != 'production' else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config.update({
    'SECRET_KEY': os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production'),
    'SESSION_COOKIE_SECURE': os.environ.get('FLASK_ENV') == 'production',
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SAMESITE': 'Lax',
    'PERMANENT_SESSION_LIFETIME': timedelta(hours=24),
})

# Global variables
recipes_df = None
recommendation_engine = None
analytics_data = defaultdict(list)
user_ratings = defaultdict(dict)
user_preferences = defaultdict(dict)

# =====================================
# Configuration and Constants
# =====================================

class Config:
    """Alkalmazás konfiguráció"""
    # Scoring weights
    SUSTAINABILITY_WEIGHT = 0.4
    HEALTH_WEIGHT = 0.4
    POPULARITY_WEIGHT = 0.2
    
    # TF-IDF parameters
    TFIDF_MAX_FEATURES = 5000
    TFIDF_MIN_DF = 1
    TFIDF_MAX_DF = 0.95
    TFIDF_NGRAM_RANGE = (1, 2)
    
    # Learning parameters
    DEFAULT_RECOMMENDATIONS = 6
    MAX_LEARNING_ROUNDS = 5
    RELEVANCE_THRESHOLD = 4
    
    # A/B/C groups
    USER_GROUPS = ['A', 'B', 'C']
    GROUP_WEIGHTS = {'A': 0.33, 'B': 0.33, 'C': 0.34}

config = Config()

# =====================================
# Helper Functions
# =====================================

def generate_user_id(prefix="user"):
    """Egyedi felhasználói azonosító generálása"""
    timestamp = datetime.now().strftime("%Y%m%d")
    random_part = secrets.token_hex(4)
    return f"{prefix}_{timestamp}_{random_part}"

def assign_user_group(user_id):
    """Determinisztikus A/B/C csoport kiosztás"""
    hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
    random_value = (hash_value % 10000) / 10000
    
    cumulative = 0
    for group, weight in config.GROUP_WEIGHTS.items():
        cumulative += weight
        if random_value <= cumulative:
            return group
    return 'C'

def get_or_create_user_session():
    """Felhasználói session kezelés"""
    if 'user_id' not in session:
        user_id = generate_user_id()
        user_group = assign_user_group(user_id)
        
        session.update({
            'user_id': user_id,
            'user_group': user_group,
            'learning_round': 1,
            'ratings': {},
            'created_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat()
        })
        
        logger.info(f"New user session: {user_id} (Group: {user_group})")
    
    session['last_activity'] = datetime.now().isoformat()
    return session

def safe_float(value, default=0.0):
    """Biztonságos float konverzió"""
    try:
        if pd.isna(value) or value is None or value == '':
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    """Biztonságos integer konverzió"""
    try:
        if pd.isna(value) or value is None or value == '':
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default

def clean_text(text):
    """Szöveg tisztítása"""
    if not text or pd.isna(text):
        return ""
    
    text = str(text).strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text

def extract_ingredients(ingredients_text):
    """Összetevők kinyerése"""
    if not ingredients_text or pd.isna(ingredients_text):
        return []
    
    text = clean_text(ingredients_text)
    
    if ',' in text:
        ingredients = [item.strip() for item in text.split(',')]
    elif '\n' in text:
        ingredients = [item.strip() for item in text.split('\n')]
    else:
        ingredients = [item.strip() for item in text.split()]
    
    ingredients = [ing for ing in ingredients if len(ing) > 2]
    return ingredients[:20]

def extract_categories(categories_text):
    """Kategóriák kinyerése"""
    if not categories_text or pd.isna(categories_text):
        return []
    
    text = clean_text(categories_text)
    
    for separator in [',', ';', '|', '\n']:
        if separator in text:
            categories = [cat.strip() for cat in text.split(separator)]
            break
    else:
        categories = [text]
    
    categories = [cat.lower().title() for cat in categories if len(cat) > 1]
    return categories[:10]

def normalize_score(value, min_val, max_val):
    """Pontszám normalizálása 0-100 skálára"""
    if max_val == min_val:
        return 50.0
    
    normalized = 100 * (value - min_val) / (max_val - min_val)
    return max(0.0, min(100.0, normalized))

def inverse_normalize_score(value, min_val, max_val):
    """Inverz pontszám normalizálása (ESI-hez)"""
    normalized = normalize_score(value, min_val, max_val)
    return 100.0 - normalized

def calculate_composite_score(esi, hsi, ppi):
    """Kompozit pontszám számítása"""
    esi = safe_float(esi, 50.0)
    hsi = safe_float(hsi, 50.0)
    ppi = safe_float(ppi, 50.0)
    
    composite = (esi * config.SUSTAINABILITY_WEIGHT + 
                hsi * config.HEALTH_WEIGHT + 
                ppi * config.POPULARITY_WEIGHT)
    return max(0.0, min(100.0, composite))

def validate_rating(rating):
    """Értékelés validálása"""
    try:
        rating_int = int(rating)
        return 1 <= rating_int <= 5
    except (ValueError, TypeError):
        return False

def jsonify_response(data, status_code=200, message="success"):
    """Standardizált JSON válasz"""
    response_data = {
        'status': 'success' if status_code < 400 else 'error',
        'message': message,
        'data': data,
        'timestamp': datetime.now().isoformat()
    }
    return jsonify(response_data), status_code

def is_ajax_request():
    """AJAX kérés detektálása"""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

# =====================================
# Analytics and Metrics
# =====================================

def track_behavior(session_id, action, context):
    """Felhasználói viselkedés tracking"""
    behavior_log = {
        'session_id': session_id,
        'timestamp': datetime.now().isoformat(),
        'action': action,
        'context': context
    }
    analytics_data['behaviors'].append(behavior_log)

def calculate_user_metrics(user_id):
    """Felhasználói metrikák számítása"""
    ratings = user_ratings.get(user_id, {})
    
    if not ratings:
        return {
            'total_ratings': 0,
            'avg_rating': 0.0,
            'relevant_items': 0,
            'precision_at_5': 0.0,
            'recall_at_5': 0.0,
            'f1_score_at_5': 0.0
        }
    
    # Alapstatisztikák
    rating_values = list(ratings.values())
    total_ratings = len(rating_values)
    avg_rating = sum(rating_values) / total_ratings
    relevant_items = sum(1 for r in rating_values if r >= config.RELEVANCE_THRESHOLD)
    
    # Precision/Recall/F1 (egyszerűsített)
    recommended_items = min(total_ratings, 5)
    relevant_in_top_5 = sum(1 for r in list(rating_values)[:5] if r >= config.RELEVANCE_THRESHOLD)
    
    precision_at_5 = relevant_in_top_5 / recommended_items if recommended_items > 0 else 0.0
    recall_at_5 = relevant_in_top_5 / relevant_items if relevant_items > 0 else 0.0
    
    if precision_at_5 + recall_at_5 > 0:
        f1_score_at_5 = 2 * (precision_at_5 * recall_at_5) / (precision_at_5 + recall_at_5)
    else:
        f1_score_at_5 = 0.0
    
    return {
        'total_ratings': total_ratings,
        'avg_rating': avg_rating,
        'relevant_items': relevant_items,
        'precision_at_5': precision_at_5,
        'recall_at_5': recall_at_5,
        'f1_score_at_5': f1_score_at_5
    }

def get_dashboard_data():
    """Dashboard adatok összesítése"""
    total_users = len(user_ratings)
    total_ratings = sum(len(ratings) for ratings in user_ratings.values())
    
    # Csoportonkénti statisztikák
    group_stats = {'A': [], 'B': [], 'C': []}
    
    for user_id, ratings in user_ratings.items():
        # Próbáljuk megtalálni a felhasználó csoportját
        user_group = 'A'  # Default
        for behavior in analytics_data['behaviors']:
            if behavior['session_id'] == user_id and 'user_group' in behavior['context']:
                user_group = behavior['context']['user_group']
                break
        
        if ratings:
            avg_rating = sum(ratings.values()) / len(ratings)
            group_stats[user_group].append(avg_rating)
    
    # Átlagok számítása
    group_averages = {}
    for group, ratings in group_stats.items():
        group_averages[group] = {
            'avg_satisfaction': np.mean(ratings) if ratings else 0.0,
            'user_count': len(ratings),
            'total_ratings': sum(len(user_ratings[uid]) for uid in user_ratings.keys())
        }
    
    return {
        'summary': {
            'total_users': total_users,
            'total_ratings': total_ratings,
            'active_users': len([uid for uid, ratings in user_ratings.items() if ratings]),
            'avg_rating': np.mean([r for ratings in user_ratings.values() for r in ratings.values()]) if total_ratings > 0 else 0.0
        },
        'group_performance': group_averages,
        'recent_activity': analytics_data['behaviors'][-10:] if analytics_data['behaviors'] else [],
        'key_insights': [
            f"📊 {total_users} aktív felhasználó",
            f"⭐ {total_ratings} értékelés összesen",
            "🔄 Tanulási algoritmus működik"
        ]
    }

# =====================================
# Recommendation Engine
# =====================================

class GreenRecEngine:
    """GreenRec ajánlórendszer"""
    
    def __init__(self, df):
        self.df = df
        self.tfidf_vectorizer = None
        self.tfidf_matrix = None
        self.setup_engine()
    
    def setup_engine(self):
        """Engine inicializálása"""
        logger.info("Setting up recommendation engine...")
        
        # Szöveges adatok előkészítése
        combined_texts = []
        for _, row in self.df.iterrows():
            text_parts = []
            
            # Név (3x súly)
            if 'name' in row and pd.notna(row['name']):
                text_parts.extend([str(row['name'])] * 3)
            
            # Leírás (2x súly)
            if 'description' in row and pd.notna(row['description']):
                text_parts.extend([str(row['description'])] * 2)
            
            # Összetevők
            if 'ingredients_text' in row and pd.notna(row['ingredients_text']):
                text_parts.append(str(row['ingredients_text']))
            
            # Kategóriák
            if 'categories_text' in row and pd.notna(row['categories_text']):
                text_parts.append(str(row['categories_text']))
            
            combined_texts.append(' '.join(text_parts))
        
        # TF-IDF vektorizálás
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=config.TFIDF_MAX_FEATURES,
            min_df=config.TFIDF_MIN_DF,
            max_df=config.TFIDF_MAX_DF,
            ngram_range=config.TFIDF_NGRAM_RANGE,
            stop_words='english',
            lowercase=True,
            token_pattern=r'\b[a-zA-Z][a-zA-Z]+\b',
            strip_accents='unicode'
        )
        
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(combined_texts)
        logger.info(f"TF-IDF matrix shape: {self.tfidf_matrix.shape}")
    
    def search_recipes(self, query, n=20):
        """Recept keresés TF-IDF alapján"""
        if not query.strip():
            return []
        
        try:
            # Query vektorizálása
            query_vector = self.tfidf_vectorizer.transform([query])
            
            # Hasonlóság számítása
            similarity_scores = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
            
            # Top eredmények
            top_indices = similarity_scores.argsort()[-n:][::-1]
            
            results = []
            for idx in top_indices:
                if similarity_scores[idx] > 0.01:  # Minimum hasonlóság
                    recipe = self.df.iloc[idx].to_dict()
                    recipe['similarity_score'] = float(similarity_scores[idx])
                    results.append(recipe)
            
            return results
            
        except Exception as e:
            logger.error(f"❌ System initialization failed: {e}")
        return False

def ensure_initialized():
    """Biztosítja, hogy a rendszer inicializálva van"""
    global recommendation_engine
    
    if recommendation_engine is None:
        if not initialize_system():
            raise RuntimeError("System initialization failed")

# =====================================
# HTML Templates (Embedded)
# =====================================

INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GreenRec - Fenntartható Receptajánló</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f8f9fa; line-height: 1.6; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #2d7d32, #4caf50); color: white; padding: 2rem 0; text-align: center; margin-bottom: 2rem; }
        .header h1 { font-size: 2.5rem; margin-bottom: 0.5rem; }
        .header p { font-size: 1.1rem; opacity: 0.9; }
        .user-info { background: #e3f2fd; padding: 1rem; border-radius: 8px; margin: 20px 0; border-left: 4px solid #2196f3; }
        .legend { background: white; padding: 1rem; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .legend h6 { margin-bottom: 1rem; color: #333; }
        .legend-items { display: flex; justify-content: space-around; text-align: center; }
        .legend-item { display: flex; flex-direction: column; align-items: center; }
        .legend-icon { font-size: 2rem; margin-bottom: 0.5rem; }
        .progress-section { background: white; padding: 1rem; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .progress-bar { width: 100%; height: 8px; background: #e0e0e0; border-radius: 4px; overflow: hidden; margin-top: 0.5rem; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #2d7d32, #4caf50); width: 0%; transition: width 0.3s ease; }
        .recipe-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin: 20px 0; }
        .recipe-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: transform 0.2s; position: relative; }
        .recipe-card:hover { transform: translateY(-4px); box-shadow: 0 8px 16px rgba(0,0,0,0.15); }
        .recipe-badge { position: absolute; top: 15px; right: 15px; background: linear-gradient(135deg, #2d7d32, #4caf50); color: white; padding: 4px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
        .recipe-title { font-size: 1.3rem; font-weight: 600; margin-bottom: 10px; color: #333; }
        .recipe-description { color: #666; margin-bottom: 15px; font-size: 0.9rem; line-height: 1.4; }
        .recipe-metrics { display: flex; justify-content: space-between; margin: 15px 0; }
        .metric-item { text-align: center; flex: 1; }
        .metric-icon { font-size: 1.5rem; display: block; margin-bottom: 4px; }
        .metric-value { font-weight: 600; color: #333; font-size: 0.9rem; }
        .composite-score { background: linear-gradient(135deg, #2d7d32, #4caf50); color: white; padding: 8px 16px; border-radius: 20px; text-align: center; font-weight: 600; margin: 15px 0; }
        .star-rating { display: flex; gap: 4px; margin: 15px 0; justify-content: center; }
        .star { font-size: 1.5rem; color: #ddd; cursor: pointer; transition: all 0.2s; user-select: none; }
        .star:hover, .star.active { color: #ffd700; transform: scale(1.1); }
        .category-tags { margin-top: 15px; }
        .category-tag { display: inline-block; background: #f0f0f0; color: #666; padding: 4px 8px; margin: 2px; border-radius: 12px; font-size: 0.8rem; }
        .btn { display: inline-block; padding: 10px 20px; background: #4caf50; color: white; text-decoration: none; border-radius: 6px; border: none; cursor: pointer; font-size: 1rem; transition: background 0.2s; }
        .btn:hover { background: #45a049; }
        .btn:disabled { background: #ccc; cursor: not-allowed; }
        .btn.hidden { display: none; }
        .alert { padding: 1rem; margin: 1rem 0; border-radius: 6px; }
        .alert-info { background: #e3f2fd; color: #1976d2; border-left: 4px solid #2196f3; }
        .alert-warning { background: #fff3e0; color: #f57c00; border-left: 4px solid #ff9800; }
        .loading { text-align: center; padding: 2rem; }
        .loading i { font-size: 2rem; animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .no-results { text-align: center; padding: 3rem; color: #666; }
        .search-container { max-width: 600px; margin: 0 auto 2rem; }
        .search-input { width: 100%; padding: 12px 20px; border: 2px solid #ddd; border-radius: 25px; font-size: 1rem; outline: none; transition: border-color 0.2s; }
        .search-input:focus { border-color: #4caf50; }
        @media (max-width: 768px) {
            .recipe-grid { grid-template-columns: 1fr; }
            .header h1 { font-size: 2rem; }
            .legend-items { flex-direction: column; gap: 1rem; }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <h1><i class="fas fa-leaf"></i> GreenRec</h1>
            <p>Fenntartható receptajánló AI technológiával</p>
        </div>
    </div>

    <div class="container">
        <!-- User Info -->
        {% if user_session %}
        <div class="user-info">
            <i class="fas fa-user-circle"></i>
            Üdvözöljük, <strong>{{ user_session.user_group }}</strong> csoport tagja! 
            ({{ user_session.learning_round }}. tanulási kör)
        </div>
        {% endif %}

        <!-- Legend -->
        <div class="legend">
            <h6><i class="fas fa-info-circle"></i> Pontszám magyarázat:</h6>
            <div class="legend-items">
                <div class="legend-item">
                    <span class="legend-icon">🌍</span>
                    <small>Környezetbarát</small>
                </div>
                <div class="legend-item">
                    <span class="legend-icon">💚</span>
                    <small>Egészséges</small>
                </div>
                <div class="legend-item">
                    <span class="legend-icon">👤</span>
                    <small>Népszerű</small>
                </div>
            </div>
        </div>

        <!-- Progress -->
        <div class="progress-section">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="rating-progress-text">0/6 recept értékelve</span>
                <button class="btn next-round-btn hidden" disabled onclick="nextRound()">
                    Következő kör indítása
                </button>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="progress-fill"></div>
            </div>
        </div>

        <!-- Search -->
        <div class="search-container">
            <input type="text" class="search-input" placeholder="Keressen recepteket... (pl. 'vegan pasta')" 
                   onkeypress="if(event.key==='Enter') searchRecipes()" id="search-input">
        </div>

        <!-- Recommendations -->
        <div class="recipe-grid">
            {% for recipe in recommendations %}
            <div class="recipe-card">
                <div class="recipe-badge">{{ "%.0f"|format(recipe.composite_score or 0) }}</div>
                
                <h3 class="recipe-title">{{ recipe.name }}</h3>
                
                {% if recipe.description %}
                <p class="recipe-description">{{ recipe.description[:150] }}{% if recipe.description|length > 150 %}...{% endif %}</p>
                {% endif %}
                
                <div class="recipe-metrics">
                    <div class="metric-item">
                        <span class="metric-icon">🌍</span>
                        <span class="metric-value">{{ "%.0f"|format(recipe.ESI_final or 0) }}</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-icon">💚</span>
                        <span class="metric-value">{{ "%.0f"|format(recipe.HSI or 0) }}</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-icon">👤</span>
                        <span class="metric-value">{{ "%.0f"|format(recipe.PPI or 0) }}</span>
                    </div>
                </div>
                
                <div class="composite-score">
                    Kompozit: {{ "%.0f"|format(recipe.composite_score or 0) }}
                </div>
                
                <div class="star-rating">
                    {% for rating in range(1, 6) %}
                    <span class="star" data-recipe-id="{{ recipe.id }}" data-rating="{{ rating }}" onclick="rateRecipe('{{ recipe.id }}', {{ rating }})">⭐</span>
                    {% endfor %}
                </div>
                
                {% if recipe.categories_list %}
                <div class="category-tags">
                    {% for category in recipe.categories_list[:3] %}
                    <span class="category-tag">{{ category }}</span>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>

        {% if not recommendations %}
        <div class="no-results">
            <i class="fas fa-search" style="font-size: 3rem; color: #ddd; margin-bottom: 1rem;"></i>
            <h3>Nincs elérhető ajánlás</h3>
            <p>Kérjük, próbálja meg később.</p>
        </div>
        {% endif %}
    </div>

    <script>
        let currentRatings = {};
        let ratingsCount = 0;

        function rateRecipe(recipeId, rating) {
            console.log(`Rating recipe ${recipeId} with ${rating} stars`);
            
            // Update UI
            updateStars(recipeId, rating);
            currentRatings[recipeId] = rating;
            updateProgress();
            
            // Send to server
            fetch('/api/rate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    recipe_id: recipeId,
                    rating: rating
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    console.log('Rating saved successfully');
                    if (data.data && data.data.round_complete) {
                        showNextRoundButton();
                    }
                } else {
                    console.error('Rating save failed:', data.message);
                    alert('Értékelés mentése sikertelen');
                }
            })
            .catch(error => {
                console.error('Rating error:', error);
                alert('Hálózati hiba történt');
            });
        }

        function updateStars(recipeId, rating) {
            const stars = document.querySelectorAll(`[data-recipe-id="${recipeId}"]`);
            stars.forEach((star, index) => {
                if (index < rating) {
                    star.classList.add('active');
                } else {
                    star.classList.remove('active');
                }
            });
        }

        function updateProgress() {
            ratingsCount = Object.keys(currentRatings).length;
            const percentage = (ratingsCount / 6) * 100;
            
            document.getElementById('progress-fill').style.width = percentage + '%';
            document.querySelector('.rating-progress-text').textContent = `${ratingsCount}/6 recept értékelve`;
            
            if (ratingsCount >= 6) {
                showNextRoundButton();
            }
        }

        function showNextRoundButton() {
            const button = document.querySelector('.next-round-btn');
            button.classList.remove('hidden');
            button.disabled = false;
        }

        function nextRound() {
            if (confirm('Biztos, hogy elindítja a következő tanulási kört?')) {
                fetch('/api/next-round', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        alert('Következő kör elkezdődött!');
                        window.location.reload();
                    } else {
                        alert('Hiba történt: ' + data.message);
                    }
                })
                .catch(error => {
                    console.error('Next round error:', error);
                    alert('Hálózati hiba történt');
                });
            }
        }

        function searchRecipes() {
            const query = document.getElementById('search-input').value.trim();
            if (query) {
                window.location.href = `/search?q=${encodeURIComponent(query)}`;
            }
        }

        // Initialize page
        document.addEventListener('DOMContentLoaded', function() {
            console.log('GreenRec loaded with {{ recommendations|length }} recommendations');
        });
    </script>
</body>
</html>
"""

SEARCH_TEMPLATE = """
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GreenRec - Keresés</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f8f9fa; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #2d7d32, #4caf50); color: white; padding: 2rem 0; text-align: center; margin-bottom: 2rem; }
        .search-form { max-width: 600px; margin: 0 auto 2rem; display: flex; gap: 10px; }
        .search-input { flex: 1; padding: 12px 20px; border: 2px solid #ddd; border-radius: 6px; font-size: 1rem; }
        .search-btn { padding: 12px 20px; background: #4caf50; color: white; border: none; border-radius: 6px; cursor: pointer; }
        .results-header { margin: 2rem 0 1rem; }
        .badge { background: #6c757d; color: white; padding: 4px 8px; border-radius: 12px; font-size: 0.8rem; }
        .recipe-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .recipe-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .recipe-title { font-size: 1.2rem; font-weight: 600; margin-bottom: 10px; color: #333; }
        .recipe-description { color: #666; margin-bottom: 15px; font-size: 0.9rem; }
        .recipe-metrics { display: flex; gap: 15px; margin: 15px 0; }
        .metric-item { font-size: 0.9rem; }
        .composite-score { background: linear-gradient(135deg, #2d7d32, #4caf50); color: white; padding: 6px 12px; border-radius: 15px; display: inline-block; font-size: 0.9rem; }
        .no-results { text-align: center; padding: 3rem; color: #666; }
        .back-link { display: inline-block; margin-bottom: 1rem; color: #4caf50; text-decoration: none; }
        .back-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <h1><i class="fas fa-search"></i> Receptkeresés</h1>
            <p>Találjon fenntartható és egészséges recepteket</p>
        </div>
    </div>

    <div class="container">
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> Vissza a főoldalra</a>
        
        <form class="search-form" method="GET">
            <input type="text" name="q" value="{{ query }}" class="search-input" 
                   placeholder="Keressen recepteket... (pl. 'vegan pasta', 'csirkemell')" autofocus>
            <button type="submit" class="search-btn">
                <i class="fas fa-search"></i> Keresés
            </button>
        </form>

        {% if query %}
        <div class="results-header">
            <h4>Találatok: "{{ query }}" <span class="badge">{{ results|length }} recept</span></h4>
        </div>

        {% if results %}
        <div class="recipe-grid">
            {% for recipe in results %}
            <div class="recipe-card">
                <h5 class="recipe-title">{{ recipe.name }}</h5>
                
                {% if recipe.description %}
                <p class="recipe-description">{{ recipe.description[:100] }}...</p>
                {% endif %}
                
                <div class="recipe-metrics">
                    <span class="metric-item">🌍 {{ "%.0f"|format(recipe.ESI_final or 0) }}</span>
                    <span class="metric-item">💚 {{ "%.0f"|format(recipe.HSI or 0) }}</span>
                    <span class="metric-item">👤 {{ "%.0f"|format(recipe.PPI or 0) }}</span>
                </div>
                
                <div class="composite-score">
                    Kompozit: {{ "%.0f"|format(recipe.composite_score or 0) }}
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="no-results">
            <i class="fas fa-search" style="font-size: 3rem; margin-bottom: 1rem;"></i>
            <h3>Nincs találat</h3>
            <p>Próbáljon meg más keresési kifejezést.</p>
        </div>
        {% endif %}
        {% endif %}
    </div>
</body>
</html>
"""

ANALYTICS_TEMPLATE = """
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GreenRec - Analitika</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f8f9fa; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #2d7d32, #4caf50); color: white; padding: 2rem 0; text-align: center; margin-bottom: 2rem; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 2rem 0; }
        .metric-card { background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; }
        .metric-icon { font-size: 2rem; margin-bottom: 0.5rem; }
        .metric-value { font-size: 2rem; font-weight: 700; color: #2d7d32; margin: 0.5rem 0; }
        .metric-label { color: #666; font-size: 0.9rem; }
        .stats-section { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin: 2rem 0; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }
        .stat-item { padding: 1rem; background: #f8f9fa; border-radius: 8px; }
        .stat-label { font-weight: 600; color: #333; }
        .stat-value { font-size: 1.2rem; color: #2d7d32; }
        .back-link { display: inline-block; margin-bottom: 1rem; color: #4caf50; text-decoration: none; }
        .back-link:hover { text-decoration: underline; }
        .refresh-btn { background: #4caf50; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; margin: 1rem 0; }
        .refresh-btn:hover { background: #45a049; }
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <h1><i class="fas fa-chart-line"></i> Analitika Dashboard</h1>
            <p>Rendszer teljesítmény és felhasználói metrikák</p>
        </div>
    </div>

    <div class="container">
        <a href="/" class="back-link"><i class="fas fa-arrow-left"></i> Vissza a főoldalra</a>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-icon">👥</div>
                <div class="metric-value" id="total-users">{{ dashboard_data.summary.total_users or 0 }}</div>
                <div class="metric-label">Aktív felhasználók</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-icon">⭐</div>
                <div class="metric-value" id="total-ratings">{{ dashboard_data.summary.total_ratings or 0 }}</div>
                <div class="metric-label">Összes értékelés</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-icon">📊</div>
                <div class="metric-value" id="avg-rating">{{ "%.1f"|format(dashboard_data.summary.avg_rating or 0) }}</div>
                <div class="metric-label">Átlagos értékelés</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-icon">🚀</div>
                <div class="metric-value" id="active-sessions">{{ dashboard_data.summary.active_users or 0 }}</div>
                <div class="metric-label">Aktív munkamenetek</div>
            </div>
        </div>

        <div class="stats-section">
            <h3><i class="fas fa-users"></i> A/B/C Csoport Teljesítmény</h3>
            <div class="stats-grid">
                {% for group, data in dashboard_data.group_performance.items() %}
                <div class="stat-item">
                    <div class="stat-label">{{ group }} Csoport</div>
                    <div class="stat-value">{{ "%.2f"|format(data.avg_satisfaction or 0) }}</div>
                    <small>{{ data.user_count or 0 }} felhasználó</small>
                </div>
                {% endfor %}
            </div>
        </div>

        <div class="stats-section">
            <h3><i class="fas fa-lightbulb"></i> Főbb Insights</h3>
            <ul>
                {% for insight in dashboard_data.key_insights %}
                <li style="margin: 0.5rem 0;">{{ insight }}</li>
                {% endfor %}
            </ul>
        </div>

        <div style="text-align: center;">
            <button class="refresh-btn" onclick="refreshDashboard()">
                <i class="fas fa-sync-alt"></i> Frissítés
            </button>
        </div>
    </div>

    <script>
        function refreshDashboard() {
            console.log('Refreshing dashboard...');
            
            fetch('/api/dashboard-data')
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        // Update metrics
                        const summary = data.data.summary || {};
                        document.getElementById('total-users').textContent = summary.total_users || 0;
                        document.getElementById('total-ratings').textContent = summary.total_ratings || 0;
                        document.getElementById('avg-rating').textContent = (summary.avg_rating || 0).toFixed(1);
                        document.getElementById('active-sessions').textContent = summary.active_users || 0;
                        
                        console.log('Dashboard updated successfully');
                    } else {
                        console.error('Dashboard refresh failed:', data.message);
                    }
                })
                .catch(error => {
                    console.error('Dashboard refresh error:', error);
                });
        }

        // Auto-refresh every 30 seconds
        setInterval(refreshDashboard, 30000);
    </script>
</body>
</html>
"""

# =====================================
# Error Handlers
# =====================================

@app.errorhandler(404)
def not_found(error):
    if is_ajax_request():
        return jsonify_response(None, 404, "Endpoint not found")
    
    return render_template_string("""
    <h1>404 - Oldal nem található</h1>
    <p><a href="/">Vissza a főoldalra</a></p>
    """), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    if is_ajax_request():
        return jsonify_response(None, 500, "Internal server error")
    
    return render_template_string("""
    <h1>500 - Belső szerver hiba</h1>
    <p>Kérjük, próbálja meg később.</p>
    <p><a href="/">Vissza a főoldalra</a></p>
    """), 500

# =====================================
# Routes
# =====================================

@app.route('/')
def index():
    """Főoldal - Ajánlások megjelenítése"""
    try:
        ensure_initialized()
        
        # Get or create user session
        user_session = get_or_create_user_session()
        
        # Get personalized recommendations
        recommendations = recommendation_engine.get_personalized_recommendations(
            user_id=user_session['user_id'],
            n=config.DEFAULT_RECOMMENDATIONS
        )
        
        # Track analytics
        track_behavior(
            session_id=user_session['user_id'],
            action='page_view',
            context={'page': 'index', 'user_group': user_session['user_group']}
        )
        
        return render_template_string(INDEX_TEMPLATE, 
                                    recommendations=recommendations,
                                    user_session=user_session)
        
    except Exception as e:
        logger.error(f"Index page error: {e}")
        return render_template_string("""
        <h1>Hiba történt</h1>
        <p>Nem sikerült betölteni az ajánlásokat: {{ error }}</p>
        <p><a href="/">Újrapróbálás</a></p>
        """, error=str(e))

@app.route('/search')
def search():
    """Keresési oldal"""
    try:
        ensure_initialized()
        
        query = request.args.get('q', '').strip()
        results = []
        
        if query:
            # Basic validation
            if len(query) > 200:
                query = query[:200]
            
            # XSS protection
            query = re.sub(r'<[^>]+>', '', query)
            
            results = recommendation_engine.search_recipes(query, n=20)
            
            # Track search
            track_behavior(
                session_id=session.get('user_id', 'anonymous'),
                action='search',
                context={'query': query, 'results_count': len(results)}
            )
        
        return render_template_string(SEARCH_TEMPLATE, 
                                    query=query, 
                                    results=results)
        
    except Exception as e:
        logger.error(f"Search page error: {e}")
        return render_template_string("""
        <h1>Keresési hiba</h1>
        <p>{{ error }}</p>
        <p><a href="/">Vissza a főoldalra</a></p>
        """, error=str(e))

@app.route('/analytics')
def analytics_dashboard():
    """Analitika dashboard"""
    try:
        ensure_initialized()
        
        # Get dashboard data
        dashboard_data = get_dashboard_data()
        
        return render_template_string(ANALYTICS_TEMPLATE, 
                                    dashboard_data=dashboard_data)
        
    except Exception as e:
        logger.error(f"Analytics dashboard error: {e}")
        return render_template_string("""
        <h1>Analitika hiba</h1>
        <p>{{ error }}</p>
        <p><a href="/">Vissza a főoldalra</a></p>
        """, error=str(e))

# =====================================
# API Routes
# =====================================

@app.route('/api/rate', methods=['POST'])
def api_rate_recipe():
    """Recept értékelése API"""
    try:
        ensure_initialized()
        
        # Get JSON data
        data = request.get_json()
        if not data:
            return jsonify_response(None, 400, "Missing JSON data")
        
        recipe_id = data.get('recipe_id')
        rating = data.get('rating')
        
        # Validation
        if not recipe_id:
            return jsonify_response(None, 400, "Missing recipe_id")
        
        if not validate_rating(rating):
            return jsonify_response(None, 400, "Invalid rating (must be 1-5)")
        
        rating = int(rating)
        
        # Get user session
        user_session = get_or_create_user_session()
        user_id = user_session['user_id']
        
        # Save rating
        if user_id not in user_ratings:
            user_ratings[user_id] = {}
        
        user_ratings[user_id][recipe_id] = rating
        
        # Update session
        session['ratings'] = user_ratings[user_id]
        
        # Calculate metrics
        user_metrics = calculate_user_metrics(user_id)
        
        # Track analytics
        track_behavior(
            session_id=user_id,
            action='rate_recipe',
            context={
                'recipe_id': recipe_id,
                'rating': rating,
                'user_group': user_session['user_group'],
                'learning_round': user_session.get('learning_round', 1)
            }
        )
        
        # Check if round is complete
        ratings_count = len(user_ratings[user_id])
        round_complete = ratings_count >= config.DEFAULT_RECOMMENDATIONS
        
        return jsonify_response({
            'rating_saved': True,
            'ratings_count': ratings_count,
            'round_complete': round_complete,
            'user_metrics': user_metrics
        })
        
    except Exception as e:
        logger.error(f"Rating API error: {e}")
        return jsonify_response(None, 500, "Rating save failed")

@app.route('/api/search', methods=['GET'])
def api_search():
    """Keresés API"""
    try:
        ensure_initialized()
        
        query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 20)), 50)
        
        if not query:
            return jsonify_response(None, 400, "Missing search query")
        
        if len(query) > 200:
            return jsonify_response(None, 400, "Query too long")
        
        # XSS protection
        query = re.sub(r'<[^>]+>', '', query)
        
        # Perform search
        results = recommendation_engine.search_recipes(query, n=limit)
        
        # Track search
        track_behavior(
            session_id=session.get('user_id', 'anonymous'),
            action='api_search',
            context={'query': query, 'results_count': len(results)}
        )
        
        return jsonify_response({
            'recipes': results, 
            'total': len(results)
        })
        
    except Exception as e:
        logger.error(f"Search API error: {e}")
        return jsonify_response(None, 500, "Search failed")

@app.route('/api/next-round', methods=['POST'])
def api_next_round():
    """Következő tanulási kör indítása"""
    try:
        ensure_initialized()
        
        # Get user session
        user_session = get_or_create_user_session()
        
        # Check if user has enough ratings
        user_id = user_session['user_id']
        ratings_count = len(user_ratings.get(user_id, {}))
        
        if ratings_count < config.DEFAULT_RECOMMENDATIONS:
            return jsonify_response(None, 400, f"Need at least {config.DEFAULT_RECOMMENDATIONS} ratings to advance")
        
        # Advance round
        new_round = min(user_session.get('learning_round', 1) + 1, config.MAX_LEARNING_ROUNDS)
        session['learning_round'] = new_round
        
        # Reset ratings for new round
        session['ratings'] = {}
        if user_id in user_ratings:
            # Keep old ratings in analytics but start fresh for recommendations
            user_ratings[f"{user_id}_round_{new_round}"] = {}
        
        # Track analytics
        track_behavior(
            session_id=user_id,
            action='advance_round',
            context={
                'new_round': new_round,
                'user_group': user_session['user_group']
            }
        )
        
        return jsonify_response({'new_round': new_round})
        
    except Exception as e:
        logger.error(f"Next round API error: {e}")
        return jsonify_response(None, 500, "Round advancement failed")

@app.route('/api/dashboard-data')
def api_dashboard_data():
    """Dashboard adatok API"""
    try:
        ensure_initialized()
        
        dashboard_data = get_dashboard_data()
        
        return jsonify_response(dashboard_data)
        
    except Exception as e:
        logger.error(f"Dashboard data API error: {e}")
        return jsonify_response({}, 500, "Dashboard data retrieval failed")

@app.route('/status')
def system_status():
    """Rendszer állapot ellenőrzése"""
    try:
        ensure_initialized()
        
        status_info = {
            'system_ready': recommendation_engine is not None,
            'recipes_loaded': len(recipes_df) if recipes_df is not None else 0,
            'total_users': len(user_ratings),
            'total_ratings': sum(len(ratings) for ratings in user_ratings.values()),
            'environment': os.environ.get('FLASK_ENV', 'development'),
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify_response(status_info)
        
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return jsonify_response({'error': str(e)}, 500, "Status check failed")

@app.route('/health')
def health_check():
    """Health check endpoint (Heroku compatible)"""
    try:
        ensure_initialized()
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'system_ready': recommendation_engine is not None
        })
    except:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat()
        }), 503

# =====================================
# Application Startup
# =====================================

@app.before_first_request
def before_first_request():
    """Initialize system before first request"""
    try:
        initialize_system()
    except Exception as e:
        logger.error(f"Initialization failed: {e}")

@app.before_request
def before_request():
    """Request preprocessing"""
    # Make session permanent
    session.permanent = True
    
    # Log requests in development
    if os.environ.get('FLASK_ENV') != 'production':
        logger.debug(f"{request.method} {request.url}")

@app.after_request
def after_request(response):
    """Response postprocessing"""
    # Add security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    return response

if __name__ == '__main__':
    try:
        # Get port from environment (Heroku compatibility)
        port = int(os.environ.get('PORT', 5000))
        
        logger.info("🚀 Starting GreenRec application...")
        
        # Initialize system
        if initialize_system():
            logger.info("✅ System ready - starting Flask server")
        else:
            logger.warning("⚠️ System initialization failed - starting anyway")
        
        # Run application
        app.run(
            host='0.0.0.0',
            port=port,
            debug=os.environ.get('FLASK_ENV') != 'production',
            threaded=True
        )
        
    except KeyboardInterrupt:
        logger.info("👋 Application shutdown requested")
    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}")
        raiseSearch error: {e}")
            return []
    
    def get_personalized_recommendations(self, user_id, user_preferences=None, n=6):
        """Személyre szabott ajánlások"""
        try:
            # User ratings lekérése
            ratings = user_ratings.get(user_id, {})
            
            if len(ratings) < 3:
                # Kevés értékelés esetén: magas kompozit pontszámú receptek
                high_scoring = self.df[self.df['composite_score'] >= 70].copy()
                
                if len(high_scoring) < n:
                    high_scoring = self.df.copy()
                
                # Véletlenszerű választás kompozit pontszám szerint súlyozva
                if len(high_scoring) >= n:
                    # Súlyozott véletlenszerű választás
                    weights = high_scoring['composite_score'] / high_scoring['composite_score'].sum()
                    selected_indices = np.random.choice(
                        high_scoring.index, 
                        size=min(n, len(high_scoring)), 
                        replace=False, 
                        p=weights
                    )
                    selected = high_scoring.loc[selected_indices]
                else:
                    selected = high_scoring
            else:
                # Személyre szabás meglévő értékelések alapján
                selected = self._get_preference_based_recommendations(user_id, ratings, n)
            
            return selected.to_dict('records')
            
        except Exception as e:
            logger.error(f"Personalized recommendations error: {e}")
            # Fallback: random selection
            return self.df.sample(n=min(n, len(self.df))).to_dict('records')
    
    def _get_preference_based_recommendations(self, user_id, ratings, n):
        """Preferencia alapú ajánlások"""
        # Kedvelt receptek (rating >= 4)
        liked_recipe_ids = [rid for rid, rating in ratings.items() if rating >= config.RELEVANCE_THRESHOLD]
        
        if not liked_recipe_ids:
            # Ha nincs kedvelt recept, magas pontszámúakat ajánljunk
            return self.df[self.df['composite_score'] >= 60].sample(n=min(n, len(self.df)))
        
        # Kedvelt receptek adatai
        liked_recipes = self.df[self.df['id'].isin(liked_recipe_ids)]
        
        # Preferenciák kinyerése
        preferred_categories = []
        preferred_ingredients = []
        
        for _, recipe in liked_recipes.iterrows():
            if 'categories_list' in recipe and isinstance(recipe['categories_list'], list):
                preferred_categories.extend(recipe['categories_list'])
            if 'ingredients_list' in recipe and isinstance(recipe['ingredients_list'], list):
                preferred_ingredients.extend(recipe['ingredients_list'])
        
        # Leggyakoribb preferenciák
        top_categories = [cat for cat, _ in Counter(preferred_categories).most_common(5)]
        top_ingredients = [ing for ing, _ in Counter(preferred_ingredients).most_common(10)]
        
        # Hasonló receptek keresése
        candidate_recipes = self.df[~self.df['id'].isin(ratings.keys())].copy()
        
        # Scoring hasonlóság alapján
        similarity_scores = []
        for _, recipe in candidate_recipes.iterrows():
            score = 0.0
            
            # Kategória hasonlóság
            recipe_categories = recipe.get('categories_list', [])
            if isinstance(recipe_categories, list):
                category_overlap = len(set(recipe_categories) & set(top_categories))
                score += category_overlap * 0.3
            
            # Összetevő hasonlóság
            recipe_ingredients = recipe.get('ingredients_list', [])
            if isinstance(recipe_ingredients, list):
                ingredient_overlap = len(set(recipe_ingredients) & set(top_ingredients))
                score += ingredient_overlap * 0.2
            
            # Kompozit pontszám
            score += recipe.get('composite_score', 0) * 0.01
            
            similarity_scores.append(score)
        
        # Top ajánlások
        candidate_recipes['similarity_score'] = similarity_scores
        top_recommendations = candidate_recipes.nlargest(n, 'similarity_score')
        
        return top_recommendations

# =====================================
# Data Loading and Processing
# =====================================

def load_and_process_data():
    """Adatok betöltése és feldolgozása"""
    global recipes_df
    
    try:
        # Próbáljuk meg különböző helyekről betölteni
        data_paths = [
            'data/greenrec_dataset.json',
            'greenrec_dataset.json',
            './greenrec_dataset.json'
        ]
        
        data = None
        for path in data_paths:
            try:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    logger.info(f"Data loaded from: {path}")
                    break
            except Exception as e:
                logger.warning(f"Failed to load from {path}: {e}")
                continue
        
        if data is None:
            # Demo adatok létrehozása ha nincs fájl
            logger.warning("No data file found, creating demo data")
            data = create_demo_data()
        
        # DataFrame létrehozása
        if isinstance(data, list):
            recipes_df = pd.DataFrame(data)
        elif isinstance(data, dict) and 'recipes' in data:
            recipes_df = pd.DataFrame(data['recipes'])
        else:
            recipes_df = pd.DataFrame([data])
        
        # Adatok feldolgozása
        process_dataframe()
        
        logger.info(f"Loaded {len(recipes_df)} recipes")
        return True
        
    except Exception as e:
        logger.error(f"Data loading failed: {e}")
        return False

def create_demo_data():
    """Demo adatok létrehozása ha nincs fájl"""
    return [
        {
            "id": "demo_1",
            "name": "Vegan Pasta Primavera",
            "description": "Fresh vegetables with pasta in light olive oil sauce",
            "ingredients": "whole wheat pasta, zucchini, bell peppers, cherry tomatoes, olive oil, garlic, basil",
            "categories": "vegan, italian, healthy, quick",
            "ESI": 15,
            "HSI": 85,
            "PPI": 70
        },
        {
            "id": "demo_2", 
            "name": "Quinoa Buddha Bowl",
            "description": "Nutritious bowl with quinoa, roasted vegetables and tahini dressing",
            "ingredients": "quinoa, sweet potato, chickpeas, avocado, kale, tahini, lemon, olive oil",
            "categories": "vegan, superfood, bowl, healthy",
            "ESI": 10,
            "HSI": 95,
            "PPI": 60
        },
        {
            "id": "demo_3",
            "name": "Grilled Chicken Salad",
            "description": "Protein-rich salad with grilled organic chicken breast",
            "ingredients": "organic chicken breast, mixed greens, cucumber, tomatoes, avocado, olive oil vinaigrette",
            "categories": "protein, salad, healthy, low-carb",
            "ESI": 45,
            "HSI": 88,
            "PPI": 85
        },
        {
            "id": "demo_4",
            "name": "Lentil Curry",
            "description": "Spicy red lentil curry with coconut milk and vegetables",
            "ingredients": "red lentils, coconut milk, onions, garlic, ginger, tomatoes, spinach, curry spices",
            "categories": "vegan, curry, indian, protein",
            "ESI": 12,
            "HSI": 90,
            "PPI": 75
        },
        {
            "id": "demo_5",
            "name": "Mediterranean Fish",
            "description": "Baked fish with Mediterranean herbs and vegetables",
            "ingredients": "white fish, olive oil, tomatoes, olives, capers, herbs, lemon",
            "categories": "mediterranean, fish, healthy, omega-3",
            "ESI": 35,
            "HSI": 92,
            "PPI": 70
        },
        {
            "id": "demo_6",
            "name": "Green Smoothie Bowl",
            "description": "Nutrient-packed smoothie bowl with superfoods",
            "ingredients": "spinach, banana, mango, chia seeds, coconut flakes, almond milk, berries",
            "categories": "vegan, smoothie, breakfast, superfood",
            "ESI": 8,
            "HSI": 93,
            "PPI": 65
        }
    ]

def process_dataframe():
    """DataFrame feldolgozása"""
    global recipes_df
    
    # ID oszlop biztosítása
    if 'id' not in recipes_df.columns:
        recipes_df['id'] = [f"recipe_{i}" for i in range(len(recipes_df))]
    else:
        recipes_df['id'] = recipes_df['id'].astype(str)
    
    # Név tisztítása
    if 'name' in recipes_df.columns:
        recipes_df['name'] = recipes_df['name'].apply(lambda x: clean_text(str(x)) if pd.notna(x) else "Unknown Recipe")
    
    # Leírás tisztítása
    if 'description' in recipes_df.columns:
        recipes_df['description'] = recipes_df['description'].apply(lambda x: clean_text(str(x)) if pd.notna(x) else "")
    
    # Összetevők feldolgozása
    if 'ingredients' in recipes_df.columns:
        recipes_df['ingredients_list'] = recipes_df['ingredients'].apply(extract_ingredients)
        recipes_df['ingredients_text'] = recipes_df['ingredients_list'].apply(lambda x: ' '.join(x) if isinstance(x, list) else "")
    else:
        recipes_df['ingredients_list'] = [[] for _ in range(len(recipes_df))]
        recipes_df['ingredients_text'] = ""
    
    # Kategóriák feldolgozása
    if 'categories' in recipes_df.columns:
        recipes_df['categories_list'] = recipes_df['categories'].apply(extract_categories)
        recipes_df['categories_text'] = recipes_df['categories_list'].apply(lambda x: ' '.join(x) if isinstance(x, list) else "")
    else:
        recipes_df['categories_list'] = [[] for _ in range(len(recipes_df))]
        recipes_df['categories_text'] = ""
    
    # Numerikus értékek feldolgozása
    for col in ['ESI', 'HSI', 'PPI']:
        if col in recipes_df.columns:
            recipes_df[col] = recipes_df[col].apply(safe_float)
        else:
            # Default értékek ha hiányzik
            if col == 'ESI':
                recipes_df[col] = 50.0
            elif col == 'HSI':
                recipes_df[col] = 70.0
            else:  # PPI
                recipes_df[col] = 60.0
    
    # ESI inverz normalizálás
    if 'ESI' in recipes_df.columns:
        esi_min = recipes_df['ESI'].min()
        esi_max = recipes_df['ESI'].max()
        
        if esi_max > esi_min:
            recipes_df['ESI_normalized'] = recipes_df['ESI'].apply(
                lambda x: normalize_score(x, esi_min, esi_max)
            )
            recipes_df['ESI_final'] = 100 - recipes_df['ESI_normalized']
        else:
            recipes_df['ESI_final'] = 50.0
    
    # HSI és PPI normalizálása (ha szükséges)
    for col in ['HSI', 'PPI']:
        if col in recipes_df.columns:
            col_min = recipes_df[col].min()
            col_max = recipes_df[col].max()
            
            if col_max > col_min and col_max > 100:
                recipes_df[f'{col}_normalized'] = recipes_df[col].apply(
                    lambda x: normalize_score(x, col_min, col_max)
                )
            else:
                recipes_df[f'{col}_normalized'] = recipes_df[col]
    
    # Kompozit pontszám számítása
    if all(col in recipes_df.columns for col in ['ESI_final', 'HSI', 'PPI']):
        recipes_df['composite_score'] = recipes_df.apply(
            lambda row: calculate_composite_score(
                row['ESI_final'], row['HSI'], row['PPI']
            ), axis=1
        )
    
    # Hiányzó értékek pótlása
    recipes_df = recipes_df.fillna({
        'name': 'Unknown Recipe',
        'description': '',
        'ingredients_text': '',
        'categories_text': '',
        'ESI_final': 50.0,
        'HSI': 70.0,
        'PPI': 60.0,
        'composite_score': 60.0
    })
    
    # Duplikátumok eltávolítása
    initial_count = len(recipes_df)
    recipes_df = recipes_df.drop_duplicates(subset=['name'], keep='first')
    removed_duplicates = initial_count - len(recipes_df)
    
    if removed_duplicates > 0:
        logger.info(f"Removed {removed_duplicates} duplicate recipes")

def initialize_system():
    """Rendszer inicializálása"""
    global recommendation_engine
    
    try:
        logger.info("🌱 GreenRec system initializing...")
        
        # Adatok betöltése
        if not load_and_process_data():
            return False
        
        # Recommendation engine létrehozása
        recommendation_engine = GreenRecEngine(recipes_df)
        
        logger.info("✅ GreenRec system ready")
        return True
        
    except Exception as e:
        logger.error(f"
