# 🍃 GreenRec - Fenntartható Receptajánló

## 🎯 Projekt Célja
GreenRec content-based filtering alapú ajánlómotor A/B/C teszteléssel, GitHub online környezetben fejlesztve. **Az Ön valós JSON struktúrájához optimalizálva.**

## 🚀 GitHub Codespaces Gyors Indítás

### 1. Repository Megnyitása
1. Nyissa meg ezt a repository-t GitHub-on
2. Kattintson a **"Code" > "Codespaces" > "Create codespace"**-re
3. Várja meg az environment betöltését (1-2 perc)

### 2. JSON Fájl Elhelyezése
**Helyezze el az Ön `greenrec_dataset.json` fájlját a projekt gyökerében!**

### 3. Alkalmazás Indítása
```bash
python app.py
```

### 4. Webalkalmazás Elérése
- A Codespaces automatikusan létrehoz egy **publikus linket**
- A link a **"PORTS"** tab-ban található (port 5000)
- Kattintson a **globe ikonra** a public URL-ért
- **Megosztható link formátum:** `https://xyz-5000.app.github.dev`

## 📊 Az Ön JSON Struktúrája (Támogatott)

A rendszer automatikusan felismeri és feldolgozza az Ön JSON struktúráját:

```json
[
  {
    "recipeid": 317804,
    "title": "New Orleans-i töltött paprika",
    "ingredients": "fokhagyma gerezdek, lila hagyma, zeller, tojás, mozzarella sajt, paprika",
    "instructions": "Süsd meg a darált húst...",
    "ESI": 216.9399893,
    "HSI": 70.88419297,
    "PPI": # 🍃 GreenRec - Fenntartható Receptajánló

## 🎯 Projekt Célja
GreenRec content-based filtering alapú ajánlómotor A/B/C teszteléssel, GitHub online környezetben fejlesztve.

## 🚀 GitHub Codespaces Gyors Indítás

### 1. Repository Megnyitása
1. Nyissa meg ezt a repository-t GitHub-on
2. Kattintson a **"Code" > "Codespaces" > "Create codespace"**-re
3. Várja meg az environment betöltését (1-2 perc)

### 2. Alkalmazás Indítása
```bash
python app.py
```

### 3. Webalkalmazás Elérése
- A Codespaces automatikusan létrehoz egy **publikus linket**
- A link a **"PORTS"** tab-ban található (port 5000)
- Kattintson a **globe ikonra** a public URL-ért
- **Megosztható link formátum:** `https://xyz-5000.app.github.dev`

## 📊 JSON Adatformátum

A `greenrec_dataset.json` fájlnak az alábbi struktúrát kell követnie:

```json
{
  "metadata": {
    "source": "Adatforrás neve",
    "total_recipes": 10
  },
  "recipes": [
    {
      "id": 1,
      "title": "Recept neve",
      "ingredients": "összetevők szóközzel elválasztva",
      "HSI": 0.8,
      "ESI": 0.7,
      "PPI": 0.6
    }
  ]
}
```

### Kötelező mezők:
- **title**: Recept neve
- **ingredients**: Összetevők szöveges formában
- **HSI**: Health Score Index (0-1 között)
- **ESI**: Environmental Score Index (0-1 között)  
- **PPI**: Personal Preference Index (0-1 között)

## 🧪 A/B/C Teszt Funkciók

### Automatikus Csoportosítás
A rendszer automatikusan három csoportba sorolja a felhasználókat:

- **A Csoport (Control):** Csak alapvető recept információk
- **B Csoport (Scores):** + HSI, ESI, PPI pontszámok megjelenítése
- **C Csoport (Explanations):** + AI magyarázatok (következő verzióban)

### Viselkedési Tracking
- Automatikus felhasználó azonosítás (anonim hash)
- Keresési viselkedés naplózása
- Értékelések és interakciók rögzítése
- Időbélyegek minden akcióhoz

## 🔗 Elérhető Oldalak

| URL | Leírás |
|-----|--------|
| `/` | Főoldal - keresés |
| `/status` | Rendszer állapot és statisztikák |
| `/reload` | JSON adatok újratöltése |
| `/export` | Viselkedési adatok JSON exportálása |

## 📈 Használati Forgatókönyv

### Kutatók számára:
1. **Setup:** JSON fájl feltöltése → Codespaces indítása → `python app.py`
2. **Megosztás:** Public link küldése a tesztelőknek
3. **Monitoring:** `/status` oldal folyamatos ellenőrzése
4. **Adatgyűjtés:** `/export` használata az eredmények letöltéséhez

