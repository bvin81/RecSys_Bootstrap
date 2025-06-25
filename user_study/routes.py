#!/usr/bin/env python3
"""
FIXED: Heroku-optimalizált user_study/routes.py
Recipe field compatibility fix for KeyError: 'name'
"""
import sqlite3
import os
import random
import json
import traceback
from pathlib import Path
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify

# Conditional imports with fallbacks
try:
    import pandas as pd
    import numpy as np
    print("✅ Scientific libraries loaded")
except ImportError as e:
    print(f"⚠️ Scientific libraries missing: {e}")
    print("🔧 Using Python built-ins as fallback")
    # Fallback - használjuk a Python built-in-eket
    class MockPandas:
        def read_csv(self, *args, **kwargs):
            return []
    pd = MockPandas()
    
    class MockNumpy:
        def random(self):
            import random
            return random
    np = MockNumpy()

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from urllib.parse import urlparse
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    print("⚠️ psycopg2 not available, falling back to SQLite")

from flask import send_file, make_response
import csv
import io
import json
from datetime import datetime

# Enhanced modules (conditional import) - FIXED VERSION WITH PATH
try:
    import sys
    import os
    
    # Add current directory to Python path for imports
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    
    # Add both paths to sys.path if not already there
    for path in [current_dir, parent_dir]:
        if path not in sys.path:
            sys.path.insert(0, path)
    
    print(f"🔍 Current dir: {current_dir}")
    print(f"🔍 Parent dir: {parent_dir}")
    print(f"🔍 Python path updated")
    
    # Try multiple import strategies
    try:
        # Strategy 1: Relative imports (preferred)
        from .enhanced_content_based import EnhancedContentBasedRecommender, create_enhanced_recommender, convert_old_recipe_format
        from .evaluation_metrics import RecommendationEvaluator, MetricsTracker, create_evaluator
        print("✅ Enhanced modules loaded with relative imports")
        import_strategy = "relative"
    except ImportError as e1:
        print(f"⚠️ Relative imports failed: {e1}")
        try:
            # Strategy 2: Absolute imports from user_study package
            from user_study.enhanced_content_based import EnhancedContentBasedRecommender, create_enhanced_recommender, convert_old_recipe_format
            from user_study.evaluation_metrics import RecommendationEvaluator, MetricsTracker, create_evaluator
            print("✅ Enhanced modules loaded with user_study prefix")
            import_strategy = "user_study_prefix"
        except ImportError as e2:
            print(f"⚠️ user_study prefix failed: {e2}")
            # Strategy 3: Direct imports (fallback)
            from enhanced_content_based import EnhancedContentBasedRecommender, create_enhanced_recommender, convert_old_recipe_format
            from evaluation_metrics import RecommendationEvaluator, MetricsTracker, create_evaluator
            print("✅ Enhanced modules loaded with direct imports")
            import_strategy = "direct"
    
    # Don't import enhanced_routes_integration for now - it causes circular imports
    ENHANCED_MODULES_AVAILABLE = True
    print(f"✅ Enhanced modules loaded successfully using {import_strategy} strategy")
    
except ImportError as e:
    print(f"⚠️ Enhanced modules not available: {e}")
    print("🔧 Falling back to original recommendation system")
    ENHANCED_MODULES_AVAILABLE = False
    import_strategy = "none"
except Exception as e:
    print(f"❌ Unexpected error loading enhanced modules: {e}")
    import traceback
    traceback.print_exc()
    ENHANCED_MODULES_AVAILABLE = False
    import_strategy = "error"

# Print final status
print(f"🎯 ENHANCED_MODULES_AVAILABLE: {ENHANCED_MODULES_AVAILABLE}")
print(f"🎯 Import strategy used: {import_strategy}")

# Blueprint és paths
user_study_bp = Blueprint('user_study', __name__, url_prefix='')

# Heroku-kompatibilis data directory
if os.environ.get('DYNO'):
    # Heroku-n: munkakönytár használata
    project_root = Path.cwd()
else:
    # Helyi fejlesztéshez
    project_root = Path(__file__).parent.parent

data_dir = project_root / "data"

print(f"🔧 Data directory: {data_dir}")
print(f"🔧 Project root: {project_root}")

# =============================================================================
# Bővített adatbázis
# =============================================================================

