# config.py
"""
GreenRec Configuration
=====================

Központi konfigurációs fájl a GreenRec alkalmazáshoz.
Tartalmazza az összes beállítást, konstanst és konfigurációt.
"""

import os
import logging
from datetime import timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.absolute()
STATIC_DIR = BASE_DIR / 'static'
TEMPLATES_DIR = BASE_DIR / 'templates'
DATA_DIR = BASE_DIR / 'data'
LOGS_DIR = BASE_DIR / 'logs'

# Ensure directories exist
for directory in [STATIC_DIR, TEMPLATES_DIR, DATA_DIR, LOGS_DIR]:
    directory.mkdir(exist_ok=True)

@dataclass
class DatabaseConfig:
    """Adatbázis konfigurációs beállítások"""
    # SQLite for development (session-based storage)
    DATABASE_URL: str = f"sqlite:///{DATA_DIR}/greenrec.db"
    
    # JSON file paths for recipe data
    RECIPE_DATA_PATHS: List[str] = None
    
    # Database connection settings
    POOL_SIZE: int = 20
    MAX_OVERFLOW: int = 30
    POOL_TIMEOUT: int = 30
    POOL_RECYCLE: int = 3600
    
    def __post_init__(self):
        if self.RECIPE_DATA_PATHS is None:
            self.RECIPE_DATA_PATHS = [
                str(DATA_DIR / 'greenrec_dataset.json'),
                str(DATA_DIR / 'data.json'),
                str(DATA_DIR / 'recipes.json')
            ]

@dataclass
class SecurityConfig:
    """Biztonsági konfigurációs beállítások"""
    # Flask secret key (változtassa meg production környezetben!)
    SECRET_KEY: str = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Session security
    SESSION_COOKIE_SECURE: bool = False  # True HTTPS-nél
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = 'Lax'
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(hours=24)
    
    # CSRF protection
    WTF_CSRF_ENABLED: bool = True
    WTF_CSRF_TIME_LIMIT: int = 3600
    
    # Rate limiting
    RATELIMIT_STORAGE_URL: str = 'memory://'
    RATELIMIT_DEFAULT: str = "1000 per hour"
    RATELIMIT_HEADERS_ENABLED: bool = True
    
    # API security
    API_RATE_LIMIT: str = "100 per minute"
    SEARCH_RATE_LIMIT: str = "50 per minute"
    RATING_RATE_LIMIT: str = "30 per minute"

@dataclass 
class RecommendationConfig:
    """Ajánlórendszer konfigurációs beállítások"""
    # Algorithm parameters
    SIMILARITY_THRESHOLD: float = 0.1
    MAX_RECOMMENDATIONS: int = 20
    DEFAULT_RECOMMENDATIONS: int = 6
    
    # TF-IDF parameters
    TFIDF_MAX_FEATURES: int = 5000
    TFIDF_MIN_DF: int = 1
    TFIDF_MAX_DF: float = 0.95
    TFIDF_NGRAM_RANGE: tuple = (1, 2)
    
    # Scoring weights
    SUSTAINABILITY_WEIGHT: float = 0.4  # ESI weight
    HEALTH_WEIGHT: float = 0.4          # HSI weight  
    POPULARITY_WEIGHT: float = 0.2      # PPI weight
    
    # Learning parameters
    LEARNING_RATE: float = 0.1
    MIN_RATINGS_FOR_LEARNING: int = 3
    RELEVANCE_THRESHOLD: int = 4  # Rating >= 4 considered relevant
    
    # Content-based filtering
    INGREDIENT_SIMILARITY_WEIGHT: float = 0.3
    CATEGORY_SIMILARITY_WEIGHT: float = 0.2
    DESCRIPTION_SIMILARITY_WEIGHT: float = 0.5
    
    # Diversity parameters
    DIVERSITY_LAMBDA: float = 0.3  # Balances relevance vs diversity
    MAX_SAME_CATEGORY: int = 3     # Max recipes from same category

@dataclass
class ABTestConfig:
    """A/B/C teszt konfigurációs beállítások"""
    # Test groups
    GROUPS: List[str] = None
    GROUP_WEIGHTS: Dict[str, float] = None
    
    # Test parameters
    MIN_USERS_PER_GROUP: int = 10
    MAX_LEARNING_ROUNDS: int = 5
    RECIPES_PER_ROUND: int = 6
    
    # Group-specific settings
    GROUP_ALGORITHMS: Dict[str, str] = None
    GROUP_LEARNING_RATES: Dict[str, float] = None
    
    def __post_init__(self):
        if self.GROUPS is None:
            self.GROUPS = ['A', 'B', 'C']
            
        if self.GROUP_WEIGHTS is None:
            self.GROUP_WEIGHTS = {
                'A': 0.33,  # Baseline group
                'B': 0.33,  # Collaborative filtering
                'C': 0.34   # Hybrid approach
            }
            
        if self.GROUP_ALGORITHMS is None:
            self.GROUP_ALGORITHMS = {
                'A': 'content_based',      # Pure content-based
                'B': 'collaborative',      # Collaborative filtering
                'C': 'hybrid'              # Hybrid (content + collaborative + sustainability)
            }
            
        if self.GROUP_LEARNING_RATES is None:
            self.GROUP_LEARNING_RATES = {
                'A': 0.05,  # Slow learning (baseline)
                'B': 0.1,   # Medium learning  
                'C': 0.15   # Fast learning (adaptive)
            }

