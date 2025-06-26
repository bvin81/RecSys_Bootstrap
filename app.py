# app.py
"""
GreenRec Flask Alkalmazás
========================
Moduláris Flask alkalmazás - csak routes és request handling.
Üzleti logika külön modulokban (core/, services/).
"""

import os
import logging
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

# Modulok importálása
from config import current_config
from core.recommendation import recommendation_engine
from core.data_manager import data_manager
from services.rating_service import rating_service
from services.analytics_service import analytics_service

# Logging beállítása
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask alkalmazás létrehozása
app = Flask(__name__)
app.config.from_object(current_config)

# Session konfiguráció
app.permanent_session_lifetime = 24 * 60 * 60  # 24 óra

@app.before_first_request
def initialize_application():
    """Alkalmazás inicializálása az első kérés előtt"""
    try:
        # Adatok betöltése
        data_manager.load_recipe_data()
        
        # Recommendation engine inicializálása
        recommendation_engine.initialize()
        
        logger.info("✅ GreenRec alkalmazás sikeresen inicializálva")
        
    except Exception as e:
        logger.error(f"❌ Alkalmazás inicializálási hiba: {e}")

@app.route('/')
def index():
    """
    Főoldal - receptajánlások megjelenítése
    """
    try:
        # Felhasználói session inicializálása
        user_id, user_group, current_round = rating_service.initialize_user_session()
        
        # Korábbi értékelések lekérése
        user_ratings = rating_service.get_user_ratings()
        
        # Ajánlások generálása (A/B/C teszt alapján)
        recommendations = recommendation_engine.get_recommendations(
            user_group=user_group,
            user_ratings=user_ratings,
            round_number=current_round,
            n=current_config.RECOMMENDATIONS_PER_ROUND
        )
        
        # Jelenlegi kör értékeléseinek száma
        current_round_ratings = rating_service.get_user_ratings(current_round)
        rated_count = len(current_round_ratings)
        
        # Következő kör ellenőrzése
        can_proceed, _, required_ratings = rating_service.can_proceed_to_next_round(current_round)
        
        return render_template('index.html',
            recipes=recommendations.to_dict('records'),
            user_group=user_group,
            current_round=current_round,
            max_rounds=current_config.MAX_LEARNING_ROUNDS,
            rated_count=rated_count,
            required_ratings=required_ratings,
            can_proceed=can_proceed,
            hide_scores=(user_group == 'A' and current_config.HIDE_SCORES_FOR_GROUP_A),
            show_images=current_config.SHOW_IMAGES,
            enable_search=current_config.ENABLE_SEARCH
        )
        
    except Exception as e:
        logger.error(f"Főoldal hiba: {e}")
        return render_template('error.html', error_message="Hiba a receptek betöltésében"), 500

@app.route('/rate', methods=['POST'])
def rate_recipe():
    """
    Recept értékelése AJAX kérés kezelése
    """
    try:
        data = request.get_json()
        
        recipe_id = data.get('recipe_id')
        rating = data.get('rating')
        round_number = data.get('round_number')
        
        # Input validáció
        if not all([recipe_id, rating, round_number]):
            return jsonify({
                'success': False, 
                'error': 'Hiányzó adatok'
            }), 400
        
        # Értékelés mentése
        success = rating_service.save_rating(
            recipe_id=int(recipe_id),
            rating=int(rating),
            round_number=int(round_number)
        )
        
        if success:
            # Frissített statisztikák
            current_round_ratings = rating_service.get_user_ratings(round_number)
            rated_count = len(current_round_ratings)
            can_proceed, _, required = rating_service.can_proceed_to_next_round(round_number)
            
            return jsonify({
                'success': True,
                'rated_count': rated_count,
                'can_proceed': can_proceed,