class EnhancedDatabase:
    """Universal database handler SQLite és PostgreSQL támogatással"""
    
    def __init__(self):
        self.conn = None
        self.is_postgres = False
        self.connect()
        self.create_tables()
    
    def connect(self):
        """Adatbázis kapcsolat létrehozása"""
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url and POSTGRES_AVAILABLE:
            try:
                # Heroku PostgreSQL
                if database_url.startswith('postgres://'):
                    database_url = database_url.replace('postgres://', 'postgresql://', 1)
                
                self.conn = psycopg2.connect(database_url)
                self.is_postgres = True
                print("✅ PostgreSQL connected")
                return
            except Exception as e:
                print(f"⚠️ PostgreSQL connection failed: {e}")
        
        # SQLite fallback
        db_path = data_dir / "study.db"
        data_dir.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.is_postgres = False
        print(f"✅ SQLite connected: {db_path}")
    
    def execute_query(self, query, params=None):
        """Query végrehajtása"""
        try:
            if self.is_postgres:
                with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, params or ())
                    if query.strip().upper().startswith('SELECT'):
                        return cursor.fetchall()
                    self.conn.commit()
                    return cursor.rowcount
            else:
                cursor = self.conn.cursor()
                cursor.execute(query, params or ())
                if query.strip().upper().startswith('SELECT'):
                    return cursor.fetchall()
                self.conn.commit()
                return cursor.rowcount
        except Exception as e:
            print(f"❌ Database error: {e}")
            if self.conn:
                self.conn.rollback()
            return None
    
    def create_tables(self):
        """Táblák létrehozása"""
        # Users tábla
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            version TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        
        # User profiles
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            age_group TEXT,
            education TEXT,
            cooking_frequency TEXT,
            sustainability_awareness INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )""")
        
        # Recipe ratings
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS recipe_ratings (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            recipe_id INTEGER,
            rating INTEGER,
            explanation_helpful INTEGER,
            view_time_seconds INTEGER DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )""")
        
        # Questionnaire responses
        self.execute_query("""
        CREATE TABLE IF NOT EXISTS questionnaire (
            user_id INTEGER PRIMARY KEY,
            system_usability INTEGER,
            recommendation_quality INTEGER,
            trust_level INTEGER,
            explanation_clarity INTEGER,
            sustainability_importance INTEGER,
            overall_satisfaction INTEGER,
            additional_comments TEXT,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )""")
        
        print("✅ Database tables created")
    
    def create_user(self, email, password, display_name, version):
        """Új felhasználó létrehozása"""
        password_hash = self._hash_password(password)
        
        try:
            if self.is_postgres:
                result = self.execute_query(
                    "INSERT INTO users (email, password_hash, display_name, version) VALUES (%s, %s, %s, %s) RETURNING user_id",
                    (email, password_hash, display_name, version)
                )
                return result[0]['user_id'] if result else None
            else:
                cursor = self.conn.cursor()
                cursor.execute(
                    "INSERT INTO users (email, password_hash, display_name, version) VALUES (?, ?, ?, ?)",
                    (email, password_hash, display_name, version)
                )
                self.conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"❌ User creation failed: {e}")
            return None
    
    def authenticate_user(self, email, password):
        """Felhasználó hitelesítése"""
        password_hash = self._hash_password(password)
        
        if self.is_postgres:
            query = "SELECT * FROM users WHERE email = %s AND password_hash = %s"
        else:
            query = "SELECT * FROM users WHERE email = ? AND password_hash = ?"
        
        result = self.execute_query(query, (email, password_hash))
        return dict(result[0]) if result else None
    
    def create_user_profile(self, user_id, profile_data):
        """Felhasználói profil létrehozása"""
        if self.is_postgres:
            query = """
            INSERT INTO user_profiles (user_id, age_group, education, cooking_frequency, sustainability_awareness)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                age_group = EXCLUDED.age_group,
                education = EXCLUDED.education,
                cooking_frequency = EXCLUDED.cooking_frequency,
                sustainability_awareness = EXCLUDED.sustainability_awareness
            """
        else:
            query = """
            INSERT OR REPLACE INTO user_profiles (user_id, age_group, education, cooking_frequency, sustainability_awareness)
            VALUES (?, ?, ?, ?, ?)
            """
        
        self.execute_query(query, (
            user_id,
            profile_data.get('age_group'),
            profile_data.get('education'),
            profile_data.get('cooking_frequency'),
            profile_data.get('sustainability_awareness')
        ))
    
    def log_interaction(self, user_id, recipe_id, rating, explanation_helpful=None, view_time=0):
        """Felhasználói interakció naplózása"""
        if self.is_postgres:
            query = """
            INSERT INTO recipe_ratings (user_id, recipe_id, rating, explanation_helpful, view_time_seconds)
            VALUES (%s, %s, %s, %s, %s)
            """
        else:
            query = """
            INSERT INTO recipe_ratings (user_id, recipe_id, rating, explanation_helpful, view_time_seconds)
            VALUES (?, ?, ?, ?, ?)
            """
        
        self.execute_query(query, (user_id, recipe_id, rating, explanation_helpful, view_time))
    
    def save_questionnaire(self, user_id, responses):
        """Kérdőív válaszok mentése"""
        if self.is_postgres:
            query = """
            INSERT INTO questionnaire (user_id, system_usability, recommendation_quality, trust_level, 
                                     explanation_clarity, sustainability_importance, overall_satisfaction, additional_comments)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                system_usability = EXCLUDED.system_usability,
                recommendation_quality = EXCLUDED.recommendation_quality,
                trust_level = EXCLUDED.trust_level,
                explanation_clarity = EXCLUDED.explanation_clarity,
                sustainability_importance = EXCLUDED.sustainability_importance,
                overall_satisfaction = EXCLUDED.overall_satisfaction,
                additional_comments = EXCLUDED.additional_comments
            """
        else:
            query = """
            INSERT OR REPLACE INTO questionnaire (user_id, system_usability, recommendation_quality, trust_level,
                                                explanation_clarity, sustainability_importance, overall_satisfaction, additional_comments)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
        
        self.execute_query(query, (
            user_id,
            responses.get('system_usability'),
            responses.get('recommendation_quality'),
            responses.get('trust_level'),
            responses.get('explanation_clarity'),
            responses.get('sustainability_importance'),
            responses.get('overall_satisfaction'),
            responses.get('additional_comments', '')
        ))
    
    def get_stats(self):
        """Statisztikák lekérése"""
        stats = {}
        
        # Alapvető statisztikák
        try:
            # Regisztrált felhasználók száma
            if self.is_postgres:
                result = self.execute_query("SELECT COUNT(*) as count FROM users")
            else:
                result = self.execute_query("SELECT COUNT(*) as count FROM users")
            stats['total_participants'] = result[0]['count'] if result else 0
            
            # Kérdőívet kitöltők száma
            if self.is_postgres:
                result = self.execute_query("SELECT COUNT(*) as count FROM questionnaire")
            else:
                result = self.execute_query("SELECT COUNT(*) as count FROM questionnaire")
            stats['completed_participants'] = result[0]['count'] if result else 0
            
            # Verzió szerinti megoszlás
            if self.is_postgres:
                result = self.execute_query("""
                    SELECT version, COUNT(*) as count 
                    FROM users 
                    GROUP BY version 
                    ORDER BY version
                """)
            else:
                result = self.execute_query("""
                    SELECT version, COUNT(*) as count 
                    FROM users 
                    GROUP BY version 
                    ORDER BY version
                """)
            stats['version_distribution'] = [dict(row) for row in result] if result else []
            
            # Átlagos értékelések
            if self.is_postgres:
                result = self.execute_query("SELECT AVG(rating) as avg_rating FROM recipe_ratings")
            else:
                result = self.execute_query("SELECT AVG(rating) as avg_rating FROM recipe_ratings")
            stats['average_rating'] = float(result[0]['avg_rating']) if result and result[0]['avg_rating'] else 0
            
            # Teljesítési arány
            if stats['total_participants'] > 0:
                stats['completion_rate'] = (stats['completed_participants'] / stats['total_participants']) * 100
            else:
                stats['completion_rate'] = 0
            
        except Exception as e:
            print(f"❌ Stats error: {e}")
            stats = {
                'total_participants': 0,
                'completed_participants': 0,
                'completion_rate': 0,
                'version_distribution': [],
                'average_rating': 0
            }
        
        return stats
    
    def get_user_ratings(self, user_id):
        """Felhasználó értékeléseinek lekérése"""
        try:
            if self.is_postgres:
                ratings = self.execute_query(
                    "SELECT recipe_id, rating FROM recipe_ratings WHERE user_id = %s",
                    (user_id,)
                )
            else:
                ratings = self.execute_query(
                    "SELECT recipe_id, rating FROM recipe_ratings WHERE user_id = ?",
                    (user_id,)
                )
                
                return [(r['recipe_id'], r['rating']) for r in ratings]
                
        except Exception as e:
            print(f"❌ Get ratings failed: {e}")
            return []
    
    # HELPER METHODS
    def _hash_password(self, password):
        """Password hashing"""
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _verify_password(self, password, password_hash):
        """Password verification"""
        return self._hash_password(password) == password_hash

class MetricsTracker:
    """Simple metrics tracker for when enhanced modules aren't available"""
    def __init__(self):
        self.metrics = {}
    
    def track_recommendation(self, user_id, recommendations):
        pass
    
    def track_rating(self, user_id, recipe_id, rating):
        pass

