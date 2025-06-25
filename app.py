# app.py - GreenRec Moduláris Verzió
"""
GreenRec - Fenntartható Receptajánló Rendszer
=============================================

Moduláris Flask alkalmazás a GreenRec ajánlórendszerhez.
Használja a szeparált services, models, utils modulokat.
"""

from flask import Flask, request, jsonify, session, render_template
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Import our modular components
from config import get_config, get_flask_config, validate_configuration
from models.recommendation import GreenRecEngine
from services.data_service import DataService
from services.rating_service import RatingService
from services.analytics_service import AnalyticsService
from utils.helpers import (
    get_or_create_user_session, jsonify_response, 
    is_ajax_request, timer
)
from utils.validation import validate_api_request_comprehensive
from utils.metrics import calculate_comprehensive_metrics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Load configuration
config = get_config()
app.config.update(get_flask_config())

# Validate configuration
config_errors = validate_configuration()
if config_errors:
    logger.warning(f"Configuration issues: {config_errors}")

# Initialize services
data_service = DataService()
rating_service = RatingService()
analytics_service = AnalyticsService()
recommendation_engine: Optional[GreenRecEngine] = None

def initialize_system():
    """Rendszer inicializálása"""
    global recommendation_engine
    
    try:
        logger.info("🌱 GreenRec system initialization starting...")
        
        # Initialize data service
        success = data_service.initialize_system()
        if not success:
            logger.error("❌ Data service initialization failed")
            return False
        
        # Get the recommendation engine
        recommendation_engine = data_service.get_recommendation_engine()
        if not recommendation_engine:
            logger.error("❌ Recommendation engine not available")
            return False
        
        logger.info("✅ GreenRec system initialized successfully")
        return True
        
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
# Error Handlers
# =====================================

@app.errorhandler(404)
def not_found(error):
    if is_ajax_request():
        return jsonify_response(
            data=None,
            status_code=404,
            message="Endpoint not found"
        )
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    if is_ajax_request():
        return jsonify_response(
            data=None,
            status_code=500,
            message="Internal server error"
        )
    return render_template('500.html'), 500

# =====================================
# Main Routes
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
            user_preferences=rating_service.get_user_preferences(user_session['user_id']),
            n=6
        )
        
        # Track analytics
        analytics_service.track_behavior(
            session_id=user_session['user_id'],
            action='page_view',
            context={'page': 'index', 'recommendations_count': len(recommendations)}
        )
        
        # Render template with recommendations
        return render_template('index.html', 
                             recommendations=recommendations,
                             user_session=user_session)
        
    except Exception as e:
        logger.error(f"Index page error: {e}")
        return render_template('error.html', 
                             error_message="Nem sikerült betölteni az ajánlásokat")

@app.route('/search')
def search():
    """Keresési oldal"""
    try:
        ensure_initialized()
        
        query = request.args.get('q', '').strip()
        results = []
        
        if query:
            # Validate search query
            validation_report = validate_api_request_comprehensive(
                endpoint='search',
                payload={'query': query},
                headers=dict(request.headers)
            )
            
            if validation_report.overall_valid:
                results = recommendation_engine.search_recipes(query, n=20)
                
                # Track search
                analytics_service.track_behavior(
                    session_id=session.get('user_id', 'anonymous'),
                    action='search',
                    context={'query': query, 'results_count': len(results)}
                )
            else:
                logger.warning(f"Invalid search query: {query}")
                results = []
        
        return render_template('search.html', 
                             query=query, 
                             results=results)
        
    except Exception as e:
        logger.error(f"Search page error: {e}")
        return render_template('error.html', 
                             error_message="Keresési hiba történt")

@app.route('/analytics')
def analytics_dashboard():
    """Analitika dashboard"""
    try:
        ensure_initialized()
        
        # Get dashboard data
        dashboard_data = analytics_service.get_dashboard_data()
        
        return render_template('analytics.html', 
                             dashboard_data=dashboard_data)
        
    except Exception as e:
        logger.error(f"Analytics dashboard error: {e}")
        return render_template('error.html', 
                             error_message="Analitika betöltési hiba")

@app.route('/about')
def about():
    """Rólunk oldal"""
    return render_template('about.html')

