# GreenRec Ajánlórendszer 🌱

Fenntarthatósági alapú recept ajánlórendszer A/B/C tesztekkel. A projekt célja annak vizsgálata, hogy a HSI/ESI/PPI pontszámok és magyarázatok megjelenítése hogyan befolyásolja a felhasználói döntéseket.

## 📋 Projekt Áttekintés

**Kutatási kérdés:** Mennyire befolyásolják a fenntarthatósági pontszámok (HSI, ESI, PPI) a felhasználói döntéseket?

**Hipotézis:** A C csoport (pontszámok + magyarázat) választásainak átlagos kompozit pontszáma lesz a legmagasabb, majd a B csoport (csak pontszámok), végül az A csoport (kontroll).

**Tesztcsoportok:**
- **A csoport (Kontroll):** Alapvető recept információk, pontszámok nélkül
- **B csoport:** Receptek + HSI/ESI/PPI pontszámok megjelenítése  
- **C csoport:** Receptek + pontszámok + XAI demonstratív magyarázat

## 🏗️ Technológiai Stack

- **Backend:** Flask (Python)
- **Adatbázis:** PostgreSQL (Heroku Postgres)
- **Ajánlórendszer:** Content-based filtering (scikit-learn)
- **Frontend:** Bootstrap 5 + HTML/CSS/JavaScript
- **Deployment:** Heroku
- **Version Control:** GitHub

## 📁 Projekt Struktúra

```
greenrec-recommender/
├── app.py                 # Fő Flask alkalmazás
├── load_data.py          # Adatbázis inicializálás és CSV betöltés
├── requirements.txt      # Python függőségek
├── Procfile             # Heroku beállítás
├── runtime.txt          # Python verzió
├── templates/           # HTML sablonok
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── results.html
│   └── stats.html
├── static/              # CSS/JS fájlok (opcionális)
├── greenrec_recipes.csv # Receptek adatfájl
└── README.md           # Ez a fájl
```

## 🚀 Helyi Fejlesztési Környezet

### 1. Előfeltételek

```bash
# Python 3.9+ telepítése
python --version

# Git telepítése
git --version
```

### 2. Projekt Klónozása

```bash
git clone https://github.com/your-username/greenrec-recommender.git
cd greenrec-recommender
```

### 3. Virtual Environment

```bash
# Virtual environment létrehozása
python -m venv venv

# Aktiválás Windows-on
venv\Scripts\activate

# Aktiválás Linux/Mac-en
source venv/bin/activate
```

### 4. Függőségek Telepítése

```bash
pip install -r requirements.txt
```

### 5. Helyi PostgreSQL Beállítás (Opcionális)

```bash
# PostgreSQL telepítése és adatbázis létrehozása
createdb greenrec_local

# Vagy használd a Heroku Postgres-t fejlesztéshez is
```

### 6. Adatbázis Inicializálás

```bash
# CSV fájl elhelyezése (greenrec_recipes.csv)
# Majd adatbázis inicializálás:
python load_data.py
```

### 7. Alkalmazás Futtatása

```bash
# Fejlesztői mód
python app.py

# Vagy
flask run
```

Alkalmazás elérhető: `http://localhost:5000`

## 🌐 Heroku Deployment

### 1. Heroku CLI Telepítése