class RecommendationEngine:
    """
    Továbbfejlesztett ajánló motor enhanced funkcionalitással
    Backward compatible a meglévő kóddal
    """
    
    def __init__(self, recipes):
        # Original initialization
        self.recipes = recipes
        
        # Enhanced initialization
        self.enhanced_engine = None
        self.metrics_tracker = MetricsTracker() if ENHANCED_MODULES_AVAILABLE else None
        
        if ENHANCED_MODULES_AVAILABLE:
            try:
                # Convert old format to new format
                converted_recipes = convert_old_recipe_format(recipes)
                
                # Create enhanced recommender
                self.enhanced_engine = create_enhanced_recommender(converted_recipes)
                
                print(f"✅ Enhanced Recommendation Engine initialized with {len(recipes)} recipes")
            except Exception as e:
                print(f"❌ Failed to initialize enhanced components: {e}")
                print("🔧 Falling back to original system")
    
    def recommend(self, search_query="", n_recommendations=5, version="v1"):
        """
        Receptek ajánlása a keresési query alapján
        
        FIXED: Recipe field compatibility - ensures all recipes have required fields
        """
        try:
            # Ha van enhanced engine, azt használjuk
            if self.enhanced_engine and ENHANCED_MODULES_AVAILABLE:
                try:
                    recommendations = self.enhanced_engine.get_recommendations(
                        query=search_query,
                        n_recommendations=n_recommendations,
                        explanation_mode=(version == 'v2' or version == 'v3'),
                        show_scores=(version == 'v3')
                    )
                    
                    # FIXED: Ensure all required fields exist
                    fixed_recommendations = []
                    for rec in recommendations:
                        fixed_rec = self._ensure_recipe_fields(rec)
                        fixed_recommendations.append(fixed_rec)
                    
                    return fixed_recommendations
                except Exception as e:
                    print(f"⚠️ Enhanced recommendation failed: {e}")
                    # Fall back to original system
            
            # Original recommendation system (fallback)
            if not self.recipes:
                print("⚠️ No recipes available")
                return []
            
            # Egyszerű szűrés search_query alapján
            filtered_recipes = []
            
            if search_query:
                search_terms = search_query.lower().split(',')
                search_terms = [term.strip() for term in search_terms if term.strip()]
                
                for recipe in self.recipes:
                    recipe_text = (
                        str(recipe.get('ingredients', '')).lower() + ' ' +
                        str(recipe.get('name', '')).lower() + ' ' +
                        str(recipe.get('title', '')).lower() + ' ' +
                        str(recipe.get('category', '')).lower()
                    )
                    
                    # Ha bármelyik keresési kifejezés megtalálható
                    if any(term in recipe_text for term in search_terms):
                        filtered_recipes.append(recipe)
            else:
                # Ha nincs keresési kifejezés, az összes receptet adjuk vissza
                filtered_recipes = self.recipes.copy()
            
            # Limit alkalmazása
            if len(filtered_recipes) > n_recommendations:
                # Composite score alapján rendezés
                filtered_recipes.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
                filtered_recipes = filtered_recipes[:n_recommendations]
            
            # FIXED: Ensure all required fields exist for template compatibility
            fixed_recommendations = []
            for recipe in filtered_recipes:
                fixed_recipe = self._ensure_recipe_fields(recipe)
                fixed_recommendations.append(fixed_recipe)
            
            print(f"✅ Returning {len(fixed_recommendations)} recommendations for query: '{search_query}'")
            return fixed_recommendations
            
        except Exception as e:
            print(f"❌ Recommendation error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _ensure_recipe_fields(self, recipe):
        """
        FIXED: Ensure all required fields exist with fallback values
        This prevents KeyError: 'name' and similar template errors
        """
        # Create a copy to avoid modifying the original
        fixed_recipe = recipe.copy()
        
        # Ensure all required fields exist with fallbacks
        field_mapping = {
            'name': recipe.get('name', recipe.get('title', 'Névtelen Recept')),
            'title': recipe.get('title', recipe.get('name', 'Névtelen Recept')),
            'recipeid': recipe.get('recipeid', recipe.get('id', 0)),
            'id': recipe.get('id', recipe.get('recipeid', 0)),
            'ingredients': recipe.get('ingredients', 'Nincs megadva'),
            'instructions': recipe.get('instructions', ''),
            'category': recipe.get('category', 'Egyéb'),
            'images': recipe.get('images', ''),
            'HSI': recipe.get('HSI', 70),
            'ESI': recipe.get('ESI', 70),
            'PPI': recipe.get('PPI', 70),
            'composite_score': recipe.get('composite_score', 70),
            'show_scores': recipe.get('show_scores', False),
            'show_explanation': recipe.get('show_explanation', False),
            'explanation': recipe.get('explanation', '')
        }
        
        # Apply the field mapping
        for field, value in field_mapping.items():
            fixed_recipe[field] = value
        
        # Ensure numeric fields are actually numeric
        numeric_fields = ['HSI', 'ESI', 'PPI', 'composite_score', 'recipeid', 'id']
        for field in numeric_fields:
            try:
                fixed_recipe[field] = float(fixed_recipe[field])
            except (ValueError, TypeError):
                fixed_recipe[field] = 70.0 if field in ['HSI', 'ESI', 'PPI', 'composite_score'] else 0
        
        return fixed_recipe

# =============================================================================
# ADATBÁZIS ÉS RECOMMENDER INICIALIZÁCIÓ
# =============================================================================

# Database initialization
print("🔧 Initializing database...")
db = EnhancedDatabase()

# Recipe data loading with enhanced error handling
print("📋 Loading recipe data...")

try:
    # Try to load greenrec_dataset.json first (for backward compatibility)
    json_path = data_dir / "greenrec_dataset.json"
    
    if not json_path.exists():
        # Try alternative locations
        alternative_paths = [
            Path.cwd() / "greenrec_dataset.json",
            Path(__file__).parent / "greenrec_dataset.json",
            data_dir / "data.json",
            data_dir / "recipes.json"
        ]
        
        for alt_path in alternative_paths:
            if alt_path.exists():
                json_path = alt_path
                break
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            raw_recipes = json.load(f)
        
        print(f"✅ Loaded {len(raw_recipes)} recipes from {json_path}")
        
        # Enhanced normalization with documented formula
        recipes_data = []
        for recipe in raw_recipes:
            # Normalize scores (0-100 scale)
            hsi_original = float(recipe.get('HSI', 70))
            esi_original = float(recipe.get('ESI', 70))  
            ppi_original = float(recipe.get('PPI', 70))
            
            # Min-max normalization documented in research
            hsi_min, hsi_max = 0, 100
            esi_min, esi_max = 0, 100
            ppi_min, ppi_max = 0, 100
            
            # Normalize to 0-1 range first
            hsi_norm = (hsi_original - hsi_min) / (hsi_max - hsi_min) if hsi_max != hsi_min else 0.5
            esi_norm = (esi_original - esi_min) / (esi_max - esi_min) if esi_max != esi_min else 0.5
            ppi_norm = (ppi_original - ppi_min) / (ppi_max - ppi_min) if ppi_max != ppi_min else 0.5
            
            # Composite score calculation (research formula)
            # ESI is environmental IMPACT, so we use (1-esi_norm) for sustainability preference
            composite_score = (1 - esi_norm) * 0.4 + hsi_norm * 0.4 + ppi_norm * 0.2
            composite_score = composite_score * 100  # Scale to 0-100
            
            # Enhanced recipe object with FIXED field compatibility
            enhanced_recipe = {
                'id': str(recipe.get('id', recipe.get('recipeid', len(recipes_data) + 1))),
                'recipeid': int(recipe.get('recipeid', recipe.get('id', len(recipes_data) + 1))),
                'name': recipe.get('name', recipe.get('title', f"Recipe {len(recipes_data) + 1}")),
                'title': recipe.get('title', recipe.get('name', f"Recipe {len(recipes_data) + 1}")),
                'ingredients': recipe.get('ingredients', 'Ingredients not specified'),
                'instructions': recipe.get('instructions', ''),
                
                # Display scores (for template)
                'HSI': round(hsi_original, 1),
                'ESI': round(100 - esi_original, 1), # Inverted for better UX (higher = better)
                'PPI': round(ppi_original, 1),
                
                # Normalized values for calculations
                'HSI_norm': hsi_norm,
                'ESI_norm': esi_norm,
                'PPI_norm': ppi_norm,
                
                # Original values for reference
                'HSI_original': float(recipe.get('HSI', 70)),
                'ESI_original': float(recipe.get('ESI', 70)),
                'PPI_original': float(recipe.get('PPI', 70)),
                
                'category': recipe.get('category', 'Egyéb'),
                'images': recipe.get('images', ''),
                'composite_score': round(composite_score, 1),
                
                # Enhanced compatibility
                'show_scores': False,
                'show_explanation': False,
                'explanation': ""
            }
            recipes_data.append(enhanced_recipe)
        
        print(f"✅ Successfully normalized {len(recipes_data)} recipes using documented method")
        print(f"📊 Sample normalized recipe: {recipes_data[0]['name']}")
        print(f"   Display scores: HSI={recipes_data[0]['HSI']}, ESI={recipes_data[0]['ESI']}, PPI={recipes_data[0]['PPI']}")
        print(f"   Composite: {recipes_data[0]['composite_score']}")
        print(f"   Formula: (1-{recipes_data[0]['ESI_norm']:.3f})*0.4 + {recipes_data[0]['HSI_norm']:.3f}*0.4 + {recipes_data[0]['PPI_norm']:.3f}*0.2 = {recipes_data[0]['composite_score']}")
        
    except FileNotFoundError:
        print(f"⚠️ Recipe data file not found at {json_path}")
        print("🔧 Using sample recipes as fallback")
        
        # FIXED: Sample recipes with all required fields
        recipes_data = [
            {
                'id': '1',
                'recipeid': 1,
                'name': 'Magyar Gulyás',
                'title': 'Magyar Gulyás',
                'ingredients': 'marhahús, hagyma, paprika, burgonya, paradicsom',
                'instructions': 'Pirítsd meg a hagymát, add hozzá a húst, fűszerezd paprikával...',
                'HSI': 75,
                'ESI': 60,
                'PPI': 90,
                'composite_score': 75,
                'category': 'Hagyományos Magyar',
                'images': '',
                'show_scores': False,
                'show_explanation': False,
                'explanation': ""
            },
            {
                'id': '2',
                'recipeid': 2,
                'name': 'Lecsó',
                'title': 'Lecsó',
                'ingredients': 'paprika, hagyma, paradicsom, tojás, kolbász',
                'instructions': 'Párold meg a paprikát hagymával, add hozzá a paradicsomot...',
                'HSI': 80,
                'ESI': 75,
                'PPI': 85,
                'composite_score': 80,
                'category': 'Hagyományos Magyar',
                'images': '',
                'show_scores': False,
                'show_explanation': False,
                'explanation': ""
            },
            {
                'id': '3',
                'recipeid': 3,
                'name': 'Schnitzel',
                'title': 'Schnitzel',
                'ingredients': 'sertéshús, tojás, zsemlemorzsa, olaj',
                'instructions': 'Verd ki a húst, forgasd meg tojásban és morzsában...',
                'HSI': 65,
                'ESI': 50,
                'PPI': 85,
                'composite_score': 67,
                'category': 'Hús',
                'images': '',
                'show_scores': False,
                'show_explanation': False,
                'explanation': ""
            }
        ]
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        recipes_data = []
    
    except Exception as e:
        print(f"❌ Unexpected error loading recipes: {e}")
        recipes_data = []
    
    # Initialize recommender with error handling
    if recipes_data:
        recommender = RecommendationEngine(recipes_data)
        print(f"✅ Recommender initialized with {len(recipes_data)} recipes")
    else:
        print("❌ No recipes loaded, using empty recommender")
        recommender = RecommendationEngine([])

except Exception as e:
    print(f"❌ Critical error during initialization: {e}")
    import traceback
    traceback.print_exc()
    # Ultimate fallback
    recommender = RecommendationEngine([])
    print("⚠️ Using empty recommender as fallback")

def get_user_version():
    """A/B/C verzió kiválasztása"""
    if 'version' not in session:
        session['version'] = random.choice(['v1', 'v2', 'v3'])
    return session['version']

# =============================================================================
# ROUTE-OK
# =============================================================================

@user_study_bp.route('/')
@user_study_bp.route('/welcome')
def welcome():
    return render_template('welcome.html')

@user_study_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            # Enhanced registration logika
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            display_name = request.form.get('display_name', '').strip()
            
            # Alapvető validáció
            if not email or not password:
                return render_template('register.html', error='Email és jelszó megadása kötelező')
            
            if len(password) < 6:
                return render_template('register.html', error='A jelszó legalább 6 karakter hosszú legyen')
            
            # User létrehozása
            version = get_user_version()
            user_id = db.create_user(email, password, display_name, version)
            if not user_id:
                return render_template('register.html', error='Ez az email cím már regisztrált')
            
            # Profil adatok
            profile_data = {
                'age_group': request.form.get('age_group'),
                'education': request.form.get('education'),
                'cooking_frequency': request.form.get('cooking_frequency'),
                'sustainability_awareness': int(request.form.get('sustainability_awareness', 3))
            }
            
            # Profil mentése
            db.create_user_profile(user_id, profile_data)
            
            # Session beállítása
            session['user_id'] = user_id
            session['email'] = email
            session['display_name'] = display_name or email.split('@')[0]
            session['is_returning_user'] = False  # Új user
            
            # Verzió kiválasztása (megtartjuk az eredeti logikát)
            version = get_user_version()
            session['version'] = version
            
            print(f"✅ New user registered: {email}")
            
            return redirect(url_for('user_study.instructions'))
            
        except Exception as e:
            print(f"Registration error: {e}")
            return render_template('register.html', error='Regisztráció sikertelen')
    
    # GET request - regisztráció form megjelenítése
    return render_template('register.html')
    
# Login route hozzáadása a register után
@user_study_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email or not password:
            return render_template('login.html', error='Email és jelszó megadása kötelező', email=email)
        
        # User authentication
        user = db.authenticate_user(email, password)
        if user:
            # Session setup
            session['user_id'] = user['user_id']
            session['email'] = user['email']
            session['display_name'] = user['display_name']
            session['is_returning_user'] = True
            
            print(f"✅ User logged in: {email}")
            
            # Redirect to study (később lehet dashboard)
            return redirect(url_for('user_study.instructions'))
        else:
            return render_template('login.html', error='Hibás email vagy jelszó', email=email)
    
    return render_template('login.html')

@user_study_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('user_study.welcome'))