@dataclass
class AnalyticsConfig:
    """Analitikai konfigurációs beállítások"""
    # Metrics calculation
    PRECISION_AT_K: List[int] = None
    RECALL_AT_K: List[int] = None
    
    # Dashboard refresh
    DASHBOARD_REFRESH_INTERVAL: int = 30  # seconds
    METRICS_CACHE_TTL: int = 300          # 5 minutes
    
    # Data export
    EXPORT_FORMATS: List[str] = None
    MAX_EXPORT_RECORDS: int = 10000
    
    # Chart configuration
    CHART_COLORS: Dict[str, str] = None
    CHART_ANIMATION_DURATION: int = 2000
    
    def __post_init__(self):
        if self.PRECISION_AT_K is None:
            self.PRECISION_AT_K = [5, 10, 20]
            
        if self.RECALL_AT_K is None:
            self.RECALL_AT_K = [5, 10, 20]
            
        if self.EXPORT_FORMATS is None:
            self.EXPORT_FORMATS = ['json', 'csv', 'xlsx']
            
        if self.CHART_COLORS is None:
            self.CHART_COLORS = {
                'group_a': '#d32f2f',      # Red
                'group_b': '#ff9800',      # Orange  
                'group_c': '#4caf50',      # Green
                'primary': '#2d7d32',      # Dark green
                'secondary': '#1976d2',    # Blue
                'success': '#43a047',      # Success green
                'warning': '#f57c00',      # Warning orange
                'error': '#d32f2f',        # Error red
                'info': '#1976d2'          # Info blue
            }

@dataclass
class LoggingConfig:
    """Logging konfigurációs beállítások"""
    # Log levels
    LOG_LEVEL: str = os.environ.get('LOG_LEVEL', 'INFO')
    
    # Log files
    LOG_FILE: str = str(LOGS_DIR / 'greenrec.log')
    ERROR_LOG_FILE: str = str(LOGS_DIR / 'errors.log')
    ACCESS_LOG_FILE: str = str(LOGS_DIR / 'access.log')
    
    # Log rotation
    MAX_LOG_SIZE: int = 10 * 1024 * 1024  # 10MB
    BACKUP_COUNT: int = 5
    
    # Log format
    LOG_FORMAT: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    DATE_FORMAT: str = '%Y-%m-%d %H:%M:%S'
    
    # Console logging
    CONSOLE_LOG_LEVEL: str = 'INFO'
    CONSOLE_LOG_FORMAT: str = '%(levelname)s: %(message)s'

@dataclass
class CacheConfig:
    """Cache konfigurációs beállítások"""
    # Cache type
    CACHE_TYPE: str = 'simple'  # 'simple', 'redis', 'memcached'
    CACHE_DEFAULT_TIMEOUT: int = 300  # 5 minutes
    
    # Redis configuration (if used)
    REDIS_URL: str = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # Cache timeouts for different data types
    RECIPE_CACHE_TIMEOUT: int = 3600      # 1 hour
    METRICS_CACHE_TIMEOUT: int = 300      # 5 minutes
    SEARCH_CACHE_TIMEOUT: int = 600       # 10 minutes
    USER_CACHE_TIMEOUT: int = 1800        # 30 minutes

@dataclass
class APIConfig:
    """API konfigurációs beállítások"""
    # API versioning
    API_VERSION: str = 'v1'
    API_PREFIX: str = '/api'
    
    # Request/Response settings
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16MB
    JSON_SORT_KEYS: bool = False
    JSONIFY_PRETTYPRINT_REGULAR: bool = False
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Response timeouts
    API_TIMEOUT: int = 30
    SEARCH_TIMEOUT: int = 10
    RATING_TIMEOUT: int = 5

