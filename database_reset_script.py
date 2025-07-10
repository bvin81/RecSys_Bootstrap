#!/usr/bin/env python3
"""
ADATBÁZIS RESET SCRIPT - database_reset_script.py
Törli a szimulációs adatokat a nudging teszt újrafuttatásához

HASZNÁLAT:
1. Másold ki ezt a kódot egy database_reset_script.py fájlba
2. Futtasd: python database_reset_script.py
3. Erősítsd meg a törlést
4. Futtatsd a sym_nudge.py szimulációt
"""

import psycopg2
import os
import logging
from datetime import datetime

# Logging beállítás
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_connection():
    """Adatbázis kapcsolat létrehozása"""
    try:
        # Heroku Postgres URL vagy helyi beállítás
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            conn = psycopg2.connect(database_url, sslmode='require')
        else:
            # Helyi PostgreSQL beállítások
            conn = psycopg2.connect(
                host=os.environ.get('DB_HOST', 'localhost'),
                database=os.environ.get('DB_NAME', 'greenrec'),
                user=os.environ.get('DB_USER', 'postgres'),
                password=os.environ.get('DB_PASSWORD', 'password'),
                port=os.environ.get('DB_PORT', '5432')
            )
        return conn
    except Exception as e:
        logger.error(f"❌ Adatbázis kapcsolódási hiba: {e}")
        return None

def backup_current_data():
    """Jelenlegi adatok biztonsági mentése"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cur = conn.cursor()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # User choices backup
        cur.execute("SELECT COUNT(*) FROM user_choices")
        choices_count = cur.fetchone()[0]
        
        # Recommendation sessions backup  
        cur.execute("SELECT COUNT(*) FROM recommendation_sessions")
        sessions_count = cur.fetchone()[0]
        
        # Users backup
        cur.execute("SELECT COUNT(*) FROM users WHERE username LIKE 'user_%'")
        test_users_count = cur.fetchone()[0]
        
        logger.info(f"📊 BACKUP INFORMÁCIÓ:")
        logger.info(f"   User choices: {choices_count} db")
        logger.info(f"   Sessions: {sessions_count} db") 
        logger.info(f"   Test users: {test_users_count} db")
        logger.info(f"   Backup timestamp: {timestamp}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Backup hiba: {e}")
        return False

def reset_simulation_data():
    """Szimulációs adatok törlése"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cur = conn.cursor()
        
        logger.info("🗑️  SZIMULÁCIÓS ADATOK TÖRLÉSE...")
        
        # 1. User choices törlése
        cur.execute("DELETE FROM user_choices")
        deleted_choices = cur.rowcount
        logger.info(f"   ✅ User choices törölve: {deleted_choices} db")
        
        # 2. Recommendation sessions törlése  
        cur.execute("DELETE FROM recommendation_sessions")
        deleted_sessions = cur.rowcount
        logger.info(f"   ✅ Sessions törölve: {deleted_sessions} db")
        
        # 3. Test felhasználók törlése (user_ prefixszel)
        cur.execute("DELETE FROM users WHERE username LIKE 'user_%' OR username LIKE 'fixed_%'")
        deleted_users = cur.rowcount
        logger.info(f"   ✅ Test users törölve: {deleted_users} db")
        
        # 4. Sequence-k reset (ha szükséges)
        cur.execute("SELECT setval('users_id_seq', (SELECT MAX(id) FROM users))")
        cur.execute("SELECT setval('user_choices_id_seq', 1, false)")
        cur.execute("SELECT setval('recommendation_sessions_id_seq', 1, false)")
        
        # Commit changes
        conn.commit()
        logger.info("✅ Adatbázis sikeresen resetelve!")
        
        # Verification
        cur.execute("SELECT COUNT(*) FROM user_choices")
        remaining_choices = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM recommendation_sessions") 
        remaining_sessions = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM users WHERE username LIKE 'user_%'")
        remaining_test_users = cur.fetchone()[0]
        
        logger.info(f"📊 ELLENŐRZÉS RESET UTÁN:")
        logger.info(f"   User choices: {remaining_choices} db")
        logger.info(f"   Sessions: {remaining_sessions} db")
        logger.info(f"   Test users: {remaining_test_users} db")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Reset hiba: {e}")
        return False

def preserve_real_users():
    """Valódi felhasználók megőrzése (nem test users)"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cur = conn.cursor()
        
        # Valódi felhasználók száma
        cur.execute("SELECT COUNT(*) FROM users WHERE username NOT LIKE 'user_%' AND username NOT LIKE 'fixed_%'")
        real_users_count = cur.fetchone()[0]
        
        logger.info(f"🔒 VALÓDI FELHASZNÁLÓK MEGŐRIZVE: {real_users_count} db")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Felhasználó ellenőrzési hiba: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 ADATBÁZIS RESET INDÍTÁSA")
    logger.info("🎯 Cél: Nudging szimulációhoz való előkészítés")
    
    # 1. Backup jelenlegi adatok
    logger.info("\n📦 1. BIZTONSÁGI MENTÉS...")
    if backup_current_data():
        logger.info("✅ Backup sikeres")
    else:
        logger.error("❌ Backup sikertelen")
        exit(1)
    
    # 2. Megerősítés kérése
    print("\n⚠️  FIGYELEM: Ez törölni fogja az összes szimulációs adatot!")
    print("   - User choices")
    print("   - Recommendation sessions") 
    print("   - Test felhasználók (user_*, fixed_*)")
    print("   - Valódi felhasználók megmaradnak")
    
    confirm = input("\n💭 Biztosan folytatod? (igen/nem): ").lower().strip()
    
    if confirm not in ['igen', 'yes', 'y', 'i']:
        logger.info("❌ Reset megszakítva felhasználó által")
        exit(0)
    
    # 3. Reset végrehajtása
    logger.info("\n🗑️  2. RESET VÉGREHAJTÁSA...")
    if reset_simulation_data():
        logger.info("✅ Reset sikeres")
    else:
        logger.error("❌ Reset sikertelen")
        exit(1)
    
    # 4. Valódi felhasználók ellenőrzése
    logger.info("\n🔒 3. VALÓDI FELHASZNÁLÓK ELLENŐRZÉSE...")
    if preserve_real_users():
        logger.info("✅ Valódi felhasználók biztonságban")
    else:
        logger.warning("⚠️  Valódi felhasználók ellenőrzése sikertelen")
    
    logger.info("\n🎉 ADATBÁZIS RESET BEFEJEZVE!")
    logger.info("🚀 Most futtathatod a sym_nudge.py szimulációt:")
    logger.info("   python sym_nudge.py")