@user_study_bp.route('/instructions')
def instructions():
    if 'user_id' not in session:
        return redirect(url_for('user_study.register'))
    
    version = session.get('version', 'v1')
    return render_template('instructions.html', version=version)

@user_study_bp.route('/study')
def study():
    """
    FIXED: Study route with proper error handling and field validation
    """
    if 'user_id' not in session:
        return redirect(url_for('user_study.register'))
    
    version = session.get('version', 'v1')
    search_query = request.args.get('search', '').strip()
    
    try:
        # Get recommendations with proper error handling
        recommendations = recommender.recommend(
            search_query=search_query,  # First parameter
            n_recommendations=5,        # Second parameter  
            version=version            # Third parameter
        )
        
        # FIXED: Ensure recommendations is a list and validate each item
        if not isinstance(recommendations, list):
            recommendations = []
        
        # Validate each recommendation has required fields
        validated_recommendations = []
        for rec in recommendations:
            try:
                # Ensure all required fields exist
                validated_rec = recommender._ensure_recipe_fields(rec)
                validated_recommendations.append(validated_rec)
            except Exception as rec_error:
                print(f"⚠️ Recipe validation error: {rec_error}")
                # Skip this recipe instead of crashing
                continue
        
        recommendations = validated_recommendations
        
        print(f"✅ Study route: returning {len(recommendations)} validated recommendations")
        
    except Exception as e:
        print(f"❌ Study route error: {e}")
        import traceback
        traceback.print_exc()
        recommendations = []
    
    # FIXED: Single return statement with proper parameters
    return render_template('study.html', 
                         recommendations=recommendations,
                         search_query=search_query,
                         version=version)

