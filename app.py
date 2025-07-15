import os
import logging
import json
import random
import numpy as np
from datetime import datetime, timedelta
from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify, Response

# Logging beállítása
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_score_color(score, score_type):
    """
    Pontszám alapján színkódolás
    score_type: 'hsi', 'esi', 'ppi'
    """
    if score_type == 'hsi' or score_type == 'ppi':
        # HSI és PPI: magasabb = jobb
        if score >= 75:
            return 'success'  # Zöld
        elif score >= 50:
            return 'warning'  # Sárga
        else:
            return 'danger'   # Piros
    
    elif score_type == 'esi':
        # ESI: alacsonyabb = jobb (normalizált 0-100 skála)
        if score <= 33:      # Alacsony környezeti hatás
            return 'success'  # Zöld
        elif score <= 66:    # Közepes környezeti hatás
            return 'warning'  # Sárga
        else:                # Magas környezeti hatás
            return 'danger'   # Piros

try:
    import psycopg2
    from psycopg2 import sql
    from urllib.parse import urlparse
    from werkzeug.security import generate_password_hash, check_password_hash
    import pandas as pd
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.preprocessing import MinMaxScaler
    logger.info("✅ Összes dependency importálva")
except ImportError as e:
    logger.error(f"❌ Import hiba: {e}")

try:
    from visualizations import visualizer
    VISUALIZATIONS_AVAILABLE = True
    logger.info("✅ Vizualizációs modul betöltve")
except ImportError as e:
    VISUALIZATIONS_AVAILABLE = False
    logger.warning(f"⚠️ Vizualizációs modul nem elérhető: {e}")

def generate_xai_explanation(recipe):
    """
    EGYSZERŰ XAI - badge színek alapján
    Ha van legalább 1 zöld vagy sárga badge -> XAI
    Ha minden badge piros -> nincs XAI
    """
    hsi = recipe.get('hsi', 0)
    esi = recipe.get('esi', 255)
    ppi = recipe.get('ppi', 0)
    
    # ESI normalizálás weboldalhoz
    esi_display = (esi / 255.0) * 100
    
    # Badge színek meghatározása (ugyanaz mint get_score_color)
    hsi_color = get_score_color(hsi, 'hsi')        # 75+ zöld, 50+ sárga, <50 piros
    esi_color = get_score_color(esi_display, 'esi') # <=33 zöld, <=66 sárga, >66 piros
    ppi_color = get_score_color(ppi, 'ppi')        # 75+ zöld, 50+ sárga, <50 piros
    
    print(f"🔍 XAI Check - {recipe.get('title', 'Unknown')}")
    print(f"   HSI: {hsi} -> {hsi_color}")
    print(f"   ESI: {esi_display:.1f} -> {esi_color}")
    print(f"   PPI: {ppi} -> {ppi_color}")
    
    # Ellenőrzés: van-e legalább 1 jó badge (zöld vagy sárga)?
    good_badges = 0
    if hsi_color in ['success', 'warning']:  # zöld vagy sárga
        good_badges += 1
    if esi_color in ['success', 'warning']:  # zöld vagy sárga
        good_badges += 1
    if ppi_color in ['success', 'warning']:  # zöld vagy sárga
        good_badges += 1
    
    print(f"   Jó badge-ek: {good_badges}/3")
    
    # ❌ Ha minden badge piros -> NINCS XAI
    if good_badges == 0:
        print("   ❌ Minden badge piros -> Nincs XAI")
        return None
    
    # ✅ Van legalább 1 jó badge -> GENERÁLJ XAI
    explanations = []
    
    # HSI magyarázat (csak ha jó a badge)
    if hsi_color == 'success':  # zöld
        explanations.append("🟢 Nagyon egészséges - kiváló tápérték")
    elif hsi_color == 'warning':  # sárga
        explanations.append("🟡 Egészséges - jó tápérték")
    
    # ESI magyarázat (csak ha jó a badge)
    if esi_color == 'success':  # zöld
        explanations.append("🟢 Környezetbarát - alacsony hatás")
    elif esi_color == 'warning':  # sárga
        explanations.append("🟡 Közepes környezeti hatás")
    
    # PPI magyarázat (csak ha jó a badge)
    if ppi_color == 'success':  # zöld
        explanations.append("🟢 Nagyon népszerű")
    elif ppi_color == 'warning':  # sárga
        explanations.append("🟡 Népszerű választás")
    
    # Fő indoklás - az első jó tulajdonság alapján
    if hsi_color in ['success', 'warning'] and esi_color in ['success', 'warning']:
        main_reason = "Azért ajánljuk, mert egészséges ÉS környezetbarát! 🌟"
    elif hsi_color == 'success':
        main_reason = "Azért ajánljuk, mert nagyon egészséges! 💚"
    elif hsi_color == 'warning':
        main_reason = "Azért ajánljuk, mert egészséges! 💚"
    elif esi_color == 'success':
        main_reason = "Azért ajánljuk, mert környezetbarát! 🌱"
    elif esi_color == 'warning':
        main_reason = "Azért ajánljuk, mert környezettudatos! 🌱"
    elif ppi_color == 'success':
        main_reason = "Azért ajánljuk, mert nagyon népszerű! ⭐"
    elif ppi_color == 'warning':
        main_reason = "Azért ajánljuk, mert népszerű választás! ⭐"
    else:
        main_reason = "Azért ajánljuk! 🍽️"  # fallback (nem kellene előfordulnia)
    
    # Kompozit pontszám
    hsi_norm = hsi / 100.0
    esi_norm = (255 - esi) / 255.0
    ppi_norm = ppi / 100.0
    composite = (0.4 * hsi_norm + 0.4 * esi_norm + 0.2 * ppi_norm) * 100
    
    print(f"   ✅ XAI generálva: {main_reason}")
    print(f"   📝 Magyarázatok: {explanations}")
    
    return {
        'main_reason': main_reason,
        'explanations': explanations,
        'composite_score': round(composite, 1)
    }