# =====================================
# API Routes
# =====================================

@app.route('/api/rate', methods=['POST'])
@timer
def api_rate_recipe():
    """Recept értékelése API"""
    try:
        ensure_initialized()
        
        # Validate request
        validation_report = validate_api_request_comprehensive(
            endpoint='rate',
            payload=request.json or {},
            headers=dict(request.headers)
        )
        
        if not validation_report.overall_valid:
            return jsonify_response(
                data={'validation_errors': validation_report.to_dict()},
                status_code=400,
                message="Validation failed"
            )
        
        # Get validated data
        recipe_id = request.json.get('recipe_id')
        rating = int(request.json.get('rating'))
        
        # Get user session
        user_session = get_or_create_user_session()
        
        # Save rating
        result = rating_service.save_rating(
            user_id=user_session['user_id'],
            recipe_id=recipe_id,
            rating=rating,
            learning_round=user_session.get('learning_round', 1)
        )
        
        # Track analytics
        analytics_service.track_behavior(
            session_id=user_session['user_id'],
            action='rate_recipe',
            context={
                'recipe_id': recipe_id,
                'rating': rating,
                'learning_round': user_session.get('learning_round', 1)
            }
        )
        
        # Check if round is complete
        ratings_count = len(rating_service.get_user_ratings(user_session['user_id']))
        round_complete = ratings_count >= 6
        
        return jsonify_response(
            data={
                'rating_saved': True,
                'ratings_count': ratings_count,
                'round_complete': round_complete,
                'user_metrics': result.get('user_metrics', {})
            },
            status_code=200,
            message="Rating saved successfully"
        )
        
    except Exception as e:
        logger.error(f"Rating API error: {e}")
        return jsonify_response(
            data=None,
            status_code=500,
            message="Rating save failed"
        )

@app.route('/api/search', methods=['GET'])
@timer
def api_search():
    """Keresés API"""
    try:
        ensure_initialized()
        
        query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 20)), 50)
        
        # Validate request
        validation_report = validate_api_request_comprehensive(
            endpoint='search',
            payload={'query': query, 'limit': limit},
            headers=dict(request.headers)
        )
        
        if not validation_report.overall_valid:
            return jsonify_response(
                data={'validation_errors': validation_report.to_dict()},
                status_code=400,
                message="Invalid search request"
            )
        
        # Perform search
        results = recommendation_engine.search_recipes(query, n=limit)
        
        # Track search
        analytics_service.track_behavior(
            session_id=session.get('user_id', 'anonymous'),
            action='api_search',
            context={'query': query, 'results_count': len(results)}
        )
        
        return jsonify_response(
            data={'recipes': results, 'total': len(results)},
            status_code=200,
            message=f"Found {len(results)} recipes"
        )
        
    except Exception as e:
        logger.error(f"Search API error: {e}")
        return jsonify_response(
            data=None,
            status_code=500,
            message="Search failed"
        )

@app.route('/api/recommend', methods=['POST'])
@timer
def api_get_recommendations():
    """Személyre szabott ajánlások API"""
    try:
        ensure_initialized()
        
        # Validate request
        validation_report = validate_api_request_comprehensive(
            endpoint='recommend',
            payload=request.json or {},
            headers=dict(request.headers)
        )
        
        if not validation_report.overall_valid:
            return jsonify_response(
                data={'validation_errors': validation_report.to_dict()},
                status_code=400,
                message="Invalid recommendation request"
            )
        
        # Get user session
        user_session = get_or_create_user_session()
        
        # Get user preferences
        user_preferences = rating_service.get_user_preferences(user_session['user_id'])
        
        # Get recommendations
        count = request.json.get('count', 6)
        recommendations = recommendation_engine.get_personalized_recommendations(
            user_id=user_session['user_id'],
            user_preferences=user_preferences,
            n=count
        )
        
        # Track analytics
        analytics_service.track_behavior(
            session_id=user_session['user_id'],
            action='get_recommendations',
            context={
                'count': len(recommendations),
                'user_group': user_session['user_group'],
                'learning_round': user_session.get('learning_round', 1)
            }
        )
        
        return jsonify_response(
            data={
                'recommendations': recommendations,
                'user_preferences': user_preferences.__dict__ if user_preferences else {},
                'user_session': user_session
            },
            status_code=200,
            message="Recommendations generated"
        )
        
    except Exception as e:
        logger.error(f"Recommendations API error: {e}")
        return jsonify_response(
            data=None,
            status_code=500,
            message="Recommendations generation failed"
        )