@user_study_bp.route('/rate_recipe', methods=['POST'])
def rate_recipe():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    data = request.get_json()
    
    recipe_id = int(data.get('recipe_id'))
    rating = int(data.get('rating'))
    explanation_helpful = data.get('explanation_helpful')
    view_time = data.get('view_time_seconds', 0)
    
    db.log_interaction(user_id, recipe_id, rating, explanation_helpful, view_time)
    
    return jsonify({'status': 'success'})

@user_study_bp.route('/questionnaire', methods=['GET', 'POST'])
def questionnaire():
    if 'user_id' not in session:
        return redirect(url_for('user_study.register'))
    
    if request.method == 'POST':
        user_id = session['user_id']
        
        responses = {
            'system_usability': request.form.get('system_usability'),
            'recommendation_quality': request.form.get('recommendation_quality'),
            'trust_level': request.form.get('trust_level'),
            'explanation_clarity': request.form.get('explanation_clarity'),
            'sustainability_importance': request.form.get('sustainability_importance'),
            'overall_satisfaction': request.form.get('overall_satisfaction'),
            'additional_comments': request.form.get('additional_comments', '')
        }
        
        db.save_questionnaire(user_id, responses)
        return redirect(url_for('user_study.thank_you'))
    
    version = session.get('version', 'v1')
    return render_template('questionnaire.html', version=version)

