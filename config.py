# config.py
"""
GreenRec Konfiguráció
==================
Központi konfigurációs fájl minden beállítással.
Heroku + PostgreSQL kompatibilis.
"""

import os
from urllib.parse import urlparse

class Config:
    """Alapértelmezett konfiguráció"""
    
    # Flask beállítások
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Adatbázis konfiguráció - Heroku PostgreSQL
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        # Heroku postgres:// -> postgresql:// konverzió
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    # Ajánlórendszer beállítások
    MAX_LEARNING_ROUNDS = 3  # 3 kör az 5 helyett
    RECOMMENDATIONS_PER_ROUND = 5  # Precision@5 konzisztencia
    MIN_RATINGS_FOR_NEXT_ROUND = 3
    
    # A/B/C teszt beállítások  
    ABC_GROUPS = ['A', 'B', 'C']
    GROUP_DISTRIBUTION = [0.33, 0.33, 0.34]  # Egyenletes eloszlás
    
    # ML paraméterek
    TFIDF_MAX_FEATURES = 1000
    TFIDF_NGRAM_RANGE = (1, 2)
    SIMILARITY_THRESHOLD = 0.1
    
    # Kompozit pontszám súlyok
    ESI_WEIGHT = 0.4  # Környezeti hatás (inverz)
    HSI_WEIGHT = 0.4  # Egészségügyi érték
    PPI_WEIGHT = 0.2  # Népszerűség
    
    # UI beállítások
    HIDE_SCORES_FOR_GROUP_A = True  # A csoport rejtett értékekkel
    SHOW_IMAGES = True  # Képek megjelenítése
    ENABLE_SEARCH = True  # Keresőmező engedélyezése
    
    # Performance beállítások
    CACHE_TIMEOUT = 300  # 5 perc cache
    MAX_SEARCH_RESULTS = 5
    
    # Adatfájl helyek
    RECIPE_DATA_FILE = 'data/recipes.json'
    BACKUP_DATA_FILE = 'greenrec_dataset.json'  # Fallback a gyökérben

class DevelopmentConfig(Config):
    """Fejlesztői konfiguráció"""
    DEBUG = True
    DATABASE_URL = os.environ.get('DEV_DATABASE_URL') or 'sqlite:///greenrec_dev.db'

class ProductionConfig(Config):
    """Éles konfiguráció"""
    DEBUG = False
    # Heroku automatikusan beállítja a DATABASE_URL-t

class TestingConfig(Config):
    """Tesztelési konfiguráció"""
    TESTING = True
    DATABASE_URL = 'sqlite:///:memory:'
    MAX_LEARNING_ROUNDS = 2  # Gyorsabb tesztek

# Környezet-specifikus konfiguráció kiválasztása
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Aktuális konfiguráció visszaadása"""
    env = os.environ.get('FLASK_ENV', 'default')
    return config.get(env, config['default'])

# Globálisan elérhető konfiguráció
current_config = get_config()
