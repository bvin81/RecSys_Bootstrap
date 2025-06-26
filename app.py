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
                'required_ratings': required
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Értékelés mentése sikertelen'
            }), 500
            
    except Exception as e:
        logger.error(f"Értékelési hiba: {e}")
        return jsonify({
            'success': False,
            'error': 'Szerver hiba'
        }), 500

@app.route('/next_round', methods=['POST'])
def next_round():
    """
    Következő körre lépés
    """
    try:
        # Következő körre lépés
        success, new_round = rating_service.advance_to_next_round()
        
        if success:
            return jsonify({
                'success': True,
                'new_round': new_round,
                'redirect_url': url_for('index') if new_round <= current_config.MAX_LEARNING_ROUNDS else url_for('results')
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Nem lehet a következő körre lépni'
            }), 400
            
    except Exception as e:
        logger.error(f"Következő kör hiba: {e}")
        return jsonify({
            'success': False,
            'error': 'Szerver hiba'
        }), 500

@app.route('/search')
def search():
    """
    Keresés összetevők alapján
    """
    try:
        query = request.args.get('q', '').strip()
        
        if len(query) < 2:
            return redirect(url_for('index'))
        
        # Keresés végrehajtása
        search_results = recommendation_engine.search_recipes(
            query=query,
            max_results=current_config.MAX_SEARCH_RESULTS
        )
        
        # Felhasználói adatok
        user_id, user_group, current_round = rating_service.initialize_user_session()
        
        return render_template('search.html',
            recipes=search_results.to_dict('records'),
            query=query,
            user_group=user_group,
            hide_scores=(user_group == 'A' and current_config.HIDE_SCORES_FOR_GROUP_A),
            results_count=len(search_results)
        )
        
    except Exception as e:
        logger.error(f"Keresési hiba: {e}")
        return render_template('error.html', error_message="Hiba a keresés során"), 500

@app.route('/results')
def results():
    """
    Eredmények oldal - tanulmány befejezése után
    """
    try:
        # Felhasználói session összefoglalása
        user_summary = rating_service.get_user_session_summary()
        
        # Felhasználói metrikák számítása
        user_ratings = rating_service.get_user_ratings()
        user_metrics = analytics_service.calculate_user_metrics(user_ratings)
        
        return render_template('results.html',
            user_summary=user_summary,
            user_metrics=user_metrics.__dict__,
            total_rounds=current_config.MAX_LEARNING_ROUNDS
        )
        
    except Exception as e:
        logger.error(f"Eredmények oldal hiba: {e}")
        return render_template('error.html', error_message="Hiba az eredmények betöltésében"), 500

@app.route('/analytics')
def analytics():
    """
    Analytics dashboard - A/B/C teszt eredmények
    """
    try:
        # Dashboard adatok lekérése
        dashboard_data = analytics_service.get_dashboard_data()
        
        return render_template('analytics.html',
            dashboard=dashboard_data
        )
        
    except Exception as e:
        logger.error(f"Analytics oldal hiba: {e}")
        return render_template('error.html', error_message="Hiba az analytics betöltésében"), 500

@app.route('/api/dashboard')
def api_dashboard():
    """
    Dashboard API endpoint - JSON adatok
    """
    try:
        dashboard_data = analytics_service.get_dashboard_data()
        return jsonify(dashboard_data)
        
    except Exception as e:
        logger.error(f"Dashboard API hiba: {e}")
        return jsonify({'error': 'Dashboard adatok nem elérhetők'}), 500

@app.route('/reset_session')
def reset_session():
    """
    Session törrlése - új kezdés
    """
    try:
        rating_service.clear_user_session()
        return redirect(url_for('index'))
        
    except Exception as e:
        logger.error(f"Session reset hiba: {e}")
        return redirect(url_for('index'))