[Heroku CLI letöltése](https://devcenter.heroku.com/articles/heroku-cli)

### 2. Heroku Alkalmazás Létrehozása

```bash
# Bejelentkezés
heroku login

# Új alkalmazás létrehozása
heroku create your-app-name

# PostgreSQL addon hozzáadása
heroku addons:create heroku-postgresql:mini
```

### 3. Environment Variables Beállítása

```bash
# Titkos kulcs beállítása
heroku config:set SECRET_KEY="your-super-secret-key-here"

# DATABASE_URL automatikusan beállítva a Postgres addon által
```

### 4. Deployment

```bash
# Git push Heroku-ra
git add .
git commit -m "Initial deployment"
git push heroku main

# Adatbázis inicializálás Heroku-n
heroku run python load_data.py
```

### 5. Alkalmazás Megnyitása

```bash
heroku open
```

## 📊 CSV Adatfájl Formátum

Az alkalmazás a következő CSV formátumot várja (`greenrec_recipes.csv`):

```csv
recipeid,env_score,nutri_score,meal_score,name,ingredients,instructions,category,images
317804,216.94,70.88,75,"New Orleans-i töltött paprika","fokhagyma, hagyma, paprika","Süsd meg a húst...","Hús","https://..."
421807,206.13,57.50,90,"Minestrone leves","marhahús, víz, hagyma","Keverd össze...","Leves","https://..."
```

**Oszlopok leírása:**
- `recipeid` → `id`: Egyedi recept azonosító
- `nutri_score` → `hsi`: Health Score Index (egészségességi pontszám) 
- `env_score` → `esi`: Environmental Score Index (környezeti pontszám)
- `meal_score` → `ppi`: Popularity Score Index (népszerűségi pontszám)
- `name` → `title`: Recept neve
- `ingredients`: Összetevők (vesszővel elválasztva)
- `instructions`: Elkészítési utasítások
- `category`: Étel kategória
- `images`: Kép URL

## 🔧 Konfigurációs Beállítások

### Environment Variables

```bash
# Kötelező
DATABASE_URL=postgresql://user:pass@host:port/dbname
SECRET_KEY=your-secret-key

# Opcionális (fejlesztéshez)
FLASK_ENV=development
FLASK_DEBUG=True
```

### Ajánlórendszer Paraméterei

Az `app.py` fájlban módosítható súlyok:

```python
# Kompozit pontszám súlyai
hsi_weight = 0.4    # Egészségességi súly
esi_weight = 0.4    # Környezeti súly (inverz)
ppi_weight = 0.2    # Népszerűségi súly

# Végső ajánlás súlyai
content_weight = 0.6   # Content-based similarity súly
score_weight = 0.4     # Kompozit pontszám súly
```

## 📈 Metrikák és Értékelés

### Implementált Metrikák

1. **Csoportonkénti felhasználószám** - A/B/C tesztek egyenletes eloszlása
2. **Átlagos pontszámok** - HSI, ESI, PPI átlagok csoportonként
3. **Választások száma** - Felhasználói aktivitás mérése
4. **Kompozit pontszám** - `0.4*HSI + 0.4*(1-ESI_norm) + 0.2*PPI`

### Statisztikai Elemzés

A `/stats` endpoint alapvető statisztikákat mutat. Részletes elemzéshez exportálhatók az adatok:

```sql
-- Csoportonkénti választási statisztikák
SELECT 
    u.group_name,
    COUNT(uc.id) as total_choices,
    AVG(r.hsi) as avg_health_score,
    AVG(r.esi) as avg_env_score,
    AVG(r.ppi) as avg_popularity_score
FROM users u
LEFT JOIN user_choices uc ON u.id = uc.user_id
LEFT JOIN recipes r ON uc.recipe_id = r.id
GROUP BY u.group_name;
```

## 🐛 Hibaelhárítás

### Gyakori Problémák

1. **Adatbázis kapcsolati hiba**
```bash
# Ellenőrizd a DATABASE_URL environment variable-t
echo $DATABASE_URL

# Heroku-n:
heroku config:get DATABASE_URL
```

2. **CSV betöltési problémák**
```bash
# Karakterkódolás problémák esetén
# Próbáld meg más encoding-gal (UTF-8, Latin-1)
# A load_data.py automatikusan próbál többfélével
```

3. **Heroku deployment hibák**
```bash
# Heroku logs megtekintése
heroku logs --tail

# Adatbázis kapcsolat tesztelése
heroku run python -c "from app import get_db_connection; print('DB OK')"
```

4. **Üres ajánlások**
```bash
# Ellenőrizd hogy van-e adat az adatbázisban
heroku run python -c "
from app import get_db_connection
import psycopg2
conn = get_db_connection()
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM recipes;')
print(f'Receptek száma: {cur.fetchone()[0]}')
"
```

### Environment Setup Hibák

- **Virtual environment aktiválás**: Mindig aktiváld a venv-et fejlesztés előtt
- **Requirements telepítés**: `pip install -r requirements.txt` minden új klónozás után
- **Port konflik**: Ha a 5000-es port foglalt, használd: `flask run --port=8000`

## 📚 API Endpoints

### Publikus Endpoints

- `GET /` - Főoldal (bejelentkezés szükséges)
- `GET /login` - Bejelentkezési oldal
- `POST /login` - Bejelentkezés feldolgozása
- `GET /register` - Regisztrációs oldal  
- `POST /register` - Regisztráció feldolgozása
- `GET /logout` - Kijelentkezés

### Védett Endpoints

- `POST /recommend` - Ajánlások generálása
- `POST /select_recipe` - Receptválasztás rögzítése (AJAX)
- `GET /stats` - Statisztikai áttekintő

### Response Formátumok

```json
// POST /select_recipe válasz
{
  "success": true
}

// Hiba esetén
{
  "error": "Error message"
}
```

## 🧪 Tesztelési Útmutató

### 1. Funkcionális Tesztelés

**A csoport tesztelése:**
1. Regisztrálj új felhasználót
2. Válassz egy receptet a főoldalon  
3. Ellenőrizd, hogy NEM látszanak pontszámok
4. Válassz egy ajánlott receptet

**B csoport tesztelése:**
1. Regisztrálj újabb felhasználót
2. Ellenőrizd, hogy látszanak a HSI/ESI/PPI pontszámok
3. NEM látható magyarázat

**C csoport tesztelése:**
1. Regisztrálj harmadik felhasználót
2. Ellenőrizd, hogy látszanak pontszámok ÉS magyarázat

### 2. Adatintegritás Ellenőrzése

```sql
-- Felhasználók egyenletes eloszlásának ellenőrzése
SELECT group_name, COUNT(*) FROM users GROUP BY group_name;

-- Választások rögzítésének ellenőrzése  
SELECT COUNT(*) FROM user_choices;
SELECT COUNT(*) FROM user_interactions;
```

### 3. Ajánlórendszer Tesztelése

```python
# Python konzolban tesztelés
from app import recommender
recommendations = recommender.recommend_by_id(1, top_n=5)
print(recommendations[['title', 'composite_score']])
```

## 📊 Kutatási Adatok Exportálása

### Excel Export Script

```python
import pandas as pd
from app import get_db_connection

def export_research_data():
    conn = get_db_connection()
    
    # Felhasználók és csoportjaik
    users_df = pd.read_sql_query("""
        SELECT id, username, group_name, created_at 
        FROM users ORDER BY created_at
    """, conn)
    
    # Választások részletes adatokkal
    choices_df = pd.read_sql_query("""
        SELECT 
            uc.id as choice_id,
            u.username,
            u.group_name,
            r.title as recipe_title,
            r.hsi, r.esi, r.ppi,
            (0.4 * r.hsi + 0.4 * (255 - r.esi) + 0.2 * r.ppi) as composite_score,
            uc.chosen_at
        FROM user_choices uc
        JOIN users u ON uc.user_id = u.id  
        JOIN recipes r ON uc.recipe_id = r.id
        ORDER BY uc.chosen_at
    """, conn)
    
    # Excel fájlba mentés
    with pd.ExcelWriter('greenrec_research_data.xlsx') as writer:
        users_df.to_excel(writer, sheet_name='Users', index=False)
        choices_df.to_excel(writer, sheet_name='Choices', index=False)
    
    conn.close()
    print("✅ Kutatási adatok exportálva: greenrec_research_data.xlsx")

# Futtatás
export_research_data()
```

## 🔄 Verziókezelés és Collaboration

### Git Workflow

```bash
# Feature branch létrehozása
git checkout -b feature/new-metrics

# Változások commitolása
git add .
git commit -m "feat: új metrikák hozzáadása"

# Push és Pull Request
git push origin feature/new-metrics
```

### Heroku Auto-Deploy Beállítása

1. Heroku Dashboard → App Settings
2. GitHub integration bekapcsolása
3. Automatic deploys engedélyezése main branch-ből

## 📄 Licenc és Hivatkozás

Ez a projekt kutatási célra készült. Ha felhasználod a kódot vagy az ötleteket:

```
@software{greenrec_recommender,
  title = {GreenRec: Sustainability-focused Recipe Recommender System},
  author = {[Your Name]},
  year = {2025},
  url = {https://github.com/your-username/greenrec-recommender}
}
```

## 🆘 Támogatás

Ha problémába ütközöl:

1. **Hibaelhárítás**: Ellenőrizd a fenti hibaelhárítási szekciókat
2. **Logs**: `heroku logs --tail` parancs segít a hibák azonosításában  
3. **GitHub Issues**: Nyiss issue-t a repository-ban
4. **Dokumentáció**: Flask és scikit-learn hivatalos dokumentációk

## 🚀 Következő Lépések

### Fejlesztési Lehetőségek

1. **Továbbfejlesztett metrikák**: Precision@K, Recall@K, Diversity, Novelty
2. **Valós XAI integráció**: LIME vagy SHAP alapú magyarázatok
3. **Felhasználói profilok**: Személyre szabott ajánlások
4. **Collaborative Filtering**: Felhasználók közötti hasonlóság
5. **Real-time analytics**: Dashboard kibővítése
6. **Mobile-friendly UI**: Responsive design javítása

### Kutatási Kiterjesztések

1. **Longitudinális vizsgálat**: Hosszú távú felhasználói viselkedés
2. **Több tesztcsoport**: D, E csoportok más megközelítésekkel
3. **Kvalitatív interjúk**: Miért döntöttek így a felhasználók?
4. **Eye-tracking**: Vizuális figyelem mérése
5. **A/B/C/D teszt**: További változók tesztelése

---

**Jó kódolást! 🌱💻**