# Flask alkalmazás inicializálás
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# ===== DATABASE CONNECTION =====
def get_db_connection():
    """Adatbázis kapcsolat létrehozása robusztus hibakezeléssel"""
    try:
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            # Heroku Postgres URL javítás
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
                logger.info("✅ Database URL javítva postgresql://-re")
            
            result = urlparse(database_url)
            conn = psycopg2.connect(
                dbname=result.path[1:],
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port,
                sslmode='require'
            )
            logger.info("✅ PostgreSQL kapcsolat létrehozva")
            return conn
        else:
            logger.warning("⚠️  DATABASE_URL nincs beállítva")
            return None
    except Exception as e:
        logger.error(f"❌ Adatbázis kapcsolat hiba: {e}")
        return None

# ===== ÚJ: ROUND TRACKING FÜGGVÉNY =====
def get_user_recommendation_round(user_id):
    """Meghatározza, hogy hanyadik ajánlási körben van a felhasználó"""
    try:
        conn = get_db_connection()
        if conn is None:
            return 1
        
        cur = conn.cursor()
        
        # Recommendation sessions számolása
        cur.execute("""
            SELECT COUNT(*) FROM recommendation_sessions 
            WHERE user_id = %s
        """, (user_id,))
        
        round_count = cur.fetchone()[0]
        conn.close()
        
        return round_count + 1  # 1-based indexing
        
    except Exception as e:
        logger.error(f"❌ Round számítási hiba: {e}")
        return 1

