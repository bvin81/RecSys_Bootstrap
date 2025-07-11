# GreenRec Ajánlórendszer 

Fenntarthatósági alapú recept ajánlórendszer A/B/C tesztekkel. A projekt célja annak vizsgálata, hogy a HSI/ESI/PPI pontszámok és magyarázatok megjelenítése hogyan befolyásolja a felhasználói döntéseket.

## 📋 Projekt áttekintés

**Kutatási kérdés:** Mennyire befolyásolják a fenntarthatósági pontszámok (HSI, ESI) a felhasználói döntéseket?

**Hipotézis:** A C csoport (pontszámok + magyarázat) választásainak átlagos HSI/ESI pontszáma lesz a legmagasabb, majd a B csoport (csak pontszámok), végül az A csoport (kontroll).

**Tesztcsoportok:**
- **A csoport (Kontroll):** Alapvető recept információk, pontszámok nélkül
- **B csoport:** Receptek + HSI/ESI/PPI pontszámok megjelenítése  
- **C csoport:** Receptek + pontszámok + XAI demonstratív magyarázat

## 🏗️ Technológiai stack

- **Backend:** Flask (Python)
- **Adatbázis:** PostgreSQL (Heroku Postgres)
- **Ajánlórendszer:** Content-based filtering (scikit-learn)
- **Frontend:** Bootstrap 5 + HTML/CSS/JavaScript
- **Deployment:** Heroku
- **Version Control:** GitHub

## 📁 Projekt struktúra

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
├── greenrec_recipes.json # Receptek adatfájl
└── README.md           
```

## 🚀 Helyi fejlesztési környezet

### 1. Előfeltételek

```bash
# Python 3.9+ telepítése
python --version

# Git telepítése
git --version
```

### 2. Projekt klónozása

```bash
git clone https://github.com/your-username/greenrec-recommender.git
cd greenrec-recommender
```

### 3. Virtual environment

```bash
# Virtual environment létrehozása
python -m venv venv

# Aktiválás Windows-on
venv\Scripts\activate

# Aktiválás Linux/Mac-en
source venv/bin/activate
```

### 4. Függőségek telepítése

```bash
pip install -r requirements.txt
```

### 5. Helyi PostgreSQL beállítás (Opcionális)

```bash
# PostgreSQL telepítése és adatbázis létrehozása
createdb greenrec_local

# Vagy használd a Heroku Postgres-t fejlesztéshez is
```

### 6. Adatbázis inicializálás

```bash
# json fájl elhelyezése (greenrec_recipes.json)
# Majd adatbázis inicializálás:
python load_data.py
```

### 7. Alkalmazás futtatása

```bash
# Fejlesztői mód
python app.py

# Vagy
flask run
```

## 🌐 Heroku Deployment

### 1. Heroku CLI telepítése

[Heroku CLI letöltése](https://devcenter.heroku.com/articles/heroku-cli)

### 2. Heroku alkalmazás létrehozása

```bash
# Bejelentkezés
heroku login

# Új alkalmazás létrehozása
heroku create your-app-name

# PostgreSQL addon hozzáadása
heroku addons:create heroku-postgresql:mini
```

### 3. Environment variables beállítása

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

### 5. Alkalmazás megnyitása

```bash
heroku open
```

## 📊 json adatfájl formátum

Az alkalmazás a következő json formátumot várja (`greenrec_recipes.json`):

```json
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

## 🔧 Konfigurációs beállítások

### Environment variables

```bash
# Kötelező
DATABASE_URL=postgresql://user:pass@host:port/dbname
SECRET_KEY=your-secret-key

# Opcionális (fejlesztéshez)
FLASK_ENV=development
FLASK_DEBUG=True
```

### Ajánlórendszer paraméterei

Az `app.py` fájlban módosítható súlyok:

```python
# Kompozit pontszám súlyai
hsi_weight = 0.4    # Egészségességi súly
esi_weight = 0.4    # Környezeti súly (inverz)
ppi_weight = 0.2    # Népszerűségi súly

# Végső ajánlás súlyai
content_weight = 0.5   # Content-based similarity súly
score_weight = 0.5     # Kompozit pontszám súly
```

## 📈 Metrikák és értékelés

### Implementált metrikák

1. **Csoportonkénti felhasználószám** - A/B/C tesztek egyenletes eloszlása
2. **Átlagos pontszámok** - HSI, ESI, PPI átlagok csoportonként
3. **Választások száma** - Felhasználói aktivitás mérése
4. **Kompozit pontszám** - `0.4*HSI + 0.4*(1-ESI_norm) + 0.2*PPI`

### Statisztikai elemzés

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


## 📚 API végpontok

### Publikus végpontok

- `GET /` - Főoldal (bejelentkezés szükséges)
- `GET /login` - Bejelentkezési oldal
- `POST /login` - Bejelentkezés feldolgozása
- `GET /register` - Regisztrációs oldal  
- `POST /register` - Regisztráció feldolgozása
- `GET /logout` - Kijelentkezés

### Védett végpontok

- `POST /recommend` - Ajánlások generálása
- `POST /select_recipe` - Receptválasztás rögzítése (AJAX)
- `GET /stats` - Statisztikai áttekintő



## 🧪 Tesztelési útmutató

### 1. Funkcionális tesztelés

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

### 2. Adatintegritás ellenőrzése

```sql
-- Felhasználók egyenletes eloszlásának ellenőrzése
SELECT group_name, COUNT(*) FROM users GROUP BY group_name;

-- Választások rögzítésének ellenőrzése  
SELECT COUNT(*) FROM user_choices;
SELECT COUNT(*) FROM user_interactions;
```

### 3. Ajánlórendszer tesztelése

```python
# Python konzolban tesztelés
from app import recommender
recommendations = recommender.recommend_by_id(1, top_n=5)
print(recommendations[['title', 'composite_score']])
```

## Kutatási adatok exportálása

### Excel export script

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

##  Következő lépések

### Fejlesztési lehetőségek

1. **Továbbfejlesztett metrikák**: Precision@K, Recall@K, Diversity, Novelty
2. **Valós XAI integráció**: LIME vagy SHAP alapú magyarázatok
3. **Felhasználói profilok**: Személyre szabott ajánlások
4. **Collaborative Filtering**: Felhasználók közötti hasonlóság
5. **Real-time analytics**: Dashboard kibővítése
6. **Mobile-friendly UI**: Responsive design javítása

### Kutatási kiterjesztések

1. **Longitudinális vizsgálat**: Hosszú távú felhasználói viselkedés
2. **Több tesztcsoport**: D, E csoportok más megközelítésekkel
3. **Kvalitatív interjúk**: Miért döntöttek így a felhasználók?
4. **Eye-tracking**: Vizuális figyelem mérése
5. **A/B/C/D teszt**: További változók tesztelése


