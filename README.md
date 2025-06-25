# GreenRec - Fenntartható Receptajánló Rendszer

🌱 AI-alapú ajánlórendszer fenntartható és egészséges receptekhez, A/B/C teszteléssel és valós idejű analitikával.

## 🚀 Gyors telepítés

### Előfeltételek
- Python 3.8+
- Git

### 1. Projekt klónozása
```bash
git clone <repository-url>
cd greenrec-system
```

### 2. Virtual environment létrehozása
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Függőségek telepítése
```bash
pip install -r requirements.txt
```

### 4. Adatfájl elhelyezése
Helyezze el a `greenrec_dataset.json` fájlt a `data/` mappában:
```
greenrec-system/
├── data/
│   └── greenrec_dataset.json  # <- Itt kell lennie
├── app.py
└── ...
```

### 5. Alkalmazás indítása
```bash
python app.py
```

A GreenRec elérhető lesz: http://localhost:5000

## 📁 Projekt struktúra

```
greenrec-system/
├── app.py                    # 🚀 Fő Flask alkalmazás
├── config.py                 # ⚙️ Központi konfiguráció
├── requirements.txt          # 📦 Python függőségek
├── README.md                 # 📖 Ez a fájl
├── models/
│   └── recommendation.py     # 🤖 ML ajánlórendszer
├── services/
│   ├── data_service.py      # 🗄️ Adatkezelés
│   ├── rating_service.py    # ⭐ Értékelések és tanulás
│   └── analytics_service.py # 📊 A/B/C teszt és metrikák
├── utils/
│   ├── helpers.py           # 🛠️ Segédfunkciók
│   ├── metrics.py           # 📈 Metrika számítások
│   ├── data_processing.py   # 🔄 Adatfeldolgozás
│   └── validation.py        # ✅ Validációs rendszer
├── templates/
│   ├── base.html           # 📄 Alap HTML template
│   ├── index.html          # 🏠 Főoldal
│   ├── search.html         # 🔍 Keresés
│   ├── analytics.html      # 📊 Dashboard
│   ├── about.html          # ℹ️ Információ
│   └── error.html          # ❌ Hibakezelés
├── static/
│   ├── css/style.css       # 🎨 Stílusok
│   └── js/main.js          # ⚡ JavaScript
├── data/
│   └── greenrec_dataset.json # 📊 Recept adatok
└── logs/                    # 📝 Log fájlok
```

## 🎯 Funkciók

### ✅ Implementált funkciók
- **🤖 AI Ajánlórendszer:** TF-IDF és cosine similarity alapú
- **🧪 A/B/C Testing:** Három különböző tanulási algoritmus
- **📊 Real-time Analytics:** Chart.js alapú dashboard
- **⭐ Rating System:** 1-5 csillagos értékelés
- **🔍 Keresés:** Szöveges keresés receptekben
- **🌱 Fenntarthatóság:** ESI/HSI/PPI kompozit pontszám
- **📱 Reszponzív UI:** Modern, mobile-first design
- **🛡️ Biztonság:** XSS, SQL injection védelem

### 📈 Metrikák
- **Precision@K, Recall@K, F1-Score@K**
- **Intra-list diverzitás**
- **Kategória és összetevő diverzitás**
- **Fenntarthatósági metrikák**
- **Tanulási görbék**
- **A/B/C csoportok statisztikai összehasonlítása**

## 🧪 A/B/C Teszt csoportok

- **A csoport (🔴):** Baseline - tiszta content-based filtering
- **B csoport (🟠):** Collaborative filtering módszer
- **C csoport (🟢):** Hibrid megközelítés (legjobb teljesítmény)

## 🌱 Fenntarthatósági pontszám

**Kompozit képlet:**
```
Composite Score = ESI_final × 0.4 + HSI × 0.4 + PPI × 0.2
```

Ahol:
- **ESI_final = 100 - normalized_ESI** (inverz, mert magasabb ESI = rosszabb környezetterhelés)
- **HSI:** Health Score Index (0-100)
- **PPI:** Popularity Index (0-100)

## 📊 API Endpoints