@dataclass
class PerformanceConfig:
    """Teljesítmény konfigurációs beállítások"""
    # Threading
    THREADS_PER_PAGE: int = 2
    
    # Caching
    SEND_FILE_MAX_AGE_DEFAULT: timedelta = timedelta(hours=12)
    
    # Compression
    COMPRESS_MIMETYPES: List[str] = None
    COMPRESS_LEVEL: int = 6
    COMPRESS_MIN_SIZE: int = 500
    
    # Database optimization
    DATABASE_QUERY_TIMEOUT: int = 30
    CONNECTION_POOL_SIZE: int = 10
    
    def __post_init__(self):
        if self.COMPRESS_MIMETYPES is None:
            self.COMPRESS_MIMETYPES = [
                'text/html', 'text/css', 'text/xml',
                'application/json', 'application/javascript'
            ]

class Config:
    """Főkonfigurációs osztály - összes beállítás központosítása"""
    
    def __init__(self, environment: str = None):
        self.environment = environment or os.environ.get('FLASK_ENV', 'development')
        
        # Initialize all configuration sections
        self.database = DatabaseConfig()
        self.security = SecurityConfig()
        self.recommendation = RecommendationConfig()
        self.ab_test = ABTestConfig()
        self.analytics = AnalyticsConfig()
        self.logging = LoggingConfig()
        self.cache = CacheConfig()
        self.api = APIConfig()
        self.performance = PerformanceConfig()
        
        # Apply environment-specific overrides
        self._apply_environment_config()
        
        # Setup logging
        self._setup_logging()
    
    def _apply_environment_config(self):
        """Környezet-specifikus konfigurációs felülírások"""
        if self.environment == 'production':
            self._apply_production_config()
        elif self.environment == 'testing':
            self._apply_testing_config()
        elif self.environment == 'development':
            self._apply_development_config()
    
    def _apply_production_config(self):
        """Production környezet beállításai"""
        # Security
        self.security.SESSION_COOKIE_SECURE = True
        self.security.SECRET_KEY = os.environ.get('SECRET_KEY', 'CHANGE-THIS-IN-PRODUCTION')
        
        # Logging
        self.logging.LOG_LEVEL = 'WARNING'
        self.logging.CONSOLE_LOG_LEVEL = 'ERROR'
        
        # Performance
        self.performance.THREADS_PER_PAGE = 4
        self.performance.CONNECTION_POOL_SIZE = 20
        
        # Cache
        self.cache.CACHE_TYPE = 'redis'
        self.cache.CACHE_DEFAULT_TIMEOUT = 3600
        
        # Database
        self.database.DATABASE_URL = os.environ.get('DATABASE_URL', self.database.DATABASE_URL)
    
    def _apply_testing_config(self):
        """Testing környezet beállításai"""
        # Database
        self.database.DATABASE_URL = 'sqlite:///:memory:'
        
        # Security
        self.security.WTF_CSRF_ENABLED = False
        self.security.SECRET_KEY = 'testing-secret-key'
        
        # Logging
        self.logging.LOG_LEVEL = 'DEBUG'
        
        # Cache
        self.cache.CACHE_TYPE = 'null'
        
        # Recommendation (faster for testing)
        self.recommendation.DEFAULT_RECOMMENDATIONS = 3
        self.ab_test.RECIPES_PER_ROUND = 3
    
    def _apply_development_config(self):
        """Development környezet beállításai"""
        # Logging
        self.logging.LOG_LEVEL = 'DEBUG'
        self.logging.CONSOLE_LOG_LEVEL = 'DEBUG'
        
        # Security
        self.security.SESSION_COOKIE_SECURE = False
        
        # API
        self.api.JSONIFY_PRETTYPRINT_REGULAR = True
        
        # Performance (disable compression for debugging)
        self.performance.COMPRESS_LEVEL = 0
    
    def _setup_logging(self):
        """Logging rendszer beállítása"""
        # Create logs directory if it doesn't exist
        LOGS_DIR.mkdir(exist_ok=True)
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, self.logging.LOG_LEVEL),
            format=self.logging.LOG_FORMAT,
            datefmt=self.logging.DATE_FORMAT,
            handlers=[
                logging.FileHandler(self.logging.LOG_FILE),
                logging.StreamHandler()
            ]
        )
        
        # Configure specific loggers
        greenrec_logger = logging.getLogger('greenrec')
        greenrec_logger.setLevel(getattr(logging, self.logging.LOG_LEVEL))
        
        # Performance logger
        perf_logger = logging.getLogger('greenrec.performance')
        perf_handler = logging.FileHandler(LOGS_DIR / 'performance.log')
        perf_handler.setFormatter(logging.Formatter(self.logging.LOG_FORMAT))
        perf_logger.addHandler(perf_handler)
    
    def get_flask_config(self) -> Dict[str, Any]:
        """Flask alkalmazáshoz szükséges konfigurációs dictionary"""
        return {
            # Flask basic settings
            'SECRET_KEY': self.security.SECRET_KEY,
            'DEBUG': self.environment == 'development',
            'TESTING': self.environment == 'testing',
            
            # Session configuration
            'SESSION_COOKIE_SECURE': self.security.SESSION_COOKIE_SECURE,
            'SESSION_COOKIE_HTTPONLY': self.security.SESSION_COOKIE_HTTPONLY,
            'SESSION_COOKIE_SAMESITE': self.security.SESSION_COOKIE_SAMESITE,
            'PERMANENT_SESSION_LIFETIME': self.security.PERMANENT_SESSION_LIFETIME,
            
            # JSON settings
            'JSON_SORT_KEYS': self.api.JSON_SORT_KEYS,
            'JSONIFY_PRETTYPRINT_REGULAR': self.api.JSONIFY_PRETTYPRINT_REGULAR,
            
            # File uploads
            'MAX_CONTENT_LENGTH': self.api.MAX_CONTENT_LENGTH,
            
            # Static files
            'SEND_FILE_MAX_AGE_DEFAULT': self.performance.SEND_FILE_MAX_AGE_DEFAULT,
            
            # Database
            'SQLALCHEMY_DATABASE_URI': self.database.DATABASE_URL,
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            
            # Cache
            'CACHE_TYPE': self.cache.CACHE_TYPE,
            'CACHE_DEFAULT_TIMEOUT': self.cache.CACHE_DEFAULT_TIMEOUT,
            'CACHE_REDIS_URL': self.cache.REDIS_URL,
        }
    
    def validate_config(self) -> List[str]:
        """Konfigurációs validálás - hibás beállítások ellenőrzése"""
        errors = []
        
        # Check secret key
        if self.security.SECRET_KEY == 'dev-secret-key-change-in-production' and self.environment == 'production':
            errors.append("Production környezetben változtassa meg a SECRET_KEY-t!")
        
        # Check data files
        for data_path in self.database.RECIPE_DATA_PATHS:
            if not os.path.exists(data_path):
                errors.append(f"Recept adatfájl nem található: {data_path}")
        
        # Check weights sum to 1.0
        total_weight = (self.recommendation.SUSTAINABILITY_WEIGHT + 
                       self.recommendation.HEALTH_WEIGHT + 
                       self.recommendation.POPULARITY_WEIGHT)
        if abs(total_weight - 1.0) > 0.001:
            errors.append(f"Scoring weights összege nem 1.0: {total_weight}")
        
        # Check AB test group weights
        ab_total = sum(self.ab_test.GROUP_WEIGHTS.values())
        if abs(ab_total - 1.0) > 0.001:
            errors.append(f"A/B test group weights összege nem 1.0: {ab_total}")
        
        return errors

