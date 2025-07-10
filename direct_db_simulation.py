#!/usr/bin/env python3
"""
DIRECT DATABASE SIMULATION - Nudging teszt web app nélkül
Közvetlenül az adatbázisba írja a szimulált nudging eredményeket
"""

import psycopg2
import os
import random
import json
import numpy as np
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Adatbázis kapcsolat"""
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        return psycopg2.connect(database_url, sslmode='require')
    else:
        return psycopg2.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            database=os.environ.get('DB_NAME', 'greenrec'),
            user=os.environ.get('DB_USER', 'postgres'),
            password=os.environ.get('DB_PASSWORD', 'password'),
            port=os.environ.get('DB_PORT', '5432')
        )

def get_recipes():
    """Receptek lekérése az adatbázisból"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT id, title, hsi, esi, ppi, category FROM recipes LIMIT 100")
    recipes = cur.fetchall()
    
    conn.close()
    
    return [
        {
            'id': r[0],
            'title': r[1], 
            'hsi': float(r[2]),
            'esi': float(r[3]),
            'ppi': float(r[4]),
            'category': r[5]
        }
        for r in recipes
    ]

def calculate_nudging_effect(base_score, group, recipe):
    """Nudging hatás számítása"""
    nudge_effect = 0
    
    if group == 'B':
        # Visual nudging (pontszámok megjelenítése)
        # Jobb receptek (magas HSI, alacsony ESI) iránt hajlam
        if recipe['hsi'] > 65 and recipe['esi'] < 140:
            nudge_effect = random.uniform(5, 15)  # +5-15% valószínűség
    
    elif group == 'C':
        # Strong nudging (pontszámok + XAI magyarázat)
        # Erősebb hatás a fenntartható receptek felé
        if recipe['hsi'] > 65 and recipe['esi'] < 140:
            nudge_effect = random.uniform(15, 30)  # +15-30% valószínűség
        elif recipe['hsi'] > 75 and recipe['esi'] < 120:
            nudge_effect = random.uniform(25, 40)  # Még erősebb a legjobb recepteknél
    
    return min(base_score + nudge_effect, 100)  # Max 100

def simulate_user_choices(user_id, group, user_type, recipes):
    """Egy felhasználó választásainak szimulálása nudging hatással"""
    
    # User típus alapú preferenciák
    type_preferences = {
        'egeszsegtudatos': {'hsi_weight': 0.6, 'esi_weight': 0.3, 'ppi_weight': 0.1},
        'kornyezettudatos': {'hsi_weight': 0.3, 'esi_weight': 0.6, 'ppi_weight': 0.1},
        'kiegyensulyozott': {'hsi_weight': 0.4, 'esi_weight': 0.4, 'ppi_weight': 0.2},
        'izorgia': {'hsi_weight': 0.2, 'esi_weight': 0.2, 'ppi_weight': 0.6},
        'kenyelmi': {'hsi_weight': 0.3, 'esi_weight': 0.2, 'ppi_weight': 0.5},
        'ujdonsagkereso': {'hsi_weight': 0.35, 'esi_weight': 0.35, 'ppi_weight': 0.3}
    }
    
    prefs = type_preferences.get(user_type, type_preferences['kiegyensulyozott'])
    choices = []
    
    # 3-8 választás per felhasználó
    num_choices = random.randint(3, 8)
    
    for round_num in range(1, num_choices + 1):
        # 5 random recept "ajánlása"
        recommended = random.sample(recipes, 5)
        
        # Választási logika nudging hatással
        choice_scores = []
        
        for recipe in recommended:
            # Alap pontszám (felhasználói preferencia alapján)
            base_score = (
                prefs['hsi_weight'] * recipe['hsi'] +
                prefs['esi_weight'] * (255 - recipe['esi']) +  # ESI inverz!
                prefs['ppi_weight'] * recipe['ppi']
            )
            
            # Nudging hatás alkalmazása
            final_score = calculate_nudging_effect(base_score, group, recipe)
            
            choice_scores.append((recipe, final_score))
        
        # Legmagasabb pontszámú recept választása (+ kis randomness)
        choice_scores.sort(key=lambda x: x[1] + random.uniform(-5, 5), reverse=True)
        chosen_recipe = choice_scores[0][0]
        
        # Kompozit pontszám számítása (ESI javított)
        hsi_norm = chosen_recipe['hsi'] / 100.0
        esi_norm = (255 - chosen_recipe['esi']) / 255.0  # ESI inverz!
        ppi_norm = chosen_recipe['ppi'] / 100.0
        
        composite_score = (0.4 * hsi_norm + 0.4 * esi_norm + 0.2 * ppi_norm) * 100
        
        choice = {
            'user_id': user_id,
            'recipe_id': chosen_recipe['id'],
            'recipe_title': chosen_recipe['title'],
            'hsi': chosen_recipe['hsi'],
            'esi': chosen_recipe['esi'],
            'ppi': chosen_recipe['ppi'],
            'composite_score': round(composite_score, 2),
            'user_type': user_type,
            'group': group,
            'round_number': round_num,
            'selected_at': datetime.now()
        }
        
        choices.append(choice)
    
    return choices