@app.route('/api/next-round', methods=['POST'])
@timer
def api_next_round():
    """Következő tanulási kör indítása"""
    try:
        ensure_initialized()
        
        # Get user session
        user_session = get_or_create_user_session()
        
        # Advance to next round
        new_round = rating_service.advance_user_round(user_session['user_id'])
        
        # Update session
        session['learning_round'] = new_round
        
        # Track analytics
        analytics_service.track_behavior(
            session_id=user_session['user_id'],
            action='advance_round',
            context={
                'new_round': new_round,
                'user_group': user_session['user_group']
            }
        )
        
        return jsonify_response(
            data={'new_round': new_round},
            status_code=200,
            message=f"Advanced to round {new_round}"
        )
        
    except Exception as e:
        logger.error(f"Next round API error: {e}")
        return jsonify_response(
            data=None,
            status_code=500,
            message="Round advancement failed"
        )

# =====================================
# Analytics API Routes
# =====================================

@app.route('/api/dashboard-data')
@timer
def api_dashboard_data():
    """Dashboard adatok API"""
    try:
        ensure_initialized()
        
        dashboard_data = analytics_service.get_dashboard_data()
        
        return jsonify_response(
            data=dashboard_data,
            status_code=200,
            message="Dashboard data retrieved"
        )
        
    except Exception as e:
        logger.error(f"Dashboard data API error: {e}")
        return jsonify_response(
            data={},
            status_code=500,
            message="Dashboard data retrieval failed"
        )

@app.route('/api/learning-curves')
@timer
def api_learning_curves():
    """Tanulási görbék adatok API"""
    try:
        ensure_initialized()
        
        curves_data = analytics_service.generate_learning_curves()
        
        return jsonify_response(
            data=curves_data,
            status_code=200,
            message="Learning curves data retrieved"
        )
        
    except Exception as e:
        logger.error(f"Learning curves API error: {e}")
        return jsonify_response(
            data={},
            status_code=500,
            message="Learning curves retrieval failed"
        )

@app.route('/api/group-comparison')
@timer
def api_group_comparison():
    """A/B/C csoportok összehasonlítása API"""
    try:
        ensure_initialized()
        
        comparison = analytics_service.compare_groups()
        
        return jsonify_response(
            data=comparison.__dict__ if comparison else {},
            status_code=200,
            message="Group comparison data retrieved"
        )
        
    except Exception as e:
        logger.error(f"Group comparison API error: {e}")
        return jsonify_response(
            data={},
            status_code=500,
            message="Group comparison failed"
        )

# =====================================
# System Status Routes
# =====================================

@app.route('/status')
def system_status():
    """Rendszer állapot ellenőrzése"""
    try:
        ensure_initialized()
        
        status_info = {
            'system_ready': recommendation_engine is not None,
            'recipes_loaded': data_service.get_recipe_count(),
            'config_valid': len(validate_configuration()) == 0,
            'services_initialized': {
                'data_service': data_service.is_initialized(),
                'rating_service': True,
                'analytics_service': True
            },
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify_response(
            data=status_info,
            status_code=200,
            message="System status retrieved"
        )
        
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return jsonify_response(
            data={'error': str(e)},
            status_code=500,
            message="Status check failed"
        )

@app.route('/health')
def health_check():
    """Egyszerű health check"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

# =====================================
# Application Startup
# =====================================

if __name__ == '__main__':
    try:
        # Initialize system on startup
        logger.info("🚀 Starting GreenRec application...")
        
        if initialize_system():
            logger.info("✅ System ready - starting Flask server")
            
            # Development server settings
            debug_mode = config.environment == 'development'
            
            app.run(
                host='0.0.0.0',
                port=5000,
                debug=debug_mode,
                threaded=True
            )
        else:
            logger.error("❌ System initialization failed - cannot start server")
            
    except KeyboardInterrupt:
        logger.info("👋 Application shutdown requested")
    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}")
        raise
