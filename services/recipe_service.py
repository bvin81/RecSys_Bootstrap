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
                learning_round=learning_round,
                previous_ratings=session.get('ratings', {}),
                n=count
            )
        
        # Response formázás
        if hasattr(recommendations, 'to_dict'):
            recommendations = recommendations.to_dict('records')
        elif not isinstance(recommendations, list):
            recommendations = []
        
        return jsonify({
            'success': True,
            'recommendations': recommendations,
            'user_group': user_group,
            'learning_round': learning_round,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ Recommendations API error: {e}")
        return jsonify({'error': 'Ajánlások generálása sikertelen'}), 500

@recipe_bp.route('/rate', methods=['POST'])
def rate_recipe():
    """Recept értékelése API"""
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        rating = int(data.get('rating', 0))
        
        # Validáció
        if not recipe_id or not (1 <= rating <= 5):
            return jsonify({'error': 'Érvénytelen adatok'}), 400
        
        # Session inicializálása
        user_id, user_group, learning_round = initialize_user_session()
        
        # Értékelés mentése session-be
        if 'ratings' not in session:
            session['ratings'] = {}
        
        session['ratings'][recipe_id] = rating
        session.modified = True
        
        logger.info(f"⭐ Rating: {user_id} rated {recipe_id} = {rating} stars (Round {learning_round})")
        
        return jsonify({
            'success': True,
            'rated_count': len(session['ratings']),
            'total_needed': Config.RECOMMENDATION_COUNT,
            'user_group': user_group,
            'learning_round': learning_round
        })
        
    except Exception as e:
        logger.error(f"❌ Rating error: {e}")
        return jsonify({'error': 'Értékelés mentése sikertelen'}), 500

@recipe_bp.route('/next_round', methods=['POST'])
def next_round():
    """Következő tanulási kör indítása"""
    try:
        user_id, user_group, learning_round = initialize_user_session()
        
        # Aktuális kör értékeléseinek ellenőrzése
        current_ratings = session.get('ratings', {})
        
        if len(current_ratings) < Config.RECOMMENDATION_COUNT:
            return jsonify({
                'success': False,
                'message': f'Kérjük, értékelje mind a {Config.RECOMMENDATION_COUNT} receptet!'
            }), 400
        
        # Metrikák számítása az aktuális körhöz
        engine = init_recommendation_engine()
        try:
            recommendations = engine.get_personalized_recommendations(
                user_id=user_id,
                user_group=user_group,
                learning_round=learning_round,
                previous_ratings=current_ratings,
                n=Config.RECOMMENDATION_COUNT
            )
            
            metrics = calculate_precision_recall_f1(
                recommendations=recommendations,
                ratings=current_ratings,
                user_group=user_group,
                learning_round=learning_round
            )
            
        except Exception as e:
            logger.error(f"❌ Metrics calculation error: {e}")
            metrics = {'precision_at_5': 0, 'recall_at_5': 0, 'f1_at_5': 0}
        
        # ✅ Maximum kör ellenőrzése (3 kör)
        if learning_round >= Config.MAX_LEARNING_ROUNDS:
            return jsonify({
                'success': False,
                'message': f'Elérte a maximum tanulási körök számát ({Config.MAX_LEARNING_ROUNDS} kör)',
                'redirect': '/analytics/dashboard',
                'final_metrics': metrics
            })
        
        # Következő kör inicializálása
        session['learning_round'] = learning_round + 1
        session['all_ratings'] = session.get('all_ratings', {})
        session['all_ratings'].update(current_ratings)  # Minden értékelés mentése
        session['ratings'] = {}  # Új kör, új értékelések
        session.modified = True
        
        logger.info(f"🔄 {user_id} moved to round {session['learning_round']}")
        
        return jsonify({
            'success': True,
            'new_round': session['learning_round'],
            'max_rounds': Config.MAX_LEARNING_ROUNDS,
            'previous_metrics': metrics,
            'message': f'Sikeresen átlépett a {session["learning_round"]}. körbe!'
        })
            
    except Exception as e:
        logger.error(f"❌ Next round error: {e}")
        return jsonify({'error': 'Szerver hiba a következő kör indításakor'}), 500

@recipe_bp.route('/user_session', methods=['GET'])
def get_user_session():
    """User session információk API"""
    try:
        user_id, user_group, learning_round = initialize_user_session()
        
        return jsonify({
            'user_id': user_id,
            'user_group': user_group,
            'learning_round': learning_round,
            'max_rounds': Config.MAX_LEARNING_ROUNDS,
            'current_ratings': session.get('ratings', {}),
            'all_ratings': session.get('all_ratings', {}),
            'rated_count': len(session.get('ratings', {})),
            'total_needed': Config.RECOMMENDATION_COUNT,
            'algorithm': Config.GROUP_ALGORITHMS.get(user_group, 'unknown'),
            'session_start': session.get('start_time'),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ User session API error: {e}")
        return jsonify({'error': 'Session információ lekérése sikertelen'}), 500

# ============================================
# HELPER FUNKCIÓK
# ============================================

@recipe_bp.route('/reset_session', methods=['POST'])
def reset_user_session():
    """Session reset (debugging célokra)"""
    try:
        old_user_id = session.get('user_id', 'unknown')
        session.clear()
        
        # Új session inicializálása
        user_id, user_group, learning_round = initialize_user_session()
        
        logger.info(f"🔄 Session reset: {old_user_id} -> {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Session reset successful',
            'new_user_id': user_id,
            'new_user_group': user_group,
            'new_learning_round': learning_round
        })
        
    except Exception as e:
        logger.error(f"❌ Session reset error: {e}")
        return jsonify({'error': 'Session reset sikertelen'}), 500

@recipe_bp.route('/status')
def service_status():
    """Recipe service status"""
    try:
        engine = init_recommendation_engine()
        
        status_info = {
            'service': 'Recipe Service',
            'status': 'running',
            'recommendation_engine': 'initialized' if engine else 'not_initialized',
            'config': {
                'max_learning_rounds': Config.MAX_LEARNING_ROUNDS,
                'recommendation_count': Config.RECOMMENDATION_COUNT,
                'relevance_threshold': Config.RELEVANCE_THRESHOLD,
                'group_algorithms': Config.GROUP_ALGORITHMS
            },
            'data_status': {
                'recipes_loaded': engine.is_initialized() if engine else False,
                'tfidf_ready': engine.tfidf_ready() if engine else False,
                'recipe_count': engine.get_recipe_count() if engine else 0
            },
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(status_info)
        
    except Exception as e:
        logger.error(f"❌ Status error: {e}")
        return jsonify({
            'service': 'Recipe Service',
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ============================================
# BLUEPRINT HELPER FUNCTIONS
# ============================================

def get_current_user_info():
    """Aktuális felhasználó információk lekérése"""
    return {
        'user_id': session.get('user_id'),
        'user_group': session.get('user_group'),
        'learning_round': session.get('learning_round', 1),
        'ratings': session.get('ratings', {}),
        'all_ratings': session.get('all_ratings', {})
    }

# Blueprint inicializálás
@recipe_bp.record
def record_config(setup_state):
    """Blueprint konfiguráció rögzítése"""
    config = setup_state.app.config
    recipe_bp.config = config
    logger.info("✅ Recipe service blueprint configured")

# Blueprint teardown
@recipe_bp.teardown_app_request
def cleanup(error):
    """Request cleanup"""
    if error:
        logger.error(f"Request error in recipe service: {error}")

# Export
__all__ = ['recipe_bp']