@user_study_bp.route('/thank_you')
def thank_you():
    version = session.get('version', 'v1')
    return render_template('thank_you.html', version=version)

# API routes for AJAX calls
@user_study_bp.route('/api/rate', methods=['POST'])
def api_rate():
    """API endpoint for rating recipes"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        user_id = session['user_id']
        recipe_id = int(data.get('recipe_id'))
        rating = int(data.get('rating'))
        explanation_helpful = data.get('explanation_helpful')
        view_time = data.get('view_time_seconds', 0)
        
        # Save to database
        db.log_interaction(user_id, recipe_id, rating, explanation_helpful, view_time)
        
        return jsonify({'status': 'success', 'message': 'Rating saved'})
        
    except Exception as e:
        print(f"❌ API rate error: {e}")
        return jsonify({'error': 'Rating failed'}), 500

@user_study_bp.route('/admin/stats')
def admin_stats():
    """Egyszerűsített admin statisztikák - kompatibilitási fix"""
    try:
        stats = db.get_stats()
        print(f"📊 Stats loaded successfully: {stats}")
        
        # Template rendering hibakezeléssel
        try:
            return render_template('admin_stats.html', stats=stats)
        except Exception as template_error:
            print(f"⚠️ Template error: {template_error}")
            
            # Fallback: egyszerű HTML válasz
            html_response = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Admin Statisztikák</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    .card {{ background: #f8f9fa; padding: 20px; margin: 10px 0; border-radius: 8px; }}
                    .export-btn {{ background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }}
                </style>
            </head>
            <body>
                <h1>📊 Admin Statisztikák</h1>
                
                <div class="card">
                    <h3>Alapvető Statisztikák</h3>
                    <p><strong>Regisztrált felhasználók:</strong> {stats.get('total_participants', 0)}</p>
                    <p><strong>Kérdőívet kitöltők:</strong> {stats.get('completed_participants', 0)}</p>
                    <p><strong>Teljesítési arány:</strong> {stats.get('completion_rate', 0):.1f}%</p>
                    <p><strong>Átlagos értékelés:</strong> {stats.get('average_rating', 0):.2f}/5</p>
                </div>
                
                <div class="card">
                    <h3>Export</h3>
                    <a href="/admin/export/csv" class="export-btn">📊 CSV Export</a>
                    <a href="/admin/export/json" class="export-btn">📄 JSON Export</a>
                </div>
            </body>
            </html>
            """
            return html_response
            
    except Exception as e:
        print(f"❌ Admin stats error: {e}")
        return f"Admin stats error: {e}", 500

