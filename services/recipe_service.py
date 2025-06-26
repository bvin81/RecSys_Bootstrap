# services/recipe_service.py - Recept Szolgáltatás Blueprint
"""
Recipe Service Blueprint
========================
Recept ajánlások, értékelések, keresés és session management.
Moduláris implementáció a GreenRec A/B/C teszt rendszerhez.
"""

from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
import logging
from datetime import datetime
import random
import json
from pathlib import Path

# Import modulok
from config import Config
from models.recommendation_engine import RecommendationEngine
from utils.metrics import calculate_precision_recall_f1
from utils.helpers import get_user_group, initialize_user_session
from utils.data_processing import normalize_esi_scores, calculate_composite_scores

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
        
        logger.info(f"✅ Generated {len(recommendations)} recommendations for user {user_id} (Group {user_group}, Round {learning_round})")
        
    except Exception as e:
        logger.error(f"❌ Recommendation generation failed: {e}")
        recommendations = _get_fallback_recommendations()
    
    # Template adatok készítése
    template_data = {
        'user_id': user_id,
        'user_group': user_group,
        'learning_round': learning_round,
        'recommendations': recommendations,
        'show_scores': user_group in ['B', 'C'],  # A csoport: rejtett pontszámok
        'show_search': True,  # Keresési funkció minden csoportnak
        'total_rounds': Config.LEARNING_ROUNDS,
        'is_final_round': learning_round >= Config.LEARNING_ROUNDS,
        'study_config': {
            'rounds_total': Config.LEARNING_ROUNDS,
            'recommendations_per_round': Config.RECOMMENDATION_COUNT,
            'rating_scale': Config.RATING_SCALE
        }
    }
    
    return render_template('enhanced_study.html', **template_data)

@recipe_bp.route('/rate_recipe', methods=['POST'])
def rate_recipe():
    """✅ Recept értékelése (AJAX endpoint)"""
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        rating = int(data.get('rating'))
        user_id = session.get('user_id')
        user_group = session.get('user_group')
        learning_round = session.get('learning_round', 1)
        
        # Validálás
        if not all([recipe_id, rating, user_id]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        if rating not in Config.RATING_SCALE:
            return jsonify({'error': f'Invalid rating. Must be in {Config.RATING_SCALE}'}), 400
        
        # Rating mentése session-be
        if 'ratings' not in session:
            session['ratings'] = {}
        
        session['ratings'][recipe_id] = {
            'rating': rating,
            'timestamp': datetime.now().isoformat(),
            'round': learning_round
        }
        
        # Adatbázisba mentés (opcionális)
        try:
            _save_rating_to_db(user_id, recipe_id, rating, user_group, learning_round)
        except Exception as e:
            logger.warning(f"⚠️ DB save failed: {e}")
        
        session.permanent = True
        
        logger.info(f"✅ Rating saved: User {user_id}, Recipe {recipe_id}, Rating {rating}")
        
        return jsonify({
            'success': True,
            'message': 'Rating saved successfully',
            'rating': rating,
            'user_group': user_group
        })
        
    except Exception as e:
        logger.error(f"❌ Rating error: {e}")
        return jsonify({'error': 'Rating failed'}), 500

@recipe_bp.route('/next_round', methods=['POST'])
def next_round():
    """✅ Következő tanulási kör"""
    try:
        current_round = session.get('learning_round', 1)
        
        if current_round >= Config.LEARNING_ROUNDS:
            # Tanulmány befejezése
            return jsonify({
                'success': True,
                'finished': True,
                'redirect': url_for('recipes.study_complete')
            })
        
        # Következő kör
        session['learning_round'] = current_round + 1
        session.permanent = True
        
        logger.info(f"✅ User {session.get('user_id')} advanced to round {current_round + 1}")
        
        return jsonify({
            'success': True,
            'finished': False,
            'next_round': current_round + 1,
            'redirect': url_for('recipes.enhanced_study')
        })
        
    except Exception as e:
        logger.error(f"❌ Next round error: {e}")
        return jsonify({'error': 'Failed to advance round'}), 500

@recipe_bp.route('/study_complete')
def study_complete():
    """✅ Tanulmány befejezése oldal"""
    user_id = session.get('user_id')
    user_group = session.get('user_group')
    ratings = session.get('ratings', {})
    
    # Összefoglaló statisztikák
    total_ratings = len(ratings)
    avg_rating = sum(r['rating'] for r in ratings.values()) / total_ratings if total_ratings > 0 else 0
    
    # Metrikák számítása
    try:
        metrics = _calculate_final_metrics(user_id, user_group, ratings)
    except Exception as e:
        logger.error(f"❌ Metrics calculation failed: {e}")
        metrics = {}
    
    return render_template('study_complete.html', 
                         user_id=user_id,
                         user_group=user_group,
                         total_ratings=total_ratings,
                         avg_rating=round(avg_rating, 2),
                         metrics=metrics)

# ============================================
# KERESÉSI FUNKCIÓK
# ============================================

@recipe_bp.route('/search')
def search_recipes():
    """✅ Recept keresés (TF-IDF alapú)"""
    query = request.args.get('q', '').strip()
    
    if not query:
        return render_template('search_results.html', 
                             query='', 
                             results=[],
                             message='Kérem adjon meg keresési kifejezést')
    
    try:
        engine = init_recommendation_engine()
        results = engine.search_recipes(query, n=10)
        
        # User group specifikus megjelenítés
        user_group = session.get('user_group', 'A')
        show_scores = user_group in ['B', 'C']
        
        for result in results:
            result['show_scores'] = show_scores
        
        logger.info(f"✅ Search '{query}' returned {len(results)} results")
        
        return render_template('search_results.html', 
                             query=query, 
                             results=results,
                             show_scores=show_scores,
                             user_group=user_group)
        
    except Exception as e:
        logger.error(f"❌ Search error: {e}")
        return render_template('search_results.html', 
                             query=query, 
                             results=[],
                             message='Hiba történt a keresés során')

# ============================================
# API ENDPOINTS
# ============================================

@recipe_bp.route('/api/recommendations')
def api_recommendations():
    """✅ API endpoint ajánlásokhoz"""
    user_id = request.args.get('user_id', session.get('user_id'))
    user_group = request.args.get('user_group', session.get('user_group'))
    n = int(request.args.get('n', Config.RECOMMENDATION_COUNT))
    
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    
    try:
        engine = init_recommendation_engine()
        recommendations = engine.get_personalized_recommendations(
            user_id=user_id,
            user_group=user_group,
            previous_ratings=session.get('ratings', {}),
            n=n
        )
        
        return jsonify({
            'success': True,
            'recommendations': recommendations,
            'user_group': user_group,
            'count': len(recommendations)
        })
        
    except Exception as e:
        logger.error(f"❌ API recommendations error: {e}")
        return jsonify({'error': 'Failed to generate recommendations'}), 500

@recipe_bp.route('/api/user_stats')
def api_user_stats():
    """✅ Felhasználó statisztikák API"""
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'No active session'}), 400
    
    ratings = session.get('ratings', {})
    
    stats = {
        'user_id': user_id,
        'user_group': session.get('user_group'),
        'learning_round': session.get('learning_round', 1),
        'total_ratings': len(ratings),
        'ratings_by_round': _group_ratings_by_round(ratings),
        'avg_rating': sum(r['rating'] for r in ratings.values()) / len(ratings) if ratings else 0,
        'session_started': session.get('session_started'),
        'study_completed': session.get('learning_round', 1) > Config.LEARNING_ROUNDS
    }
    
    return jsonify(stats)