def create_test_users_and_simulate(user_count=90):
    """Test felhasználók létrehozása és nudging szimuláció"""
    
    logger.info(f"🚀 DIRECT DATABASE NUDGING SZIMULÁCIÓ - {user_count} felhasználó")
    
    # Receptek betöltése
    recipes = get_recipes()
    logger.info(f"📊 {len(recipes)} recept betöltve")
    
    # Adatbázis kapcsolat
    conn = get_db_connection()
    cur = conn.cursor()
    
    # User típus eloszlás
    user_types = ['egeszsegtudatos', 'kornyezettudatos', 'kiegyensulyozott', 'izorgia', 'kenyelmi', 'ujdonsagkereso']
    groups = ['A', 'B', 'C']
    
    all_choices = []
    user_id_counter = 1000  # Kezdő ID
    
    # Csoportonként egyenlő eloszlás
    users_per_group = user_count // 3
    
    for group in groups:
        logger.info(f"📋 {group} csoport szimulálása ({users_per_group} felhasználó)")
        
        for i in range(users_per_group):
            user_id = user_id_counter + i
            user_type = random.choice(user_types)
            username = f"sim_{group}_{user_type}_{i+1:03d}"
            
            # Felhasználó létrehozása
            cur.execute("""
                INSERT INTO users (id, username, password_hash, group_name) 
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (user_id, username, 'hashed_password', group))
            
            # Választások szimulálása
            user_choices = simulate_user_choices(user_id, group, user_type, recipes)
            
            # Választások mentése
            for choice in user_choices:
                cur.execute("""
                    INSERT INTO user_choices (user_id, recipe_id, selected_at)
                    VALUES (%s, %s, %s)
                """, (choice['user_id'], choice['recipe_id'], choice['selected_at']))
                
                # Recommendation session is
                recommendation_types = json.dumps({str(r['id']): 'simulated' for r in random.sample(recipes, 5)})
                cur.execute("""
                    INSERT INTO recommendation_sessions 
                    (user_id, round_number, recommendation_types, session_timestamp, recommended_recipe_ids, user_group)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    user_id, 
                    choice['round_number'], 
                    recommendation_types,
                    choice['selected_at'],
                    ','.join([str(r['id']) for r in random.sample(recipes, 5)]),
                    group
                ))
            
            all_choices.extend(user_choices)
            
            if (i + 1) % 10 == 0:
                logger.info(f"   📈 Progress: {i+1}/{users_per_group} felhasználó kész")
        
        user_id_counter += users_per_group
    
    # Commit adatok
    conn.commit()
    conn.close()
    
    # Eredmények kiértékelése
    logger.info(f"\n📊 SZIMULÁCIÓ EREDMÉNYEI:")
    logger.info(f"✅ Összes választás: {len(all_choices)}")
    
    # Csoportonkénti átlagok
    group_stats = {}
    for group in groups:
        group_choices = [c for c in all_choices if c['group'] == group]
        if group_choices:
            avg_hsi = np.mean([c['hsi'] for c in group_choices])
            avg_esi = np.mean([c['esi'] for c in group_choices])
            avg_composite = np.mean([c['composite_score'] for c in group_choices])
            
            group_stats[group] = {
                'count': len(group_choices),
                'avg_hsi': round(avg_hsi, 2),
                'avg_esi': round(avg_esi, 2),
                'avg_composite': round(avg_composite, 2)
            }
            
            logger.info(f"📊 {group} csoport: {len(group_choices)} választás")
            logger.info(f"   HSI: {avg_hsi:.2f}, ESI: {avg_esi:.2f}, Kompozit: {avg_composite:.2f}")
    
    # Hipotézis ellenőrzés
    if len(group_stats) == 3:
        logger.info(f"\n🎯 HIPOTÉZIS ELLENŐRZÉS:")
        logger.info(f"Kompozit pontszámok: A={group_stats['A']['avg_composite']}, B={group_stats['B']['avg_composite']}, C={group_stats['C']['avg_composite']}")
        
        if group_stats['C']['avg_composite'] > group_stats['B']['avg_composite'] > group_stats['A']['avg_composite']:
            logger.info(f"🏆 HIPOTÉZIS IGAZOLÓDOTT: C > B > A!")
        else:
            logger.info(f"⚠️ Hipotézis részben igazolódott vagy nem teljesült")
    
    logger.info(f"\n✅ DIRECT DATABASE SZIMULÁCIÓ BEFEJEZVE!")
    logger.info(f"🎯 Most exportálhatod az adatokat a /export/json endpoint-ról")
    
    return group_stats

if __name__ == "__main__":
    # Szimuláció futtatása
    results = create_test_users_and_simulate(user_count=90)
    
    logger.info("🎉 Szimuláció kész! Használhatod a precision_recall_calculator.py-t az eredményekhez.")
