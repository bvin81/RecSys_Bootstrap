# app.py - GreenRec Slim Orchestrator
"""
GreenRec - Főalkalmazás (Moduláris Verzió)
==========================================
Slim main application - csak orchestration, üzleti logika külön modulokban

Architektúra:
- models/ → ML algoritmusok és adatmodellek
- services/ → Üzleti logika (Blueprint-ek)
- user_study/ → Meglévő kutatási modul
- utils/ → Segédfunkciók
- templates/ → HTML template-ek
- static/ → CSS/JS/képek
"""

from flask import Flask, render_template, redirect, url_for, session
import os
import logging
from datetime import datetime

# Konfiguráció import
from config import Config

# Blueprint importok
from user_study import user_study_bp
from services.recipe_service import recipe_bp
from services.analytics_service import analytics_bp

# Utility importok
from utils.helpers import setup_logging, init_data_if_needed

def create_app():
    """Flask alkalmazás factory pattern"""
    app = Flask(__name__)
    
    # Konfiguráció betöltése
    app.config.from_object(Config)
    
    # Logging beállítása
    setup_logging(app)
    
    # Adatok inicializálása (ha szükséges)
    with app.app_context():
        init_data_if_needed()
    
    # Blueprint regisztrálás
    register_blueprints(app)
    
    # Főoldal route-ok
    register_main_routes(app)
    
    # Error handling
    register_error_handlers(app)
    
    return app

def register_blueprints(app):
    """Blueprint-ek regisztrálása"""
    
    # User Study Blueprint (meglévő)
    app.register_blueprint(user_study_bp, url_prefix='/study')
    
    # Recipe Service Blueprint (új funkcionalitás)
    app.register_blueprint(recipe_bp, url_prefix='/api')
    
    # Analytics Service Blueprint (metrikák, A/B/C teszt)
    app.register_blueprint(analytics_bp, url_prefix='/analytics')
    
    app.logger.info("✅ Blueprints registered successfully")

def register_main_routes(app):
    """Főoldal route-ok regisztrálása"""
    
    @app.route('/')
    def index():
        """Főoldal - redirect a megfelelő oldalra"""
        # Ha van aktív session, direkt a study-ra
        if 'user_id' in session:
            return redirect(url_for('recipes.enhanced_study'))
        
        # Különben welcome oldalra
        return redirect(url_for('recipes.enhanced_study'))
    
    @app.route('/health')
    def health_check():
        """Health check endpoint Heroku számára"""
        return {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '2.0-modular'
        }
    
    @app.route('/favicon.ico')
    def favicon():
        """Favicon endpoint"""
        return app.send_static_file('favicon.ico')

def register_error_handlers(app):
    """Error handling regisztrálása"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'Server Error: {error}')
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        app.logger.error(f'Unhandled Exception: {e}')
        if app.debug:
            raise e
        return render_template('errors/500.html'), 500

# Context processors és template helpers
def register_template_helpers(app):
    """Template helper funkciók"""
    
    @app.context_processor
    def inject_global_vars():
        return {
            'current_year': datetime.now().year,
            'app_version': '2.0',
            'user_group': session.get('user_group', 'unknown')
        }

if __name__ == '__main__':
    # Alkalmazás létrehozása és futtatása
    app = create_app()
    
    # Template helpers regisztrálása
    register_template_helpers(app)
    
    # Environment-specific beállítások
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    port = int(os.environ.get('PORT', 5000))
    
    print("🌱 GreenRec - Moduláris Architektúra")
    print("=" * 50)
    print("✅ Slim main application")
    print("✅ Blueprint-based architecture")
    print("✅ Separation of concerns")
    print("✅ 3 tanulási kör + képek + rejtett pontszámok")
    print("✅ A/B/C teszt analytics")
    print("=" * 50)
    print(f"🚀 Server: http://localhost:{port}")
    
    # Flask alkalmazás indítása
    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=port
    )