# ============================================
# SEGÉDFUNKCIÓK
# ============================================

def _get_fallback_recommendations():
    """Fallback recommendations ha a ML engine nem működik"""
    fallback_recipes = [
        {
            'id': 'fallback_1',
            'name': 'Magyar Gulyás',
            'HSI': 75,
            'ESI': 40,  # Magas környezeti hatás
            'PPI': 85,
            'composite_score': 65,
            'ingredients': 'marhahús, hagyma, paprika, burgonya',
            'category': 'Hagyományos Magyar',
            'images': ''
        },
        {
            'id': 'fallback_2', 
            'name': 'Vegán Buddha Bowl',
            'HSI': 90,
            'ESI': 95,  # Alacsony környezeti hatás
            'PPI': 80,
            'composite_score': 90,
            'ingredients': 'quinoa, avokádó, spenót, csicseriborsó',
            'category': 'Vegán',
            'images': ''
        }
    ]
    
    return fallback_recipes

def _save_rating_to_db(user_id, recipe_id, rating, user_group, learning_round):
    """Rating mentése adatbázisba"""
    # TODO: Implementálni PostgreSQL mentést
    pass

def _calculate_final_metrics(user_id, user_group, ratings):
    """Végső metrikák számítása"""
    # TODO: Implementálni Precision@5, Recall@5, F1, Diversity, Novelty számítást
    return {
        'precision_at_5': 0.75,
        'recall_at_5': 0.65,
        'f1_score': 0.70,
        'diversity': 0.82,
        'novelty': 0.68
    }

def _group_ratings_by_round(ratings):
    """Értékelések csoportosítása tanulási körök szerint"""
    by_round = {}
    for rating_data in ratings.values():
        round_num = rating_data.get('round', 1)
        if round_num not in by_round:
            by_round[round_num] = []
        by_round[round_num].append(rating_data['rating'])
    
    return by_round

# ============================================
# BLUEPRINT REGISZTRÁCIÓ
# ============================================

def register_blueprint(app):
    """Blueprint regisztrálása az alkalmazáshoz"""
    app.register_blueprint(recipe_bp, url_prefix='/recipes')
    logger.info("✅ Recipe service blueprint registered")
