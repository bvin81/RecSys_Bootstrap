#!/usr/bin/env python3
"""
SESSIONS GENERATOR - Meglévő Választásokból
Létrehozza a hiányzó recommendation_sessions bejegyzéseket
a user_choices alapján a precision/recall számításhoz
"""

import psycopg2
import os
import random
from urllib.parse import urlparse
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

def get_database_connection():
    """PostgreSQL kapcsolat létrehozása"""
    try:
        database_url = os.environ.get('DATABASE_URL')
        url = urlparse(database_url)
        conn = psycopg2.connect(
            host=url.hostname,
            database=url.path[1:],
            user=url.username,
            password=url.password,
            port=url.port,
            sslmode='require'
        )
        logger.info("✅ PostgreSQL kapcsolat létrehozva")
        return conn
    except Exception as e:
        logger.error(f"❌ Adatbázis kapcsolódási hiba: {e}")
        return None

def load_recipes_data(conn):
    """Receptek betöltése az adatbázisból"""
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, title, hsi, esi, ppi FROM recipes")
        recipes = {}
        
        for row in cur.fetchall():
            recipe_id, title, hsi, esi, ppi = row
            recipes[recipe_id] = {
                'id': recipe_id,
                'title': title,
                'hsi': hsi,
                'esi': esi,
                'ppi': ppi
            }
        
        cur.close()
        logger.info(f"📚 {len(recipes)} recept betöltve")
        return recipes
    except Exception as e:
        logger.error(f"❌ Receptek betöltési hiba: {e}")
        return {}

def get_user_choices(conn):
    """Felhasználói választások lekérése"""
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.username, u.group_name, uc.recipe_id, uc.selected_at
            FROM users u
            JOIN user_choices uc ON u.id = uc.user_id
            WHERE u.username LIKE 'real_%'
            ORDER BY u.id, uc.selected_at
        """)
        
        choices = []
        for row in cur.fetchall():
            user_id, username, group_name, recipe_id, selected_at = row
            choices.append({
                'user_id': user_id,
                'username': username,
                'group_name': group_name,
                'recipe_id': recipe_id,
                'selected_at': selected_at
            })
        
        cur.close()
        logger.info(f"🎯 {len(choices)} választás betöltve")
        return choices
    except Exception as e:
        logger.error(f"❌ Választások betöltési hiba: {e}")
        return []

def create_recommendation_sessions(conn, choices, recipes):
    """Recommendation sessions létrehozása a választások alapján"""
    try:
        cur = conn.cursor()
        
        # Először ellenőrizzük, hogy létezik-e a tábla
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'recommendation_sessions'
            );
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            logger.info("📋 recommendation_sessions tábla létrehozása...")
            # Külön tranzakcióban hozzuk létre a táblát
            conn.commit()  # Jelenlegi tranzakció lezárása
            
            cur.execute("""
                CREATE TABLE recommendation_sessions (
                    session_id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    round_number INTEGER DEFAULT 1,
                    recommendation_types TEXT,
                    timestamp TIMESTAMP,
                    recipe_ids TEXT,
                    user_group VARCHAR(1)
                )
            """)
            conn.commit()  # Tábla létrehozás kommitálása
            logger.info("✅ recommendation_sessions tábla létrehozva")
        
        # Felhasználók csoportosítása
        user_groups = {}
        for choice in choices:
            user_id = choice['user_id']
            if user_id not in user_groups:
                user_groups[user_id] = {
                    'username': choice['username'],
                    'group_name': choice['group_name'],
                    'choices': []
                }
            user_groups[user_id]['choices'].append(choice)
        
        session_id = 1
        sessions_created = 0
        
        logger.info("📝 Sessions beszúrása...")
        
        for user_id, user_data in user_groups.items():
            user_choices = user_data['choices']
            group_name = user_data['group_name']
            
            # 5 receptes session-öket hozunk létre a választásokból
            for i in range(0, len(user_choices), 5):
                session_choices = user_choices[i:i+5]
                
                # Ha kevesebb mint 5 választás van, random receptekkel egészítjük ki
                while len(session_choices) < 5:
                    # Random recept választása
                    random_recipe_id = random.choice(list(recipes.keys()))
                    fake_choice = {
                        'recipe_id': random_recipe_id,
                        'selected_at': session_choices[-1]['selected_at'] if session_choices else None
                    }
                    session_choices.append(fake_choice)
                
                # Recipe ID-k string-be összefűzése
                recipe_ids = ",".join([str(choice['recipe_id']) for choice in session_choices[:5]])
                
                # Recommendation types JSON
                recommendation_types = '{"1": "baseline", "2": "baseline", "3": "baseline", "4": "baseline", "5": "baseline"}'
                
                # Session beszúrása
                cur.execute("""
                    INSERT INTO recommendation_sessions 
                    (user_id, round_number, recommendation_types, timestamp, recipe_ids, user_group)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    1,
                    recommendation_types,
                    session_choices[0]['selected_at'],
                    recipe_ids,
                    group_name
                ))
                sessions_created += 1
                session_id += 1
        
        conn.commit()
        cur.close()
        logger.info(f"✅ {sessions_created} recommendation session létrehozva")
        return sessions_created
    except Exception as e:
        logger.error(f"❌ Sessions létrehozási hiba: {e}")
        # Rollback és újra próbálkozás
        conn.rollback()
        return 0

def validate_sessions(conn):
    """Sessions validálása"""
    try:
        cur = conn.cursor()
        
        # Sessions számolása
        cur.execute("SELECT COUNT(*) FROM recommendation_sessions")
        total_sessions = cur.fetchone()[0]
        
        # Csoportonkénti sessions
        cur.execute("SELECT user_group, COUNT(*) FROM recommendation_sessions GROUP BY user_group")
        group_sessions = dict(cur.fetchall())
        
        cur.close()
        
        logger.info("\n📊 SESSIONS VALIDÁLÁS:")
        logger.info("=" * 40)
        logger.info(f"Összes session: {total_sessions}")
        for group, count in group_sessions.items():
            logger.info(f"{group} csoport: {count} session")
        
        return total_sessions
    except Exception as e:
        logger.error(f"❌ Validálási hiba: {e}")
        return 0

def main():
    """Főprogram - sessions generálása"""
    logger.info("🔧 SESSIONS GENERATOR - Meglévő Választásokból")
    logger.info("🎯 Recommendation_sessions létrehozása precision/recall számításhoz")
    logger.info("=" * 70)
    
    conn = get_database_connection()
    if not conn:
        return
    
    try:
        # Adatok betöltése
        recipes = load_recipes_data(conn)
        if not recipes:
            logger.error("❌ Nincs recept adat")
            return
        
        choices = get_user_choices(conn)
        if not choices:
            logger.error("❌ Nincs választási adat")
            return
        
        # Sessions létrehozása
        sessions_created = create_recommendation_sessions(conn, choices, recipes)
        
        if sessions_created > 0:
            # Validálás
            validate_sessions(conn)
            
            logger.info("\n🎉 SESSIONS GENERÁLÁS BEFEJEZVE!")
            logger.info("✅ Most már a precision_recall_calculator.py használható")
            logger.info("\n📋 Következő lépés:")
            logger.info("   heroku run python precision_recall_calculator.py -a your-app-name")
        else:
            logger.error("❌ Nem sikerült sessions-t létrehozni")
        
    except Exception as e:
        logger.error(f"❌ Főprogram hiba: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