# ===== MÓDOSÍTOTT GreenRecRecommender CLASS =====
class GreenRecRecommender:
    def __init__(self):
        logger.info("🔧 Ajánlórendszer inicializálása...")
        self.recipes_df = None
        # COSINE SIMILARITY hozzáadása
        self.vectorizer = CountVectorizer(
            stop_words='english', 
            max_features=1000,
            ngram_range=(1, 2),  # 1-2 gram kombinációk
            lowercase=True,
            token_pattern=r'\b[a-zA-ZáéíóöőúüűÁÉÍÓÖŐÚÜŰ]+\b'  # Magyar karakterek
        )
        self.scaler = MinMaxScaler()
        self.ingredient_matrix = None  # ÚJ: Cosine similarity mátrix
        self.user_history = {}  # Felhasználói előzmények tárolása
        self.load_recipes()
        logger.info("✅ Ajánlórendszer sikeresen inicializálva")
    
    def load_recipes(self):
        """Receptek betöltése adatbázisból SAFE hibakezeléssel"""
        try:
            conn = get_db_connection()
            if conn is None:
                logger.warning("⚠️  Nincs adatbázis kapcsolat, dummy adatok létrehozása")
                self.create_dummy_data()
                return
                
            # Ellenőrizzük, hogy létezik-e a recipes tábla
            cur = conn.cursor()
            try:
                cur.execute("SELECT COUNT(*) FROM recipes LIMIT 1;")
                count = cur.fetchone()[0]
                logger.info(f"✅ Recipes tábla létezik, {count} recept található")
            except psycopg2.errors.UndefinedTable:
                logger.warning("⚠️  Recipes tábla nem létezik")
                logger.warning("⚠️  Nincs recept adat, dummy adatok létrehozása")
                conn.close()
                self.create_dummy_data()
                return
            
            # Receptek betöltése
            if count > 0:
                query = """
                    SELECT id, title, hsi, esi, ppi, category, ingredients, instructions, images
                    FROM recipes 
                    ORDER BY id
                """
                self.recipes_df = pd.read_sql_query(query, conn)
                logger.info(f"✅ {len(self.recipes_df)} recept betöltve az adatbázisból")
                
                # Adatok előfeldolgozása
                self.preprocess_data()
            else:
                logger.warning("⚠️  Nincs recept adat, dummy adatok létrehozása")
                self.create_dummy_data()
                
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Recept betöltési hiba: {e}")
            self.create_dummy_data()
    
    def create_dummy_data(self):
        """3 dummy recept létrehozása ha nincs adat"""
        logger.info("🔧 Dummy adatok létrehozása...")
        dummy_recipes = [
            {
                'id': 1,
                'title': 'Zöldséges quinoa saláta',
                'hsi': 95.2,
                'esi': 24.4,
                'ppi': 67.8,
                'category': 'Saláták',
                'ingredients': 'quinoa, uborka, paradicsom, avokádó, citrom',
                'instructions': 'Főzd meg a quinoát, várd meg hogy kihűljön. Vágd apróra a zöldségeket.',
                'images': 'https://via.placeholder.com/300x200?text=Quinoa+Salat'
            },
            {
                'id': 2,
                'title': 'Vegán chili sin carne',
                'hsi': 76.3,
                'esi': 15.1,
                'ppi': 84.5,
                'category': 'Főételek',
                'ingredients': 'vörös bab, kukorica, paprika, hagyma, paradicsom',
                'instructions': 'Dinszteld le a hagymát és paprikát. Add hozzá a babot.',
                'images': 'https://via.placeholder.com/300x200?text=Vegan+Chili'
            },
            {
                'id': 3,
                'title': 'Spenótos lencse curry',
                'hsi': 82.7,
                'esi': 42.1,
                'ppi': 75.8,
                'category': 'Főételek',
                'ingredients': 'lencse, spenót, kókusztej, curry, gyömbér',
                'instructions': 'Főzd meg a lencsét, add hozzá a fűszereket.',
                'images': 'https://via.placeholder.com/300x200?text=Lentil+Curry'
            }
        ]
        
        self.recipes_df = pd.DataFrame(dummy_recipes)
        self.preprocess_data()
        logger.info("✅ Dummy adatok létrehozva")
    
    def preprocess_data(self):
        """Adatok előfeldolgozása ÉS cosine similarity előkészítés"""
        try:
            # HSI, ESI, PPI normalizálása
            score_columns = ['hsi', 'esi', 'ppi']
            self.recipes_df[score_columns] = self.scaler.fit_transform(self.recipes_df[score_columns])
            
            # ESI invertálása (alacsonyabb környezeti hatás = jobb)
            self.recipes_df['esi_inv'] = 1 - self.recipes_df['esi']
            
            # ===== COSINE SIMILARITY ELŐKÉSZÍTÉS =====
            if 'ingredients' in self.recipes_df.columns:
                # Ingredients tisztítása és előkészítése
                ingredients_text = self.recipes_df['ingredients'].fillna('').astype(str)
                
                # Alapvető szöveg tisztítás
                ingredients_text = ingredients_text.str.lower()
                ingredients_text = ingredients_text.str.replace(r'[^\w\s,]', '', regex=True)
                
                # Ingredient matrix létrehozása
                self.ingredient_matrix = self.vectorizer.fit_transform(ingredients_text)
                logger.info(f"✅ Ingredient matrix létrehozva: {self.ingredient_matrix.shape}")
                
                # Vocabulary mérete
                vocab_size = len(self.vectorizer.get_feature_names_out())
                logger.info(f"📚 Vocabulary méret: {vocab_size} ingrediens")
            
        except Exception as e:
            logger.error(f"❌ Adatok előfeldolgozási hiba: {e}")
    
    def get_content_similarity(self, target_ingredients, top_k=20):
        """ÚJ: Content-based similarity számítás ingredients alapján"""
        try:
            if self.ingredient_matrix is None:
                logger.warning("⚠️  Ingredient matrix nincs inicializálva")
                return []
            
            # Target ingredients előkészítése
            if isinstance(target_ingredients, list):
                target_text = ', '.join(target_ingredients)
            else:
                target_text = str(target_ingredients)
            
            # Tisztítás
            target_text = target_text.lower().strip()
            if not target_text:
                return []
            
            # Target vectorizálása
            target_vector = self.vectorizer.transform([target_text])
            
            # Cosine similarity számítás
            similarities = cosine_similarity(target_vector, self.ingredient_matrix).flatten()
            
            # Top K hasonló recept indexei
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            # Eredmények készítése
            similar_recipes = []
            for idx in top_indices:
                if similarities[idx] > 0.01:  # Minimum similarity threshold
                    recipe_data = self.recipes_df.iloc[idx].copy()
                    recipe_data['similarity_score'] = similarities[idx]
                    similar_recipes.append(recipe_data.to_dict())
            
            logger.info(f"🔍 {len(similar_recipes)} hasonló recept találva cosine similarity alapján")
            return similar_recipes
            
        except Exception as e:
            logger.error(f"❌ Content similarity hiba: {e}")
            return []
    
    def get_user_chosen_ingredients(self, user_id):
        """Felhasználó előző választásaiból összetevők kinyerése"""
        try:
            conn = get_db_connection()
            if conn is None:
                return ""
            
            cur = conn.cursor()
            
            # Felhasználó választásai (utolsó 5)
            cur.execute("""
                SELECT r.ingredients 
                FROM user_choices uc
                JOIN recipes r ON uc.recipe_id = r.id
                WHERE uc.user_id = %s
                ORDER BY uc.selected_at DESC
                LIMIT 5
            """, (user_id,))
            
            chosen_ingredients = cur.fetchall()
            conn.close()
            
            if chosen_ingredients:
                # Összes ingrediens összefűzése
                all_ingredients = []
                for row in chosen_ingredients:
                    if row[0]:
                        all_ingredients.extend(row[0].split(','))
                
                # Tisztítás és összeállítás
                cleaned_ingredients = [ing.strip().lower() for ing in all_ingredients if ing.strip()]
                unique_ingredients = list(set(cleaned_ingredients))
                
                result = ', '.join(unique_ingredients[:20])  # Maximum 20 ingrediens
                logger.info(f"👤 Felhasználó választásai alapján: {result}")
                return result
            
            return ""
            
        except Exception as e:
            logger.error(f"❌ User ingredients kinyerési hiba: {e}")
            return ""
    
    def get_recommendations(self, user_preferences=None, num_recommendations=5, user_id=None, diversity_factor=0.3):
        """
        🎯 KÖRÖNKÉNTI HIBRID ajánlások generálása
        1. kör: Tiszta composite score (baseline A/B/C teszt)
        2. kör+: Hibrid (content-based + score-based az előző választások alapján)
        """
        try:
            if self.recipes_df is None or len(self.recipes_df) == 0:
                logger.warning("⚠️  Nincs elérhető recept adat")
                return []

            # Meghatározzuk melyik körben vagyunk
            current_round = get_user_recommendation_round(user_id) if user_id else 1
            logger.info(f"🔄 Ajánlási kör: {current_round}")

            # 1. ALAPVETŐ PONTSZÁMOK SZÁMÍTÁSA
            df = self.recipes_df.copy()
            
            # Kompozit pontszám számítása
            df['composite_score'] = (
                0.4 * df['hsi'] +
                0.4 * df['esi_inv'] +
                0.2 * df['ppi']
            )
            
            # 2. FELHASZNÁLÓI ELŐZMÉNYEK FIGYELEMBEVÉTELE
            excluded_ids = []
            if user_id and user_id in self.user_history:
                # Kizárjuk a már látott recepteket (utolsó 10 ajánlás)
                excluded_ids = self.user_history[user_id][-10:]
                df = df[~df['id'].isin(excluded_ids)]
                logger.info(f"🔍 {len(excluded_ids)} már látott recept kizárva")
            
            recommendations = []
            
            # 3. KÖRÖNKÉNTI LOGIKA
            if current_round == 1:
                # ===== ELSŐ KÖR: TISZTA COMPOSITE SCORE =====
                logger.info("📊 1. kör: Tiszta composite score alapú ajánlás (A/B/C baseline)")
                
                # Baseline receptek - MINDEN felhasználónak ugyanazok
                baseline_recipe_ids = [1, 2, 3, 4, 5]  # Előre definiált ID-k
                
                # Ha nincs elég baseline recept, kiegészítjük a legjobbakkal
                if len(baseline_recipe_ids) < num_recommendations:
                    top_recipes = df.nlargest(num_recommendations, 'composite_score')
                    baseline_recipe_ids = top_recipes['id'].tolist()[:num_recommendations]
                
                # Baseline receptek lekérése
                for recipe_id in baseline_recipe_ids[:num_recommendations]:
                    matching_recipes = df[df['id'] == recipe_id]
                    if not matching_recipes.empty:
                        recipe = matching_recipes.iloc[0].to_dict()
                        recipe['similarity_score'] = 0.0
                        recipe['hybrid_score'] = recipe['composite_score']
                        recipe['recommendation_type'] = 'baseline'
                        recommendations.append(recipe)
                
                # Ha nem találtunk elég baseline receptet, kiegészítjük
                while len(recommendations) < num_recommendations:
                    remaining_recipes = df[~df['id'].isin([r['id'] for r in recommendations])]
                    if remaining_recipes.empty:
                        break
                        
                    best_recipe = remaining_recipes.nlargest(1, 'composite_score').iloc[0].to_dict()
                    best_recipe['similarity_score'] = 0.0
                    best_recipe['hybrid_score'] = best_recipe['composite_score']
                    best_recipe['recommendation_type'] = 'baseline_fallback'
                    recommendations.append(best_recipe)
                    
            else:
                # ===== MÁSODIK+ KÖR: HIBRID CONTENT-BASED =====
                logger.info(f"🔄 {current_round}. kör: Hibrid ajánlás (content-based + score-based)")
                
                # Előző választások lekérése az adatbázisból
                user_chosen_ingredients = self.get_user_chosen_ingredients(user_id)
                
                if user_chosen_ingredients:
                    # Content-based similarity az előző választások alapján
                    logger.info(f"🍽️ Content-based az előző választások alapján: {user_chosen_ingredients}")
                    
                    content_candidates = self.get_content_similarity(user_chosen_ingredients, top_k=15)
                    
                    if content_candidates:
                        # Hibrid pontszám: 50% similarity + 50% composite score
                        for recipe in content_candidates:
                            recipe_id = recipe['id']
                            if recipe_id in df['id'].values:
                                similarity_norm = recipe['similarity_score']
                                matching_row = df[df['id'] == recipe_id]
                                
                                if not matching_row.empty:
                                    composite_norm = matching_row['composite_score'].iloc[0]
                                    
                                    # 50/50 hibrid pontszám
                                    hybrid_score = 0.5 * similarity_norm + 0.5 * composite_norm
                                    recipe['hybrid_score'] = hybrid_score
                                    recipe['recommendation_type'] = 'hybrid'
                        
                        # Rendezés hibrid pontszám szerint
                        content_candidates.sort(key=lambda x: x.get('hybrid_score', 0), reverse=True)
                        
                        # Top receptek kiválasztása
                        for recipe in content_candidates[:num_recommendations]:
                            recommendations.append(recipe)
                
                # Ha nincs elég hibrid ajánlás, kiegészítjük score-based-del
                if len(recommendations) < num_recommendations:
                    logger.info("🔄 Kiegészítés score-based ajánlásokkal")
                    
                    remaining_needed = num_recommendations - len(recommendations)
                    used_ids = [r['id'] for r in recommendations]
                    remaining_recipes = df[~df['id'].isin(used_ids)]
                    
                    if not remaining_recipes.empty:
                        # Súlyozott véletlenszerű kiválasztás
                        weights = remaining_recipes['composite_score'].values
                        weights = (weights - weights.min() + 0.1) ** 2
                        weights = weights / weights.sum()
                        
                        selected_indices = []
                        attempts = 0
                        max_attempts = len(remaining_recipes) * 2
                        
                        while len(selected_indices) < remaining_needed and attempts < max_attempts:
                            try:
                                idx = np.random.choice(remaining_recipes.index, p=weights)
                                if idx not in selected_indices:
                                    selected_indices.append(idx)
                            except:
                                # Fallback: top receptek
                                top_recipes = remaining_recipes.nlargest(remaining_needed, 'composite_score')
                                for idx in top_recipes.index:
                                    if len(selected_indices) < remaining_needed:
                                        selected_indices.append(idx)
                                break
                            attempts += 1
                        
                        # Score-based receptek hozzáadása
                        for idx in selected_indices:
                            recipe = remaining_recipes.loc[idx].to_dict()
                            recipe['similarity_score'] = 0.0
                            recipe['hybrid_score'] = recipe['composite_score']
                            recipe['recommendation_type'] = 'score_based'
                            recommendations.append(recipe)

            # 4. FELHASZNÁLÓI ELŐZMÉNYEK FRISSÍTÉSE
            if user_id:
                if user_id not in self.user_history:
                    self.user_history[user_id] = []
                
                new_ids = [rec['id'] for rec in recommendations]
                self.user_history[user_id].extend(new_ids)
                self.user_history[user_id] = self.user_history[user_id][-50:]

            # 5. FORMÁTUM ÁTALAKÍTÁSA
            if current_round > 1:
                random.shuffle(recommendations)  # Csak 2. kör+ esetén shuffle

            final_recommendations = []
            for recipe in recommendations[:num_recommendations]:
                final_recommendations.append({
                    'id': int(recipe['id']),
                    'title': recipe['title'],
                    'hsi': round(float(recipe['hsi']) * 100, 1),
                    'esi': round(float(recipe['esi']) * 100, 1),
                    'ppi': round(float(recipe['ppi']) * 100, 1),
                    'category': recipe['category'],
                    'ingredients': recipe['ingredients'],
                    'instructions': recipe['instructions'],
                    'images': recipe.get('images', 'https://via.placeholder.com/300x200?text=No+Image'),
                    'similarity_score': round(recipe.get('similarity_score', 0), 3),
                    'hybrid_score': round(recipe.get('hybrid_score', 0), 3),
                    'recommendation_type': recipe.get('recommendation_type', 'unknown'),
                    'round_number': current_round
                })

            logger.info(f"✅ {len(final_recommendations)} ajánlás generálva ({current_round}. kör)")
            return final_recommendations

        except Exception as e:
            logger.error(f"❌ Ajánlási hiba: {e}")
            return []
    
    def get_personalized_recommendations(self, user_id, user_preferences=None, num_recommendations=5):
        """Személyre szabott ajánlások felhasználói preferenciák alapján"""
        # Alapértelmezett diversity_factor beállítás felhasználói típus szerint
        diversity_factors = {
            'A': 0.4,  # Kontroll csoport - több változatosság
            'B': 0.3,  # Pontszámos - mérsékelt változatosság  
            'C': 0.2   # Magyarázatos - kevesebb változatosság (tudatosabb választás)
        }
        
        user_group = user_preferences.get('group', 'A') if user_preferences else 'A'
        diversity = diversity_factors.get(user_group, 0.3)
        
        return self.get_recommendations(
            user_preferences=user_preferences,
            num_recommendations=num_recommendations,
            user_id=user_id,
            diversity_factor=diversity
        )