### Tesztelők számára:
1. **Link megnyitása** (automatikus csoportosítás történik)
2. **Receptek keresése** (pl. "paradicsom mozzarella")
3. **Eredmények böngészése** (csoport-specifikus felület)
4. **Értékelések és interakciók**

## 🛠️ Fejlesztési Fázisok

### ✅ FÁZIS 1: Alapfunkciók (KÉSZ)
- [x] JSON adatok betöltése
- [x] Egyszerű keresési funkció
- [x] A/B/C csoportosítás
- [x] Viselkedési tracking
- [x] Státusz monitoring

### 🔄 FÁZIS 2: ML Algoritmus (KÖVETKEZŐ)
- [ ] Content-based filtering implementálása
- [ ] TF-IDF vektorok és cosine similarity
- [ ] Hibrid pontozási rendszer

### 🔄 FÁZIS 3: UI Fejlesztés (KÉSŐBB)
- [ ] Három különböző template A/B/C csoportoknak
- [ ] Pontszámok vizualizációja (B csoport)
- [ ] XAI magyarázatok (C csoport)

### 🔄 FÁZIS 4: Analytics (UTOLSÓ)
- [ ] Részletes analytics dashboard
- [ ] Statisztikai elemzési funkciók
- [ ] Exportálási lehetőségek

## 🧪 Tesztelési Útmutató

### Alapfunkciók Ellenőrzése:
1. **JSON betöltés:** `/status` oldal ellenőrzése
2. **Keresés:** "paradicsom" vagy "quinoa" beírása
3. **Csoportosítás:** Csoport megjelenítése a jobb felső sarokban
4. **Értékelés:** "Tetszik" gomb működése

### Hibakeresés:
```bash
# JSON validáció
python -c "import json; print('JSON OK') if json.load(open('greenrec_dataset.json')) else print('JSON ERROR')"

# Flask teszt
python -c "from app import load_json_data; print('SUCCESS' if load_json_data() else 'FAILED')"
```

## 📊 Adatgyűjtés és Elemzés

### Exportált Adatok Struktúrája:
```json
{
  "export_timestamp": "2024-06-25T10:30:00",
  "behaviors": [
    {
      "user_id": "abc123",
      "group": "A|B|C",
      "action": "search|rate|page_view", 
      "timestamp": "2024-06-25T10:30:00",
      "data": {"query": "paradicsom"}
    }
  ],
  "summary": {
    "total_users": 5,
    "group_distribution": {"A": 2, "B": 2, "C": 1},
    "action_distribution": {"search": 8, "rate": 3}
  }
}
```

### Python Elemzés Példa:
```python
import pandas as pd
import json

# Adatok betöltése
with open('export.json') as f:
    data = json.load(f)

df = pd.DataFrame(data['behaviors'])

# Csoportonkénti elemzés
group_stats = df.groupby('group').agg({
    'user_id': 'nunique',
    'action': 'count'
})

print("Felhasználók csoportonként:", group_stats)
```

## 🔒 Adatvédelem és Etika

### Adatkezelés:
- **Anonimitás:** Csak hash-elt felhasználói azonosítók
- **Minimális adatgyűjtés:** Csak kutatáshoz szükséges metrikák
- **Transzparencia:** Nyílt forráskód, világos célok

### Javasolt Tájékoztatás Résztvevőknek:
> "Részt vesz egy kutatásban, amely receptajánló rendszereket hasonlít össze. Anonim módon rögzítjük a keresési viselkedését kutatási célokra. Személyes adatokat nem gyűjtünk."

## 🛠️ Hibaelhárítás

### Gyakori Problémák:

**JSON betöltési hiba:**
- Ellenőrizze a fájl helyét és nevét
- Validálja a JSON struktúrát
- Nézze meg a `/status` oldalt

**Port foglaltság:**
- Módosítsa az `app.py`-ban: `app.run(port=5001)`

**Codespaces timeout:**
- 30 perc inaktivitás után alvó állapotba kerül
- Újraindítás: `python app.py`

**Üres eredmények:**
- Ellenőrizze a keresési kifejezést
- Próbálja: "paradicsom", "quinoa", "avokádó"

## 📞 Támogatás

### Következő Lépések:
1. **Most:** Alapfunkciók tesztelése
2. **Következő:** ML algoritmus implementálása
3. **Később:** UI fejlesztés három verzióban

### Technikai Kérdések:
- GitHub Issues használata
- `/status` oldal információi
- Console output ellenőrzése

---

**🎉 Az alkalmazás készen áll az alapvető tesztelésre!** 

A következő fejlesztési ciklusban implementáljuk a content-based filtering algoritmust és a fejlettebb A/B/C UI verziókat.
