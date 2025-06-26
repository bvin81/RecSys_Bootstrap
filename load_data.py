import os
import pandas as pd
import psycopg2
from urllib.parse import urlparse
from sklearn.preprocessing import MinMaxScaler

def get_db_connection():
    """PostgreSQL kapcsolat létrehozása"""
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        # Heroku környezet
        result = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            dbname=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port,
            sslmode='require'
        )
    else:
        # Helyi fejlesztés
        conn = psycopg2.connect(
            host="localhost",
            database="greenrec_local",
            user="postgres",
            password="password"
        )
    return conn

def create_tables():
    """Adatbázis táblák létrehozása"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Táblák létrehozása
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(80) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            group_name CHAR(1) NOT NULL CHECK (group_name IN ('A','B','C')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
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
        CREATE TABLE IF NOT EXISTS user_choices (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            recipe_id INTEGER REFERENCES recipes(id) ON DELETE CASCADE,
            chosen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_interactions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            recipe_id INTEGER REFERENCES recipes(id) ON DELETE CASCADE,
            action_type VARCHAR(50) NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Indexek létrehozása
    cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_users_group ON users(group_name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_user_choices_user_id ON user_choices(user_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_user_choices_recipe_id ON user_choices(recipe_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_user_interactions_user_id ON user_interactions(user_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_recipes_category ON recipes(category);")
    
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Adatbázis táblák létrehozva!")

def load_csv_data(csv_file_path):
    """CSV adatok betöltése és előfeldolgozása"""
    try:
        # CSV beolvasása
        print(f"📁 CSV beolvasása: {csv_file_path}")
        
        # Próbáljuk különböző encoding-okkal
        encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(csv_file_path, encoding=encoding)
                print(f"✅ Sikeres beolvasás {encoding} encoding-gal")
                break
            except UnicodeDecodeError:
                continue
        
        if df is None:
            raise Exception("Nem sikerült beolvasni a CSV fájlt")
        
        print(f"📊 Beolvasva {len(df)} recept")
        
        # Oszlopnevek standardizálása
        column_mapping = {
            'recipeid': 'id',
            'name': 'title',
            'nutri_score': 'hsi',
            'env_score': 'esi', 
            'meal_score': 'ppi'
        }
        
        df = df.rename(columns=column_mapping)
        
        # Szükséges oszlopok ellenőrzése
        required_columns = ['id', 'title', 'hsi', 'esi', 'ppi', 'ingredients']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise Exception(f"Hiányzó oszlopok: {missing_columns}")
        
        # Hiányzó adatok kezelése
        df = df.dropna(subset=['id', 'title', 'hsi', 'esi', 'ppi'])
        
        # Karakterek javítása (opcionális)
        df['title'] = df['title'].str.replace('?', 'ő').str.replace('?', 'ű')
        df['ingredients'] = df['ingredients'].fillna('').str.replace('?', 'ő').str.replace('?', 'ű')
        df['instructions'] = df['instructions'].fillna('').str.replace('?', 'ő').str.replace('?', 'ű')
        
        # URL-ek javítása
        if 'images' in df.columns:
            df['images'] = df['images'].str.replace('h?tps', 'https', regex=False)
        
        # Kategória alapértelmezett értéke
        if 'category' not in df.columns:
            df['category'] = 'Egyéb'
        
        df['category'] = df['category'].fillna('Egyéb')
        
        print(f"✅ Adatok előfeldolgozva, {len(df)} érvényes recept")
        return df
        
    except Exception as e:
        print(f"❌ Hiba a CSV betöltése során: {e}")
        return None

def insert_recipes_to_db(df):
    """Receptek beszúrása az adatbázisba"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Meglévő receptek törlése
        cur.execute("DELETE FROM recipes;")
        
        # Receptek beszúrása
        insert_query = """
            INSERT INTO recipes (id, title, hsi, esi, ppi, category, ingredients, instructions, images)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        records_inserted = 0
        for _, row in df.iterrows():
            try:
                cur.execute(insert_query, (
                    int(row['id']),
                    str(row['title'])[:500],  # Limitálás 500 karakterre
                    float(row['hsi']),
                    float(row['esi']),
                    float(row['ppi']),
                    str(row.get('category', 'Egyéb'))[:100],
                    str(row.get('ingredients', ''))[:2000],
                    str(row.get('instructions', ''))[:5000],
                    str(row.get('images', ''))[:500]
                ))
                records_inserted += 1
            except Exception as e:
                print(f"⚠️  Hiba a recept beszúrásánál (ID: {row.get('id', 'N/A')}): {e}")
                continue
        
        conn.commit()
        print(f"✅ {records_inserted} recept sikeresen beszúrva az adatbázisba!")
        
    except Exception as e:
        print(f"❌ Hiba az adatbázis művelet során: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def create_sample_data():
    """Minta adatok létrehozása teszteléshez"""
    sample_recipes = [
        {
            'id': 1,
            'title': 'Mediterrán Saláta',
            'hsi': 85.5,
            'esi': 45.2,
            'ppi': 78.3,
            'category': 'Saláta',
            'ingredients': 'paradicsom, uborka, olívabogyó, feta sajt, olívaolaj, citrom',
            'instructions': 'Vágjuk fel a zöldségeket, keverjük össze a feta sajttal és öntsük le az olívaolajjal.',
            'images': 'https://example.com/mediterranean_salad.jpg'
        },
        {
            'id': 2,
            'title': 'Quinoa Buddha Bowl',
            'hsi': 92.1,
            'esi': 38.7,
            'ppi': 65.4,
            'category': 'Vegán',
            'ingredients': 'quinoa, édesburgonya, spenót, avokádó, csicseriborsó, tahini',
            'instructions': 'Főzzük meg a quinoát, süssük meg az édesburgonyát, tálaljuk a zöldségekkel.',
            'images': 'https://example.com/quinoa_bowl.jpg'
        },
        {
            'id': 3,
            'title': 'Csirkemell zöldségekkel',
            'hsi': 76.8,
            'esi': 120.5,
            'ppi': 88.2,
            'category': 'Hús',
            'ingredients': 'csirkemell, brokkoli, sárgarépa, paprika, olívaolaj, fokhagyma',
            'instructions': 'Süssük meg a csirkemellet, pároljuk a zöldségeket és tálaljuk együtt.',
            'images': 'https://example.com/chicken_vegetables.jpg'
        }
    ]
    
    df = pd.DataFrame(sample_recipes)
    insert_recipes_to_db(df)
    print("✅ Minta adatok létrehozva!")

def main():
    """Fő függvény"""
    print("🚀 GreenRec adatbázis inicializálás kezdődik...")
    
    # 1. Táblák létrehozása
    create_tables()
    
    # 2. CSV adatok betöltése (ha létezik)
    csv_file = 'greenrec_recipes.csv'  # Vagy az általad megadott fájlnév
    
    if os.path.exists(csv_file):
        print(f"📁 CSV fájl található: {csv_file}")
        df = load_csv_data(csv_file)
        if df is not None:
            insert_recipes_to_db(df)
        else:
            print("❌ CSV betöltés sikertelen, minta adatok létrehozása...")
            create_sample_data()
    else:
        print(f"⚠️  CSV fájl nem található: {csv_file}")
        print("🔧 Minta adatok létrehozása...")
        create_sample_data()
    
    print("✅ Adatbázis inicializálás befejezve!")

if __name__ == '__main__':
    main()
