# services/recipe_service.py - Recept Szolgáltatás Blueprint
"""
Recipe Service Blueprint
========================
Recept ajánlások, értékelések, keresés és session management.
Új funkcionalitás integrálása a meglévő user_study modullal.
"""

from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
import logging
from datetime import datetime
import random

# Import modulok
from config import Config
from models.recommendation_engine import RecommendationEngine
from utils.metrics import calculate_precision_recall_f1
from utils.helpers import get_user_group, initialize_user_session

# Blueprint létrehozása
recipe_bp = Blueprint('recipes', __name__)

# Logger beállítása
logger = logging.getLogger(__name__)

# Globális recommendation engine instance
recommendation_engine = None

def init_recommendation_engine():
    """Recommendation engine inicializálása"""
    global recommendation_engine
    if recommendation_engine is None:
        recommendation_engine = RecommendationEngine()
        logger.info("✅ Recommendation engine initialized")
    return recommendation_engine

@recipe_bp.before_app_first_request
def setup():
    """Blueprint setup"""
    init_recommendation_engine()

# ============================================
# FŐOLDAL ÉS ENHANCED STUDY ROUTE-OK
# ============================================

@recipe_bp.route('/enhanced_study')
def enhanced_study():
    """✅ Új enhanced study oldal (3 kör, képek, rejtett pontszámok)"""
    user_id, user_group, learning_round = initialize_user_session()
    
    # Recommendation engine inicializálása
    engine = init_recommendation_engine()
    
    # Ajánlások generálása
    try:
        recommendations = engine.get_personalized_recommendations(
            user_id=user_id,
            user_group=user_group, 
            learning_round=learning_round,
            previous_ratings=session.get('ratings', {}),
            n=Config.RECOMMENDATION_COUNT
        )
        
        # DataFrame -> dict konverzió
        if hasattr(recommendations, 'to_dict'):
            recommendations = recommendations.to_dict('records')
        elif not isinstance(recommendations, list):
            recommendations = []
            
    except Exception as e:
        logger.error(f"❌ Recommendation error: {e}")
        recommendations = []
    
    # Template renderelése
    return render_template('enhanced_study.html',
                         recipes=recommendations,
                         user_group=user_group,
                         learning_round=learning_round,
                         max_rounds=Config.MAX_LEARNING_ROUNDS,
                         rated_count=len(session.get('ratings', {})),
                         recommendation_count=Config.RECOMMENDATION_COUNT)

@recipe_bp.route('/search', methods=['GET', 'POST'])
def search_recipes():
    """🔍 Recept keresés összetevők alapján"""
    user_id, user_group, learning_round = initialize_user_session()
    
    results = []
    query = ""
    
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            engine = init_recommendation_engine()
            try:
                results = engine.search_by_ingredients(query, limit=Config.SEARCH_MAX_RESULTS)
                logger.info(f"🔍 Search: '{query}' -> {len(results)} results")
            except Exception as e:
                logger.error(f"❌ Search error: {e}")
                results = []
    
    return render_template('search.html',
                         query=query,
                         results=results,
                         user_group=user_group,
                         learning_round=learning_round)

# ============================================
# API ENDPOINT-OK
# ============================================

@recipe_bp.route('/recommendations', methods=['GET'])
def get_recommendations_api():
    """API endpoint ajánlások lekérésére"""
    try:
        user_id, user_group, learning_round = initialize_user_session()
        engine = init_recommendation_engine()
        
        # Query paraméterek
        count = int(request.args.get('count', Config.RECOMMENDATION_COUNT))
        search_query = request.args.get('search', '')
        
        # Ajánlások generálása
        if search_query:
            recommendations = engine.search_by_ingredients(search_query, limit=count)
        else:
            recommendations = engine.get_personalized_recommendations(
                user_id=user_id,
                user_group=user_group,
                learning_round=learning