# Globális ajánlórendszer inicializálás
logger.info("🔧 Globális ajánlórendszer inicializálása...")
try:
    recommender = GreenRecRecommender()
    logger.info("✅ Globális ajánlórendszer kész")
except Exception as e:
    logger.error(f"❌ Ajánlórendszer inicializálási hiba: {e}")
    recommender = None

# ===== USER MANAGEMENT =====
def create_user(username, password, group_name):
    """Új felhasználó létrehozása"""
    try:
        conn = get_db_connection()
        if conn is None:
            return False, "Adatbázis kapcsolati hiba"
        
        cur = conn.cursor()
        
        # Users tábla létrehozása ha nem létezik
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                group_name VARCHAR(10) NOT NULL DEFAULT 'A',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Ellenőrizzük, hogy létezik-e már a felhasználó
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            conn.close()
            return False, "Ez a felhasználónév már foglalt!"
        
        # Új felhasználó beszúrása
        password_hash = generate_password_hash(password)
        cur.execute("""
            INSERT INTO users (username, password_hash, group_name) 
            VALUES (%s, %s, %s)
        """, (username, password_hash, group_name))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Új felhasználó létrehozva: {username} (csoport: {group_name})")
        return True, "Sikeres regisztráció!"
        
    except Exception as e:
        logger.error(f"❌ Felhasználó létrehozási hiba: {e}")
        return False, "Hiba a regisztráció során"