### Főbb API végpontok
```
GET  /                      # Főoldal ajánlásokkal
GET  /search?q=<query>      # Keresés
GET  /analytics             # Dashboard
POST /api/rate              # Recept értékelése
GET  /api/search            # Keresés API
POST /api/recommend         # Ajánlások API
POST /api/next-round        # Következő tanulási kör
GET  /api/dashboard-data    # Dashboard adatok
GET  /status                # Rendszer állapot
```

### Példa API hívások

**Recept értékelése:**
```bash
curl -X POST http://localhost:5000/api/rate \
  -H "Content-Type: application/json" \
  -d '{"recipe_id": "recipe_123", "rating": 5}'
```

**Keresés:**
```bash
curl "http://localhost:5000/api/search?q=vegan+pasta&limit=10"
```

## 🔧 Konfiguráció

A `config.py` fájlban található az összes beállítás:

```python
# Főbb konfigurációs paraméterek
SUSTAINABILITY_WEIGHT = 0.4    # ESI súly
HEALTH_WEIGHT = 0.4           # HSI súly  
POPULARITY_WEIGHT = 0.2       # PPI súly

TFIDF_MAX_FEATURES = 5000     # TF-IDF feature limit
DEFAULT_RECOMMENDATIONS = 6    # Ajánlások száma/kör
MAX_LEARNING_ROUNDS = 5       # Maximum tanulási körök
```

## 🧪 Tesztelés

### Fejlesztői tesztelés
```bash
# Egység tesztek (ha vannak)
python -m pytest tests/

# Kód minőség ellenőrzés
flake8 .
black . --check
```

### Manuális tesztelés
1. **Regisztráció:** Új felhasználó automatikus létrehozása
2. **Értékelés:** 6 recept értékelése 1-5 csillaggal
3. **Tanulás:** "Következő kör" gomb megjelenése
4. **Personalizáció:** Új ajánlások a korábbi értékelések alapján
5. **Analytics:** Metrikák frissülése a dashboard-on

## 📝 Logging

A rendszer részletes logokat készít:
- **INFO:** Általános működési információk
- **WARNING:** Figyelmeztetések és nem kritikus hibák
- **ERROR:** Hibák és kivételek
- **DEBUG:** Részletes debug információk (development módban)

Log fájlok helye: `logs/` mappa

## 🚀 Production telepítés

### Environment változók
```bash
export FLASK_ENV=production
export SECRET_KEY=your-secure-secret-key-here
export DATABASE_URL=your-database-url-here  # opcionális
```

### Gunicorn használata
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Docker (opcionális)
```dockerfile
FROM python:3.8-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

## 🤝 Fejlesztés

### Kód stílus
- **PEP 8** Python kód stílus
- **Type hints** használata
- **Docstring** minden függvényhez
- **Modular architecture** - tiszta szeparáció

### Új funkció hozzáadása
1. Fork és branch létrehozása
2. Implementáció a megfelelő modulban
3. Tesztek írása
4. Pull request létrehozása

## 📚 Használt technológiák

- **Backend:** Flask, Python 3.8+
- **ML:** scikit-learn, pandas, numpy
- **Frontend:** Vanilla JavaScript, Chart.js
- **Styling:** CSS3, CSS Grid, Flexbox
- **Data:** JSON-based storage
- **Security:** Input validation, XSS/SQL injection protection

## 🏆 Államvizsga demonstráció

A GreenRec ideális államvizsga projektként:

1. **ML algoritmusok:** Bemutatható TF-IDF, similarity számítások
2. **A/B Testing:** Statisztikai szignifikancia tesztek
3. **Clean Code:** Moduláris architektúra, design patterns
4. **Full-Stack:** Backend + Frontend + Database
5. **Analytics:** Real-time metrikák és vizualizáció
6. **Security:** Biztonsági megfontolások implementálva

## 📞 Támogatás

Ha bármilyen problémába ütközik:
1. Ellenőrizze a log fájlokat
2. Győződjön meg róla, hogy a `greenrec_dataset.json` elérhető
3. Ellenőrizze a Python és pip verziókat
4. Indítsa újra a virtual environment-et

## 📄 Licenc

Ez a projekt oktatási célokra készült, MIT licenc alatt.