@user_study_bp.route('/admin/export/csv')
def export_csv():
    """CSV export a tanulmány adatairól - TELJES export minden adattal"""
    try:
        import csv
        import io
        from datetime import datetime
        
        # 1. FELHASZNÁLÓK ÉS PROFILOK - újfajta query
        if db.is_postgres:
            participants = db.execute_query("""
                SELECT u.user_id, u.email, u.version, u.created_at,
                       p.age_group, p.education, p.cooking_frequency, p.sustainability_awareness
                FROM users u
                LEFT JOIN user_profiles p ON u.user_id = p.user_id
                ORDER BY u.user_id
            """)
            ratings = db.execute_query("SELECT * FROM recipe_ratings ORDER BY user_id, recipe_id")
            questionnaires = db.execute_query("SELECT * FROM questionnaire ORDER BY user_id")
        else:
            participants = db.execute_query("""
                SELECT u.user_id, u.email, u.version, u.created_at,
                       p.age_group, p.education, p.cooking_frequency, p.sustainability_awareness
                FROM users u
                LEFT JOIN user_profiles p ON u.user_id = p.user_id
                ORDER BY u.user_id
            """)
            ratings = db.execute_query("SELECT * FROM recipe_ratings ORDER BY user_id, recipe_id")
            questionnaires = db.execute_query("SELECT * FROM questionnaire ORDER BY user_id")
        
        # 2. RECEPTEK ADATAI a JSON fájlból (recommender objektumból)
        # A recommender már be van töltve a routes.py tetején
        recipe_lookup = {}
        for recipe in recommender.recipes:
            recipe_id = str(recipe.get('id', recipe.get('recipeid', '')))
            if recipe_id:
                recipe_lookup[recipe_id] = {
                    'name': recipe.get('name', ''),
                    'health_score': recipe.get('HSI', 0),
                    'environmental_score': recipe.get('ESI', 0),
                    'meal_score': recipe.get('PPI', 0),
                    'composite_score': recipe.get('composite_score', 0)
                }
        
        print(f"📊 Recipe lookup created: {len(recipe_lookup)} recipes loaded")
        
        # 3. ADATOK ÖSSZEKAPCSOLÁSA
        # Group data by user_id
        profiles = {p['user_id']: dict(p) for p in participants}
        questionnaire_data = {q['user_id']: dict(q) for q in questionnaires}
        
        csv_rows = []
        
        for user in participants:
            user_id = user['user_id']
            profile = profiles.get(user_id, {})
            questionnaire = questionnaire_data.get(user_id, {})
            user_ratings = [dict(r) for r in ratings if r['user_id'] == user_id]
            
            if user_ratings:
                # Van rating - minden rating-hez egy sor
                for rating in user_ratings:
                    recipe_id = str(rating.get('recipe_id', ''))
                    
                    # Receptek adatainak kikeresése a JSON-ból
                    recipe_data = recipe_lookup.get(recipe_id, {})
                    
                    csv_rows.append({
                        'user_id': user_id,
                        'group': user.get('version', ''),
                        'age': profile.get('age_group', ''),
                        'education_level': profile.get('education', ''),
                        'cooking_frequency': profile.get('cooking_frequency', ''),
                        'importance_sustainability': profile.get('sustainability_awareness', ''),
                        
                        # RECEPT ADATOK
                        'recipeid': recipe_id,
                        'recipe_name': recipe_data.get('name', 'Unknown recipe'),
                        
                        # SCORE ADATOK A JSON-BÓL
                        'health_score': recipe_data.get('health_score', ''),
                        'env_score': recipe_data.get('environmental_score', ''),
                        'meal_score': recipe_data.get('meal_score', ''),
                        'composite_score': recipe_data.get('composite_score', ''),
                        
                        # FELHASZNÁLÓI RATING
                        'rating': rating.get('rating', ''),
                        
                        # KÉRDŐÍV ADATOK
                        'usability': questionnaire.get('system_usability', ''),
                        'quality': questionnaire.get('recommendation_quality', ''),
                        'trust': questionnaire.get('trust_level', ''),
                        'satisfaction': questionnaire.get('overall_satisfaction', ''),
                        'comment': questionnaire.get('additional_comments', '')
                    })
            else:
                # Nincs rating - csak demographic adat
                csv_rows.append({
                    'user_id': user_id,
                    'group': user.get('version', ''),
                    'age': profile.get('age_group', ''),
                    'education_level': profile.get('education', ''),
                    'cooking_frequency': profile.get('cooking_frequency', ''),
                    'importance_sustainability': profile.get('sustainability_awareness', ''),
                    'recipeid': '',
                    'recipe_name': '',
                    'health_score': '',
                    'env_score': '',
                    'meal_score': '',
                    'composite_score': '',
                    'rating': '',
                    'usability': questionnaire.get('system_usability', ''),
                    'quality': questionnaire.get('recommendation_quality', ''),
                    'trust': questionnaire.get('trust_level', ''),
                    'satisfaction': questionnaire.get('overall_satisfaction', ''),
                    'comment': questionnaire.get('additional_comments', '')
                })
        
        # 4. CSV ÍRÁS
        output = io.StringIO()
        if csv_rows:
            fieldnames = csv_rows[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)
        else:
            # Empty fallback
            writer = csv.writer(output)
            writer.writerow(['message'])
            writer.writerow(['No data available'])
        
        # Response
        output.seek(0)
        csv_data = output.getvalue()
        output.close()
        
        response = make_response(csv_data)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=study_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return response
        
    except Exception as e:
        print(f"❌ CSV Export error: {e}")
        import traceback
        traceback.print_exc()
        return f"CSV Export error: {e}", 500