def check_user_credentials(username, password):
    """Felhasználói hitelesítés ellenőrzése"""
    try:
        conn = get_db_connection()
        if conn is None:
            return False, None
        
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, password_hash, group_name 
            FROM users WHERE username = %s
        """, (username,))
        
        user = cur.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            return True, {
                'id': user[0],
                'username': user[1],
                'group': user[3]
            }
        return False, None
        
    except Exception as e:
        logger.error(f"❌ Hitelesítési hiba: {e}")
        return False, None

# ===== MÓDOSÍTOTT RECOMMENDATION LOGGING =====
def log_recommendation_session(user_id, recommendations, user_group):
    """Teljes ajánlási szesszió rögzítése + round number"""
    try:
        conn = get_db_connection()
        if conn is None:
            return
            
        cur = conn.cursor()
        
        # Tábla létrehozása round_number oszloppal
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recommendation_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                session_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                recommended_recipe_ids TEXT NOT NULL,
                recipe_positions TEXT,
                user_group VARCHAR(10),
                round_number INTEGER DEFAULT 1,
                recommendation_types TEXT
            )
        """)
        
        # Adatok készítése
        recipe_ids = [str(rec['id']) for rec in recommendations]
        recipe_positions = {str(rec['id']): i+1 for i, rec in enumerate(recommendations)}
        recommendation_types = {str(rec['id']): rec.get('recommendation_type', 'unknown') for rec in recommendations}
        round_number = recommendations[0].get('round_number', 1) if recommendations else 1
        
        # Session rögzítése
        cur.execute("""
            INSERT INTO recommendation_sessions 
            (user_id, recommended_recipe_ids, recipe_positions, user_group, round_number, recommendation_types)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            user_id, 
            ','.join(recipe_ids),
            json.dumps(recipe_positions),
            user_group,
            round_number,
            json.dumps(recommendation_types)
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Session logged: user={user_id}, round={round_number}, type_mix={list(recommendation_types.values())}")
        
    except Exception as e:
        logger.error(f"❌ Session logging hiba: {e}")

# ===== FLASK ROUTES =====
@app.route('/')
def index():
    """Főoldal - csak bejelentkezett felhasználóknak"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        username = session.get('username', 'Ismeretlen')
        user_group = session.get('user_group', 'A')
        
        return render_template('index.html', 
                             username=username,
                             user_group=user_group,
                             recommendations=[])
    except Exception as e:
        logger.error(f"❌ Index oldal hiba: {e}")
        flash('Hiba történt az oldal betöltésekor.', 'error')
        return render_template('index.html', 
                             recommendations=[], 
                             user_group='A',
                             username=session.get('username'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Bejelentkezés oldal"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Kérlek add meg a felhasználónevet és jelszót!', 'error')
            return render_template('login.html')
        
        success, user_data = check_user_credentials(username, password)
        
        if success and user_data:
            session['user_id'] = user_data['id']
            session['username'] = user_data['username']
            session['user_group'] = user_data['group']
            logger.info(f"✅ Sikeres bejelentkezés: {username}")
            return redirect(url_for('index'))
        else:
            flash('Hibás felhasználónév vagy jelszó!', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Regisztráció oldal"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not username or not password:
            flash('Kérlek add meg a felhasználónevet és jelszót!', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('A jelszavak nem egyeznek!', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('A jelszónak legalább 6 karakter hosszúnak kell lennie!', 'error')
            return render_template('register.html')
        
        # Random csoport hozzárendelés (A/B/C teszt)
        group_name = random.choice(['A', 'B', 'C'])
        
        success, message = create_user(username, password, group_name)
        
        if success:
            flash(f'Sikeres regisztráció! Te a(z) {group_name} csoportba kerültél.', 'success')
            return redirect(url_for('login'))
        else:
            flash(message, 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """Kijelentkezés"""
    username = session.get('username', 'Ismeretlen')
    session.clear()
    logger.info(f"✅ Kijelentkezés: {username}")
    flash('Sikeresen kijelentkeztél!', 'info')
    return redirect(url_for('login'))

@app.route('/recommend', methods=['POST'])
def recommend():
    """🎯 KÖRÖNKÉNTI HIBRID AJAX ajánlások endpoint"""
    if 'user_id' not in session:
        return jsonify({'error': 'Nincs bejelentkezve'}), 401
    
    try:
        if recommender is None:
            return jsonify({'error': 'Ajánlórendszer nem elérhető'}), 500
        
        # Felhasználói csoport és preferenciák
        user_group = session.get('user_group', 'A')
        user_preferences = {
            'group': user_group,
            'user_id': session['user_id'],
            'ingredients': ''  # Körönkénti rendszerben nincs keresés
        }
        
        logger.info(f"🔍 Ajánlás kérés: user={session['user_id']}, group={user_group}")
        
        # 🚀 KÖRÖNKÉNTI HIBRID ajánlások generálása
        recommendations = recommender.get_personalized_recommendations(
            user_id=session['user_id'],
            user_preferences=user_preferences,
            num_recommendations=5
        )
        
        # Ellenőrzés hogy van-e eredmény
        if not recommendations:
            logger.warning("⚠️ Nincs ajánlás eredmény")
            return jsonify({'error': 'Nem sikerült ajánlásokat generálni'}), 500
        
        # ✨ SZÍNKÓDOLÁS hozzáadása minden recepthez
        for rec in recommendations:
            rec['hsi_color'] = get_score_color(rec['hsi'], 'hsi')
            rec['esi_color'] = get_score_color(rec['esi'], 'esi')
            rec['ppi_color'] = get_score_color(rec['ppi'], 'ppi')
            
            # Tooltip szövegek
            rec['hsi_tooltip'] = f"Egészségességi mutató: {rec['hsi']:.1f} (magasabb = jobb)"
            rec['esi_tooltip'] = f"Környezeti hatás: {rec['esi']:.1f} (alacsonyabb = jobb)"
            rec['ppi_tooltip'] = f"Népszerűségi mutató: {rec['ppi']:.1f} (magasabb = jobb)"

            if user_group == 'C':
                rec['xai_explanation'] = generate_xai_explanation(rec)
            
            # Round-based tooltip info
            round_num = rec.get('round_number', 1)
            rec_type = rec.get('recommendation_type', 'unknown')
            
            if round_num == 1:
                rec['round_tooltip'] = "1. kör: Baseline ajánlás (minden felhasználó ugyanazt kapja)"
            else:
                if rec_type == 'hybrid':
                    rec['round_tooltip'] = f"{round_num}. kör: Hibrid ajánlás (50% előző választások + 50% minőség)"
                else:
                    rec['round_tooltip'] = f"{round_num}. kör: Minőség alapú ajánlás"
        
        # ✅ KULCS: AJÁNLÁSOK TELJES LOGGING-JA
        if recommendations:
            log_recommendation_session(session['user_id'], recommendations, user_group)
        
        logger.info(f"✅ {len(recommendations)} ajánlás generálva user_id={session['user_id']}, group={user_group}, round={recommendations[0].get('round_number', 1)}")
        
        # Debug info logolása
        hybrid_count = sum(1 for rec in recommendations if rec.get('recommendation_type') == 'hybrid')
        baseline_count = sum(1 for rec in recommendations if rec.get('recommendation_type') == 'baseline')
        logger.info(f"📊 Ajánlás típusok: {baseline_count} baseline, {hybrid_count} hibrid")
        
        return jsonify({'recommendations': recommendations})
        
    except Exception as e:
        logger.error(f"❌ Körönkénti ajánlási endpoint hiba: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Hiba az ajánlások generálásakor'}), 500

@app.route('/select_recipe', methods=['POST'])
def select_recipe():
    """Recept választás rögzítése"""
    if 'user_id' not in session:
        return jsonify({'error': 'Nincs bejelentkezve'}), 401
    
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        
        if not recipe_id:
            return jsonify({'error': 'Hiányzó recept ID'}), 400
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Adatbázis kapcsolati hiba'}), 500
        
        cur = conn.cursor()
        
        # User choices tábla létrehozása ha nem létezik
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_choices (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                recipe_id INTEGER NOT NULL,
                selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Választás rögzítése
        cur.execute("""
            INSERT INTO user_choices (user_id, recipe_id, selected_at)
            VALUES (%s, %s, %s)
            """, (session['user_id'], recipe_id, datetime.now()))
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Recept választás rögzítve: user={session['user_id']}, recipe={recipe_id}")
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"❌ Recept választás hiba: {e}")
        return jsonify({'error': 'Hiba történt a választás rögzítésekor'}), 500

@app.route('/stats')
def stats():
    """Statisztikai áttekintő oldal"""
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Adatbázis kapcsolati hiba', 'error')
            return render_template('stats.html', stats={})
        
        cur = conn.cursor()
        
        # Alapvető statisztikák
        stats = {}
        
        # Felhasználók száma csoportonként
        try:
            cur.execute("SELECT group_name, COUNT(*) FROM users GROUP BY group_name ORDER BY group_name")
            stats['users_by_group'] = dict(cur.fetchall())
        except:
            stats['users_by_group'] = {'A': 0, 'B': 0, 'C': 0}
        
        # Választások száma
        try:
            cur.execute("SELECT COUNT(*) FROM user_choices")
            stats['total_choices'] = cur.fetchone()[0]
        except:
            stats['total_choices'] = 0
        
        # Receptek száma
        try:
            cur.execute("SELECT COUNT(*) FROM recipes")
            stats['total_recipes'] = cur.fetchone()[0]
        except:
            stats['total_recipes'] = 0
        
        # Total users számítása
        stats['total_users'] = sum(stats['users_by_group'].values())
        
        # Template által várt group_stats lista generálása
        stats['group_stats'] = [
            {
                'group': group,
                'user_count': count,
                'percentage': round(count / stats['total_users'] * 100, 1) if stats['total_users'] > 0 else 0
            }
            for group, count in stats['users_by_group'].items()
        ]
        
        # Átlag kompozit pontszám számítása
        try:
            cur.execute("""
                SELECT AVG(
                    0.4 * r.hsi + 
                    0.4 * (100 - r.esi * 100.0 / 255.0) + 
                    0.2 * r.ppi
                ) as avg_composite
                FROM user_choices uc
                JOIN recipes r ON uc.recipe_id = r.id
                WHERE r.hsi IS NOT NULL 
                AND r.esi IS NOT NULL 
                AND r.ppi IS NOT NULL
            """)
            
            result = cur.fetchone()
            if result and result[0] is not None:
                stats['avg_composite_score'] = round(float(result[0]), 1)
            else:
                stats['avg_composite_score'] = 0.0
                
        except Exception as e:
            logger.error(f"❌ Kompozit pontszám számítási hiba: {e}")
            stats['avg_composite_score'] = 0.0     
        
        conn.close()
        return render_template('stats.html', stats=stats)
        
    except Exception as e:
        logger.error(f"❌ Statisztikák hiba: {e}")
        return render_template('stats.html', stats={})

# ===== EXPORT ENDPOINTS =====
@app.route('/export/users')
def export_users():
    """Felhasználók exportálása CSV formátumban"""
    try:
        conn = get_db_connection()
        if conn is None:
            return "Adatbázis kapcsolati hiba", 500
        
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, group_name, created_at,
            CASE WHEN username LIKE 'user_%' THEN 'teszt' ELSE 'valós' END as user_type
            FROM users ORDER BY created_at
        """)
        
        users_data = cur.fetchall()
        conn.close()
        
        # CSV generálás
        csv_content = "id,username,group_name,created_at,user_type\n"
        for user in users_data:
            csv_content += f"{user[0]},{user[1]},{user[2]},{user[3]},{user[4]}\n"
        
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=greenrec_users.csv'}
        )
        
    except Exception as e:
        logger.error(f"❌ Users export hiba: {e}")
        return "Export hiba", 500

@app.route('/export/choices')
def export_choices():
    """Választások exportálása CSV formátumban"""
    try:
        conn = get_db_connection()
        if conn is None:
            return "Adatbázis kapcsolati hiba", 500
        
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                uc.id as choice_id,
                u.username,
                u.group_name,
                r.title as recipe_title,
                r.hsi, r.esi, r.ppi,
                r.category,
                uc.selected_at,
                CASE WHEN u.username LIKE 'user_%' THEN 'teszt' ELSE 'valós' END as user_type
            FROM user_choices uc
            JOIN users u ON uc.user_id = u.id  
            JOIN recipes r ON uc.recipe_id = r.id
            ORDER BY uc.selected_at
        """)
        
        choices_data = cur.fetchall()
        conn.close()
        
        # CSV generálás
        csv_content = "choice_id,username,group_name,recipe_title,hsi,esi,ppi,category,selected_at,user_type\n"
        for choice in choices_data:
            csv_content += f"{choice[0]},{choice[1]},{choice[2]},{choice[3]},{choice[4]},{choice[5]},{choice[6]},{choice[7]},{choice[8]},{choice[9]}\n"
        
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=greenrec_choices.csv'}
        )
        
    except Exception as e:
        logger.error(f"❌ Choices export hiba: {e}")
        return "Export hiba", 500

@app.route('/export/json')
def export_json():
    """TELJES JSON export - körönkénti adatokkal"""
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Adatbázis kapcsolati hiba'}), 500
            
        cur = conn.cursor()
        
        logger.info("🔍 JSON export kezdése - körönkénti adatokkal")
        
        # Recommendation sessions lekérdezése round info-val
        cur.execute("""
            SELECT rs.id, rs.user_id, rs.round_number, rs.recommendation_types, 
                   rs.session_timestamp, rs.recommended_recipe_ids, u.group_name
            FROM recommendation_sessions rs
            JOIN users u ON rs.user_id = u.id
            ORDER BY rs.session_timestamp
        """)
        sessions_data = cur.fetchall()
        
        # User choices lekérdezése
        cur.execute("""
            SELECT uc.id, uc.user_id, uc.recipe_id, uc.selected_at,
                   u.username, u.group_name, r.title, r.hsi, r.esi, r.ppi, r.category
            FROM user_choices uc
            JOIN users u ON uc.user_id = u.id
            JOIN recipes r ON uc.recipe_id = r.id
            ORDER BY uc.selected_at
        """)
        choices_data = cur.fetchall()
        
        conn.close()
        
        # Export adatok összeállítása
        export_data = {
            'metadata': {
                'export_timestamp': str(datetime.now()),
                'total_sessions': len(sessions_data),
                'total_choices': len(choices_data),
                'export_type': 'round_based_hybrid_system'
            },
            'recommendation_sessions': [
                {
                    'session_id': s[0],
                    'user_id': s[1],
                    'round_number': s[2],
                    'recommendation_types': s[3],
                    'timestamp': s[4].isoformat() if s[4] else None,
                    'recipe_ids': s[5],
                    'user_group': s[6]
                } for s in sessions_data
            ],
            'user_choices': [
                {
                    'choice_id': c[0],
                    'user_id': c[1],
                    'recipe_id': c[2],
                    'selected_at': c[3].isoformat() if c[3] else None,
                    'username': c[4],
                    'group_name': c[5],
                    'recipe_title': c[6],
                    'hsi': float(c[7]),
                    'esi': float(c[8]),
                    'ppi': float(c[9]),
                    'category': c[10],
                    'composite_score': round(0.4 * float(c[7]) + 0.4 * (100 - float(c[8]) * 100 / 255) + 0.2 * float(c[9]), 2)
                } for c in choices_data
            ]
        }
        
        logger.info(f"✅ Körönkénti JSON export kész: {len(export_data['recommendation_sessions'])} session, {len(export_data['user_choices'])} választás")
        
        return Response(
            json.dumps(export_data, indent=2, ensure_ascii=False),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=greenrec_round_based.json'}
        )
        
    except Exception as e:
        logger.error(f"❌ JSON export hiba: {e}")
        return jsonify({'error': f'Export hiba: {str(e)}'}), 500

# ===== HEALTH CHECK =====
@app.route('/health')
def health_check():
    """Alkalmazás állapot ellenőrzés"""
    try:
        conn = get_db_connection()
        status = {
            'status': 'healthy',
            'database': 'connected' if conn else 'disconnected',
            'recommender': 'active' if recommender else 'inactive',
            'system_type': 'round_based_hybrid',
            'timestamp': datetime.now().isoformat()
        }
        if conn:
            conn.close()
        return jsonify(status)
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ===== ERROR HANDLERS =====
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# ===== APPLICATION STARTUP =====
if __name__ == '__main__':
    logger.info("🚀 GreenRec körönkénti hibrid alkalmazás indítása...")
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"🌐 Szerver indítás port {port}, debug={debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
