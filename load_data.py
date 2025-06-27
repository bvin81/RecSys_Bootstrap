import os
import json
import pandas as pd
import psycopg2
from urllib.parse import urlparse
import logging

# Logging beállítása
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """PostgreSQL kapcsolat létrehozása hibakezeléssel"""
    try:
        DATABASE_URL = os.environ.get('DATABASE_URL')
        if DATABASE_URL:
            # Heroku PostgreSQL URL javítása
            if DATABASE_URL.startswith('postgres://'):
                DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
                logger.info("✅ Database URL javítva postgresql://-re")
            
            result = urlparse(DATABASE_URL)
            conn = psycopg2.connect(
                dbname=result.path[1:],
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port,
                sslmode='require'
            )
            logger.info("✅ PostgreSQL kapcsolat létrehozva (Heroku)")
            return conn
        else:
            # Helyi fejlesztés
            conn = psycopg2.connect(
                host="localhost",
                database="greenrec_local",
                user="postgres",
                password="password"
            )
            logger.info("✅ PostgreSQL kapcsolat létrehozva (helyi)")
            return conn
    except Exception as e:
        logger.error(f"❌ Adatbázis kapcsolat hiba: {e}")
        raise

def create_tables():
    """Adatbázis táblák létrehozása hibakezeléssel"""
    logger.info("🔧 Adatbázis táblák létrehozása...")
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 1. Először töröljük a függő táblákat ha léteznek
        cur.execute("DROP TABLE IF EXISTS user_interactions CASCADE;")
        cur.execute("DROP TABLE IF EXISTS user_choices CASCADE;")
        cur.execute("DROP TABLE IF EXISTS users CASCADE;")
        cur.execute("DROP TABLE IF EXISTS recipes CASCADE;")
        logger.info("🗑️  Régi táblák törölve")
        
        # 2. Users tábla létrehozása
        cur.execute("""
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                group_name CHAR(1) NOT NULL CHECK (group_name IN ('A','B','C')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("✅ Users tábla létrehozva")
        
        # 3. Recipes tábla létrehozása
        cur.execute("""
            CREATE TABLE recipes (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                hsi FLOAT NOT NULL,
                esi FLOAT NOT NULL,
                ppi FLOAT NOT NULL,
                category VARCHAR(100),
                ingredients TEXT,
                instructions TEXT,
                images TEXT
            );
        """)
        logger.info("✅ Recipes tábla létrehozva")
        
        # 4. User choices tábla létrehozása (foreign key-ekkel)
        cur.execute("""
            CREATE TABLE user_choices (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                recipe_id INTEGER REFERENCES recipes(id) ON DELETE CASCADE,
                selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("✅ User_choices tábla létrehozva")
        
        # 5. User interactions tábla létrehozása (opcionális)
        cur.execute("""
            CREATE TABLE user_interactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                recipe_id INTEGER REFERENCES recipes(id) ON DELETE CASCADE,
                action_type VARCHAR(50) NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("✅ User_interactions tábla létrehozva")
        
    except Exception as e:
        logger.error(f"❌ Tábla létrehozási hiba: {e}")
        # Ha hiba van, próbáljuk egyszerűbb módon
        logger.info("🔄 Egyszerűbb táblák létrehozása foreign key-ek nélkül...")
        
        # Fallback: táblák foreign key-ek nélkül
        cur.execute("DROP TABLE IF EXISTS user_interactions CASCADE;")
        cur.execute("DROP TABLE IF EXISTS user_choices CASCADE;")
        cur.execute("DROP TABLE IF EXISTS users CASCADE;")
        cur.execute("DROP TABLE IF EXISTS recipes CASCADE;")
        
        cur.execute("""
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                group_name CHAR(1) NOT NULL CHECK (group_name IN ('A','B','C')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cur.execute("""
            CREATE TABLE recipes (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                hsi FLOAT NOT NULL,
                esi FLOAT NOT NULL,
                ppi FLOAT NOT NULL,
                category VARCHAR(100),
                ingredients TEXT,
                instructions TEXT,
                images TEXT
            );
        """)
        
        cur.execute("""
            CREATE TABLE user_choices (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                recipe_id INTEGER,
                selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cur.execute("""
            CREATE TABLE user_interactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                recipe_id INTEGER,
                action_type VARCHAR(50) NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("✅ Egyszerű táblák létrehozva foreign key-ek nélkül")
    
    # 6. Indexek létrehozása a teljesítményért
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_group ON users(group_name);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_choices_user_id ON user_choices(user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_choices_recipe_id ON user_choices(recipe_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_recipes_category ON recipes(category);")
        logger.info("✅ Indexek létrehozva")
    except Exception as e:
        logger.warning(f"⚠️  Index létrehozási figyelmeztetés: {e}")
    
    conn.commit()
    cur.close()
    conn.close()
    logger.info("✅ Adatbázis táblák létrehozva!")

def load_json_data(json_file_path):
    """JSON adatok betöltése és DataFrame-be konvertálása"""
    try:
        logger.info(f"📁 JSON fájl beolvasása: {json_file_path}")
        
        # JSON fájl beolvasása
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        logger.info(f"📊 JSON betöltve, {len(data)} recept található")
        
        # DataFrame létrehozása
        df = pd.DataFrame(data)
        
        # Oszlopnevek standardizálása és ellenőrzése
        logger.info(f"📋 Elérhető oszlopok: {list(df.columns)}")
        
        # Oszlopnevek mapping a projektre jellemző nevek alapján
        column_mapping = {
            'recipeid': 'id',
            'recipe_id': 'id', 
            'name': 'title',
            'recipe_name': 'title',
            'nutri_score': 'hsi',
            'nutrition_score': 'hsi',
            'health_score': 'hsi',
            'HSI': 'hsi',          # 🔥 ÚJ
            'env_score': 'esi',
            'environment_score': 'esi',
            'environmental_score': 'esi',
            'ESI': 'esi',          # 🔥 ÚJ
            'meal_score': 'ppi',
            'popularity_score': 'ppi',
            'pop_score': 'ppi',
            'PPI': 'ppi'           # 🔥 ÚJ
        }
        
        # Oszlopnevek átnevezése ha szükséges
        for old_name, new_name in column_mapping.items():
            if old_name in df.columns:
                df = df.rename(columns={old_name: new_name})
                logger.info(f"🔄 Oszlop átnevezve: {old_name} → {new_name}")
        
        # Szükséges oszlopok ellenőrzése
        required_columns = ['id', 'title', 'hsi', 'esi', 'ppi']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.error(f"❌ Hiányzó oszlopok: {missing_columns}")
            logger.info(f"📋 Elérhető oszlopok: {list(df.columns)}")
            raise Exception(f"Hiányzó oszlopok: {missing_columns}")
        
        # Adatok tisztítása
        original_count = len(df)
        df = df.dropna(subset=required_columns)
        logger.info(f"🧹 {original_count - len(df)} sor eltávolítva (hiányzó adatok)")
        
        # Típuskonverziók
        df['id'] = pd.to_numeric(df['id'], errors='coerce')
        df['hsi'] = pd.to_numeric(df['hsi'], errors='coerce')
        df['esi'] = pd.to_numeric(df['esi'], errors='coerce')
        df['ppi'] = pd.to_numeric(df['ppi'], errors='coerce')
        
        # További NaN-ek eltávolítása a konverzió után
        df = df.dropna(subset=['id', 'hsi', 'esi', 'ppi'])
        
        # Alapértelmezett értékek beállítása hiányzó oszlopokhoz
        if 'category' not in df.columns:
            df['category'] = 'Általános'
        if 'ingredients' not in df.columns:
            df['ingredients'] = 'Nem elérhető'
        if 'instructions' not in df.columns:
            df['instructions'] = 'Nem elérhető'
        if 'images' not in df.columns:
            df['images'] = 'https://via.placeholder.com/300x200?text=No+Image'
        
        # Hiányzó értékek kezelése a nem kötelező oszlopokban
        df['category'] = df['category'].fillna('Általános')
        df['ingredients'] = df['ingredients'].fillna('Nem elérhető')
        df['instructions'] = df['instructions'].fillna('Nem elérhető')
        df['images'] = df['images'].fillna('https://via.placeholder.com/300x200?text=No+Image')
        
        logger.info(f"✅ {len(df)} érvényes recept előkészítve az adatbázis számára")
        return df
        
    except FileNotFoundError:
        logger.error(f"❌ JSON fájl nem található: {json_file_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON dekódolási hiba: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ JSON betöltési hiba: {e}")
        return None

def insert_recipes_to_db(df):
    """Receptek beszúrása az adatbázisba"""
    try:
        logger.info(f"💾 {len(df)} recept beszúrása az adatbázisba...")
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Régi receptek törlése
        cur.execute("DELETE FROM recipes;")
        logger.info("🗑️  Régi receptek törölve")
        
        # Új receptek beszúrása
        insert_count = 0
        for _, recipe in df.iterrows():
            try:
                cur.execute("""
                    INSERT INTO recipes (id, title, hsi, esi, ppi, category, ingredients, instructions, images)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        int(recipe['id']),
                        str(recipe['title'])[:255],  # Limit title length
                        float(recipe['hsi']),
                        float(recipe['esi']),
                        float(recipe['ppi']),
                        str(recipe['category'])[:100],  # Limit category length
                        str(recipe['ingredients']),
                        str(recipe['instructions']),
                        str(recipe['images'])
                    ))
                insert_count += 1
            except Exception as e:
                logger.warning(f"⚠️  Recept beszúrási hiba (ID: {recipe.get('id', 'N/A')}): {e}")
                continue
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ {insert_count} recept sikeresen beszúrva az adatbázisba!")
        
    except Exception as e:
        logger.error(f"❌ Adatbázis beszúrási hiba: {e}")
        raise

def create_sample_data():
    """Minta adatok létrehozása ha nincs JSON fájl"""
    logger.info("🔧 Minta adatok létrehozása...")
    
    sample_recipes = [
        {
            'id': 1,
            'title': 'Zöldséges quinoa saláta',
            'hsi': 85.5,
            'esi': 45.2,
            'ppi': 78.0,
            'category': 'Saláták',
            'ingredients': 'quinoa, uborka, paradicsom, avokádó, citrom, olívaolaj',
            'instructions': 'Főzd meg a quinoát, várd meg hogy kihűljön. Vágd apróra a zöldségeket és keverd össze a quinoával. Citromlével és olívaolajjal ízesítsd.',
            'images': 'https://via.placeholder.com/300x200?text=Quinoa+Salat'
        },
        {
            'id': 2,
            'title': 'Vegán chili sin carne',
            'hsi': 78.3,
            'esi': 38.7,
            'ppi': 82.5,
            'category': 'Főételek',
            'ingredients': 'vörös bab, kukorica, paprika, hagyma, paradicsom, chili, kömény',
            'instructions': 'Dinszteld le a hagymát és paprikát. Add hozzá a babot, kukoricát és paradicsomot. Fűszerezd és főzd 20 percig.',
            'images': 'https://via.placeholder.com/300x200?text=Vegan+Chili'
        },
        {
            'id': 3,
            'title': 'Spenótos lencse curry',
            'hsi': 82.7,
            'esi': 42.1,
            'ppi': 75.8,
            'category': 'Főételek',
            'ingredients': 'vörös lencse, spenót, kókusztej, curry por, gyömbér, fokhagyma',
            'instructions': 'Főzd meg a lencsét. Külön serpenyőben dinszteld meg a fűszereket, add hozzá a spenótot és kókusztejet.',
            'images': 'https://via.placeholder.com/300x200?text=Lentil+Curry'
        },
        {
            'id': 4,
            'title': 'Mediterrán halfilé',
            'hsi': 72.1,
            'esi': 65.3,
            'ppi': 88.9,
            'category': 'Hal',
            'ingredients': 'tőkehal filé, olívabogyó, paradicsom, oregano, citrom',
            'instructions': 'Süsd meg a halat, tálald mediterrán zöldségekkel.',
            'images': 'https://via.placeholder.com/300x200?text=Fish+Mediterranean'
        },
        {
            'id': 5,
            'title': 'Avokádós toast',
            'hsi': 68.4,
            'esi': 52.1,
            'ppi': 91.2,
            'category': 'Snackek',
            'ingredients': 'teljes kiőrlésű kenyér, avokádó, lime, só, bors',
            'instructions': 'Pirítsd meg a kenyeret, törj rá avokádót és ízesítsd.',
            'images': 'https://via.placeholder.com/300x200?text=Avocado+Toast'
        }
    ]
    
    df = pd.DataFrame(sample_recipes)
    insert_recipes_to_db(df)
    logger.info("✅ Minta adatok létrehozva!")

def main():
    """Fő függvény - adatbázis inicializálás"""
    logger.info("🚀 GreenRec adatbázis inicializálás kezdődik...")
    
    try:
        # 1. Táblák létrehozása
        create_tables()
        
        # 2. JSON adatok betöltése
        json_file = 'greenrec_dataset.json'
        
        if os.path.exists(json_file):
            logger.info(f"📁 JSON fájl található: {json_file}")
            df = load_json_data(json_file)
            if df is not None and len(df) > 0:
                insert_recipes_to_db(df)
                logger.info(f"🎉 Adatbázis sikeresen inicializálva {len(df)} recepttel!")
            else:
                logger.warning("❌ JSON betöltés sikertelen, minta adatok létrehozása...")
                create_sample_data()
        else:
            logger.warning(f"⚠️  JSON fájl nem található: {json_file}")
            logger.info("🔧 Minta adatok létrehozása...")
            create_sample_data()
        
        logger.info("✅ Adatbázis inicializálás befejezve!")
        
    except Exception as e:
        logger.error(f"❌ Kritikus hiba az inicializálás során: {e}")
        raise

if __name__ == '__main__':
    main()