@user_study_bp.route('/admin/export/json')
def export_json():
    """JSON export a tanulmány adatairól"""
    try:
        stats = db.get_stats()
        
        # Export metadata hozzáadása
        export_data = {
            'export_date': datetime.now().isoformat(),
            'export_version': '1.0',
            'study_name': 'Sustainable Recipe Recommender Study',
            'data': stats
        }
        
        response = make_response(json.dumps(export_data, indent=2, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=study_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        return response
        
    except Exception as e:
        return f"JSON Export error: {e}", 500

# Debug és health check endpoints
@user_study_bp.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'recipes_loaded': len(recommender.recipes),
        'database_connected': db.conn is not None,
        'enhanced_modules': ENHANCED_MODULES_AVAILABLE
    })

@user_study_bp.route('/debug/status')
def debug_status():
    """Debug information"""
    return jsonify({
        'recipes_count': len(recommender.recipes),
        'database_type': 'PostgreSQL' if db.is_postgres else 'SQLite',
        'enhanced_available': ENHANCED_MODULES_AVAILABLE,
        'sample_recipe': recommender.recipes[0] if recommender.recipes else None
    })

@user_study_bp.route('/metrics')
def metrics():
    """Metrics endpoint for monitoring"""
    try:
        stats = db.get_stats()
        return jsonify({
            'total_users': stats.get('total_participants', 0),
            'completed_users': stats.get('completed_participants', 0),
            'completion_rate': stats.get('completion_rate', 0),
            'avg_rating': stats.get('average_rating', 0)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