# Global configuration instances
config = Config()

# Convenience functions for easy access
def get_config() -> Config:
    """Globális konfiguráció lekérdezése"""
    return config

def get_flask_config() -> Dict[str, Any]:
    """Flask konfigurációs dictionary lekérdezése"""
    return config.get_flask_config()

def validate_configuration() -> List[str]:
    """Konfigurációs validálás futtatása"""
    return config.validate_config()

# Environment-specific configuration loading
def load_config_for_environment(env: str) -> Config:
    """Specifikus környezethez konfiguráció betöltése"""
    return Config(environment=env)

# Constants for easy access
class Constants:
    """Alkalmazás konstansok"""
    
    # User groups
    USER_GROUPS = ['A', 'B', 'C']
    
    # Rating scale
    MIN_RATING = 1
    MAX_RATING = 5
    RELEVANCE_THRESHOLD = 4
    
    # Recommendation limits
    MIN_RECOMMENDATIONS = 1
    MAX_RECOMMENDATIONS = 50
    DEFAULT_RECOMMENDATIONS = 6
    
    # Learning parameters
    MIN_LEARNING_ROUNDS = 1
    MAX_LEARNING_ROUNDS = 10
    DEFAULT_LEARNING_ROUNDS = 5
    
    # Sustainability metrics
    ESI_RANGE = (0, 100)  # Environmental Score Index
    HSI_RANGE = (0, 100)  # Health Score Index  
    PPI_RANGE = (0, 100)  # Popularity Index
    
    # File extensions
    ALLOWED_DATA_EXTENSIONS = {'.json', '.csv'}
    ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    
    # API response codes
    SUCCESS_CODE = 200
    ERROR_CODE = 400
    NOT_FOUND_CODE = 404
    SERVER_ERROR_CODE = 500

# Export hlavní konfiguráció
__all__ = [
    'Config',
    'config', 
    'get_config',
    'get_flask_config',
    'validate_configuration',
    'load_config_for_environment',
    'Constants',
    'DatabaseConfig',
    'SecurityConfig', 
    'RecommendationConfig',
    'ABTestConfig',
    'AnalyticsConfig',
    'LoggingConfig',
    'CacheConfig',
    'APIConfig',
    'PerformanceConfig'
]