@app.route('/status')
def status():
    """
    Rendszer állapot ellenőrzése - debug endpoint
    """
    try:
        # Rendszer statisztikák
        data_stats = data_manager.get_data_statistics()
        engine_stats = recommendation_engine.get_engine_stats()
        user_summary = rating_service.get_user_session_summary()
        
        status_info = {
            'system_status': 'operational',
            'timestamp': app.config.get('startup_time', 'unknown'),
            'data_manager': {
                'recipes_loaded': data_stats.get('total_recipes', 0),
                'esi_range': data_stats.get('esi_range', (0, 100)),
                'composite_range': data_stats.get('composite_range', (0, 100)),
                'categories': data_stats.get('categories', [])
            },
            'recommendation_engine': engine_stats,
            'current_user': {
                'user_id': user_summary.get('user_id', 'none'),
                'group': user_summary.get('user_group', 'none'),
                'round': user_summary.get('current_round', 0),
                'total_ratings': user_summary.get('total_ratings', 0)
            },
            'configuration': {
                'max_rounds': current_config.MAX_LEARNING_ROUNDS,
                'recommendations_per_round': current_config.RECOMMENDATIONS_PER_ROUND,
                'min_ratings_for_next': current_config.MIN_RATINGS_FOR_NEXT_ROUND,
                'esi_weight': current_config.ESI_WEIGHT,
                'hsi_weight': current_config.HSI_WEIGHT,
                'ppi_weight': current_config.PPI_WEIGHT
            }
        }
        
        return jsonify(status_info)
        
    except Exception as e:
        logger.error(f"Status endpoint hiba: {e}")
        return jsonify({
            'system_status': 'error',
            'error': str(e)
        }), 500

@app.route('/health')
def health():
    """
    Health check endpoint - Heroku számára
    """
    try:
        # Egyszerű egészségügyi ellenőrzés
        healthy = (
            data_manager.recipes_df is not None and
            recommendation_engine.is_initialized
        )
        
        if healthy:
            return jsonify({'status': 'healthy'}), 200
        else:
            return jsonify({'status': 'unhealthy'}), 503
            
    except Exception as e:
        logger.error(f"Health check hiba: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 503

@app.errorhandler(404)
def not_found(error):
    """404 hiba kezelése"""
    return render_template('error.html', 
                         error_message="Az oldal nem található"), 404

@app.errorhandler(500)
def internal_error(error):
    """500 szerver hiba kezelése"""
    logger.error(f"Szerver hiba: {error}")
    return render_template('error.html', 
                         error_message="Belső szerver hiba"), 500

# Template helper funkciók
@app.template_filter('round_float')
def round_float(value, decimals=2):
    """Template filter - float kerekítése"""
    try:
        return round(float(value), decimals)
    except (ValueError, TypeError):
        return value

@app.template_filter('percentage')
def percentage(value):
    """Template filter - százalékká alakítás"""
    try:
        return f"{float(value) * 100:.1f}%"
    except (ValueError, TypeError):
        return "0%"

@app.template_global()
def get_group_name(group_code):
    """Template global - csoport név leképezése"""
    group_names = {
        'A': 'Alapértelmezett',
        'B': 'Score-támogatott', 
        'C': 'Intelligens hibrid'
    }
    return group_names.get(group_code, 'Ismeretlen')

# Template filterek hozzáadása (ÚJ RÉSZ)
@app.template_filter('highlight_search')
def highlight_search(text, query):
    """Keresési kifejezések kiemelése"""
    if not query:
        return text
    import re
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(f'<mark>{query}</mark>', text)

@app.template_global()
def moment():
    """Aktuális datetime objektum"""
    from datetime import datetime
    return datetime.now()

# Alkalmazás futtatása
if __name__ == '__main__':
    # Startup timestamp
    from datetime import datetime
    app.config['startup_time'] = datetime.now().isoformat()
    
    # Port beállítása (Heroku kompatibilitás)
    port = int(os.environ.get('PORT', 5000))
    
    # Alkalmazás indítása
    app.run(
        host='0.0.0.0',
        port=port,
        debug=current_config.DEBUG
    )
