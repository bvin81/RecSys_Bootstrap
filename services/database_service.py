# services/database_service.py - PostgreSQL Integráció
"""
GreenRec Database Service
========================
PostgreSQL integráció Heroku környezethez.
Perzisztens adattárolás user sessions, ratings, analytics számára.
"""

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)

class DatabaseService:
    """PostgreSQL adatbázis szolgáltatás"""
    
    def __init__(self):
        self.database_url = Config.DATABASE_URL
        if self.database_url and self.database_url.startswith('postgres://'):
            # Heroku Postgres URL fix
            self.database_url = self.database_url.replace('postgres://', 'postgresql://', 1)
        
        self.initialized = False
        self._init_database()
    
    def _init_database(self):
        """Adatbázis táblák inicializálása"""
        if not self.database_url:
            logger.warning("⚠️ No DATABASE_URL found, using session-based storage")
            return
        
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                
                # User sessions tábla
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        user_id VARCHAR(100) PRIMARY KEY,
                        user_group VARCHAR(1) NOT NULL CHECK (user_group IN ('A', 'B', 'C')),
                        learning_round INTEGER DEFAULT 1 CHECK (learning_round >= 1 AND learning_round <= 5),
                        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed BOOLEAN DEFAULT FALSE,
                        session_data JSONB DEFAULT '{}'::jsonb
                    )
                """)
                
                # Recipe ratings tábla  
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS recipe_ratings (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(100) NOT NULL,
                        recipe_id VARCHAR(100) NOT NULL,
                        rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
                        learning_round INTEGER NOT NULL CHECK (learning_round >= 1 AND learning_round <= 5),
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        additional_data JSONB DEFAULT '{}'::jsonb,
                        UNIQUE(user_id, recipe_id, learning_round)
                    )
                """)
                
                # Analytics metrics tábla
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS analytics_metrics (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(100) NOT NULL,
                        user_group VARCHAR(1) NOT NULL CHECK (user_group IN ('A', 'B', 'C')),
                        learning_round INTEGER NOT NULL CHECK (learning_round >= 1 AND learning_round <= 5),
                        precision_at_5 FLOAT CHECK (precision_at_5 >= 0 AND precision_at_5 <= 1),
                        recall_at_5 FLOAT CHECK (recall_at_5 >= 0 AND recall_at_5 <= 1),
                        f1_at_5 FLOAT CHECK (f1_at_5 >= 0 AND f1_at_5 <= 1),
                        avg_rating FLOAT CHECK (avg_rating >= 1 AND avg_rating <= 5),
                        relevant_count INTEGER DEFAULT 0,
                        recommended_count INTEGER DEFAULT 0,
                        diversity_score FLOAT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metrics_data JSONB DEFAULT '{}'::jsonb
                    )
                """)
                
                # Search interactions tábla (keresési viselkedés tracking)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS search_interactions (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(100) NOT NULL,
                        user_group VARCHAR(1) NOT NULL,
                        search_query TEXT NOT NULL,
                        results_count INTEGER DEFAULT 0,
                        clicked_results JSONB DEFAULT '[]'::jsonb,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Indexek létrehozása teljesítményért
                cur.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_recipe_ratings_user_id ON recipe_ratings(user_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_recipe_ratings_learning_round ON recipe_ratings(learning_round)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_analytics_user_group ON analytics_metrics(user_group)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_analytics_learning_round ON analytics_metrics(learning_round)")
                
                conn.commit()
                self.initialized = True
                logger.info("✅ PostgreSQL database initialized")
                
        except Exception as e:
            logger.error(f"❌ Database initialization error: {e}")
            self.initialized = False
    
    @contextmanager
    def get_connection(self):
        """PostgreSQL kapcsolat context manager"""
        if not self.database_url:
            raise Exception("No database URL configured")
        
        conn = None
        try:
            conn = psycopg2.connect(self.database_url, sslmode='require')
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    # ============================================
    # USER SESSION OPERATIONS
    # ============================================
    
    def save_user_session(self, user_id: str, user_group: str, learning_round: int = 1, 
                         session_data: Dict = None) -> bool:
        """User session mentése PostgreSQL-be"""
        if not self.initialized:
            return False
        
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO user_sessions (user_id, user_group, learning_round, session_data, last_activity)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        learning_round = %s,
                        session_data = %s,
                        last_activity = CURRENT_TIMESTAMP
                """, (
                    user_id, user_group, learning_round, 
                    psycopg2.extras.Json(session_data or {}),
                    learning_round,
                    psycopg2.extras.Json(session_data or {})
                ))
                conn.commit()
                logger.info(f"💾 User session saved: {user_id} (Group {user_group}, Round {learning_round})")
                return True
                
        except Exception as e:
            logger.error(f"❌ Save user session error: {e}")
            return False
    
    def get_user_session(self, user_id: str) -> Optional[Dict]:
        """User session lekérése PostgreSQL-ből"""
        if not self.initialized:
            return None
        
        try:
            with self.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("""
                    SELECT user_id, user_group, learning_round, start_time, 
                           last_activity, completed, session_data
                    FROM user_sessions 
                    WHERE user_id = %s
                """, (user_id,))
                
                result = cur.fetchone()
                if result:
                    return dict(result)
                return None
                
        except Exception as e:
            logger.error(f"❌ Get user session error: {e}")
            return None
    
    # ============================================
    # RECIPE RATING OPERATIONS  
    # ============================================
    
    def save_rating(self, user_id: str, recipe_id: str, rating: int, 
                   learning_round: int, additional_data: Dict = None) -> bool:
        """Recept értékelés mentése PostgreSQL-be"""
        if not self.initialized:
            return False
        
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO recipe_ratings 
                    (user_id, recipe_id, rating, learning_round, additional_data)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, recipe_id, learning_round)
                    DO UPDATE SET 
                        rating = %s,
                        additional_data = %s,
                        timestamp = CURRENT_TIMESTAMP
                """, (
                    user_id, recipe_id, rating, learning_round,
                    psycopg2.extras.Json(additional_data or {}),
                    rating,
                    psycopg2.extras.Json(additional_data or {})
                ))
                conn.commit()
                logger.info(f"⭐ Rating saved: {user_id} rated {recipe_id} = {rating} (Round {learning_round})")
                return True
                
        except Exception as e:
            logger.error(f"❌ Save rating error: {e}")
            return False
    
    def get_user_ratings(self, user_id: str, learning_round: Optional[int] = None) -> Dict[str, int]:
        """User értékelések lekérése PostgreSQL-ből"""
        if not self.initialized:
            return {}
        
        try:
            with self.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                if learning_round:
                    cur.execute("""
                        SELECT recipe_id, rating 
                        FROM recipe_ratings 
                        WHERE user_id = %s AND learning_round = %s
                    """, (user_id, learning_round))
                else:
                    cur.execute("""
                        SELECT recipe_id, rating 
                        FROM recipe_ratings 
                        WHERE user_id = %s
                    """, (user_id,))
                
                results = cur.fetchall()
                return {row['recipe_id']: row['rating'] for row in results}
                
        except Exception as e:
            logger.error(f"❌ Get user ratings error: {e}")
            return {}
    
    def get_all_user_ratings(self, user_id: str) -> Dict[int, Dict[str, int]]:
        """Összes user értékelés csoportosítva körönként"""
        if not self.initialized:
            return {}
        
        try:
            with self.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("""
                    SELECT learning_round, recipe_id, rating 
                    FROM recipe_ratings 
                    WHERE user_id = %s
                    ORDER BY learning_round, timestamp
                """, (user_id,))
                
                results = cur.fetchall()
                ratings_by_round = {}
                
                for row in results:
                    round_num = row['learning_round']
                    if round_num not in ratings_by_round:
                        ratings_by_round[round_num] = {}
                    ratings_by_round[round_num][row['recipe_id']] = row['rating']
                
                return ratings_by_round
                
        except Exception as e:
            logger.error(f"❌ Get all user ratings error: {e}")
            return {}
    
    # ============================================
    # ANALYTICS OPERATIONS
    # ============================================
    
    def save_metrics(self, user_id: str, user_group: str, learning_round: int, 
                    metrics: Dict[str, float], additional_data: Dict = None) -> bool:
        """Metrikák mentése PostgreSQL-be"""
        if not self.initialized:
            return False
        
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO analytics_metrics 
                    (user_id, user_group, learning_round, precision_at_5, recall_at_5, 
                     f1_at_5, avg_rating, relevant_count, recommended_count, 
                     diversity_score, metrics_data)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id, user_group, learning_round,
                    metrics.get('precision_at_5', 0),
                    metrics.get('recall_at_5', 0),
                    metrics.get('f1_at_5', 0),
                    metrics.get('avg_rating', 0),
                    metrics.get('relevant_count', 0),
                    metrics.get('recommended_count', 0),
                    metrics.get('diversity_score'),
                    psycopg2.extras.Json(additional_data or {})
                ))
                conn.commit()
                logger.info(f"📊 Metrics saved: {user_id} Round {learning_round} F1={metrics.get('f1_at_5', 0):.3f}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Save metrics error: {e}")
            return False
    
    def get_analytics_summary(self) -> Dict[str, Any]:
        """Analytics összefoglaló lekérése A/B/C csoportonként"""
        if not self.initialized:
            return {}
        
        try:
            with self.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                # Csoportonkénti összesítő statisztikák
                cur.execute("""
                    SELECT 
                        user_group,
                        COUNT(*) as total_measurements,
                        COUNT(DISTINCT user_id) as unique_users,
                        AVG(precision_at_5) as avg_precision,
                        AVG(recall_at_5) as avg_recall,
                        AVG(f1_at_5) as avg_f1,
                        AVG(avg_rating) as avg_user_rating,
                        STDDEV(f1_at_5) as f1_stddev,
                        MAX(learning_round) as max_round_reached
                    FROM analytics_metrics 
                    GROUP BY user_group 
                    ORDER BY user_group
                """)
                
                group_stats = {}
                for row in cur.fetchall():
                    group_stats[row['user_group']] = dict(row)
                
                # Tanulási görbék körönként
                cur.execute("""
                    SELECT 
                        user_group,
                        learning_round,
                        AVG(f1_at_5) as avg_f1_score,
                        AVG(precision_at_5) as avg_precision,
                        AVG(recall_at_5) as avg_recall,
                        COUNT(*) as measurements
                    FROM analytics_metrics 
                    GROUP BY user_group, learning_round 
                    ORDER BY user_group, learning_round
                """)
                
                learning_curves = {}
                for row in cur.fetchall():
                    group = row['user_group']
                    if group not in learning_curves:
                        learning_curves[group] = []
                    learning_curves[group].append(dict(row))
                
                return {
                    'group_statistics': group_stats,
                    'learning_curves': learning_curves,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Get analytics summary error: {e}")
            return {}
    
    # ============================================
    # SEARCH TRACKING OPERATIONS
    # ============================================
    
    def track_search(self, user_id: str, user_group: str, search_query: str, 
                    results_count: int, clicked_results: List = None) -> bool:
        """Keresési viselkedés tracking PostgreSQL-be"""
        if not self.initialized:
            return False
        
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO search_interactions 
                    (user_id, user_group, search_query, results_count, clicked_results)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    user_id, user_group, search_query, results_count,
                    psycopg2.extras.Json(clicked_results or [])
                ))
                conn.commit()
                logger.info(f"🔍 Search tracked: {user_id} searched '{search_query}' ({results_count} results)")
                return True
                
        except Exception as e:
            logger.error(f"❌ Track search error: {e}")
            return False
    
    def get_search_analytics(self) -> Dict[str, Any]:
        """Keresési analytics lekérése"""
        if not self.initialized:
            return {}
        
        try:
            with self.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                # Keresési statisztikák csoportonként
                cur.execute("""
                    SELECT 
                        user_group,
                        COUNT(*) as total_searches,
                        COUNT(DISTINCT user_id) as users_who_searched,
                        AVG(results_count) as avg_results_per_search,
                        COUNT(DISTINCT search_query) as unique_queries
                    FROM search_interactions 
                    GROUP BY user_group 
                    ORDER BY user_group
                """)
                
                search_stats = {row['user_group']: dict(row) for row in cur.fetchall()}
                
                # Legnépszerűbb keresési kifejezések
                cur.execute("""
                    SELECT search_query, COUNT(*) as frequency
                    FROM search_interactions 
                    GROUP BY search_query 
                    ORDER BY frequency DESC 
                    LIMIT 20
                """)
                
                popular_queries = [dict(row) for row in cur.fetchall()]
                
                return {
                    'search_statistics': search_stats,
                    'popular_queries': popular_queries
                }
                
        except Exception as e:
            logger.error(f"❌ Get search analytics error: {e}")
            return {}
    
    # ============================================
    # EXPORT ÉS ADMIN FUNKCIÓK
    # ============================================
    
    def export_all_data(self) -> Dict[str, Any]:
        """Összes adat exportálása (admin funkcióhoz)"""
        if not self.initialized:
            return {'error': 'Database not initialized'}
        
        try:
            with self.get_connection() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                export_data = {
                    'export_timestamp': datetime.now().isoformat(),
                    'database_status': 'connected'
                }
                
                # User sessions export
                cur.execute("SELECT * FROM user_sessions ORDER BY start_time")
                export_data['user_sessions'] = [dict(row) for row in cur.fetchall()]
                
                # Recipe ratings export
                cur.execute("SELECT * FROM recipe_ratings ORDER BY timestamp")
                export_data['recipe_ratings'] = [dict(row) for row in cur.fetchall()]
                
                # Analytics metrics export
                cur.execute("SELECT * FROM analytics_metrics ORDER BY timestamp")
                export_data['analytics_metrics'] = [dict(row) for row in cur.fetchall()]
                
                # Search interactions export
                cur.execute("SELECT * FROM search_interactions ORDER BY timestamp")
                export_data['search_interactions'] = [dict(row) for row in cur.fetchall()]
                
                # Summary statistics
                export_data['summary'] = {
                    'total_users': len(export_data['user_sessions']),
                    'total_ratings': len(export_data['recipe_ratings']),
                    'total_metrics': len(export_data['analytics_metrics']),
                    'total_searches': len(export_data['search_interactions'])
                }
                
                logger.info(f"📤 Data export completed: {export_data['summary']}")
                return export_data
                
        except Exception as e:
            logger.error(f"❌ Export all data error: {e}")
            return {'error': str(e)}
    
    def get_database_status(self) -> Dict[str, Any]:
        """Adatbázis állapot lekérése"""
        status = {
            'initialized': self.initialized,
            'database_url_configured': bool(self.database_url),
            'connection_test': False
        }
        
        if self.initialized:
            try:
                with self.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT 1")
                    status['connection_test'] = True
                    
                    # Táblák számának ellenőrzése
                    cur.execute("""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name IN ('user_sessions', 'recipe_ratings', 'analytics_metrics', 'search_interactions')
                    """)
                    status['tables_count'] = cur.fetchone()[0]
                    
            except Exception as e:
                status['connection_error'] = str(e)
        
        return status

# Singleton instance
_db_service = None

def get_database_service() -> DatabaseService:
    """Database service singleton"""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service

# Export
__all__ = ['DatabaseService', 'get_database_service']
