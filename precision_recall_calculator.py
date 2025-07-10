#!/usr/bin/env python3
"""
FIXED PRECISION/RECALL CALCULATOR
Kifejezetten a final_large_simulation.py adataira optimalizálva

HASZNÁLAT:
heroku run python fixed_precision_recall.py -a your-app-name
"""

import psycopg2
import os
import numpy as np
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Adatbázis kapcsolat"""
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        return psycopg2.connect(database_url, sslmode='require')
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'greenrec'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', 'password'),
        port=os.environ.get('DB_PORT', '5432')
    )

# Relevancia kritériumok (precision_recall_calculator.py-ból)
RELEVANCE_CRITERIA = {
    'egeszsegtudatos': {'hsi_min': 75, 'esi_max': 180, 'ppi_min': 50},
    'kornyezettudatos': {'hsi_min': 60, 'esi_max': 150, 'ppi_min': 40},
    'kiegyensulyozott': {'hsi_min': 65, 'esi_max': 165, 'ppi_min': 45},
    'izorgia': {'hsi_min': 55, 'esi_max': 200, 'ppi_min': 70},
    'kenyelmi': {'hsi_min': 50, 'esi_max': 220, 'ppi_min': 60},
    'ujdonsagkereso': {'hsi_min': 55, 'esi_max': 180, 'ppi_min': 45}
}

def load_final_simulation_data():
    """Az új final_ prefix-ű szimuláció adatainak betöltése"""
    conn = get_db_connection()
    if not conn:
        return None, None
    
    try:
        cur = conn.cursor()
        
        # Receptek betöltése
        cur.execute("SELECT id, title, hsi, esi, ppi FROM recipes")
        recipes_data = cur.fetchall()
        
        recipes = {}
        for r in recipes_data:
            recipes[r[0]] = {
                'id': r[0],
                'title': r[1],
                'hsi': float(r[2]),
                'esi': float(r[3]),
                'ppi': float(r[4])
            }
        
        # Sessions betöltése - CSAK final_ prefix-ű felhasználóktól
        cur.execute("""
            SELECT rs.user_id, rs.recommended_recipe_ids, rs.user_group, 
                   rs.round_number, u.username
            FROM recommendation_sessions rs
            JOIN users u ON rs.user_id = u.id
            WHERE u.username LIKE 'final_%'
            ORDER BY rs.user_id, rs.round_number
        """)
        sessions_data = cur.fetchall()
        
        # User choices betöltése - CSAK final_ prefix-ű felhasználóktól
        cur.execute("""
            SELECT uc.user_id, uc.recipe_id, u.username, u.group_name
            FROM user_choices uc
            JOIN users u ON uc.user_id = u.id
            WHERE u.username LIKE 'final_%'
            ORDER BY uc.user_id
        """)
        choices_data = cur.fetchall()
        
        conn.close()
        
        logger.info(f"📊 Betöltött adatok:")
        logger.info(f"   🍽️ Receptek: {len(recipes)}")
        logger.info(f"   📋 Sessions: {len(sessions_data)}")
        logger.info(f"   🎯 Választások: {len(choices_data)}")
        
        # Sessions feldolgozása
        sessions = []
        for session in sessions_data:
            user_id, recipe_ids_str, group, round_num, username = session
            
            # User típus kinyerése a username-ből (final_A_egeszsegtudatos_001)
            username_parts = username.split('_')
            if len(username_parts) >= 3:
                user_type = username_parts[2]
            else:
                user_type = 'kiegyensulyozott'  # Default
            
            # Recipe IDs parsing
            if recipe_ids_str:
                recommended_ids = [int(id.strip()) for id in recipe_ids_str.split(',') if id.strip().isdigit()]
            else:
                recommended_ids = []
            
            sessions.append({
                'user_id': user_id,
                'user_type': user_type,
                'group': group,
                'round_number': round_num,
                'recommended_recipe_ids': recommended_ids
            })
        
        return recipes, sessions
        
    except Exception as e:
        logger.error(f"❌ Adatok betöltési hiba: {e}")
        if conn:
            conn.close()
        return None, None

def get_relevant_recipes(user_type, recipes):
    """User típus alapján releváns receptek meghatározása"""
    if user_type not in RELEVANCE_CRITERIA:
        logger.warning(f"⚠️ Ismeretlen user típus: {user_type}, default használata")
        user_type = 'kiegyensulyozott'
    
    criteria = RELEVANCE_CRITERIA[user_type]
    relevant_ids = []
    
    for recipe_id, recipe in recipes.items():
        hsi = recipe['hsi']
        esi = recipe['esi']
        ppi = recipe['ppi']
        
        # Relevancia kritériumok ellenőrzése
        if (hsi >= criteria['hsi_min'] and 
            esi <= criteria['esi_max'] and 
            ppi >= criteria['ppi_min']):
            relevant_ids.append(recipe_id)
    
    logger.debug(f"📊 {user_type}: {len(relevant_ids)} releváns recept")
    return relevant_ids

def calculate_precision_recall(recommended_ids, relevant_ids, k=5):
    """Precision@K és Recall@K számítás"""
    if not recommended_ids or not relevant_ids:
        return 0.0, 0.0, 0, len(relevant_ids)
    
    top_k = recommended_ids[:k]
    relevant_in_topk = [r_id for r_id in top_k if r_id in relevant_ids]
    
    precision = len(relevant_in_topk) / len(top_k)
    recall = len(relevant_in_topk) / len(relevant_ids)
    
    return precision, recall, len(relevant_in_topk), len(relevant_ids)

def calculate_final_simulation_metrics():
    """Final simulation metrikák számítása"""
    
    logger.info("🚀 FIXED PRECISION@5 ÉS RECALL@5 KALKULÁTOR")
    logger.info("🎯 Final Large Simulation Adatokra Optimalizálva")
    logger.info("=" * 60)
    
    # Adatok betöltése
    recipes, sessions = load_final_simulation_data()
    if not recipes or not sessions:
        logger.error("❌ Adatok betöltése sikertelen")
        return None
    
    # Csoportonkénti eredmények
    group_results = defaultdict(list)
    
    logger.info("🔍 PRECISION@5, RECALL@5 SZÁMÍTÁS...")
    
    processed_sessions = 0
    for session in sessions:
        user_type = session['user_type']
        group = session['group']
        recommended_ids = session['recommended_recipe_ids']
        
        # Releváns receptek meghatározása
        relevant_ids = get_relevant_recipes(user_type, recipes)
        
        # Precision/Recall számítás
        precision, recall, hits, total_relevant = calculate_precision_recall(
            recommended_ids, relevant_ids, 5
        )
        
        metrics = {
            'precision_at_5': precision,
            'recall_at_5': recall,
            'relevant_in_top5': hits,
            'total_relevant': total_relevant,
            'user_type': user_type
        }
        
        group_results[group].append(metrics)
        processed_sessions += 1
        
        if processed_sessions % 100 == 0:
            logger.info(f"   📈 Progress: {processed_sessions}/{len(sessions)} sessions feldolgozva")
    
    logger.info(f"✅ {processed_sessions} session feldolgozva")
    
    # Csoportonkénti átlagok
    final_results = {}
    
    logger.info(f"\n📊 CSOPORTONKÉNTI EREDMÉNYEK:")
    logger.info("=" * 40)
    
    for group in ['A', 'B', 'C']:
        if group in group_results and group_results[group]:
            group_data = group_results[group]
            
            avg_precision = np.mean([m['precision_at_5'] for m in group_data])
            avg_recall = np.mean([m['recall_at_5'] for m in group_data])
            avg_hits = np.mean([m['relevant_in_top5'] for m in group_data])
            avg_total_relevant = np.mean([m['total_relevant'] for m in group_data])
            
            # User típus eloszlás
            user_types = {}
            for m in group_data:
                ut = m['user_type']
                user_types[ut] = user_types.get(ut, 0) + 1
            
            final_results[group] = {
                'precision_at_5': round(avg_precision, 4),
                'recall_at_5': round(avg_recall, 4),
                'avg_relevant_in_top5': round(avg_hits, 2),
                'avg_total_relevant': round(avg_total_relevant, 1),
                'session_count': len(group_data),
                'user_type_distribution': user_types
            }
            
            logger.info(f"\n📊 {group} Csoport ({len(group_data)} session):")
            logger.info(f"   🎯 Precision@5: {final_results[group]['precision_at_5']}")
            logger.info(f"   🔍 Recall@5: {final_results[group]['recall_at_5']}")
            logger.info(f"   📈 Átlag releváns/top5: {final_results[group]['avg_relevant_in_top5']}")
            logger.info(f"   📊 Átlag összes releváns: {final_results[group]['avg_total_relevant']}")
            logger.info(f"   👥 User típusok: {user_types}")
    
    # Hipotézis ellenőrzés
    if len(final_results) >= 2:
        logger.info(f"\n🎯 PRECISION/RECALL HIPOTÉZIS ELLENŐRZÉS:")
        logger.info("=" * 45)
        
        # Precision trend
        prec_values = [(group, final_results[group]['precision_at_5']) for group in ['A', 'B', 'C'] if group in final_results]
        prec_values.sort(key=lambda x: x[1], reverse=True)
        
        # Recall trend  
        recall_values = [(group, final_results[group]['recall_at_5']) for group in ['A', 'B', 'C'] if group in final_results]
        recall_values.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"📈 Precision@5 ranking: {' > '.join([f'{g}({v:.3f})' for g, v in prec_values])}")
        logger.info(f"🔍 Recall@5 ranking: {' > '.join([f'{g}({v:.3f})' for g, v in recall_values])}")
        
        # Trend ellenőrzés
        precision_trend_ok = len(prec_values) >= 3 and prec_values[0][0] in ['C', 'B'] and prec_values[-1][0] == 'A'
        recall_trend_ok = len(recall_values) >= 3 and recall_values[0][0] in ['C', 'B'] and recall_values[-1][0] == 'A'
        
        if precision_trend_ok and recall_trend_ok:
            logger.info(f"🏆 PRECISION/RECALL TREND POZITÍV!")
            logger.info(f"✅ Nudging hatás kimutatható a metrikákban")
        elif precision_trend_ok or recall_trend_ok:
            logger.info(f"✅ PRECISION/RECALL TREND RÉSZBEN POZITÍV")
        else:
            logger.info(f"⚠️ Precision/Recall trend nem optimális")
    
    # Kompozit pontszám számítás (adatbázisból)
    logger.info(f"\n📊 KOMPOZIT PONTSZÁMOK VALIDÁLÁSA:")
    logger.info("=" * 35)
    
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            
            # Kompozit pontszámok a választott receptekből
            for group in ['A', 'B', 'C']:
                cur.execute("""
                    SELECT AVG(r.hsi), AVG(r.esi), AVG(r.ppi), COUNT(*)
                    FROM user_choices uc
                    JOIN users u ON uc.user_id = u.id
                    JOIN recipes r ON uc.recipe_id = r.id
                    WHERE u.username LIKE 'final_%' AND u.group_name = %s
                """, (group,))
                
                result = cur.fetchone()
                if result and result[3] > 0:  # Ha van adat
                    avg_hsi, avg_esi, avg_ppi, count = result
                    
                    # Kompozit számítás
                    hsi_norm = avg_hsi / 100.0
                    esi_norm = (255 - avg_esi) / 255.0  # ESI inverz
                    ppi_norm = avg_ppi / 100.0
                    
                    avg_composite = (0.4 * hsi_norm + 0.4 * esi_norm + 0.2 * ppi_norm) * 100
                    
                    final_results[group]['mean_hsi'] = round(avg_hsi, 2)
                    final_results[group]['mean_esi'] = round(avg_esi, 2)
                    final_results[group]['mean_ppi'] = round(avg_ppi, 2)
                    final_results[group]['mean_composite'] = round(avg_composite, 2)
                    final_results[group]['choices_count'] = count
                    
                    logger.info(f"{group}: HSI={avg_hsi:.1f}, ESI={avg_esi:.1f}, Kompozit={avg_composite:.1f} ({count} választás)")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Kompozit számítási hiba: {e}")
            if conn:
                conn.close()
    
    return final_results

def print_final_table(results):
    """Végleges táblázat kiírása"""
    
    logger.info(f"\n📋 VÉGLEGES PRECISION/RECALL TÁBLÁZAT:")
    logger.info("=" * 70)
    logger.info("Csoport | Precision@5 | Recall@5 | Mean HSI | Mean ESI | Mean Kompozit")
    logger.info("-" * 70)
    
    for group in ['A', 'B', 'C']:
        if group in results:
            r = results[group]
            precision = r.get('precision_at_5', 0.0)
            recall = r.get('recall_at_5', 0.0)
            hsi = r.get('mean_hsi', 0.0)
            esi = r.get('mean_esi', 0.0)
            composite = r.get('mean_composite', 0.0)
            
            logger.info(f"{group}       | {precision:<11.3f} | {recall:<8.3f} | {hsi:<8.1f} | {esi:<8.1f} | {composite:<13.1f}")

if __name__ == "__main__":
    logger.info("🔧 FIXED PRECISION/RECALL CALCULATOR")
    logger.info("🎯 Final Large Simulation adataira optimalizálva")
    
    try:
        results = calculate_final_simulation_metrics()
        
        if results:
            # Végleges táblázat
            print_final_table(results)
            
            logger.info(f"\n🎉 FIXED PRECISION/RECALL SZÁMÍTÁS BEFEJEZVE!")
            logger.info(f"✅ Most már megvannak a pontos Precision@5 és Recall@5 értékek")
            logger.info(f"📋 Használd ezeket az értékeket a dolgozat táblázatában")
        else:
            logger.error("❌ Számítás sikertelen")
            
    except Exception as e:
        logger.error(f"❌ Kritikus hiba: {e}")
        import traceback
        logger.error(traceback.format_exc())
