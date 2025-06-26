# config.py - GreenRec Központi Konfiguráció
"""
GreenRec Konfiguráció
====================
Központi konfiguráció minden modul számára.
Environment-specific beállítások és konstansok.
"""

import os
from datetime import timedelta

class Config:
    """Alap konfiguráció osztály"""
    
    # Flask alapbeállítások
    SECRET_KEY = os.environ.get('SECRET_KEY', 'greenrec-dev-secret-key-change-in-production')
    DEBUG = os.environ.get('FLASK_ENV') == 'development'
    
    # Session konfiguráció
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    
    # Adatbázis konfiguráció
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    # ✅ GREENREC SPECIFIKUS BEÁLLÍTÁSOK
    
    # Tanulási rendszer
    MAX_LEARNING_ROUNDS = 3              # ✅ 3 kör (5 helyett)
    RECOMMENDATION_COUNT = 5             # ✅ 5 recept/kör (Precision@5)
    RELEVANCE_THRESHOLD = 4              # Rating >= 4 = releváns
    
    # A/B/C teszt konfiguráció
    GROUP_ALGORITHMS = {
        'A': 'content_based_hidden',     # ✅ Rejtett pontszámok
        'B': 'score_enhanced',          # Pontszámok láthatók
        'C': 'hybrid_xai'               # Hibrid + magyarázatok
    }
    
    # Pontszám súlyozás (ESI inverz normalizálás)
    SCORE_WEIGHTS = {
        'ESI': 0.4,    # Környezeti hatás (inverz: 100-ESI)
        'HSI': 0.4,    # Egészségügyi érték
        'PPI': 0.2     # Népszerűség
    }
    
    # TF-IDF beállítások
    TFIDF_MAX_FEATURES = 1000
    TFIDF_NGRAM_RANGE = (1, 2)
    
    # Adatfájlok
    DATA_FILES = [
        'greenrec_dataset.json',
        'data/greenrec_dataset.json',
        'data/processed_recipes.csv',
        'hungarian_recipes_github.csv'
    ]
    
    # Képek konfiguráció
    DEFAULT_RECIPE_IMAGE = 'https://via.placeholder.com/300x200/667eea/white?text=🍽️+Recept'
    IMAGE_PLACEHOLDER_BASE = 'https://picsum.photos/300/200?random='
    
    # Keresési beállítások
    SEARCH_MIN_SIMILARITY = 0.1
    SEARCH_MAX_RESULTS = 15
    
    # Metrikák és analytics
    METRICS_CONFIG = {
        'precision_recall_k_values': [5, 10, 20],
        'diversity_features': ['category', 'ingredients', 'sustainability'],
        'cache_timeout': 300  # 5 perc
    }
    
    # Logging konfiguráció
    LOG_LEVEL = 'INFO' if not DEBUG else 'DEBUG'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Rate limiting (ha szükséges)
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'memory://')
    
    # File upload (ha később szükséges)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # Cache konfiguráció
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300

class DevelopmentConfig(Config):
    """Development környezet konfiguráció"""
    DEBUG = True
    TESTING = False
    
    # Development-specific beállítások
    LOG_LEVEL = 'DEBUG'
    SESSION_COOKIE_SECURE = False
    
    # Demo adatok használata
    USE_DEMO_DATA = True

class ProductionConfig(Config):
    """Production környezet konfiguráció"""
    DEBUG = False
    TESTING = False
    
    # Production-specific beállítások
    LOG_LEVEL = 'WARNING'
    SESSION_COOKIE_SECURE = True
    
    # Biztonsági fejlesztések
    WTF_CSRF_ENABLED = True
    
    # Cache és teljesítmény
    CACHE_TYPE = 'redis' if os.environ.get('REDIS_URL') else 'simple'

class TestingConfig(Config):
    """Testing környezet konfiguráció"""
    TESTING = True
    DEBUG = True
    
    # Test-specific beállítások
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True
    
    # In-memory cache tesztekhez
    CACHE_TYPE = 'null'

# Environment-based konfiguráció kiválasztása
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

# Aktuális konfiguráció
current_config = config_by_name.get(
    os.environ.get('FLASK_ENV', 'development'),
    DevelopmentConfig
)

# Konfiguráció validáció
def validate_config():
    """Konfiguráció validálása"""
    errors = []
    
    # Secret key ellenőrzése production-ben
    if current_config == ProductionConfig:
        if Config.SECRET_KEY == 'greenrec-dev-secret-key-change-in-production':
            errors.append("❌ SECRET_KEY must be changed in production!")
    
    # Súlyok ellenőrzése
    total_weight = sum(Config.SCORE_WEIGHTS.values())
    if abs(total_weight - 1.0) > 0.001:
        errors.append(f"❌ Score weights must sum to 1.0, got {total_weight}")
    
    # Tanulási körök ellenőrzése
    if Config.MAX_LEARNING_ROUNDS < 1 or Config.MAX_LEARNING_ROUNDS > 10:
        errors.append(f"❌ MAX_LEARNING_ROUNDS must be 1-10, got {Config.MAX_LEARNING_ROUNDS}")
    
    if errors:
        print("🔧 Configuration Validation Errors:")
        for error in errors:
            print(f"  {error}")
        return False
    
    print("✅ Configuration validation passed")
    return True

# Konfiguráció információk kiírása
def print_config_info():
    """Konfiguráció információk kiírása"""
    print(f"🔧 Configuration: {current_config.__name__}")
    print(f"🌱 Learning rounds: {Config.MAX_LEARNING_ROUNDS}")
    print(f"📊 Recommendations per round: {Config.RECOMMENDATION_COUNT}")
    print(f"🎯 A/B/C groups: {list(Config.GROUP_ALGORITHMS.keys())}")
    print(f"⚖️ Score weights: ESI={Config.SCORE_WEIGHTS['ESI']}, HSI={Config.SCORE_WEIGHTS['HSI']}, PPI={Config.SCORE_WEIGHTS['PPI']}")

if __name__ == '__main__':
    # Konfiguráció tesztelése
    print("🔧 GreenRec Configuration Test")
    print("=" * 40)
    print_config_info()
    validate_config()
